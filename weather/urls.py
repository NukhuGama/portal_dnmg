from django.urls import path
from . import views

app_name = 'weather'

urlpatterns = [
    # Public weather information architecture. Existing technical/admin URLs below remain unchanged.
    path('', views.PublicWeatherOverviewView.as_view(), name='public_overview'),
    path('current/', views.PublicWeatherOverviewView.as_view(), name='public_current_conditions'),
    path('public-warnings/', views.PublicWarningListView.as_view(), name='public_warning_list'),
    path('public-warnings/<int:pk>/', views.PublicWarningDetailView.as_view(), name='public_warning_detail'),
    path('radar/', views.WeatherUnavailableView.as_view(), {'service': 'radar'}, name='radar'),
    # Stations
    path('stations/', views.WeatherStationListView.as_view(), name='station_list'),
    path('stations/create/', views.WeatherStationCreateView.as_view(), name='station_create'),
    path('stations/<int:pk>/update/', views.WeatherStationUpdateView.as_view(), name='station_update'),

    # Observations
    path('observations/', views.WeatherObservationListView.as_view(), name='observation_list'),
    path('observations/create/', views.WeatherObservationCreateView.as_view(), name='observation_create'),

    # Forecasts
    path('forecasts/', views.WeatherForecastListView.as_view(), name='forecast_list'),
    path('forecasts/create/', views.WeatherForecastCreateView.as_view(), name='forecast_create'),
    path('forecasts/<int:pk>/update/', views.WeatherForecastUpdateView.as_view(), name='forecast_update'),
    path('forecasts/official/', views.OfficialForecastListView.as_view(), name='official_forecast_list'),
    path('forecasts/official/create/', views.OfficialForecastCreateView.as_view(), name='official_forecast_create'),
    path('forecasts/official/<int:pk>/update/', views.OfficialForecastUpdateView.as_view(), name='official_forecast_update'),

    # Public official forecasts managed by meteorologists.
    path('official-forecasts/', views.PublicOfficialForecastListView.as_view(), name='public_official_forecast_list'),
    path('official-forecasts/<int:pk>/', views.PublicOfficialForecastDetailView.as_view(), name='public_official_forecast_detail'),

    # Live API & Interactive Map
    path('api/live-stations/', views.LiveStationGeoJSONView.as_view(), name='api_live_stations'),
    path('api/10day-forecast-map/', views.TenDayForecastGeoJSONView.as_view(), name='api_10day_forecast_map'),
    path('api/sync-stations/', views.StationSyncAPIView.as_view(), name='api_sync_stations'),
    path('map/', views.InteractiveMapView.as_view(), name='interactive_map'),
    path('forecast-map/', views.ForecastMapView.as_view(), name='forecast_map'),

    # Early Warnings
    path('warnings/', views.EarlyWarningListView.as_view(), name='warning_list'),
    path('warnings/create/', views.EarlyWarningCreateView.as_view(), name='warning_create'),
    path('warnings/<int:pk>/update/', views.EarlyWarningUpdateView.as_view(), name='warning_update'),
    path('warnings/<int:pk>/toggle/', views.EarlyWarningToggleActiveView.as_view(), name='warning_toggle'),
]
