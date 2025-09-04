from django.contrib import admin
from .models import Property, Building, PropertyAnalytics, PropertyMetrics


@admin.register(Building)
class BuildingAdmin(admin.ModelAdmin):
    list_display = ['name', 'address', 'area', 'sale_count', 'rent_count', 'avg_sale_price']
    list_filter = ['area']
    search_fields = ['name', 'address']
    readonly_fields = ['avg_sale_price', 'avg_rent_price', 'sale_count', 'rent_count', 'avg_roi']
    
    def avg_sale_price(self, obj):
        return f"{obj.avg_sale_price():,.0f} AED"
    avg_sale_price.short_description = "Средняя цена продажи"
    
    def avg_rent_price(self, obj):
        return f"{obj.avg_rent_price():,.0f} AED"
    avg_rent_price.short_description = "Средняя цена аренды"


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ['title', 'price', 'price_currency', 'price_duration', 'bedrooms', 
                   'building', 'agent_name', 'days_on_market', 'roi']
    list_filter = ['price_duration', 'property_type', 'bedrooms', 'verified', 'building__area']
    search_fields = ['title', 'display_address', 'agent_name', 'broker_name']
    readonly_fields = ['property_id', 'roi', 'days_on_market', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('property_id', 'title', 'url', 'display_address')
        }),
        ('Характеристики', {
            'fields': ('bedrooms', 'bathrooms', 'area_sqft', 'area_sqm', 'property_type', 'furnishing')
        }),
        ('Цена', {
            'fields': ('price', 'price_currency', 'price_duration')
        }),
        ('Местоположение', {
            'fields': ('latitude', 'longitude', 'building')
        }),
        ('Агент и брокер', {
            'fields': ('agent_name', 'agent_phone', 'broker_name', 'broker_license')
        }),
        ('Дополнительно', {
            'fields': ('verified', 'reference', 'rera_number', 'added_on')
        }),
        ('Расчетные поля', {
            'fields': ('roi', 'days_on_market', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
        ('Описание', {
            'fields': ('description', 'features', 'images'),
            'classes': ('collapse',)
        })
    )


@admin.register(PropertyAnalytics)
class PropertyAnalyticsAdmin(admin.ModelAdmin):
    list_display = ['date', 'area', 'avg_sale_price', 'avg_rent_price', 
                   'total_sale_listings', 'total_rent_listings', 'avg_days_on_market']
    list_filter = ['date', 'area']
    search_fields = ['area']
    date_hierarchy = 'date'


@admin.register(PropertyMetrics)
class PropertyMetricsAdmin(admin.ModelAdmin):
    list_display = ['property', 'roi', 'building_avg_roi', 'price_per_sqft', 
                   'building_sale_count', 'building_rent_count', 'updated_at']
    list_filter = ['updated_at']
    search_fields = ['property__title', 'property__building__name']
    readonly_fields = ['updated_at']
    
    fieldsets = (
        ('Основные показатели', {
            'fields': ('property', 'roi', 'price_per_sqft')
        }),
        ('Показатели здания', {
            'fields': ('building_avg_price', 'building_avg_price_by_bedrooms', 
                      'building_avg_roi', 'building_avg_exposure_days')
        }),
        ('Количественные показатели', {
            'fields': ('building_sale_count', 'building_rent_count',
                      'building_sale_count_by_bedrooms', 'building_rent_count_by_bedrooms')
        }),
        ('Показатели района', {
            'fields': ('area_avg_days_on_market', 'avg_rent_by_bedrooms')
        }),
        ('Служебная информация', {
            'fields': ('updated_at',),
            'classes': ('collapse',)
        })
    ) 