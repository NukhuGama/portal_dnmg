from datetime import timedelta

from django.views.generic import ListView, CreateView, UpdateView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.http import JsonResponse
from django.views.generic import TemplateView
from django.db.models import Q
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from .models import WeatherStation, WeatherObservation, WeatherForecast, EarlyWarning, Municipality
from .forms import WeatherStationForm, WeatherObservationForm, WeatherForecastForm, EarlyWarningForm
from .permissions import (
    TechnicalStaffRequiredMixin,
    EarlyWarningViewRequiredMixin,
    EarlyWarningCreateRequiredMixin,
    EarlyWarningEditRequiredMixin,
)


# Weather Station Management Views
class WeatherStationListView(TechnicalStaffRequiredMixin, ListView):
    permission_code = 'weather_stations.view'
    model = WeatherStation
    template_name = 'weather/station_list.html'
    context_object_name = 'stations'
    paginate_by = 15

    def get_queryset(self):
        queryset = WeatherStation.objects.all().order_by('name')
        q = self.request.GET.get('q')
        if q:
            queryset = queryset.filter(
                Q(name__icontains=q) |
                Q(code__icontains=q)
            )
        st_type = self.request.GET.get('station_type')
        if st_type:
            queryset = queryset.filter(station_type=st_type)
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        municipality = self.request.GET.get('municipality')
        if municipality:
            queryset = queryset.filter(municipality=municipality)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['station_type_choices'] = WeatherStation.StationType.choices
        context['status_choices'] = WeatherStation.Status.choices
        context['municipality_choices'] = Municipality.choices
        context['selected_type'] = self.request.GET.get('station_type', '')
        context['selected_status'] = self.request.GET.get('status', '')
        context['selected_municipality'] = self.request.GET.get('municipality', '')
        context['search_query'] = self.request.GET.get('q', '')
        return context


class WeatherStationCreateView(TechnicalStaffRequiredMixin, CreateView):
    permission_code = 'weather_stations.create'
    model = WeatherStation
    form_class = WeatherStationForm
    template_name = 'weather/station_form.html'
    success_url = reverse_lazy('weather:station_list')

    def form_valid(self, form):
        messages.success(self.request, _(f"Weather station '{form.cleaned_data['name']}' was created successfully."))
        return super().form_valid(form)


class WeatherStationUpdateView(TechnicalStaffRequiredMixin, UpdateView):
    permission_code = 'weather_stations.edit'
    model = WeatherStation
    form_class = WeatherStationForm
    template_name = 'weather/station_form.html'
    success_url = reverse_lazy('weather:station_list')

    def form_valid(self, form):
        messages.success(self.request, _(f"Weather station '{form.cleaned_data['name']}' was updated successfully."))
        return super().form_valid(form)


# Weather Observations Views
class WeatherObservationListView(TechnicalStaffRequiredMixin, ListView):
    permission_code = 'observations.view'
    model = WeatherObservation
    template_name = 'weather/observation_list.html'
    context_object_name = 'observations'
    paginate_by = 20

    def get_queryset(self):
        queryset = WeatherObservation.objects.select_related('station', 'recorded_by').all().order_by('-recorded_at')
        q = self.request.GET.get('q')
        if q:
            queryset = queryset.filter(
                Q(station__name__icontains=q) |
                Q(station__code__icontains=q) |
                Q(condition_text__icontains=q) |
                Q(recorded_by__username__icontains=q) |
                Q(recorded_by__first_name__icontains=q) |
                Q(recorded_by__last_name__icontains=q)
            )
        station_id = self.request.GET.get('station')
        if station_id:
            queryset = queryset.filter(station_id=station_id)
        date_from = self.request.GET.get('date_from')
        if date_from:
            queryset = queryset.filter(recorded_at__date__gte=date_from)
        date_to = self.request.GET.get('date_to')
        if date_to:
            queryset = queryset.filter(recorded_at__date__lte=date_to)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['stations'] = WeatherStation.objects.all().order_by('name')
        context['selected_station'] = self.request.GET.get('station', '')
        context['date_from'] = self.request.GET.get('date_from', '')
        context['date_to'] = self.request.GET.get('date_to', '')
        context['search_query'] = self.request.GET.get('q', '')
        return context


