from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('climate/', views.ServiceLandingView.as_view(), {'service': 'climate'}, name='climate'),
    path('air-quality/', views.ServiceLandingView.as_view(), {'service': 'air-quality'}, name='air_quality'),
    path('marine/', views.ServiceLandingView.as_view(), {'service': 'marine'}, name='marine'),
    path('aviation/', views.ServiceLandingView.as_view(), {'service': 'aviation'}, name='aviation'),
    path(
        'aviation/airports/dili/live-observation/',
        views.DiliAwosLiveObservationView.as_view(),
        name='dili_awos_live_observation',
    ),
    path(
        'aviation/airports/<slug:airport>/',
        views.AviationAirportDetailView.as_view(),
        name='aviation_airport_detail',
    ),
    path('data-maps/', views.ServiceLandingView.as_view(), {'service': 'data-maps'}, name='data_maps'),
    path('dss/', views.DSSView.as_view(), name='dss'),
    path('profile/about/', views.AboutDNMGView.as_view(), name='about_dnmg'),
    path('profile/structure/', views.DNMGStructureView.as_view(), name='dnmg_structure'),
]
