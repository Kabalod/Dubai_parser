from django.shortcuts import render
from django.db.models import Q, Avg, Count, Case, When, FloatField
from django.core.paginator import Paginator
from django.http import JsonResponse
from django_tables2 import RequestConfig
from .models import Property, Building, AREAS_WITH_PROPERTY
from .tables import PropertyTable
from django.conf import settings


def property_list_tables2(request):
    """Главная страница со списком недвижимости с Django Tables 2"""
    
    # Базовый queryset с предзагрузкой связанных объектов и метрик
    properties = Property.objects.select_related('building', 'metrics')
    
    # Поиск
    search_query = request.GET.get('search', '')
    if search_query:
        properties = properties.filter(
            Q(title__icontains=search_query) |
            Q(display_address__icontains=search_query) |
            Q(building__name__icontains=search_query) |
            Q(agent_name__icontains=search_query) |
            Q(broker_name__icontains=search_query)
        )
    
    # Фильтрация по цене
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    if min_price:
        try:
            properties = properties.filter(price__gte=float(min_price))
        except ValueError:
            pass
    if max_price:
        try:
            properties = properties.filter(price__lte=float(max_price))
        except ValueError:
            pass
    
    # Фильтрация по количеству спален
    bedrooms = request.GET.get('bedrooms')
    if bedrooms:
        try:
            properties = properties.filter(bedrooms=int(bedrooms))
        except ValueError:
            pass
    
    # Фильтрация по типу (продажа/аренда)
    price_duration = request.GET.get('price_duration')
    if price_duration in ['sell', 'rent']:
        properties = properties.filter(price_duration=price_duration)
    
    # Фильтрация по району
    area = request.GET.get('area')
    if area:
        properties = properties.filter(building__area__icontains=area)
    
    # Фильтрация по зданию
    building_name = request.GET.get('building')
    if building_name:
        properties = properties.filter(building__name__icontains=building_name)
    
    # Фильтрация по ROI
    min_roi = request.GET.get('min_roi')
    max_roi = request.GET.get('max_roi')
    if min_roi:
        try:
            properties = properties.filter(roi__gte=float(min_roi))
        except ValueError:
            pass
    if max_roi:
        try:
            properties = properties.filter(roi__lte=float(max_roi))
        except ValueError:
            pass
    
    # Создаем таблицу
    table = PropertyTable(properties)
    
    # Настраиваем таблицу с параметрами запроса
    RequestConfig(request, paginate={'per_page': 50}).configure(table)
    
    # Получаем список разрешенных районов
    available_areas = sorted(AREAS_WITH_PROPERTY.keys())
    
    buildings = Building.objects.values_list('name', flat=True).distinct().order_by('name')
    buildings = [building for building in buildings if building]  # Убираем пустые значения
    
    bedroom_choices = Property.objects.values_list('bedrooms', flat=True).distinct().order_by('bedrooms')
    bedroom_choices = [br for br in bedroom_choices if br is not None]
    
    context = {
        'table': table,
        'search_query': search_query,
        'available_areas': available_areas,
        'buildings': buildings,
        'bedroom_choices': bedroom_choices,
        'current_filters': {
            'min_price': min_price,
            'max_price': max_price,
            'bedrooms': bedrooms,
            'price_duration': price_duration,
            'area': area,
            'building': building_name,
            'min_roi': min_roi,
            'max_roi': max_roi,
        },
        'total_properties': properties.count(),
    }
    
    return render(request, 'properties/property_list_tables2.html', context)