class WeatherObservationCreateView(TechnicalStaffRequiredMixin, CreateView):
    permission_code = 'observations.create'
    model = WeatherObservation
    form_class = WeatherObservationForm
    template_name = 'weather/observation_form.html'
    success_url = reverse_lazy('weather:observation_list')

    def form_valid(self, form):
        form.instance.recorded_by = self.request.user
        messages.success(self.request, _("New weather observation recorded successfully."))
        return super().form_valid(form)


# Weather Forecast Views
class WeatherForecastListView(TechnicalStaffRequiredMixin, ListView):
    permission_code = 'forecasts.view'
    model = WeatherForecast
    template_name = 'weather/forecast_list.html'
    context_object_name = 'forecasts'
    paginate_by = 15

    def get_queryset(self):
        queryset = WeatherForecast.objects.select_related('issued_by').all().order_by('-forecast_date')
        q = self.request.GET.get('q')
        if q:
            queryset = queryset.filter(
                Q(condition__icontains=q) |
                Q(notes__icontains=q) |
                Q(issued_by__username__icontains=q)
            )
        municipality = self.request.GET.get('municipality')
        if municipality:
            queryset = queryset.filter(municipality=municipality)
        date_from = self.request.GET.get('date_from')
        if date_from:
            queryset = queryset.filter(forecast_date__gte=date_from)
        date_to = self.request.GET.get('date_to')
        if date_to:
            queryset = queryset.filter(forecast_date__lte=date_to)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['municipality_choices'] = Municipality.choices
        context['selected_municipality'] = self.request.GET.get('municipality', '')
        context['date_from'] = self.request.GET.get('date_from', '')
        context['date_to'] = self.request.GET.get('date_to', '')
        context['search_query'] = self.request.GET.get('q', '')
        return context


class WeatherForecastCreateView(TechnicalStaffRequiredMixin, CreateView):
    permission_code = 'forecasts.create'
    model = WeatherForecast
    form_class = WeatherForecastForm
    template_name = 'weather/forecast_form.html'
    success_url = reverse_lazy('weather:forecast_list')

    def form_valid(self, form):
        form.instance.issued_by = self.request.user
        messages.success(self.request, _(f"Forecast for {form.cleaned_data['municipality']} was published."))
        return super().form_valid(form)


class WeatherForecastUpdateView(TechnicalStaffRequiredMixin, UpdateView):
    permission_code = 'forecasts.edit'
    model = WeatherForecast
    form_class = WeatherForecastForm
    template_name = 'weather/forecast_form.html'
    success_url = reverse_lazy('weather:forecast_list')

    def form_valid(self, form):
        messages.success(self.request, _("Forecast details updated."))
        return super().form_valid(form)


# Early Warning Management Views
class EarlyWarningListView(EarlyWarningViewRequiredMixin, ListView):
    model = EarlyWarning
    template_name = 'weather/warning_list.html'
    context_object_name = 'warnings'
    paginate_by = 15

    def get_queryset(self):
        queryset = EarlyWarning.objects.select_related('issued_by').all().order_by('-created_at')
        q = self.request.GET.get('q')
        if q:
            queryset = queryset.filter(
                Q(title__icontains=q) |
                Q(description__icontains=q) |
                Q(region__icontains=q)
            )
        severity = self.request.GET.get('severity')
        if severity:
            queryset = queryset.filter(severity=severity)
        is_active = self.request.GET.get('is_active')
        if is_active in ['1', 'true', 'True']:
            queryset = queryset.filter(is_active=True)
        elif is_active in ['0', 'false', 'False']:
            queryset = queryset.filter(is_active=False)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['severity_choices'] = EarlyWarning.Severity.choices
        context['selected_severity'] = self.request.GET.get('severity', '')
        context['selected_active'] = self.request.GET.get('is_active', '')
        context['search_query'] = self.request.GET.get('q', '')
        return context


class EarlyWarningCreateView(EarlyWarningCreateRequiredMixin, CreateView):
    model = EarlyWarning
    form_class = EarlyWarningForm
    template_name = 'weather/warning_form.html'
    success_url = reverse_lazy('weather:warning_list')

    def get_initial(self):
        initial = super().get_initial()
        current_time = timezone.localtime().replace(second=0, microsecond=0)
        initial.update({"valid_from": current_time, "valid_to": current_time + timedelta(hours=24)})
        return initial

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if not self.request.user.has_portal_permission('early_warnings.publish'):
            form.fields['is_active'].initial = False
            form.fields['is_active'].disabled = True
        return form

    def form_valid(self, form):
        if form.cleaned_data['is_active'] and not self.request.user.has_portal_permission('early_warnings.publish'):
            form.add_error('is_active', _("You need permission to publish an alert. Create it as inactive, or ask an administrator for publish access."))
            return self.form_invalid(form)
        form.instance.issued_by = self.request.user
        current_time = timezone.now()
        if form.cleaned_data['is_active'] and form.cleaned_data['valid_from'] <= current_time <= form.cleaned_data['valid_to']:
            messages.success(self.request, _(f"Early Warning '{form.cleaned_data['title']}' is now live on the public website."))
        else:
            messages.success(self.request, _(f"Early Warning '{form.cleaned_data['title']}' was saved. It will be public only during its valid period."))
        return super().form_valid(form)


