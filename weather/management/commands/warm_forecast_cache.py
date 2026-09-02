from django.core.management.base import BaseCommand, CommandError

from weather.services import DNMG10DayForecastService, METNorwayForecastService


class Command(BaseCommand):
    help = 'Refresh the cached public ECMWF rainfall forecast without serving a web request.'

    def handle(self, *args, **options):
        forecast = DNMG10DayForecastService.fetch_forecast(variable='tp', model='ECMWF-IFS')
        if forecast is None:
            raise CommandError('The forecast API returned no data and no stale cache is available.')
        municipality_forecast = METNorwayForecastService.fetch_municipality_forecast()
        if not municipality_forecast:
            self.stderr.write('MET Norway municipality forecast is currently unavailable.')
        self.stdout.write(self.style.SUCCESS('Forecast caches are warm.'))