def property_list(request):
    """Главная страница со списком недвижимости"""
    
    # Базовый queryset с предзагрузкой связанных объектов
    properties = Property.objects.select_related('building').prefetch_related('building__properties')
    
    # Поиск
    search_query = request.GET.get('search', '')
    if search_query:
        properties = properties.filter(
            Q(title__icontains=search_query) |
            Q(display_address__icontains=search_query) |
            Q(building__name__icontains=search_query) |
            Q(agent_name__icontains=search_query) |
            Q(broker_name__icontains=search_query)
        )
    
    # Фильтрация по цене
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    if min_price:
        try:
            properties = properties.filter(price__gte=float(min_price))
        except ValueError:
            pass
    if max_price:
        try:
            properties = properties.filter(price__lte=float(max_price))
        except ValueError:
            pass
    
    # Фильтрация по количеству спален
    bedrooms = request.GET.get('bedrooms')
    if bedrooms:
        try:
            properties = properties.filter(bedrooms=int(bedrooms))
        except ValueError:
            pass
    
    # Фильтрация по типу (продажа/аренда)
    price_duration = request.GET.get('price_duration')
    if price_duration in ['sell', 'rent']:
        properties = properties.filter(price_duration=price_duration)
    
    # Фильтрация по району
    area = request.GET.get('area')
    if area:
        properties = properties.filter(building__area__icontains=area)
    
    # Фильтрация по зданию
    building_name = request.GET.get('building')
    if building_name:
        properties = properties.filter(building__name__icontains=building_name)
    
    # Фильтрация по ROI
    min_roi = request.GET.get('min_roi')
    max_roi = request.GET.get('max_roi')
    if min_roi:
        try:
            properties = properties.filter(roi__gte=float(min_roi))
        except ValueError:
            pass
    if max_roi:
        try:
            properties = properties.filter(roi__lte=float(max_roi))
        except ValueError:
            pass
    
    # Сортировка
    sort_by = request.GET.get('sort', 'created_at')
    sort_order = request.GET.get('order', 'desc')
    
    # Определяем доступные поля для сортировки
    sortable_fields = {
        'price': 'price',
        'bedrooms': 'bedrooms',
        'area': 'area_sqm',
        'roi': 'roi',
        'days_on_market': 'days_on_market',
        'created_at': 'created_at',
        'building': 'building__name',
        'area_name': 'building__area'
    }
    
    if sort_by in sortable_fields:
        order_prefix = '-' if sort_order == 'desc' else ''
        properties = properties.order_by(f'{order_prefix}{sortable_fields[sort_by]}')
    
    # Пагинация
    paginator = Paginator(properties, getattr(settings, 'PAGINATION_PER_PAGE', 50))
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Получаем список разрешенных районов
    available_areas = sorted(AREAS_WITH_PROPERTY.keys())
    
    buildings = Building.objects.values_list('name', flat=True).distinct().order_by('name')
    buildings = [building for building in buildings if building]  # Убираем пустые значения
    
    bedroom_choices = Property.objects.values_list('bedrooms', flat=True).distinct().order_by('bedrooms')
    bedroom_choices = [br for br in bedroom_choices if br is not None]
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'available_areas': available_areas,
        'buildings': buildings,
        'bedroom_choices': bedroom_choices,
        'current_filters': {
            'min_price': min_price,
            'max_price': max_price,
            'bedrooms': bedrooms,
            'price_duration': price_duration,
            'area': area,
            'building': building_name,
            'min_roi': min_roi,
            'max_roi': max_roi,
            'sort': sort_by,
            'order': sort_order,
        },
        'total_properties': paginator.count,
    }
    
    return render(request, 'properties/property_list_simple.html', context)


def property_analytics(request):
    """Страница с аналитикой"""
    
    # Аналитика по районам
    area_stats = Building.objects.values('area').annotate(
        total_buildings=Count('id'),
        total_properties=Count('properties'),
        avg_sale_price=Avg(
            Case(
                When(properties__price_duration='sell', then='properties__price'),
                output_field=FloatField()
            )
        ),
        avg_rent_price=Avg(
            Case(
                When(properties__price_duration='rent', then='properties__price'),
                output_field=FloatField()
            )
        ),
        sale_count=Count(
            Case(
                When(properties__price_duration='sell', then=1)
            )
        ),
        rent_count=Count(
            Case(
                When(properties__price_duration='rent', then=1)
            )
        ),
        avg_roi=Avg('properties__roi')
    ).exclude(area__isnull=True).order_by('area')
    
    # Общая статистика
    total_properties = Property.objects.count()
    total_buildings = Building.objects.count()
    avg_price_sale = Property.objects.filter(
        price_duration='sell', 
        price__isnull=False
    ).aggregate(avg=Avg('price'))['avg'] or 0
    avg_price_rent = Property.objects.filter(
        price_duration='rent', 
        price__isnull=False
    ).aggregate(avg=Avg('price'))['avg'] or 0
    
    context = {
        'area_stats': area_stats,
        'total_properties': total_properties,
        'total_buildings': total_buildings,
        'avg_price_sale': avg_price_sale,
        'avg_price_rent': avg_price_rent,
    }
    
    return render(request, 'properties/analytics.html', context)


def building_detail(request, building_id):
    """Детальная информация о здании"""
    try:
        building = Building.objects.get(id=building_id)
        properties = building.properties.all().order_by('-created_at')
        
        # Статистика здания
        stats = {
            'total_properties': properties.count(),
            'sale_count': properties.filter(price_duration='sell').count(),
            'rent_count': properties.filter(price_duration='rent').count(),
            'avg_sale_price': building.avg_sale_price(),
            'avg_rent_price': building.avg_rent_price(),
            'avg_roi': building.avg_roi(),
        }
        
        context = {
            'building': building,
            'properties': properties,
            'stats': stats,
        }
        
        return render(request, 'properties/building_detail.html', context)
    
    except Building.DoesNotExist:
        return render(request, '404.html', status=404)


def api_buildings(request):
    """API для получения списка зданий (для AJAX)"""
    term = request.GET.get('term', '')
    buildings = Building.objects.filter(name__icontains=term)[:10]
    
    results = [
        {
            'id': building.id,
            'text': building.name,
            'address': building.address
        }
        for building in buildings
    ]
    
    return JsonResponse({'results': results})


def api_areas(request):
    """API для получения списка районов (для AJAX)"""
    term = request.GET.get('term', '')
    areas = Building.objects.filter(
        area__icontains=term
    ).values_list('area', flat=True).distinct()[:10]
    
    results = [
        {'id': area, 'text': area}
        for area in areas if area
    ]
    
    return JsonResponse({'results': results}) 