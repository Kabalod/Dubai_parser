import json
import os
import re
from decimal import Decimal
from datetime import datetime
from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_datetime
from properties.models import Property, Building, AREAS_WITH_PROPERTY


class Command(BaseCommand):
    help = 'Импорт данных недвижимости из JSON файлов'

    def add_arguments(self, parser):
        parser.add_argument(
            'path',
            type=str,
            help='Путь к JSON файлу или папке с JSON файлами'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Очистить существующие данные перед импортом'
        )
        parser.add_argument(
            '--update',
            action='store_true',
            help='Обновлять существующие записи'
        )

    def handle(self, *args, **options):
        path = options['path']
        clear_data = options['clear']
        update_existing = options['update']

        if clear_data:
            self.stdout.write('Очистка существующих данных...')
            Property.objects.all().delete()
            Building.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('Данные очищены'))

        if os.path.isfile(path):
            # Импорт одного файла
            self.import_json_file(path, update_existing)
        elif os.path.isdir(path):
            # Импорт всех JSON файлов в папке
            self.import_directory(path, update_existing)
        else:
            raise CommandError(f'Путь {path} не существует')

        self.stdout.write(self.style.SUCCESS('Импорт завершен успешно!'))

    def import_directory(self, directory_path, update_existing):
        """Импорт всех JSON файлов из директории"""
        json_files = []
        
        # Рекурсивный поиск JSON файлов
        for root, dirs, files in os.walk(directory_path):
            for file in files:
                if file.endswith('.json'):
                    json_files.append(os.path.join(root, file))
        
        if not json_files:
            self.stdout.write(self.style.WARNING(f'JSON файлы не найдены в {directory_path}'))
            return

        self.stdout.write(f'Найдено {len(json_files)} JSON файлов')
        
        for json_file in json_files:
            try:
                self.import_json_file(json_file, update_existing)
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Ошибка при обработке {json_file}: {e}')
                )

    def import_json_file(self, file_path, update_existing):
        """Импорт данных из одного JSON файла"""
        self.stdout.write(f'Обработка файла: {file_path}')
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Ошибка чтения файла {file_path}: {e}')
            )
            return

        # Определяем формат данных
        if isinstance(data, list):
            # Массив объектов
            properties_data = data
        elif isinstance(data, dict):
            # Может быть один объект или содержать массив
            if 'props' in data:
                # Формат из парсера
                props = data.get('props', {})
                page_props = props.get('pageProps', {})
                property_result = page_props.get('propertyResult', {})
                property_data = property_result.get('property', {})
                if property_data:
                    properties_data = [property_data]
                else:
                    properties_data = []
            else:
                # Одиночный объект
                properties_data = [data]
        else:
            self.stdout.write(
                self.style.WARNING(f'Неизвестный формат данных в {file_path}')
            )
            return

        imported_count = 0
        updated_count = 0
        
        for property_data in properties_data:
            try:
                success, updated = self.create_or_update_property(property_data, update_existing)
                if success:
                    if updated:
                        updated_count += 1
                    else:
                        imported_count += 1
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Ошибка при создании объекта: {e}')
                )

        self.stdout.write(
            f'Файл {file_path}: создано {imported_count}, обновлено {updated_count} объектов'
        )

    def create_or_update_property(self, data, update_existing):
        """Создание или обновление объекта недвижимости"""
        
        # Извлекаем ID объекта
        property_id = data.get('id')
        if not property_id:
            self.stdout.write(
                self.style.WARNING('Объект без ID пропущен')
            )
            return False, False

        # Проверяем существующий объект
        try:
            existing_property = Property.objects.get(property_id=str(property_id))
            if not update_existing:
                return False, False  # Пропускаем существующие объекты
            property_obj = existing_property
            is_new = False
        except Property.DoesNotExist:
            property_obj = Property()
            is_new = True

        # Заполняем основные поля
        property_obj.property_id = str(property_id)
        property_obj.url = data.get('url', '') or data.get('share_url', '')
        property_obj.title = data.get('title', '')
        property_obj.display_address = data.get('displayAddress', '') or data.get('location', {}).get('full_name', '')

        # Характеристики
        property_obj.bedrooms = self.safe_int(data.get('bedrooms'))
        property_obj.bathrooms = self.safe_int(data.get('bathrooms'))
        
        # Площадь
        size_min = data.get('sizeMin', '')
        if size_min:
            area_value = self.extract_area(size_min)
            if 'м²' in size_min or 'sqm' in size_min.lower():
                property_obj.area_sqm = area_value
            else:
                property_obj.area_sqft = area_value

        # Цена
        price = data.get('price')
        if price:
            try:
                property_obj.price = Decimal(str(price))
            except:
                pass
        
        property_obj.price_currency = data.get('priceCurrency', 'AED')
        property_obj.price_duration = data.get('priceDuration', 'sell')

        # Координаты
        coordinates = data.get('coordinates', {})
        if coordinates:
            property_obj.latitude = coordinates.get('latitude')
            property_obj.longitude = coordinates.get('longitude')

        # Агент и брокер
        property_obj.agent_name = data.get('agent', '')
        property_obj.agent_phone = data.get('agentPhone', '')
        property_obj.broker_name = data.get('broker', '')
        property_obj.broker_license = data.get('brokerLicenseNumber', '')

        # Дополнительные поля
        property_obj.property_type = data.get('propertyType', '')
        property_obj.furnishing = data.get('furnishing', '')
        property_obj.verified = data.get('verified', False)
        property_obj.reference = data.get('reference', '')
        property_obj.rera_number = data.get('rera', '')

        # Дата добавления
        added_on = data.get('addedOn')
        if added_on:
            try:
                if isinstance(added_on, str):
                    property_obj.added_on = parse_datetime(added_on)
                elif isinstance(added_on, (int, float)):
                    property_obj.added_on = datetime.fromtimestamp(added_on)
            except:
                pass

        # Описание и особенности
        property_obj.description = data.get('description', '') or data.get('descriptionHTML', '')
        property_obj.features = data.get('features', [])
        property_obj.images = data.get('images', [])

        # Сохраняем объект (метод save автоматически создаст здание)
        property_obj.save()

        return True, not is_new

    def safe_int(self, value):
        """Безопасное преобразование в int"""
        if value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    def extract_area(self, size_string):
        """Извлечение числового значения площади из строки"""
        if not size_string:
            return None
        
        # Ищем числа в строке
        numbers = re.findall(r'\d+\.?\d*', str(size_string))
        if numbers:
            try:
                return float(numbers[0])
            except ValueError:
                pass
        return None 