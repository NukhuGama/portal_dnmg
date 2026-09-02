from django.core.management.base import BaseCommand, CommandError

from weather.services import AwosDiliSyncService


class Command(BaseCommand):
    help = 'Synchronize the selected current WPDL AWOS values and latest METAR report.'

    def handle(self, *args, **options):
        result = AwosDiliSyncService.sync()
        status = result['status']
        if status == 'disabled':
            self.stdout.write(self.style.WARNING('Dili AWOS synchronization is disabled: AWOS credentials are not configured.'))
            return
        if status == 'no_data':
            self.stdout.write(self.style.WARNING('Dili AWOS returned no usable selected values.'))
            return
        if status == 'failed':
            raise CommandError(f"Dili AWOS synchronization failed: {result['reason']}")

        metar_status = 'with METAR' if result['metar'] else 'without a new METAR'
        self.stdout.write(
            self.style.SUCCESS(
                f"Synchronized {result['station'].code} observation {metar_status}; "
                f"removed {result['observations_deleted']} expired observations and "
                f"{result['metar_reports_deleted']} expired METAR reports."
            )
        )
