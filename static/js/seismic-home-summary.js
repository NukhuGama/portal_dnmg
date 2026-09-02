/* Asynchronous Home-page summary; detailed interaction remains in seismic.js. */
(function () {
    'use strict';

    class SeismicHomeSummary {
        constructor(element) {
            this.element = element;
            this.apiUrl = element.dataset.apiUrl;
            this.fields = {
                total: element.querySelector('[data-seismic-total]'),
                recent: element.querySelector('[data-seismic-recent]'),
                latest: element.querySelector('[data-seismic-latest]'),
                place: element.querySelector('[data-seismic-place]'),
                details: element.querySelector('[data-seismic-details]'),
                magnitude: element.querySelector('[data-seismic-magnitude]'),
                status: element.querySelector('[data-seismic-status]'),
            };
        }

        setStatus(message) { this.fields.status.textContent = message; }

        render(summary) {
            const event = summary.latest_event;
            this.fields.total.textContent = Number(summary.total_events || 0).toLocaleString();
            this.fields.recent.textContent = Number(summary.recent_events || 0).toLocaleString();
            if (!event) {
                this.fields.place.textContent = this.element.dataset.noEventsMessage;
                this.fields.details.textContent = '';
                this.fields.magnitude.textContent = '—';
                this.setStatus('');
                return;
            }
            this.fields.place.textContent = event.place || 'Location not specified';
            this.fields.details.textContent = `${event.time_display || ''} · ${event.depth_km == null ? 'Depth not available' : `${event.depth_km} km deep`} · ${event.distance_km == null ? '' : `${Number(event.distance_km).toLocaleString()} km away`}`;
            this.fields.magnitude.textContent = `M ${Number(event.magnitude).toFixed(1)}`;
            this.fields.latest.style.setProperty('--home-seismic-risk', event.color || 'var(--primary)');
            this.setStatus('');
        }

        async load() {
            try {
                const response = await fetch(this.apiUrl, { headers: { Accept: 'application/json' } });
                const summary = await response.json();
                if (!response.ok) throw new Error(summary.error || this.element.dataset.unavailableMessage);
                this.render(summary);
            } catch (error) {
                this.fields.place.textContent = this.element.dataset.unavailableMessage;
                this.fields.details.textContent = '';
                this.fields.magnitude.textContent = '—';
                this.setStatus(error.message || this.element.dataset.unavailableMessage);
            }
        }
    }

    const element = document.querySelector('[data-seismic-home-summary]');
    if (element) new SeismicHomeSummary(element).load();
}());
