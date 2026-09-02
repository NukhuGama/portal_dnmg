/* Shared live clock for the public portal navbar. */
(function () {
    'use strict';

    const clockGroups = document.querySelectorAll('[data-live-clocks]');
    const currentDateElements = document.querySelectorAll('[data-current-date]');
    if (!clockGroups.length && !currentDateElements.length) {
        return;
    }

    const formatters = new Map();

    function getFormatter(timeZone, options) {
        const key = `${timeZone}:${JSON.stringify(options)}`;
        if (!formatters.has(key)) {
            formatters.set(key, new Intl.DateTimeFormat(undefined, {
                ...options,
                timeZone,
            }));
        }
        return formatters.get(key);
    }

    function updateClocks() {
        const currentTime = new Date();

        document.querySelectorAll('[data-live-clock]').forEach((clock) => {
            const timeZone = clock.dataset.clockTimezone;
            const timeElement = clock.querySelector('[data-clock-time]');
            if (!timeZone || !timeElement) {
                return;
            }

            try {
                const isCompact = clock.closest('.portal-time-clocks--compact');
                timeElement.textContent = getFormatter(timeZone, {
                    hour: '2-digit',
                    minute: '2-digit',
                    ...(isCompact ? {} : { second: '2-digit' }),
                    hour12: false,
                }).format(currentTime);
                timeElement.dateTime = currentTime.toISOString();
            } catch (error) {
                // Keep the component usable in browsers without timezone support.
                timeElement.textContent = currentTime.toUTCString().slice(17, 25);
            }
        });

        currentDateElements.forEach((dateContainer) => {
            const timeZone = dateContainer.dataset.currentDateTimezone || 'Asia/Dili';
            const dateElement = dateContainer.querySelector('[data-current-date-value]');
            if (!dateElement) {
                return;
            }

            try {
                dateElement.textContent = getFormatter(timeZone, {
                    day: '2-digit',
                    month: 'short',
                    year: 'numeric',
                }).format(currentTime);
                dateElement.dateTime = currentTime.toISOString();
            } catch (error) {
                dateElement.textContent = currentTime.toISOString().slice(0, 10);
            }
        });
    }

    updateClocks();
    window.setInterval(updateClocks, 1000);
})();