class EarlyWarningUpdateView(EarlyWarningEditRequiredMixin, UpdateView):
    model = EarlyWarning
    form_class = EarlyWarningForm
    template_name = 'weather/warning_form.html'
    success_url = reverse_lazy('weather:warning_list')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        required_permission = 'early_warnings.archive' if self.object.is_active else 'early_warnings.publish'
        if not self.request.user.has_portal_permission(required_permission):
            form.fields['is_active'].disabled = True
        return form

    def form_valid(self, form):
        if form.cleaned_data['is_active'] != self.object.is_active:
            permission = 'early_warnings.publish' if form.cleaned_data['is_active'] else 'early_warnings.archive'
            if not self.request.user.has_portal_permission(permission):
                raise PermissionDenied(_("You do not have permission to change this alert's publication status."))
        messages.success(self.request, _(f"Early Warning '{form.cleaned_data['title']}' updated."))
        return super().form_valid(form)


class EarlyWarningToggleActiveView(EarlyWarningViewRequiredMixin, View):
    def dispatch(self, request, *args, **kwargs):
        warning = get_object_or_404(EarlyWarning, pk=kwargs['pk'])
        self.permission_code = 'early_warnings.archive' if warning.is_active else 'early_warnings.publish'
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, pk, *args, **kwargs):
        warning = get_object_or_404(EarlyWarning, pk=pk)
        warning.is_active = not warning.is_active
        warning.save()
        status_text = _("activated") if warning.is_active else _("deactivated / archived")
        messages.success(request, _(f"Early Warning status was {status_text}."))
        return redirect('weather:warning_list')


