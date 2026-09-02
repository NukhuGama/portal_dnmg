"""Presentation metadata for public service landing pages.

Keeping this catalog separate from the view makes service names, sections, and
airport metadata easy to review without mixing them with request handling.
"""

from django.utils.translation import gettext_lazy as _


def _section(section_id, title):
    """Build a service section with a stable, language-independent anchor."""
    return {'id': section_id, 'title': title}


SERVICE_LANDINGS = {
    'climate': {
        'title': _('Climate'),
        'icon': 'bi-thermometer-sun',
        'description': _(
            'Climate monitoring, historical records, outlooks, and reports '
            'for Timor-Leste.'
        ),
        'sections': [
            _section('climate-monitoring', _('Climate Monitoring')),
            _section('historical-climate', _('Historical Climate')),
            _section('climate-data', _('Climate Data')),
            _section('seasonal-outlooks', _('Seasonal Outlooks')),
            _section('climate-reports', _('Climate Reports')),
            _section(
                'climate-change-information',
                _('Climate Change Information'),
            ),
            _section('climate-bulletins', _('Climate Bulletins')),
        ],
    },
    'air-quality': {
        'title': _('Air Quality'),
        'icon': 'bi-lungs',
        'description': _(
            'Air-quality information and health guidance will be published '
            'here when DNMG monitoring data is connected.'
        ),
        'sections': [
            _section('current-air-quality', _('Current Air Quality')),
            _section('aqi-map', _('AQI Map')),
            _section('monitoring-stations', _('Monitoring Stations')),
            _section('main-pollutants', _('Main Pollutants')),
            _section('health-advice', _('Health Advice')),
            _section('air-quality-forecast', _('Air-Quality Forecast')),
            _section('historical-air-quality', _('Historical Air Quality')),
            _section('air-quality-reports', _('Air-Quality Reports')),
        ],
    },
    'marine': {
        'title': _('Marine'),
        'icon': 'bi-water',
        'description': _(
            'Marine and coastal weather services, including wind, waves, '
            'tides, warnings, and official bulletins.'
        ),
        'sections': [
            _section('marine-forecast', _('Marine Forecast')),
            _section('coastal-forecast', _('Coastal Forecast')),
            _section('ocean-conditions', _('Ocean Conditions')),
            _section('wave-forecast', _('Wave Forecast')),
            _section('wind-forecast', _('Wind Forecast')),
            _section('tide-information', _('Tide Information')),
            _section('marine-warnings', _('Marine Warnings')),
            _section('marine-bulletins', _('Marine Bulletins')),
        ],
    },
    'aviation': {
        'title': _('Aviation'),
        'icon': 'bi-airplane-engines',
        'description': _(
            'Aviation meteorological products for airport operations and '
            'flight planning.'
        ),
        'airports': [
            {
                'id': 'airport-dili',
                'slug': 'dili',
                'name': _('Dili Airport'),
                'official_name': _(
                    'Presidente Nicolau Lobato International Airport'),
                'location': _('Dili'),
            },
            {
                'id': 'airport-suai',
                'slug': 'suai',
                'name': _('Suai Airport'),
                'official_name': _(
                    'Kay Rala Xanana Gusmão International Airport'
                ),
                'location': _('Suai'),
            },
            {
                'id': 'airport-oecusse',
                'slug': 'oecusse',
                'name': _('Oecusse Airport'),
                'official_name': _('Rota do Sândalo International Airport'),
                'location': _('Oecusse'),
            },
        ],
        'sections': [
            _section('airport-weather', _('Airport Weather')),
            _section('airport-observations', _('Airport Observations')),
            _section('metar', _('METAR')),
            _section('taf', _('TAF')),
            _section('visibility', _('Visibility')),
            _section('wind-conditions', _('Wind Conditions')),
            _section('aviation-warnings', _('Aviation Warnings')),
            _section(
                'aviation-weather-reports',
                _('Aviation Weather Reports'),
            ),
        ],
    },
    'data-maps': {
        'title': _('Data & Maps'),
        'icon': 'bi-map',
        'description': _(
            'Discover DNMG maps, observations, datasets, publications, and '
            'technical data services.'
        ),
        'sections': [
            _section('interactive-gis-map', _('Interactive GIS Map')),
            _section('live-station-data', _('Live Station Data')),
            _section('weather-observations', _('Weather Observations')),
            _section('forecast-map-data', _('Forecast Map Data')),
            _section('climate-data', _('Climate Data')),
            _section('air-quality-data', _('Air-Quality Data')),
            _section('seismic-data', _('Seismic Data')),
            _section('downloads', _('Downloads')),
            _section('reports-publications', _('Reports & Publications')),
            _section('dataapi-information', _('Data/API Information')),
        ],
    },
}
