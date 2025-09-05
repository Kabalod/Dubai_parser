import json
from typing import List

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from properties.models import Property


class Command(BaseCommand):
    help = 'Быстрая загрузка фикстуры свойств (bulk_create, без тяжёлых расчётов)'

    def add_arguments(self, parser):
        parser.add_argument('input', type=str, help='Путь к фикстуре JSON (санитизированной)')
        parser.add_argument('--batch-size', type=int, default=2000, help='Размер батча bulk_create')

    def handle(self, *args, **options):
        input_path = options['input']
        batch_size = max(int(options['batch_size']), 100)

        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as exc:
            raise CommandError(f'Не удалось прочитать файл {input_path}: {exc}')

        if not isinstance(data, list):
            raise CommandError('Ожидался список объектов в фикстуре JSON')

        objects: List[Property] = []
        total = 0

        self.stdout.write('Подготовка объектов...')
        for obj in data:
            if not isinstance(obj, dict):
                continue
            if obj.get('model') != 'properties.property':
                continue
            fields = obj.get('fields') or {}

            p = Property()
            # Первичный ключ
            if 'pk' in obj and obj['pk'] is not None:
                p.id = int(obj['pk'])

            # Простые поля
            for name in [
                'property_id','url','title','display_address','bedrooms','bathrooms',
                'area_sqft','area_sqm','price','price_currency','price_duration',
                'latitude','longitude','agent_name','agent_phone','broker_name',
                'broker_license','property_type','furnishing','verified','reference',
                'rera_number','added_on','description','features','images','roi',
                'days_on_market'
            ]:
                if name in fields:
                    setattr(p, name, fields[name])

            # FK без запроса к БД
            if 'building' in fields and fields['building'] is not None:
                p.building_id = int(fields['building'])

            # Отключаем тяжёлые калькуляции и автосоздание Building
            p._skip_calculations = True

            objects.append(p)
            total += 1

        if not objects:
            self.stdout.write(self.style.WARNING('В фикстуре не найдено объектов properties.property'))
            return

        self.stdout.write(f'Готово к вставке: {total} объектов. Вставка батчами по {batch_size}...')

        created = 0
        with transaction.atomic():
            start = 0
            while start < total:
                end = min(start + batch_size, total)
                batch = objects[start:end]
                Property.objects.bulk_create(batch, batch_size=batch_size)
                created += len(batch)
                self.stdout.write(f'Вставлено: {created}/{total}')
                start = end

        # Сброс sequence для таблицы Property
        try:
            seq_sql = connection.ops.sequence_reset_sql(no_style(), [Property])
        except Exception:
            # no_style импортируем локально чтобы не тянуть лишнее наверх
            from django.core.management.color import no_style as _no_style
            seq_sql = connection.ops.sequence_reset_sql(_no_style(), [Property])
        with connection.cursor() as cursor:
            for sql in seq_sql:
                cursor.execute(sql)

        self.stdout.write(self.style.SUCCESS(f'Загрузка завершена. Создано {created} объектов.'))


