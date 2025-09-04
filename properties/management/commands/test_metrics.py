from django.core.management.base import BaseCommand
from django.db import transaction
from properties.models import Property, PropertyMetrics


class Command(BaseCommand):
    help = 'Quick test of metrics calculation on a small sample'

    def handle(self, *args, **options):
        self.stdout.write('Testing metrics calculation on 10 properties...')
        
        # Get first 10 properties without metrics
        properties = Property.objects.filter(
            metrics__isnull=True,
            price__isnull=False,
            building__isnull=False
        )[:10]
        
        if not properties.exists():
            self.stdout.write(self.style.WARNING('No properties found for testing'))
            return
        
        self.stdout.write(f'Found {properties.count()} properties for testing')
        
        for prop in properties:
            self.stdout.write(f'Processing property {prop.id}: {prop.title[:50]}...')
            
            # Simple metrics calculation
            metrics_data = {
                'roi': self._calculate_simple_roi(prop),
                'price_per_sqft': (prop.price / prop.area_sqft) if prop.price and prop.area_sqft else 0,
                'building_avg_price': 0,  # Will be calculated later
                'building_avg_roi': 0,
                'building_avg_exposure_days': 0,
                'building_sale_count': 0,
                'building_rent_count': 0,
                'building_avg_price_by_bedrooms': 0,
                'building_sale_count_by_bedrooms': 0,
                'building_rent_count_by_bedrooms': 0,
                'area_avg_days_on_market': 0,
                'avg_rent_by_bedrooms': 0,
            }
            
            # Create metrics
            PropertyMetrics.objects.create(property=prop, **metrics_data)
            
            self.stdout.write(f'  ROI: {metrics_data["roi"]:.2f}%')
            self.stdout.write(f'  Price per sqft: {metrics_data["price_per_sqft"]:.2f}')
        
        self.stdout.write(self.style.SUCCESS('Test completed successfully!'))
    
    def _calculate_simple_roi(self, prop):
        """Simple ROI calculation"""
        if prop.price_duration != 'sell' or not prop.price or not prop.building:
            return 0
        
        # Find average rent in the same building with same bedrooms
        from django.db.models import Avg
        avg_rent = Property.objects.filter(
            building=prop.building,
            bedrooms=prop.bedrooms,
            price_duration='rent',
            price__isnull=False
        ).aggregate(avg_rent=Avg('price'))['avg_rent']
        
        if not avg_rent:
            return 0
        
        annual_rent = avg_rent * 12
        return (annual_rent / prop.price) * 100 if prop.price > 0 else 0 