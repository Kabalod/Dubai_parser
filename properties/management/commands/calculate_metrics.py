"""
Команда для расчета и сохранения всех метрик недвижимости
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Avg, Count, Q, F, Case, When, DecimalField
from django.db.models.functions import Coalesce
from properties.models import Property, PropertyMetrics
import json


class Command(BaseCommand):
    help = 'Calculate and store property metrics efficiently'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force recalculation of all metrics',
        )
        parser.add_argument(
            '--limit',
            type=int,
            help='Limit number of properties to process',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=1000,
            help='Batch size for bulk operations (default: 1000)',
        )

    def handle(self, *args, **options):
        force = options['force']
        limit = options['limit']
        batch_size = options['batch_size']

        self.stdout.write('Starting optimized metrics calculation...')

        # Get properties to process
        if force:
            properties_qs = Property.objects.all()
        else:
            # Only process properties without metrics or with old metrics
            existing_metrics = PropertyMetrics.objects.values_list('property_id', flat=True)
            properties_qs = Property.objects.exclude(id__in=existing_metrics)

        if limit:
            properties_qs = properties_qs[:limit]

        total_count = properties_qs.count()
        self.stdout.write(f'Processing {total_count} properties...')

        if total_count == 0:
            self.stdout.write(self.style.SUCCESS('No properties to process.'))
            return

        # Process in batches
        processed = 0
        batch_start = 0

        while batch_start < total_count:
            batch_end = min(batch_start + batch_size, total_count)
            batch_properties = list(properties_qs[batch_start:batch_end].select_related('building'))
            
            self.stdout.write(f'Processing batch {batch_start + 1}-{batch_end} of {total_count}...')
            
            # Calculate metrics for this batch
            metrics_to_create = []
            metrics_to_update = []
            
            # Pre-calculate building-level metrics to avoid repeated queries
            building_metrics = self._calculate_building_metrics(batch_properties)
            area_metrics = self._calculate_area_metrics(batch_properties)
            
            for prop in batch_properties:
                metrics_data = self._calculate_property_metrics(prop, building_metrics, area_metrics)
                
                # Check if metrics already exist
                try:
                    existing_metric = PropertyMetrics.objects.get(property=prop)
                    # Update existing
                    for key, value in metrics_data.items():
                        setattr(existing_metric, key, value)
                    metrics_to_update.append(existing_metric)
                except PropertyMetrics.DoesNotExist:
                    # Create new
                    metrics_to_create.append(PropertyMetrics(property=prop, **metrics_data))

            # Bulk operations
            with transaction.atomic():
                if metrics_to_create:
                    PropertyMetrics.objects.bulk_create(metrics_to_create, batch_size=500)
                    self.stdout.write(f'Created {len(metrics_to_create)} new metrics')
                
                if metrics_to_update:
                    PropertyMetrics.objects.bulk_update(
                        metrics_to_update,
                        ['roi', 'price_per_sqft', 'building_avg_price', 'building_avg_price_by_bedrooms',
                         'building_avg_roi', 'building_avg_exposure_days', 'building_sale_count',
                         'building_rent_count', 'building_sale_count_by_bedrooms', 
                         'building_rent_count_by_bedrooms', 'area_avg_days_on_market', 'avg_rent_by_bedrooms'],
                        batch_size=500
                    )
                    self.stdout.write(f'Updated {len(metrics_to_update)} existing metrics')

            processed += len(batch_properties)
            batch_start = batch_end
            
            self.stdout.write(f'Progress: {processed}/{total_count} ({processed/total_count*100:.1f}%)')

        self.stdout.write(self.style.SUCCESS(f'Successfully processed {processed} properties'))

    def _calculate_building_metrics(self, properties):
        """Pre-calculate building-level metrics to avoid repeated queries"""
        building_ids = list(set(prop.building_id for prop in properties if prop.building_id))
        
        if not building_ids:
            return {}
        
        # Get all properties in these buildings for calculations
        building_properties = Property.objects.filter(building_id__in=building_ids).select_related('building')
        
        building_metrics = {}
        
        for building_id in building_ids:
            building_props = [p for p in building_properties if p.building_id == building_id]
            
            # Sale properties
            sale_props = [p for p in building_props if p.price_duration == 'sell' and p.price and p.area_sqft]
            rent_props = [p for p in building_props if p.price_duration == 'rent' and p.price and p.area_sqft]
            
            # Basic metrics
            avg_price = sum(float(p.price) for p in sale_props) / len(sale_props) if sale_props else 0
            avg_roi = sum(self._calculate_roi(p, building_props) for p in sale_props) / len(sale_props) if sale_props else 0
            # Calculate average exposure days (days_on_market is a field, not a method)
            exposure_props = [p for p in building_props if p.days_on_market is not None]
            avg_exposure = sum(p.days_on_market for p in exposure_props) / len(exposure_props) if exposure_props else 0
            
            # Bedroom-specific metrics
            bedroom_metrics = {}
            for bedrooms in set(p.bedrooms for p in building_props if p.bedrooms):
                bedroom_props = [p for p in building_props if p.bedrooms == bedrooms]
                bedroom_sale_props = [p for p in bedroom_props if p.price_duration == 'sell' and p.price]
                bedroom_rent_props = [p for p in bedroom_props if p.price_duration == 'rent' and p.price]
                
                bedroom_metrics[bedrooms] = {
                    'avg_price': sum(float(p.price) for p in bedroom_sale_props) / len(bedroom_sale_props) if bedroom_sale_props else 0,
                    'sale_count': len(bedroom_sale_props),
                    'rent_count': len(bedroom_rent_props),
                    'avg_rent': sum(float(p.price) for p in bedroom_rent_props) / len(bedroom_rent_props) if bedroom_rent_props else 0,
                }
            
            building_metrics[building_id] = {
                'avg_price': avg_price,
                'avg_roi': avg_roi,
                'avg_exposure': avg_exposure,
                'sale_count': len(sale_props),
                'rent_count': len(rent_props),
                'bedroom_metrics': bedroom_metrics,
            }
        
        return building_metrics

    def _calculate_area_metrics(self, properties):
        """Pre-calculate area-level metrics"""
        areas = list(set(prop.building.area if prop.building else None for prop in properties))
        areas = [area for area in areas if area]
        
        if not areas:
            return {}
        
        area_metrics = {}
        
        for area in areas:
            area_props = Property.objects.filter(building__area=area, days_on_market__isnull=False)
            avg_days = area_props.aggregate(avg_days=Avg('days_on_market'))['avg_days'] or 0
            
            area_metrics[area] = {
                'avg_days_on_market': avg_days
            }
        
        return area_metrics

    def _calculate_property_metrics(self, prop, building_metrics, area_metrics):
        """Calculate metrics for a single property using pre-calculated data"""
        metrics = {}
        
        # Basic metrics
        metrics['roi'] = self._calculate_roi_simple(prop)
        metrics['price_per_sqft'] = (float(prop.price) / prop.area_sqft) if prop.price and prop.area_sqft else 0
        
        # Building metrics
        if prop.building_id and prop.building_id in building_metrics:
            bm = building_metrics[prop.building_id]
            metrics['building_avg_price'] = bm['avg_price']
            metrics['building_avg_roi'] = bm['avg_roi']
            metrics['building_avg_exposure_days'] = bm['avg_exposure']
            metrics['building_sale_count'] = bm['sale_count']
            metrics['building_rent_count'] = bm['rent_count']
            
            # Bedroom-specific metrics
            if prop.bedrooms and prop.bedrooms in bm['bedroom_metrics']:
                bedroom_data = bm['bedroom_metrics'][prop.bedrooms]
                metrics['building_avg_price_by_bedrooms'] = bedroom_data['avg_price']
                metrics['building_sale_count_by_bedrooms'] = bedroom_data['sale_count']
                metrics['building_rent_count_by_bedrooms'] = bedroom_data['rent_count']
                metrics['avg_rent_by_bedrooms'] = bedroom_data['avg_rent']
            else:
                metrics['building_avg_price_by_bedrooms'] = 0
                metrics['building_sale_count_by_bedrooms'] = 0
                metrics['building_rent_count_by_bedrooms'] = 0
                metrics['avg_rent_by_bedrooms'] = 0
        else:
            # Default values if no building data
            metrics.update({
                'building_avg_price': 0,
                'building_avg_roi': 0,
                'building_avg_exposure_days': 0,
                'building_sale_count': 0,
                'building_rent_count': 0,
                'building_avg_price_by_bedrooms': 0,
                'building_sale_count_by_bedrooms': 0,
                'building_rent_count_by_bedrooms': 0,
                'avg_rent_by_bedrooms': 0,
            })
        
        # Area metrics
        if prop.building and prop.building.area in area_metrics:
            metrics['area_avg_days_on_market'] = area_metrics[prop.building.area]['avg_days_on_market']
        else:
            metrics['area_avg_days_on_market'] = 0
        
        return metrics

    def _calculate_roi_simple(self, prop):
        """Simple ROI calculation for a single property"""
        if not prop.building_id or prop.price_duration != 'sell' or not prop.price:
            return 0
        
        # Find average rent for similar properties in the same building
        avg_rent = Property.objects.filter(
            building_id=prop.building_id,
            bedrooms=prop.bedrooms,
            price_duration='rent',
            price__isnull=False
        ).aggregate(avg_rent=Avg('price'))['avg_rent']
        
        if not avg_rent:
            return 0
        
        annual_rent = float(avg_rent) * 12
        return (annual_rent / float(prop.price)) * 100 if prop.price > 0 else 0

    def _calculate_roi(self, prop, building_props):
        """Calculate ROI using building properties list"""
        if prop.price_duration != 'sell' or not prop.price:
            return 0
        
        # Find rent properties with same bedrooms in the building
        rent_props = [p for p in building_props 
                     if p.price_duration == 'rent' and p.bedrooms == prop.bedrooms and p.price]
        
        if not rent_props:
            return 0
        
        avg_rent = sum(float(p.price) for p in rent_props) / len(rent_props)
        annual_rent = avg_rent * 12
        return (annual_rent / float(prop.price)) * 100 if prop.price > 0 else 0