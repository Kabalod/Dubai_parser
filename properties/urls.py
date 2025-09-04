from django.urls import path
from . import views

app_name = 'properties'

urlpatterns = [
    path('', views.property_list_tables2, name='property_list'),  # Новая версия с Django Tables 2
    path('simple/', views.property_list, name='property_list_simple'),  # Старая версия
    path('analytics/', views.property_analytics, name='analytics'),
    path('building/<int:building_id>/', views.building_detail, name='building_detail'),
    
    # API endpoints
    path('api/buildings/', views.api_buildings, name='api_buildings'),
    path('api/areas/', views.api_areas, name='api_areas'),
] 