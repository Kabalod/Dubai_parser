from django.db import models
from django.db.models import Avg, Count
from datetime import datetime, timedelta
import re

# Список разрешенных районов Дубая
AREAS_WITH_PROPERTY = {
    "Jumeirah Village Circle": 0,
    "Business Bay": 0,
    "Dubai Land": 0,
    "Downtown Dubai": 0,
    "Dubai Marina": 0,
    "Mohammed Bin Rashid City": 0,
    "Jumeirah Village Triangle": 0,
    "Deira": 0,
    "Arjan": 0,
    "Dubai Creek Harbour The Lagoons": 0,
    "Dubai Hills Estate": 0,
    "Al Furjan": 0,
    "Dubai Science Park": 0,
    "Dubai Sports City": 0,
    "Al Jaddaf": 0,
    "Palm Jumeirah": 0,
    "Dubai Harbour": 0,
    "Jumeirah Lake Towers": 0,
    "City of Arabia": 0,
    "Dubai Production City IMPZ": 0,
    "Dubai Land Residence Complex": 0,
    "Dubai South Dubai World Central": 0,
    "Dubai Investment Park DIP": 0,
    "Maritime City": 0,
    "Meydan": 0,
    "Dubai Studio City": 0,
    "Dubai Silicon Oasis": 0,
    "Al Satwa": 0,
    "Motor City": 0,
    "Jumeirah Beach Residence": 0,
    "DAMAC Hills": 0,
    "Town Square": 0,
    "Bukadra": 0,
    "Al Warsan": 0,
    "Wasl Gate": 0,
    "City Walk": 0,
    "Zabeel": 0,
    "Umm Suqeim": 0,
    "Al Wasl": 0,
    "International City": 0,
    "Mina Rashid": 0,
    "Jebel Ali": 0,
    "Expo City": 0,
    "Damac Lagoons": 0,
    "Bluewaters": 0,
    "DIFC": 0,
    "Downtown Jebel Ali": 0,
    "Jumeirah": 0,
    "Damac Hills": 0,
    "Discovery Gardens": 0,
    "Sheikh Zayed Road": 0,
    "Al Barsha": 0,
    "Nad Al Sheba": 0,
    "Ras Al Khor": 0,
    "Barsha Heights Tecom": 0,
    "Culture Village": 0,
    "Greens": 0,
    "Old Town": 0,
    "Mirdif": 0,
    "The Views": 0,
    "Dubai Design District": 0,
    "Al Sufouh": 0,
    "Dubai Industrial City": 0,
    "Jumeirah Islands": 0,
    "Living Legends": 0,
    "Dubai Media City": 0,
    "Al Safa": 0,
    "Dubai Internet City": 0,
    "Emirates Hills": 0,
    "The World Islands": 0,
    "Jumeirah Golf Estates": 0,
    "Falcon City of Wonders": 0,
    "Al Quoz": 0,
    "Dubai Festival City": 0,
    "The Hills": 0,
    "Al Muhaisnah": 0,
    "Al Yelayiss": 0,
    "Al Barari": 0,
    "Bur Dubai": 0,
    "World Trade Center": 0,
    "Mudon": 0,
    "The Valley": 0,
    "Wadi Al Safa": 0,
    "Dubai Waterfront": 0,
    "DuBiotech": 0,
    "The Oasis by Emaar": 0,
    "Nadd Al Hammar": 0,
    "Al Qusais": 0,
    "Arabian Ranches": 0,
    "Palm Jebel Ali": 0,
    "Al Nahda": 0,
    "Tilal Al Ghaf": 0,
    "Mohammad Bin Rashid Gardens": 0,
}


