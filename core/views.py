from django.views.generic import TemplateView
from django.views import View
from django.db.models import Prefetch
from django.http import FileResponse
from django.shortcuts import render
from django.core.files.storage import default_storage
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from weather.models import EarlyWarning, WeatherObservation, WeatherForecast
from cms.models import NewsArticle, OfficialBulletin
from hr.models import Department, DepartmentSection
from weather.services import DNMG10DayForecastService
from .media import media_available
import unicodedata

class HomeView(TemplateView):
    template_name = 'core/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _("Home")
        
        # 1. Early Warnings / Hazard Alerts from database
        db_warnings = EarlyWarning.objects.currently_public().order_by('-valid_from')
        alerts = []
        for w in db_warnings:
            alerts.append({
                'severity': w.severity,
                'title': w.title,
                'region': w.region,
                'period': f"{w.valid_from.strftime('%b %d')} - {w.valid_to.strftime('%b %d, %Y')}",
                'description': w.description
            })
        context['alerts'] = alerts

        # 2. Latest Weather Observation
        latest_obs = WeatherObservation.objects.select_related('station').order_by('-recorded_at').first()
        if latest_obs:
            context['current_weather'] = {
                'temp': float(latest_obs.temperature) if latest_obs.temperature else 29.4,
                'humidity': latest_obs.humidity or 76,
                'wind': f"{latest_obs.wind_speed_kmh or 18} km/h {latest_obs.wind_direction or 'ESE'}",
                'pressure': f"{latest_obs.pressure_hpa or 1011} hPa",
                'condition': latest_obs.condition_text or _('Partly Cloudy'),
                'station': latest_obs.station.name,
                'updated': f"Recorded at {latest_obs.recorded_at.strftime('%H:%M, %b %d')}"
            }
        else:
            context['current_weather'] = {
                'temp': 29.4,
                'humidity': 76,
                'wind': '18 km/h ESE',
                'pressure': '1011 hPa',
                'condition': _('Partly Cloudy'),
                'station': _('Presidente Nicolau Lobato International Airport (Dili)'),
                'updated': _('Updated 10 minutes ago')
            }

        # 3. 10-Day ECMWF Forecast. The background sync loop refreshes this
        # cache; page loads must never wait for the external forecast API.
        raw_forecast = DNMG10DayForecastService.get_cached_forecast(
            variable='tp', model='ECMWF-IFS'
        ) or {}

        def norm_name(s):
            if not s:
                return ''
            s = unicodedata.normalize('NFD', str(s)).encode('ascii', 'ignore').decode('utf-8').lower()
            s = s.replace(' ', '').replace('-', '')
            if 'cova' in s:
                return 'covalima'
            if 'oecus' in s:
                return 'oecusse'
            return s

        # Build structured list: [{name, days: [{date_label, value, color, alert}]}]
        forecast_municipalities = []
        for muni_name, days_raw in raw_forecast.items():
            if not isinstance(days_raw, list):
                continue
            days_out = []
            for d in days_raw[:10]:   # hard-limit to 10 days
                from django.utils.dateparse import parse_datetime
                p_start = d.get('period_start', '')
                dt_obj = parse_datetime(p_start) if p_start else None
                date_label = dt_obj.strftime('%b %d') if dt_obj else ''
                color_arr = d.get('color', [])
                color_code = color_arr[0] if isinstance(color_arr, list) and len(color_arr) > 0 else '#94CB55'
                alert_level = color_arr[1] if isinstance(color_arr, list) and len(color_arr) > 1 else 'Normal'
                days_out.append({
                    'date_label': date_label,
                    'value': d.get('aggregate_value', 0),
                    'color': color_code,
                    'alert': alert_level,
                    'period_start': p_start,
                })
            forecast_municipalities.append({
                'name': muni_name,
                'days': days_out,
            })

        context['forecast_municipalities'] = forecast_municipalities
        context['forecast_variable'] = 'tp'
        context['forecast_variable_name'] = 'Total Rainfall'
        context['forecast_variable_unit'] = 'mm'
        context['forecast_api_url'] = '/weather/api/10day-forecast-map/'

        # 4. News Articles
        db_articles = NewsArticle.objects.filter(status=NewsArticle.Status.PUBLISHED).select_related('category')[:3]
        news_headlines = []
        if db_articles.exists():
            for article in db_articles:
                news_headlines.append({
                    'title': article.title,
                    'summary': article.excerpt,
                    'date': article.published_at.strftime('%b %d, %Y') if article.published_at else article.created_at.strftime('%b %d, %Y'),
                    'category': article.category.name if article.category else _("General"),
                    'slug': article.slug
                })
        else:
            news_headlines = [
                {
                    'title': _("DNMG Installs New Automated Weather Stations in Ermera"),
                    'summary': _("To strengthen micro-climate monitoring and support local coffee growers, three new high-precision automated stations were successfully deployed."),
                    'date': "July 19, 2026",
                    'category': _("Infrastructure")
                },
                {
                    'title': _("Timor-Leste Weather Forum Focuses on El Niño Mitigation"),
                    'summary': _("National climate scientists and agriculture experts met in Dili to address water resource management policies ahead of the dry season."),
                    'date': "July 15, 2026",
                    'category': _("Climate")
                }
            ]
        context['news_headlines'] = news_headlines

        # 5. Bulletins
        db_bulletins = OfficialBulletin.objects.all().order_by('-publication_date')[:5]
        bulletins = []
        if db_bulletins.exists():
            for b in db_bulletins:
                bulletins.append({
                    'title': b.title,
                    'date': b.publication_date.strftime('%b %d, %Y'),
                    'type': b.get_bulletin_type_display(),
                    'file_url': b.pdf_file.url if media_available(b.pdf_file) else None,
                    'slug': b.slug,
                })
        else:
            bulletins = [
                {'title': _("Monthly Climate Outlook - July 2026"), 'date': "July 01, 2026", 'type': "PDF"},
                {'title': _("Marine Bulletin for Coastal Shipping"), 'date': "July 21, 2026", 'type': "PDF"},
                {'title': _("Daily Meteorological Analysis"), 'date': "July 21, 2026", 'type': "PDF"},
            ]
        context['bulletins'] = bulletins

        return context


