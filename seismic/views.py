from django.http import JsonResponse
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView, View

from .classification import RECENT_EVENT_HOURS, RISK_LEVELS
from .filters import EarthquakeQuery, SeismicQueryError
from .services import EarthquakeServiceError, USGSEarthquakeService
from .summaries import build_home_summary


class EarthquakeExplorerView(TemplateView):
    """Public seismic event map, filters, statistics and event table."""

    template_name = "seismic/earthquakes.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        start_date, end_date = EarthquakeQuery.defaults()
        context.update({
            "title": _("Earthquake Activity"),
            "default_start_date": start_date.isoformat(),
            "default_end_date": end_date.isoformat(),
            "risk_levels": RISK_LEVELS,
            "recent_event_hours": RECENT_EVENT_HOURS,
        })
        return context


class EarthquakeGeoJSONView(View):
    """Validated seismic API endpoint backed by the selected data provider."""

    def get(self, request, *args, **kwargs):
        try:
            query = EarthquakeQuery.from_request(request)
            return JsonResponse(USGSEarthquakeService.fetch(query.scope, query.start_date, query.end_date))
        except SeismicQueryError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        except EarthquakeServiceError as exc:
            return JsonResponse({"error": str(exc)}, status=503)


class EarthquakeHomeSummaryView(View):
    """Compact, asynchronous Home-page projection of nearby activity."""

    def get(self, request, *args, **kwargs):
        start_date, end_date = EarthquakeQuery.defaults()
        try:
            events = USGSEarthquakeService.fetch("timor-leste", start_date, end_date)
            return JsonResponse(build_home_summary(events))
        except EarthquakeServiceError as exc:
            return JsonResponse({"error": str(exc)}, status=503)