class Building(models.Model):
    """Модель здания"""
    name = models.CharField(max_length=500, verbose_name="Название здания")
    address = models.TextField(verbose_name="Адрес")
    latitude = models.FloatField(null=True, blank=True, verbose_name="Широта")
    longitude = models.FloatField(null=True, blank=True, verbose_name="Долгота")
    area = models.CharField(max_length=200, null=True, blank=True, verbose_name="Район")
    
    class Meta:
        verbose_name = "Здание"
        verbose_name_plural = "Здания"
        unique_together = ['name', 'address']
    
    def __str__(self):
        return f"{self.name} - {self.address}"
    
    def avg_sale_price(self):
        """Средняя цена продажи в здании"""
        return self.properties.filter(
            price_duration='sell',
            price__isnull=False
        ).aggregate(avg_price=Avg('price'))['avg_price'] or 0
    
    def avg_rent_price(self):
        """Средняя цена аренды в здании"""
        return self.properties.filter(
            price_duration='rent',
            price__isnull=False
        ).aggregate(avg_price=Avg('price'))['avg_price'] or 0
    
    def sale_count(self):
        """Количество объявлений на продажу"""
        return self.properties.filter(price_duration='sell').count()
    
    def rent_count(self):
        """Количество объявлений на аренду"""
        return self.properties.filter(price_duration='rent').count()
    
    def avg_roi(self):
        """Средний ROI здания"""
        properties = self.properties.filter(
            price_duration='sell',
            price__isnull=False,
            roi__isnull=False
        )
        return properties.aggregate(avg_roi=Avg('roi'))['avg_roi'] or 0
    
    def avg_price_by_bedrooms(self, bedrooms, price_duration='sell'):
        """Средняя цена в здании для определенного количества спален"""
        properties = self.properties.filter(
            price_duration=price_duration,
            price__isnull=False,
            bedrooms=bedrooms
        )
        return properties.aggregate(avg_price=Avg('price'))['avg_price'] or 0


