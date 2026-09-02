from django.urls import path

from . import views

app_name = "seismic"

urlpatterns = [
    path("earthquakes/", views.EarthquakeExplorerView.as_view(), name="earthquakes"),
    path("api/earthquakes/", views.EarthquakeGeoJSONView.as_view(), name="api_earthquakes"),
    path("api/home-summary/", views.EarthquakeHomeSummaryView.as_view(), name="home_summary"),
]
