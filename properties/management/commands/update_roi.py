"""
Команда для обновления ROI всех объектов недвижимости
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from properties.models import Property
from properties.utils import calculate_roi_for_property


class Command(BaseCommand):
    help = 'Обновляет ROI для всех объектов недвижимости'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Пересчитать ROI даже для объектов, у которых он уже есть',
        )
        parser.add_argument(
            '--limit',
            type=int,
            help='Ограничить количество обрабатываемых объектов',
        )

    def handle(self, *args, **options):
        force = options['force']
        limit = options['limit']
        
        # Получаем объекты для обновления
        queryset = Property.objects.filter(price_duration='sell', price__isnull=False)
        
        if not force:
            queryset = queryset.filter(roi__isnull=True)
        
        if limit:
            queryset = queryset[:limit]
        
        total_count = queryset.count()
        
        if total_count == 0:
            self.stdout.write(
                self.style.WARNING('Нет объектов для обновления ROI')
            )
            return
        
        self.stdout.write(f'Обновление ROI для {total_count} объектов...')
        
        updated_count = 0
        skipped_count = 0
        
        with transaction.atomic():
            for i, property_obj in enumerate(queryset.iterator(), 1):
                roi = calculate_roi_for_property(property_obj)
                
                if roi is not None:
                    property_obj.roi = roi
                    property_obj.save(update_fields=['roi'])
                    updated_count += 1
                else:
                    skipped_count += 1
                
                # Показываем прогресс каждые 100 объектов
                if i % 100 == 0:
                    self.stdout.write(f'Обработано {i}/{total_count} объектов...')
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Обновление завершено!\n'
                f'Обновлено: {updated_count}\n'
                f'Пропущено: {skipped_count}\n'
                f'Всего обработано: {total_count}'
            )
        ) 