class MediaUnavailableView(View):
    """Friendly response used when a requested uploaded file is no longer stored."""

    def get(self, request, *args, **kwargs):
        return render(request, 'core/media_unavailable.html', status=404)


class MediaFileView(View):
    """Development media serving with a user-facing response for missing files."""

    private_media_prefixes = ('hr/documents/', 'hr/downloads/')

    def get(self, request, path):
        # Match the production Nginx deny rules so local development never
        # accidentally trains users to access confidential HR files by URL.
        if path.startswith(self.private_media_prefixes):
            return MediaUnavailableView().get(request)
        try:
            if path and default_storage.exists(path):
                return FileResponse(default_storage.open(path, 'rb'))
        except Exception:
            pass
        return MediaUnavailableView().get(request)


class AboutDNMGView(TemplateView):
    template_name = 'core/about_dnmg.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('About DNMG')
        return context


class DNMGStructureView(TemplateView):
    template_name = 'core/dnmg_structure.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('DNMG Structure')
        departments = list(
            Department.objects.filter(is_active=True)
            .select_related('head')
            .prefetch_related(Prefetch('sections', queryset=DepartmentSection.objects.filter(is_active=True).order_by('order', 'name')))
            .order_by('name')
        )

        # This fallback keeps the public chart useful before HR data is entered.
        # It is intentionally isolated here so an API-backed source can replace it later.
        if not departments:
            departments = [
                {
                    'name': _('Meteorology and Climate Department'),
                    'code': 'METCLIM',
                    'description': _('Temporary placeholder department.'),
                    'head': None,
                },
                {
                    'name': _('Geophysics Department'),
                    'code': 'GEO',
                    'description': _('Temporary placeholder department.'),
                    'head': None,
                },
                {
                    'name': _('Support Services Department'),
                    'code': 'SUPPORT',
                    'description': _('Temporary placeholder department.'),
                    'head': None,
                },
            ]
            context['structure_uses_mock_data'] = True
        else:
            context['structure_uses_mock_data'] = False

        context['departments'] = departments
        return context