# Live Station API and GIS Interactive Map Views
class LiveStationGeoJSONView(View):
    """
    Public API endpoint serving live station telemetry, 24h status, coordinates, 
    and time-series chart data for Leaflet GIS.
    """
    def get(self, request, *args, **kwargs):
        from django.utils.timezone import now, localtime
        from datetime import timedelta

        # Synchronization is performed by the dedicated background container.
        # This public request must only read the last stored PostgreSQL snapshot.
        from .services import DNMGStationSyncService

        stations = WeatherStation.objects.all().select_related()
        features = []
        current_time = now()

        for station in stations:
            # The public portal and staff dashboard share this snapshot, including
            # the complete rolling 24-hour observation history.
            snapshot = DNMGStationSyncService.get_station_snapshot(station, current_time)
            latest_obs = snapshot['obs']
            recent_obs_qs = snapshot['observations_24h']

            # 24-hour Online / Offline logic as requested
            is_online = snapshot['is_online']
            last_seen_formatted = "No Data"
            if latest_obs and latest_obs.recorded_at:
                time_diff = current_time - latest_obs.recorded_at
                local_recorded_at = localtime(latest_obs.recorded_at)
                if time_diff <= timedelta(hours=24):
                    is_online = True
                    last_seen_formatted = f"Online • Updated {local_recorded_at.strftime('%H:%M, %b %d')} (GMT+9)"
                else:
                    is_online = False
                    last_seen_formatted = f"Offline • Last data: {local_recorded_at.strftime('%b %d, %Y %H:%M')} (GMT+9)"

            obs_data = None
            history_data = {
                "timestamps": [],
                "temp": [],
                "pressure": [],
                "peak_period": [],
                "humidity": [],
                "tide": [],
                "wave": []
            }

            if latest_obs:
                local_latest = localtime(latest_obs.recorded_at)
                obs_data = {
                    "temp": float(latest_obs.temperature) if latest_obs.temperature is not None else None,
                    "humidity": latest_obs.humidity,
                    "rainfall": float(latest_obs.rainfall_mm) if latest_obs.rainfall_mm is not None else None,
                    "wind_speed": float(latest_obs.wind_speed_kmh) if latest_obs.wind_speed_kmh is not None else None,
                    "wind_direction": latest_obs.wind_direction or "",
                    "pressure": float(latest_obs.pressure_hpa) if latest_obs.pressure_hpa is not None else None,
                    "wave_height": float(latest_obs.wave_height_m) if latest_obs.wave_height_m is not None else None,
                    "tide_level": float(latest_obs.tide_level_mm) if latest_obs.tide_level_mm is not None else None,
                    "peak_period": float(latest_obs.peak_period_s) if latest_obs.peak_period_s is not None else None,
                    "solar_radiation": float(latest_obs.solar_radiation) if latest_obs.solar_radiation is not None else None,
                    "wind_gust": float(latest_obs.wind_gust_kmh) if latest_obs.wind_gust_kmh is not None else None,
                    "sea_surface_temp": float(latest_obs.sea_surface_temp) if latest_obs.sea_surface_temp is not None else None,
                    "battery_voltage": float(latest_obs.battery_voltage) if latest_obs.battery_voltage is not None else None,
                    "condition": latest_obs.condition_text or ("Online" if is_online else "Offline"),
                    "recorded_at": local_latest.isoformat() if latest_obs.recorded_at else None,
                    "recorded_at_formatted": local_latest.strftime('%b %d, %H:%M (GMT+9)') if latest_obs.recorded_at else None,
                }

                # AWS stations sometimes report at irregular times. Preserve
                # those actual timestamps instead of dropping the observations
                # solely because they do not fall on a 30-minute boundary.
                preserve_irregular_aws = station.station_type == WeatherStation.StationType.AWS
                regular_chart_observations = DNMGStationSyncService.get_chart_observations(
                    recent_obs_qs,
                    30,
                )
                chart_observations = DNMGStationSyncService.get_chart_observations(
                    recent_obs_qs,
                    30,
                    include_irregular=preserve_irregular_aws,
                )
                uses_actual_timestamps = preserve_irregular_aws and (
                    len(chart_observations) != len(regular_chart_observations)
                )
                for loc_ob_time, ob in chart_observations:
                    history_data["timestamps"].append(loc_ob_time.strftime('%b %d %H:%M'))
                    history_data["temp"].append(float(ob.temperature) if ob.temperature is not None else None)
                    history_data["pressure"].append(float(ob.pressure_hpa) if ob.pressure_hpa is not None else None)
                    history_data["peak_period"].append(float(ob.peak_period_s) if ob.peak_period_s is not None else None)
                    history_data["humidity"].append(ob.humidity)
                    history_data["tide"].append(float(ob.tide_level_mm) if ob.tide_level_mm is not None else None)
                    history_data["wave"].append(float(ob.wave_height_m) if ob.wave_height_m is not None else None)
            else:
                uses_actual_timestamps = False

            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(station.longitude), float(station.latitude)]
                },
                "properties": {
                    "id": station.id,
                    "external_id": station.external_id or station.code,
                    "name": station.name,
                    "code": station.code,
                    "station_type": station.station_type,
                    "station_type_display": station.get_station_type_display(),
                    "municipality": station.municipality,
                    "municipality_display": station.get_municipality_display(),
                    "elevation": float(station.elevation) if station.elevation is not None else 0.0,
                    "latitude": float(station.latitude),
                    "longitude": float(station.longitude),
                    "is_online": is_online,
                    "online_status": "ONLINE" if is_online else "OFFLINE",
                    "status_display": _("ONLINE") if is_online else _("OFFLINE"),
                    "last_seen_formatted": last_seen_formatted,
                    "observation": obs_data,
                    "history": history_data,
                    "history_interval_minutes": 30,
                    "history_uses_actual_timestamps": uses_actual_timestamps,
                }
            }
            features.append(feature)

        geojson = {
            "type": "FeatureCollection",
            "features": features
        }
        return JsonResponse(geojson)


class InteractiveMapView(TemplateView):
    template_name = 'weather/interactive_map.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _("Live Weather Observations Map")
        context['map_mode'] = 'observations'
        context['stations_count'] = WeatherStation.objects.count()
        context['active_warnings'] = EarlyWarning.objects.currently_public()
        return context


class ForecastMapView(InteractiveMapView):
    """Dedicated public map for ECMWF forecast data, isolated from live observations."""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _("10-Day ECMWF Forecast Map")
        context['map_mode'] = 'forecast'
        return context