class Property(models.Model):
    """Модель объекта недвижимости"""
    
    # Основные поля
    property_id = models.CharField(max_length=100, unique=True, verbose_name="ID объекта")
    url = models.URLField(verbose_name="Ссылка")
    title = models.CharField(max_length=500, verbose_name="Заголовок")
    display_address = models.TextField(verbose_name="Адрес для отображения")
    
    # Характеристики
    bedrooms = models.IntegerField(null=True, blank=True, verbose_name="Спальни")
    bathrooms = models.IntegerField(null=True, blank=True, verbose_name="Ванные")
    area_sqft = models.FloatField(null=True, blank=True, verbose_name="Площадь (кв.фт)")
    area_sqm = models.FloatField(null=True, blank=True, verbose_name="Площадь (кв.м)")
    
    # Цена и тип
    price = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name="Цена")
    price_currency = models.CharField(max_length=10, default='AED', verbose_name="Валюта")
    price_duration = models.CharField(max_length=10, choices=[
        ('sell', 'Продажа'),
        ('rent', 'Аренда')
    ], verbose_name="Тип цены")
    
    # Местоположение
    latitude = models.FloatField(null=True, blank=True, verbose_name="Широта")
    longitude = models.FloatField(null=True, blank=True, verbose_name="Долгота")
    
    # Агент и брокер
    agent_name = models.CharField(max_length=200, null=True, blank=True, verbose_name="Имя агента")
    agent_phone = models.CharField(max_length=50, null=True, blank=True, verbose_name="Телефон агента")
    broker_name = models.CharField(max_length=200, null=True, blank=True, verbose_name="Брокер")
    broker_license = models.CharField(max_length=100, null=True, blank=True, verbose_name="Лицензия брокера")
    
    # Дополнительные поля
    property_type = models.CharField(max_length=100, null=True, blank=True, verbose_name="Тип недвижимости")
    furnishing = models.CharField(max_length=50, null=True, blank=True, verbose_name="Меблировка")
    verified = models.BooleanField(default=False, verbose_name="Проверено")
    reference = models.CharField(max_length=100, null=True, blank=True, verbose_name="Референс")
    rera_number = models.CharField(max_length=100, null=True, blank=True, verbose_name="RERA номер")
    
    # Даты
    added_on = models.DateTimeField(null=True, blank=True, verbose_name="Дата добавления")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")
    
    # Описание и изображения
    description = models.TextField(null=True, blank=True, verbose_name="Описание")
    features = models.JSONField(default=list, blank=True, verbose_name="Особенности")
    images = models.JSONField(default=list, blank=True, verbose_name="Изображения")
    
    # Связи
    building = models.ForeignKey(Building, on_delete=models.SET_NULL, null=True, blank=True, 
                                related_name='properties', verbose_name="Здание")
    
    # Расчетные поля
    roi = models.FloatField(null=True, blank=True, verbose_name="ROI (%)")
    days_on_market = models.IntegerField(null=True, blank=True, verbose_name="Дней на рынке")
    
    class Meta:
        verbose_name = "Объект недвижимости"
        verbose_name_plural = "Объекты недвижимости"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.price} {self.price_currency}"
    
    def save(self, *args, **kwargs):
        # Автоматическое создание/привязка к зданию
        if self.display_address and not self.building:
            building_name = self.extract_building_name()
            if building_name:
                building, created = Building.objects.get_or_create(
                    name=building_name,
                    address=self.display_address,
                    defaults={
                        'latitude': self.latitude,
                        'longitude': self.longitude,
                        'area': self.extract_area_name()
                    }
                )
                self.building = building
        
        # Расчет ROI
        if self.price_duration == 'sell' and self.price:
            calculated_roi = self.calculate_property_roi()
            if calculated_roi:
                self.roi = calculated_roi
        
        # Расчет дней на рынке
        if self.added_on:
            self.days_on_market = (datetime.now().date() - self.added_on.date()).days
        
        super().save(*args, **kwargs)
    
    def extract_building_name(self):
        """Извлекает название здания из адреса"""
        if not self.display_address:
            return None
        
        # Простая логика извлечения названия здания
        # Можно улучшить в зависимости от формата адресов
        address_parts = self.display_address.split(',')
        if len(address_parts) > 0:
            # Берем первую часть как название здания
            building_name = address_parts[0].strip()
            # Убираем номера квартир/офисов
            building_name = re.sub(r'\b\d+\b', '', building_name).strip()
            return building_name if building_name else None
        return None
    
    def extract_area_name(self):
        """Извлекает название района из адреса на основе списка разрешенных районов"""
        if not self.display_address:
            return None
        
        address_text = self.display_address.lower()
        
        # Ищем точное совпадение с районами из списка
        for area_name in AREAS_WITH_PROPERTY.keys():
            if area_name.lower() in address_text:
                return area_name
        
        # Если точного совпадения нет, пробуем найти по частям
        # Например, "JVC" для "Jumeirah Village Circle"
        area_mappings = {
            'jvc': 'Jumeirah Village Circle',
            'jvt': 'Jumeirah Village Triangle',
            'jlt': 'Jumeirah Lake Towers',
            'jbr': 'Jumeirah Beach Residence',
            'impz': 'Dubai Production City IMPZ',
            'dip': 'Dubai Investment Park DIP',
            'tecom': 'Barsha Heights Tecom',
            'dlrc': 'Dubai Land Residence Complex',
            'dsf': 'Dubai Sports City',
            'dsc': 'Dubai Studio City',
            'dso': 'Dubai Silicon Oasis',
            'dmc': 'Dubai Media City',
            'dic': 'Dubai Internet City',
            'dwc': 'Dubai South Dubai World Central',
        }
        
        for abbr, full_name in area_mappings.items():
            if abbr in address_text:
                return full_name
        
        # Если ничего не найдено, возвращаем None
        return None
    
    def get_area_avg_days_on_market(self):
        """Средняя экспозиция района"""
        if not self.building or not self.building.area:
            return 0
        
        area_properties = Property.objects.filter(
            building__area=self.building.area,
            days_on_market__isnull=False
        )
        
        return area_properties.aggregate(
            avg_days=Avg('days_on_market')
        )['avg_days'] or 0
    
    def get_avg_building_price_by_bedrooms(self):
        """Средняя цена в здании для данного количества спален"""
        if not self.building or self.bedrooms is None:
            return 0
        
        return self.building.avg_price_by_bedrooms(self.bedrooms, self.price_duration)
    
    @property
    def rooms_display(self):
        """Отображение количества комнат"""
        if self.bedrooms:
            return f"{self.bedrooms} спален"
        return "Не указано"
    
    @property
    def area_display(self):
        """Отображение площади"""
        if self.area_sqm:
            return f"{self.area_sqm} кв.м"
        elif self.area_sqft:
            return f"{self.area_sqft} кв.фт"
        return "Не указано"
    
    def calculate_property_roi(self):
        """Расчет ROI конкретного объявления"""
        if self.price_duration != 'sell' or not self.price or not self.building:
            return None
        
        # Находим среднюю арендную плату для аналогичных объектов в том же здании
        if self.bedrooms is not None:
            avg_rent = self.building.properties.filter(
                price_duration='rent',
                bedrooms=self.bedrooms,
                price__isnull=False
            ).aggregate(avg_price=Avg('price'))['avg_price']
            
            if not avg_rent:
                # Если нет данных по аренде в здании, берем общую среднюю по району
                if self.building.area:
                    avg_rent = Property.objects.filter(
                        price_duration='rent',
                        bedrooms=self.bedrooms,
                        building__area=self.building.area,
                        price__isnull=False
                    ).aggregate(avg_price=Avg('price'))['avg_price']
        else:
            # Если количество спален не указано, берем общую среднюю
            avg_rent = self.building.properties.filter(
                price_duration='rent',
                price__isnull=False
            ).aggregate(avg_price=Avg('price'))['avg_price']
            
            if not avg_rent and self.building.area:
                avg_rent = Property.objects.filter(
                    price_duration='rent',
                    building__area=self.building.area,
                    price__isnull=False
                ).aggregate(avg_price=Avg('price'))['avg_price']
        
        if avg_rent and avg_rent > 0:
            annual_rent = float(avg_rent) * 12
            return round((annual_rent / float(self.price)) * 100, 2)
        
        return None
    
    def get_building_avg_roi(self):
        """Средний ROI здания"""
        if not self.building:
            return None
        
        # Получаем все объекты продажи в здании с ROI
        building_properties = self.building.properties.filter(
            price_duration='sell',
            roi__isnull=False
        )
        
        if building_properties.exists():
            return round(building_properties.aggregate(avg_roi=Avg('roi'))['avg_roi'], 2)
        
        # Если нет готовых ROI, рассчитываем на лету
        sale_properties = self.building.properties.filter(
            price_duration='sell',
            price__isnull=False
        )
        
        roi_values = []
        for prop in sale_properties:
            roi = prop.calculate_property_roi()
            if roi:
                roi_values.append(roi)
        
        if roi_values:
            return round(sum(roi_values) / len(roi_values), 2)
        
        return None
    
    def get_price_per_sqft(self):
        """Цена за квадратный фут"""
        if not self.price:
            return None
        
        if self.area_sqft and self.area_sqft > 0:
            return round(float(self.price) / self.area_sqft, 2)
        elif self.area_sqm and self.area_sqm > 0:
            # Конвертируем кв.м в кв.фт (1 кв.м = 10.764 кв.фт)
            area_sqft = self.area_sqm * 10.764
            return round(float(self.price) / area_sqft, 2)
        
        return None
    
    def get_building_avg_exposure_days(self):
        """Среднее время экспозиции в здании"""
        if not self.building:
            return None
        
        building_properties = self.building.properties.filter(
            days_on_market__isnull=False,
            price_duration=self.price_duration
        )
        
        if building_properties.exists():
            return round(building_properties.aggregate(
                avg_days=Avg('days_on_market')
            )['avg_days'], 1)
        
        return None
    
    def get_building_rent_count(self):
        """Количество объявлений на аренду в здании"""
        if not self.building:
            return 0
        
        return self.building.properties.filter(price_duration='rent').count()
    
    def get_building_sale_count(self):
        """Количество объявлений на продажу в здании"""
        if not self.building:
            return 0
        
        return self.building.properties.filter(price_duration='sell').count()
    
    def get_building_rent_count_by_bedrooms(self):
        """Количество объявлений на аренду в здании с таким же количеством спален"""
        if not self.building or self.bedrooms is None:
            return 0
        
        return self.building.properties.filter(
            price_duration='rent',
            bedrooms=self.bedrooms
        ).count()
    
    def get_building_sale_count_by_bedrooms(self):
        """Количество объявлений на продажу в здании с таким же количеством спален"""
        if not self.building or self.bedrooms is None:
            return 0
        
        return self.building.properties.filter(
            price_duration='sell',
            bedrooms=self.bedrooms
        ).count()
    
    def get_avg_rent_in_building_by_bedrooms(self):
        """Средняя арендная плата в здании для данного количества спален"""
        if not self.building or self.bedrooms is None:
            return None
        
        avg_rent = self.building.properties.filter(
            price_duration='rent',
            bedrooms=self.bedrooms,
            price__isnull=False
        ).aggregate(avg_price=Avg('price'))['avg_price']
        
        return round(float(avg_rent), 2) if avg_rent else None


