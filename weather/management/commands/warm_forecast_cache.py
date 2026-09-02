from django.core.management.base import BaseCommand, CommandError

from weather.services import DNMG10DayForecastService


class Command(BaseCommand):
    help = 'Refresh the cached public ECMWF rainfall forecast without serving a web request.'

    def handle(self, *args, **options):
        forecast = DNMG10DayForecastService.fetch_forecast(variable='tp', model='ECMWF-IFS')
        if forecast is None:
            raise CommandError('The forecast API returned no data and no stale cache is available.')
        self.stdout.write(self.style.SUCCESS('Forecast cache is warm.'))
