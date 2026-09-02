"""Validated query state for seismic data-source requests."""

from dataclasses import dataclass
from datetime import date, timedelta

from django.utils import timezone
from django.utils.dateparse import parse_date


class SeismicQueryError(ValueError):
    pass


@dataclass(frozen=True)
class EarthquakeQuery:
    scope: str
    start_date: date
    end_date: date

    SCOPES = frozenset({"timor-leste", "global"})
    MAX_RANGE_DAYS = 90

    @classmethod
    def defaults(cls):
        end_date = timezone.localdate()
        return end_date - timedelta(days=6), end_date

    @classmethod
    def from_request(cls, request):
        scope = request.GET.get("scope", "timor-leste")
        if scope not in cls.SCOPES:
            raise SeismicQueryError("Unknown earthquake scope.")
        default_start, default_end = cls.defaults()
        raw_start, raw_end = request.GET.get("start_date", ""), request.GET.get("end_date", "")
        start_date = parse_date(raw_start) if raw_start else default_start
        end_date = parse_date(raw_end) if raw_end else default_end
        if start_date is None or end_date is None:
            raise SeismicQueryError("Dates must use the YYYY-MM-DD format.")
        if start_date > end_date:
            raise SeismicQueryError("The start date must be before the end date.")
        if end_date - start_date > timedelta(days=cls.MAX_RANGE_DAYS):
            raise SeismicQueryError("Choose a date range of 90 days or fewer.")
        return cls(scope=scope, start_date=start_date, end_date=end_date)
