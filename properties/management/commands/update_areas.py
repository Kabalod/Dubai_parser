from django.core.management.base import BaseCommand
from properties.models import Property, Building


class Command(BaseCommand):
    help = 'Обновляет районы у всех существующих объявлений'

    def handle(self, *args, **options):
        updated_count = 0
        
        # Обновляем здания, определяя район для каждого
        buildings = Building.objects.all()
        for building in buildings:
            if not building.area and building.address:
                # Находим любое объявление в этом здании для определения района
                property_sample = Property.objects.filter(building=building).first()
                if property_sample:
                    area_name = property_sample.extract_area_name()
                    if area_name:
                        building.area = area_name
                        building.save()
                        updated_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(f'Обновлено здание: {building.name} -> {area_name}')
                        )
        
        # Обновляем объявления без зданий
        properties_without_buildings = Property.objects.filter(building__isnull=True)
        for prop in properties_without_buildings:
            area_name = prop.extract_area_name()
            if area_name and prop.display_address:
                # Пытаемся найти или создать здание
                building_name = prop.display_address.split(',')[0].strip()
                building, created = Building.objects.get_or_create(
                    name=building_name,
                    defaults={
                        'address': prop.display_address,
                        'area': area_name
                    }
                )
                prop.building = building
                prop.save()
                updated_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Обновлено объявление: {prop.title} -> {area_name}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(f'Обновлено записей: {updated_count}')
        ) 