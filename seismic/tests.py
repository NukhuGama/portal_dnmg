from datetime import date
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from .classification import risk_for_magnitude
from .filters import EarthquakeQuery
from .geography import distance_from_timor_leste
from .services import USGSEarthquakeService
from .summaries import build_home_summary


class EarthquakeExplorerTestCase(TestCase):
    def test_explorer_page_uses_seismic_template_and_statistics_components(self):
        response = self.client.get(reverse("seismic:earthquakes"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "seismic/earthquakes.html")
        self.assertContains(response, 'id="seismic_statistics"')
        self.assertContains(response, 'id="seismic_stat_recent"')
        self.assertContains(response, 'id="seismic_magnitude_min"')
        self.assertEqual(response.context["recent_event_hours"], 24)

    def test_api_passes_validated_scope_and_dates_to_usgs_service(self):
        result = {"type": "FeatureCollection", "features": [], "metadata": {"count": 0}}
        with patch.object(USGSEarthquakeService, "fetch", return_value=result) as fetch:
            response = self.client.get(reverse("seismic:api_earthquakes"), {
                "scope": "global", "start_date": "2026-08-01", "end_date": "2026-08-02",
            })

        self.assertEqual(response.status_code, 200)
        fetch.assert_called_once_with("global", date(2026, 8, 1), date(2026, 8, 2))

    def test_api_rejects_invalid_date_range_without_calling_provider(self):
        with patch.object(USGSEarthquakeService, "fetch") as fetch:
            response = self.client.get(reverse("seismic:api_earthquakes"), {
                "start_date": "2026-08-03", "end_date": "2026-08-01",
            })

        self.assertEqual(response.status_code, 400)
        fetch.assert_not_called()

    def test_home_summary_endpoint_uses_nearby_data_and_compact_contract(self):
        result = {
            "features": [{"properties": {"place": "Banda Sea", "magnitude": 5.2, "is_recent": True, "time": "2026-08-17T00:00:00+09:00", "color": "#0d6efd"}}],
            "metadata": {"scope": "timor-leste"},
        }
        with patch.object(EarthquakeQuery, "defaults", return_value=(date(2026, 8, 11), date(2026, 8, 17))), patch.object(USGSEarthquakeService, "fetch", return_value=result) as fetch:
            response = self.client.get(reverse("seismic:home_summary"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["recent_events"], 1)
        self.assertEqual(response.json()["latest_event"]["place"], "Banda Sea")
        self.assertNotIn("is_recent", response.json()["latest_event"])
        fetch.assert_called_once_with("timor-leste", date(2026, 8, 11), date(2026, 8, 17))

    def test_home_summary_prefers_recent_event_and_reports_strongest_magnitude(self):
        summary = build_home_summary({"features": [
            {"properties": {"place": "Older", "magnitude": 6.1, "time": "2026-08-16T00:00:00+09:00", "is_recent": False}},
            {"properties": {"place": "Recent", "magnitude": 4.1, "time": "2026-08-17T00:00:00+09:00", "is_recent": True}},
        ]})

        self.assertEqual(summary["latest_event"]["place"], "Recent")
        self.assertEqual(summary["strongest_magnitude"], 6.1)

    def test_risk_thresholds_and_distance_are_canonical(self):
        self.assertEqual(risk_for_magnitude(3.9)["label"], "Low")
        self.assertEqual(risk_for_magnitude(4.0)["label"], "Moderate")
        self.assertEqual(risk_for_magnitude(5.0)["label"], "High")
        self.assertEqual(risk_for_magnitude(6.0)["label"], "Very High")
        self.assertEqual(risk_for_magnitude(7.0)["label"], "Danger")
        self.assertEqual(distance_from_timor_leste(-8.8742, 125.7275), 0)

    def test_usgs_event_serializer_includes_map_detail_data(self):
        from .serializers import USGSEarthquakeSerializer

        event = USGSEarthquakeSerializer.normalize_feature({
            "id": "us-test-event", "geometry": {"coordinates": [125.7, -8.8, 12.3]},
            "properties": {"mag": 5.1, "magType": "mww", "time": 0, "place": "Test location"},
        })

        self.assertEqual(event["properties"]["latitude"], -8.8)
        self.assertEqual(event["properties"]["depth_km"], 12.3)
        self.assertEqual(event["properties"]["risk_code"], "high")
        self.assertIn("is_recent", event["properties"])