class StationSyncAPIView(TechnicalStaffRequiredMixin, View):
    permission_code = 'weather_stations.manage_configuration'
    """
    Triggers live synchronization of all 15 stations with ms-obs.dnmg.gov.tl API.
    """
    def post(self, request, *args, **kwargs):
        from .services import DNMGStationSyncService
        results = DNMGStationSyncService.sync_all_stations(force=True)
        synced_count = sum(1 for r in results if r.get("status") == "synced")
        messages.success(request, _(f"Successfully synchronized {synced_count}/15 stations with live DNMG API."))
        return JsonResponse({
            "status": "success",
            "synced_count": synced_count,
            "total": len(results),
            "results": results
        })


class TenDayForecastGeoJSONView(View):
    """
    Public API endpoint returning Timor-Leste administrative municipality polygons
    merged with 10-day ECMWF forecast telemetry & color-coded alert levels from ms-api.dnmg.gov.tl.
    """
    def get(self, request, *args, **kwargs):
        import os, json, unicodedata
        from django.conf import settings
        from django.utils.dateparse import parse_datetime
        from .services import DNMG10DayForecastService

        variable = request.GET.get('variable', 'tp')
        model = request.GET.get('model', 'ECMWF-IFS')
        var_meta = DNMG10DayForecastService.VARIABLE_META.get(variable, DNMG10DayForecastService.VARIABLE_META['tp'])

        # Load Timor-Leste Municipal GeoJSON boundaries
        geojson_path = os.path.join(settings.BASE_DIR, 'static', 'geojson', 'timor_leste_municipalities.json')
        if not os.path.exists(geojson_path):
            return JsonResponse({"type": "FeatureCollection", "features": []})

        with open(geojson_path, 'r', encoding='utf-8') as f:
            base_geojson = json.load(f)

        # Fetch 10-day forecast dataset from ms-api.dnmg.gov.tl
        forecast_data = DNMG10DayForecastService.fetch_forecast(variable=variable, model=model) or {}

        def norm_name(s):
            if not s:
                return ""
            s = unicodedata.normalize('NFD', str(s)).encode('ascii', 'ignore').decode('utf-8').lower()
            s = s.replace(' ', '').replace('-', '')
            if 'cova' in s: return 'covalima'
            if 'oecus' in s or ('oe' in s and 'cus' in s): return 'oecusse'
            return s

        # Build map of normalized API name -> forecast days array
        api_map = {}
        for muni_name, days in forecast_data.items():
            if isinstance(days, list):
                api_map[norm_name(muni_name)] = (muni_name, days)

        out_features = []
        for feature in base_geojson.get('features', []):
            props = dict(feature.get('properties', {}))
            shape_name = props.get('shapeName', '')
            norm_shape = norm_name(shape_name)

            matched_entry = api_map.get(norm_shape)
            forecast_days_formatted = []

            if matched_entry:
                _, raw_days = matched_entry
                for idx, d in enumerate(raw_days[:10]):   # hard-limit to 10 days
                    p_start = d.get('period_start', '')
                    p_end = d.get('period_end', '')

                    # Date formatting
                    dt_obj = parse_datetime(p_start) if p_start else None
                    date_label = dt_obj.strftime('%b %d') if dt_obj else f"Day {idx + 1}"

                    color_arr = d.get('color', [])
                    color_code = color_arr[0] if isinstance(color_arr, list) and len(color_arr) > 0 else "#94CB55"
                    alert_level = color_arr[1] if isinstance(color_arr, list) and len(color_arr) > 1 else "Normal"

                    forecast_days_formatted.append({
                        "day_index": idx + 1,
                        "date_label": date_label,
                        "period_start": p_start,
                        "period_end": p_end,
                        "aggregate_value": d.get('aggregate_value'),
                        "color_code": color_code,
                        "alert_level": alert_level,
                    })

            props.update({
                "municipality_name": shape_name,
                "variable": variable,
                "variable_name": var_meta['name'],
                "unit": var_meta['unit'],
                "icon": var_meta['icon'],
                "forecast_days": forecast_days_formatted
            })

            out_features.append({
                "type": "Feature",
                "properties": props,
                "geometry": feature.get('geometry')
            })

        return JsonResponse({
            "type": "FeatureCollection",
            "features": out_features,
            "variable": variable,
            "variable_name": var_meta['name'],
            "unit": var_meta['unit'],
            "model": model,
        })
