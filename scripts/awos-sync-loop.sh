#!/bin/sh
set -eu

interval="${AWOS_SYNC_INTERVAL_SECONDS:-300}"
health_file="/tmp/dnmg-last-successful-awos-sync"

case "$interval" in
    *[!0-9]*|'')
        echo "AWOS_SYNC_INTERVAL_SECONDS must be a positive integer; got: $interval" >&2
        exit 1
        ;;
esac

if [ "$interval" -eq 0 ]; then
    echo "AWOS_SYNC_INTERVAL_SECONDS must be greater than zero." >&2
    exit 1
fi

trap 'exit 0' TERM INT

while :; do
    date -u '+%Y-%m-%dT%H:%M:%SZ starting Dili AWOS synchronization'
    if python manage.py sync_awos_dili; then
        touch "$health_file"
    else
        echo "Dili AWOS synchronization failed; the next scheduled attempt will still run." >&2
    fi

    sleep "$interval" &
    wait $!
done