class PropertyAnalytics(models.Model):
    """Модель для хранения аналитических данных"""
    date = models.DateField(verbose_name="Дата")
    area = models.CharField(max_length=200, verbose_name="Район")
    avg_sale_price = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Средняя цена продажи")
    avg_rent_price = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Средняя цена аренды")
    total_sale_listings = models.IntegerField(verbose_name="Объявлений на продажу")
    total_rent_listings = models.IntegerField(verbose_name="Объявлений на аренду")
    avg_days_on_market = models.FloatField(verbose_name="Средние дни на рынке")
    
    class Meta:
        verbose_name = "Аналитика"
        verbose_name_plural = "Аналитика"
        unique_together = ['date', 'area']


class PropertyMetrics(models.Model):
    """Модель для хранения предрассчитанных метрик недвижимости"""
    
    # Связь с основным объектом
    property = models.OneToOneField(
        Property, 
        on_delete=models.CASCADE, 
        related_name='metrics',
        verbose_name="Объект недвижимости"
    )
    
    # Основные показатели
    roi = models.FloatField(null=True, blank=True, verbose_name="ROI объявления (%)")
    price_per_sqft = models.FloatField(null=True, blank=True, verbose_name="Цена за кв.фт")
    
    # Показатели здания
    building_avg_price = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True,
        verbose_name="Средняя цена в здании"
    )
    building_avg_price_by_bedrooms = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True,
        verbose_name="Средняя цена в здании для данного кол-ва спален"
    )
    building_avg_roi = models.FloatField(null=True, blank=True, verbose_name="Средний ROI здания (%)")
    building_avg_exposure_days = models.FloatField(
        null=True, blank=True, verbose_name="Средняя экспозиция здания (дни)"
    )
    
    # Количественные показатели здания
    building_sale_count = models.IntegerField(default=0, verbose_name="Объявлений на продажу в здании")
    building_rent_count = models.IntegerField(default=0, verbose_name="Объявлений на аренду в здании")
    building_sale_count_by_bedrooms = models.IntegerField(
        default=0, verbose_name="Объявлений на продажу в здании с таким же кол-вом спален"
    )
    building_rent_count_by_bedrooms = models.IntegerField(
        default=0, verbose_name="Объявлений на аренду в здании с таким же кол-вом спален"
    )
    
    # Показатели района
    area_avg_days_on_market = models.FloatField(
        null=True, blank=True, verbose_name="Средняя экспозиция района (дни)"
    )
    
    # Арендные показатели
    avg_rent_by_bedrooms = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True,
        verbose_name="Средняя аренда в здании для данного кол-ва спален"
    )
    
    # Дата последнего обновления
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")
    
    class Meta:
        verbose_name = "Метрики недвижимости"
        verbose_name_plural = "Метрики недвижимости"
        indexes = [
            models.Index(fields=['roi']),
            models.Index(fields=['building_avg_roi']),
            models.Index(fields=['price_per_sqft']),
            models.Index(fields=['building_avg_exposure_days']),
            models.Index(fields=['area_avg_days_on_market']),
        ]
    
    def __str__(self):
        return f"Метрики для {self.property.title}" 