"""
Утилиты для расчета показателей недвижимости
По аналогии с предоставленным кодом pfimport
"""
from django.db.models import Avg, Count
from .models import Property


def calculate_roi_for_property(property_obj):
    """
    Расчет ROI объявления по аналогии с предоставленным кодом
    
    Args:
        property_obj: Объект Property
        
    Returns:
        float: ROI в процентах или None
    """
    if property_obj.price_duration != 'sell' or not property_obj.price or not property_obj.building:
        return None
    
    # Получаем среднюю арендную плату для аналогичных объектов
    bedrooms = property_obj.bedrooms
    building = property_obj.building
    
    # Ищем среднюю аренду в здании для такого же количества спален
    if bedrooms is not None:
        avg_rent = building.properties.filter(
            price_duration='rent',
            bedrooms=bedrooms,
            price__isnull=False
        ).aggregate(avg_price=Avg('price'))['avg_price']
        
        if not avg_rent and building.area:
            # Если нет данных по зданию, берем по району
            avg_rent = Property.objects.filter(
                price_duration='rent',
                bedrooms=bedrooms,
                building__area=building.area,
                price__isnull=False
            ).aggregate(avg_price=Avg('price'))['avg_price']
    else:
        # Если количество спален не указано, берем общую среднюю по зданию
        avg_rent = building.properties.filter(
            price_duration='rent',
            price__isnull=False
        ).aggregate(avg_price=Avg('price'))['avg_price']
        
        if not avg_rent and building.area:
            # Если нет данных по зданию, берем по району
            avg_rent = Property.objects.filter(
                price_duration='rent',
                building__area=building.area,
                price__isnull=False
            ).aggregate(avg_price=Avg('price'))['avg_price']
    
    if avg_rent and avg_rent > 0:
        annual_rent = float(avg_rent) * 12
        roi = (annual_rent / float(property_obj.price)) * 100
        return round(roi, 2)
    
    return None


def calculate_building_avg_roi(building_obj):
    """
    Расчет среднего ROI здания
    
    Args:
        building_obj: Объект Building
        
    Returns:
        float: Средний ROI в процентах или None
    """
    if not building_obj:
        return None
    
    # Получаем все объекты продажи в здании
    sale_properties = building_obj.properties.filter(
        price_duration='sell',
        price__isnull=False
    )
    
    roi_values = []
    for prop in sale_properties:
        roi = calculate_roi_for_property(prop)
        if roi is not None:
            roi_values.append(roi)
    
    if roi_values:
        return round(sum(roi_values) / len(roi_values), 2)
    
    return None


def get_building_stats_by_bedrooms(building_obj, bedrooms, price_duration='sell'):
    """
    Получение статистики здания по количеству спален
    
    Args:
        building_obj: Объект Building
        bedrooms: Количество спален
        price_duration: 'sell' или 'rent'
        
    Returns:
        dict: Статистика
    """
    if not building_obj:
        return {
            'count': 0,
            'avg_price': None,
            'avg_roi': None
        }
    
    if bedrooms is not None:
        properties = building_obj.properties.filter(
            price_duration=price_duration,
            bedrooms=bedrooms,
            price__isnull=False
        )
    else:
        properties = building_obj.properties.filter(
            price_duration=price_duration,
            price__isnull=False
        )
    
    count = properties.count()
    avg_price = properties.aggregate(avg_price=Avg('price'))['avg_price']
    
    # Для продажи рассчитываем ROI
    avg_roi = None
    if price_duration == 'sell' and count > 0:
        roi_values = []
        for prop in properties:
            roi = calculate_roi_for_property(prop)
            if roi is not None:
                roi_values.append(roi)
        
        if roi_values:
            avg_roi = round(sum(roi_values) / len(roi_values), 2)
    
    return {
        'count': count,
        'avg_price': round(float(avg_price), 2) if avg_price else None,
        'avg_roi': avg_roi
    }


def get_area_avg_exposure_days(area_name, price_duration='sell'):
    """
    Получение средней экспозиции района
    
    Args:
        area_name: Название района
        price_duration: 'sell' или 'rent'
        
    Returns:
        float: Средние дни экспозиции или None
    """
    if not area_name:
        return None
    
    properties = Property.objects.filter(
        building__area=area_name,
        price_duration=price_duration,
        days_on_market__isnull=False
    )
    
    if properties.exists():
        avg_days = properties.aggregate(avg_days=Avg('days_on_market'))['avg_days']
        return round(avg_days, 1) if avg_days else None
    
    return None


def format_roi_badge(roi_value):
    """
    Форматирование ROI с цветовой индикацией
    
    Args:
        roi_value: Значение ROI
        
    Returns:
        dict: Данные для отображения
    """
    if roi_value is None:
        return {
            'value': None,
            'class': 'text-muted',
            'text': '-'
        }
    
    if roi_value >= 8:
        badge_class = 'bg-success'
    elif roi_value >= 5:
        badge_class = 'bg-warning text-dark'
    else:
        badge_class = 'bg-danger'
    
    return {
        'value': roi_value,
        'class': f'badge {badge_class}',
        'text': f'{roi_value:.2f}%'
    }


def format_exposure_badge(days):
    """
    Форматирование экспозиции с цветовой индикацией
    
    Args:
        days: Количество дней
        
    Returns:
        dict: Данные для отображения
    """
    if days is None:
        return {
            'value': None,
            'class': 'text-muted',
            'text': '-'
        }
    
    if days <= 30:
        badge_class = 'bg-success'
    elif days <= 90:
        badge_class = 'bg-warning'
    else:
        badge_class = 'bg-danger'
    
    return {
        'value': days,
        'class': f'badge {badge_class}',
        'text': f'{days:.1f} дней'
    } 