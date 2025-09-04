from django.core.management.base import BaseCommand
from django.db import transaction
from properties.models import Property, Building
import json
import os
from decimal import Decimal
from datetime import datetime


class Command(BaseCommand):
    help = 'Import rent data from JSON file'

    def add_arguments(self, parser):
        parser.add_argument(
            'json_file',
            type=str,
            help='Path to JSON file with rent data',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=1000,
            help='Batch size for bulk operations (default: 1000)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be imported without actually importing',
        )

    def handle(self, *args, **options):
        json_file = options['json_file']
        batch_size = options['batch_size']
        dry_run = options['dry_run']
        
        if not os.path.exists(json_file):
            self.stdout.write(
                self.style.ERROR(f'File not found: {json_file}')
            )
            return
        
        self.stdout.write(f'Loading data from {json_file}...')
        
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error loading JSON: {e}')
            )
            return
        
        if not isinstance(data, list):
            self.stdout.write(
                self.style.ERROR('JSON should contain a list of properties')
            )
            return
        
        self.stdout.write(f'Found {len(data)} properties in JSON')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No data will be imported'))
            # Show first few records
            for i, item in enumerate(data[:3]):
                self.stdout.write(f'Sample {i+1}: {item.get("title", "No title")[:50]}...')
            return
        
        # Process in batches
        total_created = 0
        total_skipped = 0
        
        for i in range(0, len(data), batch_size):
            batch = data[i:i + batch_size]
            self.stdout.write(f'Processing batch {i//batch_size + 1}: items {i+1}-{min(i+batch_size, len(data))}')
            
            properties_to_create = []
            
            for item in batch:
                try:
                    # Check if property already exists
                    property_id = item.get('property_id') or item.get('id')
                    if not property_id:
                        self.stdout.write(f'Skipping item without property_id: {item.get("title", "Unknown")[:30]}...')
                        total_skipped += 1
                        continue
                    
                    # Add RENT_ prefix if not already present
                    if not property_id.startswith('RENT_'):
                        property_id = f'RENT_{property_id}'
                    
                    if Property.objects.filter(property_id=property_id).exists():
                        total_skipped += 1
                        continue
                    
                    # Get or create building
                    building = None
                    building_name = item.get('building_name') or item.get('building')
                    if building_name:
                        building, created = Building.objects.get_or_create(
                            name=building_name,
                            defaults={
                                'address': item.get('display_address', ''),
                                'latitude': item.get('latitude'),
                                'longitude': item.get('longitude'),
                                'area': self.extract_area_name(item.get('display_address', '')),
                            }
                        )
                    
                    # Create property object
                    property_obj = Property(
                        property_id=property_id,
                        url=item.get('url', ''),
                        title=item.get('title', ''),
                        display_address=item.get('display_address', ''),
                        bedrooms=self.safe_int(item.get('bedrooms')),
                        bathrooms=self.safe_int(item.get('bathrooms')),
                        area_sqft=self.safe_float(item.get('area_sqft')),
                        area_sqm=self.safe_float(item.get('area_sqm')),
                        price=self.safe_decimal(item.get('price')),
                        price_currency=item.get('price_currency', 'AED'),
                        price_duration='rent',  # Force rent type
                        latitude=self.safe_float(item.get('latitude')),
                        longitude=self.safe_float(item.get('longitude')),
                        agent_name=item.get('agent_name', ''),
                        agent_phone=item.get('agent_phone', ''),
                        broker_name=item.get('broker_name', ''),
                        broker_license=item.get('broker_license', ''),
                        property_type=item.get('property_type', ''),
                        furnishing=item.get('furnishing', ''),
                        verified=item.get('verified', False),
                        reference=item.get('reference', ''),
                        rera_number=item.get('rera_number', ''),
                        added_on=self.safe_datetime(item.get('added_on')),
                        description=item.get('description', ''),
                        features=item.get('features', []),
                        images=item.get('images', []),
                        building=building,
                        days_on_market=self.safe_int(item.get('days_on_market')),
                    )
                    
                    properties_to_create.append(property_obj)
                    
                except Exception as e:
                    self.stdout.write(f'Error processing item: {e}')
                    total_skipped += 1
                    continue
            
            # Bulk create
            if properties_to_create:
                with transaction.atomic():
                    Property.objects.bulk_create(properties_to_create, batch_size=500)
                    total_created += len(properties_to_create)
                    self.stdout.write(f'Created {len(properties_to_create)} properties in this batch')
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Import completed!\n'
                f'Created: {total_created} properties\n'
                f'Skipped: {total_skipped} properties'
            )
        )
        
        # Show final statistics
        total_properties = Property.objects.count()
        sale_count = Property.objects.filter(price_duration='sell').count()
        rent_count = Property.objects.filter(price_duration='rent').count()
        
        self.stdout.write(f'\nDatabase statistics:')
        self.stdout.write(f'Total properties: {total_properties}')
        self.stdout.write(f'Sale properties: {sale_count}')
        self.stdout.write(f'Rent properties: {rent_count}')

    def safe_int(self, value):
        """Safely convert to int"""
        if value is None or value == '':
            return None
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return None

    def safe_float(self, value):
        """Safely convert to float"""
        if value is None or value == '':
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def safe_decimal(self, value):
        """Safely convert to Decimal"""
        if value is None or value == '':
            return None
        try:
            return Decimal(str(value))
        except (ValueError, TypeError):
            return None

    def safe_datetime(self, value):
        """Safely convert to datetime"""
        if not value:
            return None
        try:
            if isinstance(value, str):
                # Try different datetime formats
                for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y']:
                    try:
                        return datetime.strptime(value, fmt)
                    except ValueError:
                        continue
            return None
        except:
            return None

    def extract_area_name(self, address):
        """Extract area name from address"""
        if not address:
            return None
        
        # List of known areas in Dubai
        from properties.models import AREAS_WITH_PROPERTY
        areas = list(AREAS_WITH_PROPERTY.keys())
        
        # Find area in address
        for area in areas:
            if area.lower() in address.lower():
                return area
        
        return None 