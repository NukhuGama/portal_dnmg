from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('profile/about/', views.AboutDNMGView.as_view(), name='about_dnmg'),
    path('profile/structure/', views.DNMGStructureView.as_view(), name='dnmg_structure'),
]
