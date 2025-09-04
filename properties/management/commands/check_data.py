from django.core.management.base import BaseCommand
from properties.models import Property


class Command(BaseCommand):
    help = 'Check data in database - count of sale and rent properties'

    def handle(self, *args, **options):
        total_count = Property.objects.count()
        sell_count = Property.objects.filter(price_duration='sell').count()
        rent_count = Property.objects.filter(price_duration='rent').count()
        
        self.stdout.write(f'Total properties: {total_count}')
        self.stdout.write(f'Sale properties: {sell_count}')
        self.stdout.write(f'Rent properties: {rent_count}')
        
        # Check unique price_duration values
        unique_durations = set(Property.objects.values_list('price_duration', flat=True).distinct())
        self.stdout.write(f'Unique price_duration values: {list(unique_durations)}')
        
        # Show some examples
        self.stdout.write('\nExamples of rent properties:')
        rent_examples = Property.objects.filter(price_duration='rent')[:5]
        for prop in rent_examples:
            self.stdout.write(f'  ID: {prop.id}, Title: {prop.title[:50]}..., Price: {prop.price}')
        
        self.stdout.write('\nExamples of sale properties:')
        sale_examples = Property.objects.filter(price_duration='sell')[:5]
        for prop in sale_examples:
            self.stdout.write(f'  ID: {prop.id}, Title: {prop.title[:50]}..., Price: {prop.price}')
        
        # Check for properties with empty or null price_duration
        empty_duration = Property.objects.filter(price_duration__isnull=True).count()
        blank_duration = Property.objects.filter(price_duration='').count()
        
        self.stdout.write(f'\nProperties with NULL price_duration: {empty_duration}')
        self.stdout.write(f'Properties with empty price_duration: {blank_duration}')
        
        # Check properties with price but no price_duration
        no_duration_with_price = Property.objects.filter(
            price__isnull=False, 
            price__gt=0
        ).exclude(
            price_duration__in=['sell', 'rent']
        ).count()
        
        self.stdout.write(f'Properties with price but invalid price_duration: {no_duration_with_price}') 