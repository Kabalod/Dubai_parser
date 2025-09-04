import django_tables2 as tables
from django.utils.html import format_html
from django.urls import reverse
from .models import Property


class PropertyTable(tables.Table):
    """Таблица PF недвижимости """
    
    # 1. Ссылка на объявление (сортировка по title)
    title = tables.TemplateColumn(
        template_name='properties/columns/title_link.html',
        verbose_name='Ссылка',
        orderable=True,
        order_by='title',
        attrs={'th': {'style': 'width: 12%;'}}
    )
    
    # 2. Название здания (сортировка по building.name)
    building_name = tables.Column(
        accessor='building.name',
        verbose_name='Билдинг',
        orderable=True,
        attrs={'th': {'style': 'width: 12%;'}}
    )
    
    # 3. Район (сортировка по building.area)
    area = tables.TemplateColumn(
        template_name='properties/columns/area_badge.html',
        accessor='building.area',
        verbose_name='Area',
        orderable=True,
        order_by='building__area',
        attrs={'th': {'style': 'width: 10%;'}}
    )

    # 4. Комнаты (сортировка по bedrooms)
    bedrooms = tables.Column(
        verbose_name='Комнаты',
        orderable=True,
        attrs={'th': {'style': 'width: 6%;'}}
    )
    
    # 5. Цена (сортировка по price)
    price = tables.TemplateColumn(
        template_name='properties/columns/price.html',
        verbose_name='Цена',
        orderable=True,
        order_by='price',
        attrs={'th': {'style': 'width: 10%;'}}
    )
    
    # 6. Средняя цена в здании - сортировка по metrics__building_avg_price
    avg_building_price = tables.TemplateColumn(
        template_name='properties/columns/avg_building_price_cached.html',
        verbose_name='Средняя в билдинге',
        orderable=True,
        order_by='metrics__building_avg_price',
        attrs={'th': {'style': 'width: 9%;'}}
    )
    
    # 7. Средняя цена в здании для данного количества спален - сортировка по metrics__building_avg_price_by_bedrooms
    avg_building_price_by_bedrooms = tables.TemplateColumn(
        template_name='properties/columns/avg_building_price_by_bedrooms_cached.html',
        verbose_name='Средняя в билдинге для данного кол-ва bedrooms',
        orderable=True,
        order_by='metrics__building_avg_price_by_bedrooms',
        attrs={'th': {'style': 'width: 11%;'}}
    )
    
    # 8. Количество продаж в здании - сортировка по metrics__building_sale_count
    building_sale_count = tables.TemplateColumn(
        template_name='properties/columns/building_sale_count_cached.html',
        verbose_name='Объявлений на продажу в билдинге',
        orderable=True,
        order_by='metrics__building_sale_count',
        attrs={'th': {'style': 'width: 7%;'}}
    )
    
    # 9. Экспозиция (дни на рынке) - сортировка по days_on_market
    days_on_market = tables.TemplateColumn(
        template_name='properties/columns/days_on_market.html',
        verbose_name='Экспозиция',
        orderable=True,
        order_by='days_on_market',
        attrs={'th': {'style': 'width: 7%;'}}
    )
    
    # 10. Средняя экспозиция района - сортировка по metrics__area_avg_days_on_market
    area_avg_days = tables.TemplateColumn(
        template_name='properties/columns/area_avg_days_cached.html',
        verbose_name='Средняя экспозиция района',
        orderable=True,
        order_by='metrics__area_avg_days_on_market',
        attrs={'th': {'style': 'width: 9%;'}}
    )

    # 15. Среднее время экспозиции здания - сортировка по metrics__building_avg_exposure_days
    building_avg_exposure = tables.TemplateColumn(
        template_name='properties/columns/building_avg_exposure_cached.html',
        verbose_name='Средняя экспозиция билдинга',
        orderable=True,
        order_by='metrics__building_avg_exposure_days',
        attrs={'th': {'style': 'width: 9%;'}}
    )
    
    # 11. ROI объявления - сортировка по metrics__roi
    roi = tables.TemplateColumn(
        template_name='properties/columns/roi_cached.html',
        verbose_name='ROI объявления',
        orderable=True,
        order_by='metrics__roi',
        attrs={'th': {'style': 'width: 7%;'}}
    )
    
    # 12. Средний ROI здания - сортировка по metrics__building_avg_roi
    building_avg_roi = tables.TemplateColumn(
        template_name='properties/columns/building_avg_roi_cached.html',
        verbose_name='Средний ROI билдинга',
        orderable=True,
        order_by='metrics__building_avg_roi',
        attrs={'th': {'style': 'width: 9%;'}}
    )
    
    # 13. Количество аренды в здании - сортировка по metrics__building_rent_count
    building_rent_count = tables.TemplateColumn(
        template_name='properties/columns/building_rent_count_cached.html',
        verbose_name='Объявлений на аренду в билдинге',
        orderable=True,
        order_by='metrics__building_rent_count',
        attrs={'th': {'style': 'width: 7%;'}}
    )
    
    # 14. Цена за квадратный фут - сортировка по metrics__price_per_sqft
    price_per_sqft = tables.TemplateColumn(
        template_name='properties/columns/price_per_sqft_cached.html',
        verbose_name='Цена за кв.фт',
        orderable=True,
        order_by='metrics__price_per_sqft',
        attrs={'th': {'style': 'width: 8%;'}}
    )
    

    
    # 16. Средняя арендная плата в здании для данного количества спален - сортировка по metrics__avg_rent_by_bedrooms
    avg_rent_by_bedrooms = tables.TemplateColumn(
        template_name='properties/columns/avg_rent_by_bedrooms_cached.html',
        verbose_name='Средняя аренда в билдинге для данного кол-ва bedrooms',
        orderable=True,
        order_by='metrics__avg_rent_by_bedrooms',
        attrs={'th': {'style': 'width: 11%;'}}
    )
    
    # 17. Количество объявлений на продажу в здании с таким же количеством спален - сортировка по metrics__building_sale_count_by_bedrooms
    building_sale_count_by_bedrooms = tables.TemplateColumn(
        template_name='properties/columns/building_sale_count_by_bedrooms_cached.html',
        verbose_name='Объявлений на продажу в билдинге с таким же кол-вом спален',
        orderable=True,
        order_by='metrics__building_sale_count_by_bedrooms',
        attrs={'th': {'style': 'width: 10%;'}}
    )
    
    # 18. Количество объявлений на аренду в здании с таким же количеством спален - сортировка по metrics__building_rent_count_by_bedrooms
    building_rent_count_by_bedrooms = tables.TemplateColumn(
        template_name='properties/columns/building_rent_count_by_bedrooms_cached.html',
        verbose_name='Объявлений на аренду в билдинге с таким же кол-вом спален',
        orderable=True,
        order_by='metrics__building_rent_count_by_bedrooms',
        attrs={'th': {'style': 'width: 10%;'}}
    )

    class Meta:
        model = Property
        template_name = 'django_tables2/bootstrap5.html'
        fields = ()  # Используем только определенные выше поля
        attrs = {
            'class': 'table table-striped table-hover',
            'thead': {
                'class': 'table-dark'
            }
        }
        per_page = 50
        order_by = '-created_at'
        
    def render_building_name(self, value):
        """Рендер названия здания с ограничением длины"""
        if value:
            return value[:20] + '...' if len(value) > 20 else value
        return '-' 
