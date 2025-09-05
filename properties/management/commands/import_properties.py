import json
import os
import re
from decimal import Decimal
from datetime import datetime
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db import transaction
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
        parser.add_argument(
            '--atomic-batch-size',
            type=int,
            default=1,
            help='Группировать импорт нескольких файлов в одну транзакцию (1 = по одному файлу)'
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

        from django.db import connection
        batch_size = max(int(self.options.get('atomic_batch_size', 1)) if hasattr(self, 'options') else 1, 1)
        # Если вызывается из handle, сохраним options для доступа здесь
        if not hasattr(self, 'options'):
            setattr(self, 'options', {})
        self.options['atomic_batch_size'] = batch_size

        if batch_size == 1:
            for json_file in json_files:
                try:
                    self.import_json_file(json_file, update_existing)
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'Ошибка при обработке {json_file}: {e}')
                    )
                finally:
                    try:
                        connection.close()
                    except Exception:
                        pass
        else:
            for i in range(0, len(json_files), batch_size):
                group = json_files[i:i+batch_size]
                self.stdout.write(f'Импорт файлов {i+1}-{i+len(group)} из {len(json_files)} в одной транзакции...')
                with transaction.atomic():
                    for json_file in group:
                        try:
                            self.import_json_file(json_file, update_existing)
                        except Exception as e:
                            self.stdout.write(
                                self.style.ERROR(f'Ошибка при обработке {json_file}: {e}')
                            )
                # Закрываем соединение между группами
                try:
                    connection.close()
                except Exception:
                    pass

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
        # Попытка вывести тип объявления из имени файла (rent/sell) как запасной вариант
        inferred_duration = None
        fn_lower = str(file_path).lower()
        if 'for_rent' in fn_lower or '_rent_' in fn_lower or '/rent_' in fn_lower:
            inferred_duration = 'rent'
        elif 'for_sale' in fn_lower or '_sale_' in fn_lower or '/sale_' in fn_lower:
            inferred_duration = 'sell'
        self._inferred_duration = inferred_duration
        if isinstance(data, list):
            # Массив объектов
            properties_data = data
        elif isinstance(data, dict):
            # Может быть один объект или содержать массив в различных ключах
            properties_data = None
            # 1) Формат из парсера (один объект под props.pageProps.propertyResult.property)
            try:
                if 'props' in data:
                    props = data.get('props', {}) or {}
                    page_props = props.get('pageProps', {}) or {}
                    property_result = page_props.get('propertyResult', {}) or {}
                    property_data = property_result.get('property')
                    if property_data:
                        properties_data = property_data if isinstance(property_data, list) else [property_data]
            except Exception:
                pass

            # 2) Распространённые агрегированные ключи с массивами объектов
            if properties_data is None:
                for key in ['results', 'hits', 'items', 'properties', 'listings']:
                    arr = data.get(key)
                    if isinstance(arr, list) and arr and isinstance(arr[0], (dict,)):
                        properties_data = arr
                        break

            # 3) Иногда данные лежат под data
            if properties_data is None and 'data' in data:
                d = data.get('data')
                if isinstance(d, list):
                    properties_data = [x for x in d if isinstance(x, dict)]
                elif isinstance(d, dict):
                    # Попробуем типичные вложенные массивы внутри data
                    for key in ['results', 'hits', 'items', 'properties', 'listings']:
                        arr = d.get(key)
                        if isinstance(arr, list) and arr and isinstance(arr[0], (dict,)):
                            properties_data = arr
                            break
                    if properties_data is None and 'property' in d and isinstance(d['property'], (dict, list)):
                        pd = d['property']
                        properties_data = pd if isinstance(pd, list) else [pd]

            # 4) Если ничего из вышеперечисленного — считаем это единичным объектом
            if properties_data is None:
                properties_data = [data] if isinstance(data, dict) else []
        else:
            self.stdout.write(
                self.style.WARNING(f'Неизвестный формат данных в {file_path}')
            )
            return

        # Оптимизированный массовый импорт: bulk_create/bulk_update
        try:
            ids = []
            prepared = []
            for item in properties_data:
                pid = item.get('id')
                if not pid:
                    continue
                ids.append(str(pid))
                obj = self._build_property_from_data(item)
                if obj is not None:
                    prepared.append(obj)

            if not prepared:
                self.stdout.write(self.style.WARNING('Нет валидных объектов для импорта'))
                return

            # Определяем какие уже существуют
            existing_ids = set(Property.objects.filter(property_id__in=ids).values_list('property_id', flat=True))
            to_create = [p for p in prepared if p.property_id not in existing_ids]
            to_update_ids = [pid for pid in ids if pid in existing_ids]

            created = 0
            updated = 0

            # ВАЖНО: весь импорт файла выполняем в одной транзакции для скорости (особенно SQLite)
            with transaction.atomic():
                if to_create:
                    # Extra safety: hard-truncate any CharField values to DB max_length
                    for p in to_create:
                        self._sanitize_model_lengths(p)
                    # отключаем тяжелые расчёты и привязки
                    for p in to_create:
                        p._skip_calculations = True
                        p.building = None
                    Property.objects.bulk_create(to_create, batch_size=500, ignore_conflicts=True)
                    created = len(to_create)

                if update_existing and to_update_ids:
                    # Загружаем существующие и обновляем поля, затем bulk_update
                    existing_map = {p.property_id: p for p in Property.objects.filter(property_id__in=to_update_ids)}
                    fields_to_update = [
                        'url', 'title', 'display_address', 'bedrooms', 'bathrooms',
                        'area_sqft', 'area_sqm', 'price', 'price_currency', 'price_duration',
                        'latitude', 'longitude', 'agent_name', 'agent_phone', 'broker_name',
                        'broker_license', 'property_type', 'furnishing', 'verified', 'reference',
                        'rera_number', 'added_on', 'description', 'features', 'images'
                    ]
                    updates = []
                    for item in properties_data:
                        pid = str(item.get('id')) if item.get('id') else None
                        if not pid or pid not in existing_map:
                            continue
                        obj_new = self._build_property_from_data(item)
                        if obj_new is None:
                            continue
                        obj_old = existing_map[pid]
                        # переносим значения
                        for f in fields_to_update:
                            setattr(obj_old, f, getattr(obj_new, f))
                        obj_old._skip_calculations = True
                        # building не трогаем при обновлении, чтобы не вызывать лишние обращения к БД
                        self._sanitize_model_lengths(obj_old)
                        updates.append(obj_old)
                    if updates:
                        Property.objects.bulk_update(updates, fields=fields_to_update, batch_size=500)
                        updated = len(updates)

            self.stdout.write(
                f'Файл {file_path}: создано {created}, обновлено {updated} объектов'
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Ошибка пакетного импорта: {e}'))

    def create_or_update_property(self, data, update_existing):
        """Создание или обновление объекта недвижимости"""
        
        def truncate(value, field_name):
            """Обрезает строку по max_length для указанного поля модели Property."""
            if value is None:
                return None
            try:
                field = Property._meta.get_field(field_name)
                max_len = getattr(field, 'max_length', None)
                if max_len and isinstance(value, str) and len(value) > max_len:
                    return value[:max_len]
            except Exception:
                pass
            return value
        
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
        property_obj.property_id = truncate(str(property_id), 'property_id')
        property_obj.url = truncate(data.get('url', '') or data.get('share_url', ''), 'url')
        property_obj.title = truncate(data.get('title', ''), 'title')
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

        # Цена (с поддержкой запасных ключей для аренды)
        price_raw = self._extract_price(data, price_duration)
        price_decimal = self._parse_price_to_decimal(price_raw)
        property_obj.price = price_decimal
        
        property_obj.price_currency = data.get('priceCurrency', 'AED')
        price_duration = data.get('priceDuration')
        if not price_duration:
            price_duration = getattr(self, '_inferred_duration', None) or 'sell'
        property_obj.price_duration = price_duration

        # Координаты
        coordinates = data.get('coordinates', {})
        if coordinates:
            property_obj.latitude = coordinates.get('latitude')
            property_obj.longitude = coordinates.get('longitude')

        # Агент и брокер
        property_obj.agent_name = truncate(data.get('agent', ''), 'agent_name')
        property_obj.agent_phone = data.get('agentPhone', '')
        property_obj.broker_name = truncate(data.get('broker', ''), 'broker_name')
        property_obj.broker_license = truncate(data.get('brokerLicenseNumber', ''), 'broker_license')

        # Дополнительные поля
        property_obj.property_type = truncate(data.get('propertyType', ''), 'property_type')
        property_obj.furnishing = truncate(data.get('furnishing', ''), 'furnishing')
        property_obj.verified = data.get('verified', False)
        property_obj.reference = truncate(data.get('reference', ''), 'reference')
        property_obj.rera_number = truncate(data.get('rera', ''), 'rera_number')

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
        # Disable heavy calculations during mass import for performance
        property_obj._skip_calculations = True
        property_obj.save()

        return True, not is_new

    def _build_property_from_data(self, data):
        """Строит объект Property (не сохраняет), с усечением полей.
        Используется для пакетного импорта.
        """
        try:
            property_id = data.get('id')
            if not property_id:
                return None
            obj = Property()
            obj.property_id = self._truncate(str(property_id), 'property_id')
            obj.url = self._truncate(data.get('url', '') or data.get('share_url', ''), 'url')
            obj.title = self._truncate(data.get('title', ''), 'title')
            obj.display_address = data.get('displayAddress', '') or data.get('location', {}).get('full_name', '')
            obj.bedrooms = self.safe_int(data.get('bedrooms'))
            obj.bathrooms = self.safe_int(data.get('bathrooms'))
            size_min = data.get('sizeMin', '')
            if size_min:
                area_value = self.extract_area(size_min)
                if isinstance(size_min, str) and ('м²' in size_min or 'sqm' in size_min.lower()):
                    obj.area_sqm = area_value
                else:
                    obj.area_sqft = area_value
            # Цена с учётом запасных ключей
            pdur = data.get('priceDuration') or getattr(self, '_inferred_duration', None) or 'sell'
            price_raw = self._extract_price(data, pdur)
            obj.price = self._parse_price_to_decimal(price_raw)
            obj.price_currency = data.get('priceCurrency', 'AED')
            price_duration = data.get('priceDuration')
            if not price_duration:
                price_duration = getattr(self, '_inferred_duration', None) or 'sell'
            obj.price_duration = price_duration
            coords = data.get('coordinates', {}) or {}
            obj.latitude = coords.get('latitude')
            obj.longitude = coords.get('longitude')
            obj.agent_name = self._truncate(data.get('agent', ''), 'agent_name')
            obj.agent_phone = data.get('agentPhone', '')
            obj.broker_name = self._truncate(data.get('broker', ''), 'broker_name')
            obj.broker_license = self._truncate(data.get('brokerLicenseNumber', ''), 'broker_license')
            obj.property_type = self._truncate(data.get('propertyType', ''), 'property_type')
            obj.furnishing = self._truncate(data.get('furnishing', ''), 'furnishing')
            obj.verified = data.get('verified', False)
            obj.reference = self._truncate(data.get('reference', ''), 'reference')
            obj.rera_number = self._truncate(data.get('rera', ''), 'rera_number')
            added_on = data.get('addedOn')
            if added_on:
                try:
                    if isinstance(added_on, str):
                        obj.added_on = parse_datetime(added_on)
                    elif isinstance(added_on, (int, float)):
                        obj.added_on = datetime.fromtimestamp(added_on)
                except Exception:
                    pass
            obj.description = data.get('description', '') or data.get('descriptionHTML', '')
            obj.features = data.get('features', [])
            obj.images = data.get('images', [])
            obj._skip_calculations = True
            obj.building = None
            return obj
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Ошибка подготовки объекта: {e}'))
            return None

    def _truncate(self, value, field_name):
        if value is None:
            return None
        try:
            field = Property._meta.get_field(field_name)
            max_len = getattr(field, 'max_length', None)
            if max_len:
                s = str(value) if not isinstance(value, str) else value
                if len(s) > max_len:
                    return s[:max_len]
                return s
        except Exception:
            pass
        return value

    def _sanitize_model_lengths(self, instance: Property):
        """Hard truncate all CharField values on the model to avoid DB errors."""
        char_fields = [
            'property_id', 'url', 'title', 'agent_name', 'agent_phone', 'broker_name',
            'broker_license', 'property_type', 'furnishing', 'price_currency',
            'reference', 'rera_number'
        ]
        for fname in char_fields:
            try:
                val = getattr(instance, fname, None)
                if val is not None:
                    setattr(instance, fname, self._truncate(val, fname))
            except Exception:
                continue

    def _extract_price(self, data: dict, price_duration: str):
        """Возвращает цену из JSON с учётом разных возможных ключей.
        Для аренды часто используются альтернативные поля.
        """
        # прямой ключ
        if data.get('price') not in (None, ''):
            return data.get('price')
        # альтернативные ключи
        candidates_common = ['priceValue', 'amount', 'value']
        candidates_rent = [
            'rent', 'rentValue', 'rent_value', 'annualRent', 'yearly_rent',
            'yearlyRent', 'price_year', 'price_per_year'
        ]
        keys = candidates_common + (candidates_rent if price_duration == 'rent' else [])
        for k in keys:
            v = data.get(k)
            if v not in (None, ''):
                return v
        return None

    def _parse_price_to_decimal(self, value):
        """Нормализует цену в Decimal. Поддерживает строки вида 'AED 80,000/year'."""
        if value is None:
            return None
        try:
            # Если уже число/Decimal
            if isinstance(value, (int, float, Decimal)):
                return Decimal(str(value))
            s = str(value).lower()
            # Удаляем валюты/слова
            for token in ['aed', 'د.إ', 'per year', 'per month', '/year', '/month', 'yearly', 'monthly', 'yr', 'mo']:
                s = s.replace(token, ' ')
            # Заменяем запятые и нецифровые разделители
            s = s.replace('\u00a0', ' ').replace(',', '')
            # Ищем первое число
            import re
            m = re.search(r"\d+(?:[\.\s]\d+)?", s)
            if not m:
                return None
            num = m.group(0).replace(' ', '')
            return Decimal(num)
        except Exception:
            return None

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