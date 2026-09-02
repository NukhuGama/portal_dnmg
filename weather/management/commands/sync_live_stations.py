from django.core.management.base import BaseCommand
from weather.services import DNMGStationSyncService

class Command(BaseCommand):
    help = 'Fetches live station telemetry data from DNMG API (ms-obs.dnmg.gov.tl) for all 15 stations.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Starting live DNMG station synchronization..."))
        results = DNMGStationSyncService.sync_all_stations()

        synced_count = sum(1 for r in results if r["status"] == "synced")
        no_data_count = sum(1 for r in results if r["status"] == "no_live_data")
        failed_count = sum(1 for r in results if r["status"] == "failed")
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully processed {synced_count + no_data_count}/{len(results)} stations "
                f"({synced_count} live, {no_data_count} offline/no-data, {failed_count} failed)."
            )
        )
        for res in results:
            label = res['status']
            if label == 'synced':
                self.stdout.write(f"  - [{res['external_id']}] {res['station']}: synced")
            elif label == 'no_live_data':
                self.stdout.write(self.style.WARNING(f"  - [{res['external_id']}] {res['station']}: OFFLINE (no live data)"))
            else:
                self.stdout.write(self.style.ERROR(f"  - [{res['external_id']}] {res['station']}: FAILED"))

