(() => {
    const refreshInterval = 60_000;

    const updateField = (dashboard, name, value) => {
        dashboard.querySelectorAll(`[data-awos-field="${name}"]`).forEach((element) => {
            element.textContent = value;
        });
    };

    const updateTimestamps = (dashboard, observation, metar) => {
        dashboard.querySelectorAll('[data-awos-datetime]').forEach((element) => {
            const timestamp = element.dataset.awosDatetimeSource === 'metar'
                ? metar.reported_at
                : observation.recorded_at;
            element.dateTime = timestamp || '';
        });
    };

    const refreshDashboard = async (dashboard) => {
        if (document.hidden) return;

        try {
            const response = await fetch(dashboard.dataset.awosLiveUrl, {
                headers: { Accept: 'application/json' },
                cache: 'no-store',
            });
            if (!response.ok) throw new Error('AWOS data is unavailable');

            const payload = await response.json();
            if (!payload.available) throw new Error('AWOS data is unavailable');

            Object.entries(payload.observation).forEach(([name, value]) => {
                if (name !== 'recorded_at') {
                    updateField(dashboard, name, value);
                }
            });
            updateTimestamps(dashboard, payload.observation, payload.metar);

            const hasMetar = Boolean(payload.metar.raw_report);
            updateField(dashboard, 'metar_utc_display', payload.metar.utc_display || '');
            updateField(dashboard, 'metar_local_display', payload.metar.local_display || '');
            updateField(
                dashboard,
                'metar_raw_report',
                payload.metar.raw_report || dashboard.dataset.awosEmptyMetar,
            );
            dashboard.querySelectorAll('[data-awos-field="metar_raw_report"]').forEach((element) => {
                element.classList.toggle('airport-awos-metar__empty', !hasMetar);
            });
            dashboard.classList.remove('airport-awos-dashboard--stale');
        } catch (error) {
            // Keep the last verified reading visible while a refresh is delayed.
            dashboard.classList.add('airport-awos-dashboard--stale');
        }
    };

    document.querySelectorAll('[data-awos-auto-refresh]').forEach((dashboard) => {
        if (!dashboard.dataset.awosLiveUrl) return;

        refreshDashboard(dashboard);
        window.setInterval(() => refreshDashboard(dashboard), refreshInterval);
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden) refreshDashboard(dashboard);
        });
    });
})();
