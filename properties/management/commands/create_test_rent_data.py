from django.core.management.base import BaseCommand
from django.db import transaction
from properties.models import Property
import random
from decimal import Decimal


class Command(BaseCommand):
    help = 'Create test rent data based on existing sale properties'

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=1000,
            help='Number of rent properties to create (default: 1000)',
        )
        parser.add_argument(
            '--ratio',
            type=float,
            default=0.08,
            help='Annual rent to sale price ratio (default: 0.08 = 8%)',
        )

    def handle(self, *args, **options):
        count = options['count']
        ratio = options['ratio']
        
        self.stdout.write(f'Creating {count} test rent properties...')
        
        # Get sale properties to base rent data on
        sale_properties = list(Property.objects.filter(
            price_duration='sell',
            price__isnull=False,
            price__gt=0
        ).order_by('?')[:count])  # Random selection
        
        if len(sale_properties) < count:
            self.stdout.write(
                self.style.WARNING(
                    f'Only {len(sale_properties)} sale properties available. '
                    f'Creating {len(sale_properties)} rent properties.'
                )
            )
        
        rent_properties = []
        
        for sale_prop in sale_properties:
            # Calculate monthly rent based on sale price and ratio
            annual_rent = float(sale_prop.price) * ratio
            monthly_rent = annual_rent / 12
            
            # Add some randomness (±20%)
            variation = random.uniform(0.8, 1.2)
            monthly_rent = monthly_rent * variation
            
            # Create rent property based on sale property
            rent_prop = Property(
                property_id=f"RENT_{sale_prop.property_id}",
                url=sale_prop.url.replace('for-sale', 'for-rent') if sale_prop.url else '',
                title=sale_prop.title.replace('for Sale', 'for Rent').replace('For Sale', 'For Rent'),
                display_address=sale_prop.display_address,
                bedrooms=sale_prop.bedrooms,
                bathrooms=sale_prop.bathrooms,
                area_sqft=sale_prop.area_sqft,
                area_sqm=sale_prop.area_sqm,
                price=Decimal(str(round(monthly_rent, 2))),
                price_currency=sale_prop.price_currency,
                price_duration='rent',  # This is the key difference
                latitude=sale_prop.latitude,
                longitude=sale_prop.longitude,
                agent_name=sale_prop.agent_name,
                agent_phone=sale_prop.agent_phone,
                broker_name=sale_prop.broker_name,
                broker_license=sale_prop.broker_license,
                property_type=sale_prop.property_type,
                furnishing=sale_prop.furnishing,
                verified=sale_prop.verified,
                reference=f"RENT_{sale_prop.reference}" if sale_prop.reference else None,
                rera_number=sale_prop.rera_number,
                added_on=sale_prop.added_on,
                description=sale_prop.description,
                features=sale_prop.features,
                images=sale_prop.images,
                building=sale_prop.building,
                # Calculate days on market (random 1-90 days)
                days_on_market=random.randint(1, 90),
            )
            
            rent_properties.append(rent_prop)
        
        # Bulk create rent properties
        with transaction.atomic():
            Property.objects.bulk_create(rent_properties, batch_size=500)
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created {len(rent_properties)} test rent properties!\n'
                f'Average monthly rent: {sum(float(p.price) for p in rent_properties) / len(rent_properties):,.0f} AED\n'
                f'Rent-to-price ratio used: {ratio:.1%}'
            )
        )
        
        # Show statistics
        total_properties = Property.objects.count()
        sale_count = Property.objects.filter(price_duration='sell').count()
        rent_count = Property.objects.filter(price_duration='rent').count()
        
        self.stdout.write(f'\nDatabase statistics:')
        self.stdout.write(f'Total properties: {total_properties}')
        self.stdout.write(f'Sale properties: {sale_count}')
        self.stdout.write(f'Rent properties: {rent_count}') 