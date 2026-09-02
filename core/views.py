import unicodedata
from datetime import timezone as datetime_timezone

from django.core.files.storage import default_storage
from django.db.models import Prefetch
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import TemplateView

from cms.models import NewsArticle, OfficialBulletin, JobOpening
from hr.models import Department, DepartmentSection
from weather.models import AwosMetarReport, WeatherForecast, WeatherObservation, WeatherStation
from weather.services import AwosDiliSyncService, DNMG10DayForecastService, METNorwayForecastService

from .media import media_available
from .service_catalog import SERVICE_LANDINGS


def awos_number(value, decimal_places):
    """Format optional AWOS numeric data consistently for HTML and JSON."""
    if value is None:
        return '--'
    return f'{value:.{decimal_places}f}'


class HomeView(TemplateView):
    template_name = 'core/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _("Home")
        
        # 1. Network metadata for the public station map preview.
        context['station_count'] = WeatherStation.objects.count()

        context['municipality_conditions'] = METNorwayForecastService.get_cached_forecast()

        # 2. 10-Day ECMWF Forecast. The background sync loop refreshes this
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

        # 3. News Articles
        db_articles = (
            NewsArticle.objects.filter(status=NewsArticle.Status.PUBLISHED)
            .select_related('category')[:3]
        )
        news_headlines = []
        if db_articles.exists():
            for article in db_articles:
                news_headlines.append({
                    'title': article.title,
                    'summary': article.excerpt,
                    'date': (
                        article.published_at.strftime('%b %d, %Y')
                        if article.published_at
                        else article.created_at.strftime('%b %d, %Y')
                    ),
                    'category': article.category.name if article.category else _("General"),
                    'slug': article.slug
                })
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
        context['bulletins'] = bulletins
        context['open_jobs_count'] = JobOpening.objects.filter(status=JobOpening.Status.OPEN).count()

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
            .prefetch_related(Prefetch(
                'sections',
                queryset=DepartmentSection.objects.filter(is_active=True).order_by(
                    'order', 'name'
                ),
            ))
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


class ServiceLandingView(TemplateView):
    """Public service pages backed by verified, stored operational data only."""

    template_name = 'core/service_landing.html'

    services = SERVICE_LANDINGS

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        service = self.services[self.kwargs['service']]
        context.update(service)
        context['service_key'] = self.kwargs['service']
        if context['service_key'] == 'aviation':
            context['airports'] = [
                {
                    **airport,
                    'detail_url': reverse('core:aviation_airport_detail', args=[airport['slug']]),
                }
                for airport in service['airports']
            ]
        return context


class AviationAirportDetailView(TemplateView):
    """Show verified aviation products for one airport without duplicating the directory."""

    template_name = 'core/aviation_airport_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        airport_slug = self.kwargs['airport']
        airport = next(
            (
                item for item in SERVICE_LANDINGS['aviation']['airports']
                if item['slug'] == airport_slug
            ),
            None,
        )
        if airport is None:
            raise Http404('Airport not found.')

        context.update({
            'airport': airport,
            'title': airport['name'],
            'icon': SERVICE_LANDINGS['aviation']['icon'],
            'aviation_directory_url': reverse('core:aviation'),
        })
        if airport_slug == 'dili':
            awos_station = WeatherStation.objects.filter(
                code='WPDL',
                station_type=WeatherStation.StationType.AWOS,
            ).first()
            context['awos_station'] = awos_station
            awos_observation = (
                WeatherObservation.objects.filter(station=awos_station).first()
                if awos_station else None
            )
            context['awos_observation'] = awos_observation
            context['awos_wind_speed_knots'] = AwosDiliSyncService.wind_kmh_to_knots(
                awos_observation.wind_speed_kmh if awos_observation else None,
            )
            context['awos_wind_gust_knots'] = AwosDiliSyncService.wind_kmh_to_knots(
                awos_observation.wind_gust_kmh if awos_observation else None,
            )
            context['awos_metar'] = (
                AwosMetarReport.objects.filter(station=awos_station).first()
                if awos_station else None
            )
        return context


class DiliAwosLiveObservationView(View):
    """Return the latest stored AWOS snapshot for the in-page live display.

    This endpoint reads only portal data.  The browser never connects to the
    AWOS source directly and therefore cannot make page loads depend on that
    operational network connection.
    """

    def get(self, request, *args, **kwargs):
        station = WeatherStation.objects.filter(
            code=AwosDiliSyncService.STATION_CODE,
            station_type=WeatherStation.StationType.AWOS,
        ).first()
        observation = (
            WeatherObservation.objects.filter(station=station).first()
            if station else None
        )
        if observation is None:
            return JsonResponse({'available': False}, status=503)

        metar = AwosMetarReport.objects.filter(station=station).first()
        wind_speed_knots = AwosDiliSyncService.wind_kmh_to_knots(
            observation.wind_speed_kmh,
        )
        wind_gust_knots = AwosDiliSyncService.wind_kmh_to_knots(
            observation.wind_gust_kmh,
        )
        recorded_at_utc = observation.recorded_at.astimezone(datetime_timezone.utc)
        payload = {
            'available': True,
            'observation': {
                'temperature': awos_number(observation.temperature, 1),
                'dew_point': awos_number(observation.dew_point_c, 1),
                'humidity': awos_number(observation.humidity, 0),
                'pressure': awos_number(observation.pressure_hpa, 1),
                'visibility': awos_number(observation.visibility_m, 0),
                'runway_visual_range': awos_number(
                    observation.runway_visual_range_m,
                    0,
                ),
                'wind_speed': awos_number(wind_speed_knots, 1),
                'wind_gust': awos_number(wind_gust_knots, 1),
                'wind_direction': observation.wind_direction or '--',
                'utc_display': recorded_at_utc.strftime('%d %b %Y · %H:%MZ'),
                'local_display': timezone.localtime(observation.recorded_at).strftime(
                    '%d %b %Y · %H:%M UTC+9',
                ),
                'recorded_at': observation.recorded_at.isoformat(),
            },
            'metar': {
                'raw_report': metar.raw_report if metar else '',
                'utc_display': (
                    metar.reported_at.astimezone(datetime_timezone.utc).strftime(
                        '%d %b %H:%MZ',
                    )
                    if metar else ''
                ),
                'local_display': (
                    timezone.localtime(metar.reported_at).strftime(
                        '%d %b %H:%M UTC+9',
                    )
                    if metar else ''
                ),
                'reported_at': metar.reported_at.isoformat() if metar else '',
            },
        }
        response = JsonResponse(payload)
        response['Cache-Control'] = 'no-store'
        return response


class DSSView(TemplateView):
    template_name = 'core/dss.html'
