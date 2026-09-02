from django import forms
from django.utils.translation import gettext_lazy as _
from .models import WeatherStation, WeatherObservation, WeatherForecast, EarlyWarning

class WeatherStationForm(forms.ModelForm):
    class Meta:
        model = WeatherStation
        fields = ['name', 'code', 'municipality', 'latitude', 'longitude', 'elevation', 'station_type', 'status', 'installed_date']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('e.g. Dili International Airport AWS')}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('e.g. DILI-AWS-01')}),
            'municipality': forms.Select(attrs={'class': 'form-select'}),
            'latitude': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.000001', 'placeholder': '-8.555890'}),
            'longitude': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.000001', 'placeholder': '125.573610'}),
            'elevation': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '8.5'}),
            'station_type': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'installed_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }


class WeatherObservationForm(forms.ModelForm):
    class Meta:
        model = WeatherObservation
        fields = [
            'station', 'temperature', 'humidity', 'rainfall_mm',
            'wind_speed_kmh', 'wind_direction', 'pressure_hpa',
            'wave_height_m', 'condition_text', 'recorded_at'
        ]
        widgets = {
            'station': forms.Select(attrs={'class': 'form-select'}),
            'temperature': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '29.50'}),
            'humidity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '75.00'}),
            'rainfall_mm': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '12.40'}),
            'wind_speed_kmh': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '15.00'}),
            'wind_direction': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ESE'}),
            'pressure_hpa': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '1011.20'}),
            'wave_height_m': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '1.50'}),
            'condition_text': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Partly Cloudy')}),
            'recorded_at': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
        }


class WeatherForecastForm(forms.ModelForm):
    class Meta:
        model = WeatherForecast
        fields = ['municipality', 'forecast_date', 'temp_min', 'temp_max', 'condition', 'icon', 'rain_probability', 'wind_summary']
        widgets = {
            'municipality': forms.Select(attrs={'class': 'form-select'}),
            'forecast_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'temp_min': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '23'}),
            'temp_max': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '32'}),
            'condition': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Scattered Showers')}),
            'icon': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'cloud-rain'}),
            'rain_probability': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '60'}),
            'wind_summary': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '15 km/h E'}),
        }


class EarlyWarningForm(forms.ModelForm):
    class Meta:
        model = EarlyWarning
        fields = ['title', 'severity', 'region', 'description', 'valid_from', 'valid_to', 'is_active']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Heavy Rainfall & Strong Wind Advisory')}),
            'severity': forms.Select(attrs={'class': 'form-select'}),
            'region': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Viqueque & Lautem Municipalities')}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': _('Detailed hazard information...')}),
            'valid_from': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'valid_to': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
