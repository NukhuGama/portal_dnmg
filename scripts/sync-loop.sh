#!/bin/sh
set -eu

interval="${SYNC_INTERVAL_SECONDS:-300}"
health_file="/tmp/dnmg-last-successful-sync"

case "$interval" in
    *[!0-9]*|'')
        echo "SYNC_INTERVAL_SECONDS must be a positive integer; got: $interval" >&2
        exit 1
        ;;
esac

if [ "$interval" -eq 0 ]; then
    echo "SYNC_INTERVAL_SECONDS must be greater than zero." >&2
    exit 1
fi

trap 'exit 0' TERM INT

while :; do
    date -u '+%Y-%m-%dT%H:%M:%SZ starting live-station synchronization'
    if python manage.py sync_live_stations; then
        touch "$health_file"
    else
        echo "Live-station synchronization failed; the next scheduled attempt will still run." >&2
    fi

    # Public page loads use this cache and never wait for the forecast API.
    # A forecast failure does not hide a successful station synchronization.
    if ! python manage.py warm_forecast_cache; then
        echo "Forecast cache refresh failed; stale forecast data will be used when available." >&2
    fi

    sleep "$interval" &
    wait $!
done
