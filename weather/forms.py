from pathlib import Path

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from core.widgets import AdminFileInput
from .content import sanitize_forecast_html
from .models import (
    EarlyWarning, OfficialForecast, OfficialForecastAttachment, OfficialForecastImage,
    WeatherForecast, WeatherObservation, WeatherStation,
)


def validate_official_forecast_upload_size(uploaded_file):
    """Apply the project-wide upload limit to official forecast media."""
    if uploaded_file and uploaded_file.size > settings.MAX_UPLOAD_SIZE:
        limit_mb = settings.MAX_UPLOAD_SIZE // (1024 * 1024)
        raise ValidationError(
            _('Files must be %(limit)s MB or smaller.'),
            params={'limit': limit_mb},
        )
    return uploaded_file


class WeatherStationForm(forms.ModelForm):
    class Meta:
        model = WeatherStation
        fields = [
            'name', 'code', 'municipality', 'latitude', 'longitude', 'coordinate_source',
            'elevation', 'station_type', 'status', 'installed_date',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('e.g. Dili International Airport AWS')}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('e.g. DILI-AWS-01')}),
            'municipality': forms.Select(attrs={'class': 'form-select'}),
            'latitude': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.000001', 'placeholder': '-8.555890'}),
            'longitude': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.000001', 'placeholder': '125.573610'}),
            'coordinate_source': forms.Select(attrs={'class': 'form-select'}),
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


class OfficialForecastForm(forms.ModelForm):
    allowed_attachment_extensions = {
        '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.odt', '.ods', '.rtf', '.txt', '.csv', '.zip',
    }

    class Meta:
        model = OfficialForecast
        fields = [
            'title', 'forecast_period', 'valid_from', 'valid_to', 'coverage', 'summary', 'notes',
            'image', 'attachment', 'status',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('National Weather Forecast')}),
            'forecast_period': forms.Select(attrs={'class': 'form-select'}),
            'valid_from': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'valid_to': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'coverage': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Timor-Leste')}),
            'summary': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': _('Public forecast summary...')}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': _('Additional meteorologist notes...')}),
            'image': AdminFileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'attachment': AdminFileInput(attrs={'class': 'form-control', 'accept': '.pdf,.doc,.docx,.xls,.xlsx,.odt,.ods,.rtf,.txt,.csv,.zip'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }

    def clean_attachment(self):
        uploaded_file = self.cleaned_data.get('attachment')
        if uploaded_file and Path(uploaded_file.name).suffix.lower() not in self.allowed_attachment_extensions:
            raise ValidationError(_(
                'Upload a supporting document, spreadsheet, text file, CSV file, or ZIP archive.'
            ))
        return validate_official_forecast_upload_size(uploaded_file)

    def clean_image(self):
        return validate_official_forecast_upload_size(self.cleaned_data.get('image'))

    def clean_summary(self):
        return sanitize_forecast_html(self.cleaned_data.get('summary', ''))

    def clean(self):
        cleaned_data = super().clean()
        valid_from = cleaned_data.get('valid_from')
        valid_to = cleaned_data.get('valid_to')
        if valid_from and valid_to and valid_to < valid_from:
            self.add_error('valid_to', _('The validity end date cannot be before the start date.'))
        return cleaned_data


class OfficialForecastImageForm(forms.ModelForm):
    class Meta:
        model = OfficialForecastImage
        fields = ['image', 'caption', 'sort_order']
        widgets = {
            'image': AdminFileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'caption': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Image caption (optional)')}),
            'sort_order': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
        }

    def clean_image(self):
        return validate_official_forecast_upload_size(self.cleaned_data.get('image'))


class OfficialForecastAttachmentForm(forms.ModelForm):
    allowed_extensions = OfficialForecastForm.allowed_attachment_extensions

    class Meta:
        model = OfficialForecastAttachment
        fields = ['file', 'title', 'sort_order']
        widgets = {
            'file': AdminFileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.doc,.docx,.xls,.xlsx,.odt,.ods,.rtf,.txt,.csv,.zip',
            }),
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('File title (optional)')}),
            'sort_order': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
        }

    def clean_file(self):
        uploaded_file = self.cleaned_data.get('file')
        if uploaded_file and Path(uploaded_file.name).suffix.lower() not in self.allowed_extensions:
            raise ValidationError(_(
                'Upload a supporting document, spreadsheet, text file, CSV file, or ZIP archive.'
            ))
        return validate_official_forecast_upload_size(uploaded_file)


OfficialForecastImageFormSet = forms.inlineformset_factory(
    OfficialForecast,
    OfficialForecastImage,
    form=OfficialForecastImageForm,
    extra=3,
    can_delete=True,
)

OfficialForecastAttachmentFormSet = forms.inlineformset_factory(
    OfficialForecast,
    OfficialForecastAttachment,
    form=OfficialForecastAttachmentForm,
    extra=3,
    can_delete=True,
)


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
