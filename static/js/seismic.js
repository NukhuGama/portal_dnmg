/* Seismic explorer: state, pure filters, renderers, data loading, and statistics. */
(function () {
    'use strict';

    const TIMOR_LESTE = [-8.8742, 125.7275];
    const numberFormat = new Intl.NumberFormat();
    const escapeHtml = (value) => String(value == null ? '' : value).replace(/[&<>'"]/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[character]));
    const asNumber = (value) => value === '' || value == null ? null : Number(value);
    const hasValue = (value) => value !== null && value !== undefined && value !== '' && !Number.isNaN(value);
    const markerRadius = (magnitude) => Math.max(8, Math.min(23, 4 + Number(magnitude) * 2.5));
    const RECENT_EVENT_RING = Object.freeze({ baseRadiusMeters: 16000, metersPerMagnitude: 2200, coreWeight: 3, coreFillOpacity: .07, pulseWeight: 3, pulseStart: .3, pulseEnd: 1.25, pulseDurationMs: 1800 });

    class FilterState {
        constructor(defaults) { this.defaults = Object.freeze({ ...defaults }); this.reset(); }
        reset() { this.values = { ...this.defaults, riskCodes: [...this.defaults.riskCodes] }; }
        set(key, value) { this.values[key] = value; }
        snapshot() { return { ...this.values, riskCodes: [...this.values.riskCodes] }; }
    }

    class EventFilters {
        static matchesMagnitudeExpression(event, query) {
            const match = query.match(/^(?:m(?:ag(?:nitude)?)?\s*)?(>=|<=|>|<|=)\s*(-?\d+(?:\.\d+)?)$/i);
            if (!match) return null;
            const value = Number(match[2]);
            return { '>': event.magnitude > value, '<': event.magnitude < value, '>=': event.magnitude >= value, '<=': event.magnitude <= value, '=': event.magnitude === value }[match[1]];
        }
        static matchesText(event, query) {
            if (!query) return true;
            const magnitudeResult = this.matchesMagnitudeExpression(event, query);
            return magnitudeResult === null ? `${event.place} ${event.risk} ${event.id}`.toLowerCase().includes(query.toLowerCase()) : magnitudeResult;
        }
        static apply(events, state) {
            const values = state.snapshot();
            const magnitudeMin = asNumber(values.magnitudeMin), magnitudeMax = asNumber(values.magnitudeMax);
            const depthMin = asNumber(values.depthMin), depthMax = asNumber(values.depthMax);
            const distanceMin = asNumber(values.distanceMin), distanceMax = asNumber(values.distanceMax);
            const riskCodes = new Set(values.riskCodes), location = values.location.trim().toLowerCase();
            return events.filter((event) => (
                (magnitudeMin === null || event.magnitude >= magnitudeMin) && (magnitudeMax === null || event.magnitude <= magnitudeMax) &&
                (depthMin === null || (event.depth_km != null && event.depth_km >= depthMin)) && (depthMax === null || (event.depth_km != null && event.depth_km <= depthMax)) &&
                (distanceMin === null || event.distance_km >= distanceMin) && (distanceMax === null || event.distance_km <= distanceMax) &&
                riskCodes.has(event.risk_code) && (!location || event.place.toLowerCase().includes(location)) && this.matchesText(event, values.textSearch.trim())
            ));
        }
        static sort(events, sort) {
            const selectors = { time: (event) => event.time, magnitude: (event) => event.magnitude, risk: (event) => event.risk, place: (event) => event.place, depth: (event) => event.depth_km, distance: (event) => event.distance_km };
            return [...events].sort((first, second) => {
                const a = selectors[sort.key](first), b = selectors[sort.key](second);
                const comparison = typeof a === 'string' ? a.localeCompare(b) : (a ?? -1) - (b ?? -1);
                return sort.direction === 'asc' ? comparison : -comparison;
            });
        }
    }

    class EarthquakeDetails {
        static coordinate(value) { const coordinate = Number(value); return Number.isFinite(coordinate) ? coordinate.toFixed(5) : 'Not available'; }
        static value(value) { return hasValue(value) ? escapeHtml(value) : 'Not available'; }
        static popup(event) {
            return `<div class="seismic-popup__title">${event.is_recent ? '<i class="bi bi-star-fill seismic-recent-star" title="Recent event"></i>' : ''}M ${Number(event.magnitude).toFixed(1)} · ${escapeHtml(event.risk)}</div><div class="seismic-popup__place">${escapeHtml(event.place)}</div><div class="seismic-popup__details">
                <div><i class="bi bi-clock"></i> ${escapeHtml(event.time_display)}</div><div><i class="bi bi-geo-alt"></i> Latitude: ${this.coordinate(event.latitude)} · Longitude: ${this.coordinate(event.longitude)}</div>
                <div><i class="bi bi-arrow-down"></i> Depth: ${event.depth_km == null ? 'Not available' : `${event.depth_km} km`} · Distance: ${numberFormat.format(event.distance_km)} km</div>
                <div><i class="bi bi-bar-chart"></i> Magnitude type: ${this.value(event.magnitude_type)} · Felt reports: ${this.value(event.felt)}</div>
                <div><i class="bi bi-graph-up"></i> Significance: ${this.value(event.significance)} · Tsunami: ${event.tsunami ? 'Yes' : 'No'}</div>
                <div><i class="bi bi-info-circle"></i> Status: ${this.value(event.status)} · USGS alert: ${this.value(event.alert)}</div><div><i class="bi bi-fingerprint"></i> Event ID: ${this.value(event.id)}</div></div>
                ${event.usgs_url ? `<a class="btn btn-sm btn-outline-primary mt-2" href="${escapeHtml(event.usgs_url)}" target="_blank" rel="noopener noreferrer">View USGS event <i class="bi bi-box-arrow-up-right ms-1"></i></a>` : ''}`;
        }
    }

    class RecentEventRingRenderer {
        constructor(layer) {
            this.layer = layer;
            this.rings = new Map();
            this.frameId = null;
            this.reducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        }
        radiusFor(event) { return RECENT_EVENT_RING.baseRadiusMeters + Number(event.magnitude) * RECENT_EVENT_RING.metersPerMagnitude; }
        create(event) {
            const position = [Number(event.latitude), Number(event.longitude)];
            const radius = this.radiusFor(event);
            const core = L.circle(position, {
                radius, color: event.color, weight: RECENT_EVENT_RING.coreWeight, opacity: .95,
                fillColor: event.color, fillOpacity: RECENT_EVENT_RING.coreFillOpacity,
                dashArray: '8 10', interactive: false, className: 'seismic-recent-event-ring'
            }).addTo(this.layer);
            const pulse = L.circle(position, {
                radius: radius * RECENT_EVENT_RING.pulseStart, color: event.color, weight: RECENT_EVENT_RING.pulseWeight,
                opacity: .85, fillOpacity: 0, interactive: false, className: 'seismic-recent-event-pulse'
            }).addTo(this.layer);
            return { core, pulse, radius };
        }
        sync(events) {
            const recentEvents = events.filter((event) => event.is_recent);
            const incoming = new Set(recentEvents.map((event) => event.id));
            this.rings.forEach((ring, id) => {
                if (!incoming.has(id)) { this.layer.removeLayer(ring.core); this.layer.removeLayer(ring.pulse); this.rings.delete(id); }
            });
            recentEvents.forEach((event) => {
                if (!this.rings.has(event.id)) this.rings.set(event.id, this.create(event));
            });
            if (this.rings.size && !this.reducedMotion && !this.frameId) this.animate();
            if (!this.rings.size && this.frameId) { window.cancelAnimationFrame(this.frameId); this.frameId = null; }
        }
        animate = (now = performance.now()) => {
            const phase = (now % RECENT_EVENT_RING.pulseDurationMs) / RECENT_EVENT_RING.pulseDurationMs;
            this.rings.forEach((ring) => {
                ring.pulse.setRadius(ring.radius * (RECENT_EVENT_RING.pulseStart + (RECENT_EVENT_RING.pulseEnd - RECENT_EVENT_RING.pulseStart) * phase));
                ring.pulse.setStyle({ opacity: .9 * (1 - phase) });
            });
            this.frameId = this.rings.size ? window.requestAnimationFrame(this.animate) : null;
        };
    }

    class MapRenderer {
        constructor(element, boundaryUrl) {
            this.map = L.map(element, { zoomControl: true, tap: true }).setView(TIMOR_LESTE, 6);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors', subdomains: ['a', 'b', 'c'], maxZoom: 19 }).addTo(this.map);
            this.addTimorLesteBoundary(boundaryUrl);
            this.ringLayer = L.layerGroup().addTo(this.map);
            this.markerLayer = L.layerGroup().addTo(this.map);
            this.markers = new Map(); this.recentRingRenderer = new RecentEventRingRenderer(this.ringLayer);
            L.circleMarker(TIMOR_LESTE, { radius: 7, color: '#12354b', weight: 2, fillColor: '#fff', fillOpacity: 1 }).bindTooltip('Timor-Leste', { direction: 'top' }).addTo(this.map);
        }
        addTimorLesteBoundary(boundaryUrl) {
            if (!boundaryUrl) return;
            fetch(boundaryUrl)
                .then((response) => { if (!response.ok) throw new Error(`Boundary request failed: ${response.status}`); return response.json(); })
                .then((boundary) => L.geoJSON(boundary, {
                    style: { color: '#087f8c', weight: 2.2, opacity: .95, fillColor: '#74c0c3', fillOpacity: .12, dashArray: '5 4' },
                    onEachFeature: (feature, layer) => {
                        const name = feature.properties && feature.properties.shapeName;
                        if (name) layer.bindTooltip(name, { sticky: true, opacity: .9 });
                    }
                }).addTo(this.map))
                .catch((error) => console.warn('Timor-Leste boundary unavailable:', error));
        }
        static positions(events) {
            const groups = new Map(), positions = new Map();
            events.forEach((event) => { const key = `${Number(event.latitude).toFixed(5)},${Number(event.longitude).toFixed(5)}`; groups.set(key, [...(groups.get(key) || []), event]); });
            groups.forEach((group) => group.forEach((event, index) => { const angle = (Math.PI * 2 * index) / group.length, offset = group.length > 1 ? .018 : 0; positions.set(event.id, [Number(event.latitude) + Math.sin(angle) * offset, Number(event.longitude) + Math.cos(angle) * offset]); }));
            return positions;
        }
        createMarker(event, position) {
            const marker = L.circleMarker(position, { radius: markerRadius(event.magnitude), color: event.is_recent ? '#ffc107' : '#fff', weight: event.is_recent ? 3 : 2, fillColor: event.color, fillOpacity: .9, className: `seismic-marker${event.is_recent ? ' seismic-marker--recent' : ''}` }).bindPopup(EarthquakeDetails.popup(event), { className: 'seismic-popup', maxWidth: 360, autoPanPadding: [24, 24] });
            if (event.is_recent) marker.bindTooltip('★', { permanent: true, direction: 'center', className: 'seismic-recent-marker-star', interactive: false, opacity: 1 });
            marker.on('click', () => marker.bringToFront()); marker.addTo(this.markerLayer); return marker;
        }
        render(events, { fit = false } = {}) {
            const positions = MapRenderer.positions(events), incoming = new Set(events.map((event) => event.id));
            this.markers.forEach((marker, id) => {
                if (!incoming.has(id)) {
                    this.markerLayer.removeLayer(marker); this.markers.delete(id);
                }
            });
            events.forEach((event) => {
                if (!this.markers.has(event.id)) this.markers.set(event.id, this.createMarker(event, positions.get(event.id)));
            });
            this.recentRingRenderer.sync(events);
            if (fit && events.length) this.map.fitBounds(L.latLngBounds(events.map((event) => positions.get(event.id))), { padding: [34, 34], maxZoom: 7 });
        }
        focus(eventId) { const marker = this.markers.get(eventId); if (marker) { this.map.flyTo(marker.getLatLng(), Math.max(this.map.getZoom(), 8), { duration: .45 }); marker.openPopup(); } }
    }

    class TableRenderer {
        constructor(table, emptyState, onFocus) {
            this.body = table.querySelector('tbody'); this.emptyState = emptyState;
            table.addEventListener('click', (event) => { const target = event.target.closest('[data-event-focus]'); if (target) onFocus(target.dataset.eventFocus); });
        }
        render(events) {
            this.body.innerHTML = events.map((event) => `<tr class="${event.is_recent ? 'seismic-event--recent' : ''}"><td class="small text-nowrap">${event.is_recent ? '<i class="bi bi-star-fill seismic-recent-star" title="Recent event" aria-label="Recent event"></i>' : ''}${escapeHtml(event.time_display)}</td><td><span class="magnitude-value">${Number(event.magnitude).toFixed(1)}</span></td><td><span class="seismic-risk-badge risk-swatch--${escapeHtml(event.risk_code)}">${escapeHtml(event.risk)}</span></td><td class="table-location">${escapeHtml(event.place)}</td><td class="text-nowrap">${event.depth_km == null ? '—' : `${event.depth_km} km`}</td><td class="text-nowrap">${numberFormat.format(event.distance_km)} km</td><td class="text-end"><button type="button" class="btn btn-sm btn-outline-primary" data-event-focus="${escapeHtml(event.id)}"><i class="bi bi-crosshair me-1"></i>Map</button></td></tr>`).join('');
            this.emptyState.classList.toggle('d-none', events.length !== 0);
        }
    }

    class StatisticsRenderer {
        constructor(root, riskLevels) { this.root = root; this.riskLevels = riskLevels; this.magnitudeChart = null; this.depthChart = null; }
        updateChart(chartName, elementId, labels, data, colors) {
            if (!window.Chart) return;
            const config = { type: 'bar', data: { labels, datasets: [{ data, backgroundColor: colors, borderRadius: 5, borderSkipped: false }] }, options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } } };
            if (this[chartName]) { this[chartName].data.labels = labels; this[chartName].data.datasets[0].data = data; this[chartName].update(); } else this[chartName] = new Chart(this.root.querySelector(`#${elementId}`), config);
        }
        render(events) {
            const depths = events.map((event) => event.depth_km).filter((depth) => depth != null);
            const maxMagnitude = events.length ? Math.max(...events.map((event) => event.magnitude)) : null;
            const recentEvents = events.filter((event) => event.is_recent);
            const nearTimorLeste = events.filter((event) => event.distance_km <= 550);
            this.root.querySelector('#seismic_stat_total').textContent = numberFormat.format(events.length);
            this.root.querySelector('#seismic_stat_recent').textContent = numberFormat.format(recentEvents.length);
            this.root.querySelector('#seismic_stat_max_magnitude').textContent = maxMagnitude == null ? '—' : `M ${maxMagnitude.toFixed(1)}`;
            this.root.querySelector('#seismic_stat_near_timor').textContent = numberFormat.format(nearTimorLeste.length);
            const risks = this.riskLevels;
            this.root.querySelector('#seismic_risk_counts').innerHTML = risks.map((risk) => `<span class="seismic-risk-count risk-swatch--${risk.code}"><i class="risk-swatch"></i>${risk.label} <strong>${events.filter((event) => event.risk_code === risk.code).length}</strong></span>`).join('');
            this.updateChart('magnitudeChart', 'seismic_magnitude_chart', risks.map((risk) => `${risk.label} (${risk.range})`), risks.map((risk) => events.filter((event) => event.risk_code === risk.code).length), risks.map((risk) => risk.color));
            const depthBuckets = [['< 70 km', (depth) => depth < 70], ['70 - 299 km', (depth) => depth >= 70 && depth < 300], ['>= 300 km', (depth) => depth >= 300]];
            this.updateChart('depthChart', 'seismic_depth_chart', depthBuckets.map((bucket) => bucket[0]), depthBuckets.map((bucket) => depths.filter(bucket[1]).length), ['#0dcaf0', '#0d6efd', '#6f42c1']);
        }
    }

    class SeismicExplorer {
        constructor(root) {
            this.root = root; this.apiUrl = root.dataset.apiUrl; this.events = []; this.sort = { key: 'time', direction: 'desc' }; this.dateTimer = null;
            this.recentEventHours = Number(root.dataset.recentEventHours) || 24;
            const riskLevelsElement = document.getElementById('seismic-risk-levels');
            this.riskLevels = riskLevelsElement ? JSON.parse(riskLevelsElement.textContent) : [];
            const riskCodes = [...root.querySelectorAll('[data-filter-risk]')].map((input) => input.value);
            this.state = new FilterState({ scope: 'timor-leste', startDate: root.dataset.defaultStartDate, endDate: root.dataset.defaultEndDate, magnitudeMin: '', magnitudeMax: '', depthMin: '', depthMax: '', distanceMin: '', distanceMax: '', location: '', textSearch: '', riskCodes });
            this.map = new MapRenderer(root.querySelector('#seismic_map'), root.dataset.boundaryUrl); this.table = new TableRenderer(root.querySelector('#seismic_table'), root.querySelector('#seismic_empty'), (id) => this.map.focus(id)); this.statistics = new StatisticsRenderer(root, this.riskLevels);
            this.count = root.querySelector('#seismic_count'); this.error = root.querySelector('#seismic_error'); this.bind(); this.load({ fit: true });
        }
        bind() {
            this.root.querySelectorAll('[data-filter]').forEach((input) => input.addEventListener('input', () => { this.state.set(input.dataset.filter, input.value); this.render(false); }));
            this.root.querySelectorAll('[data-filter-risk]').forEach((input) => input.addEventListener('change', () => { this.state.set('riskCodes', [...this.root.querySelectorAll('[data-filter-risk]:checked')].map((item) => item.value)); this.render(false); }));
            this.root.querySelectorAll('input[name="seismic_scope"]').forEach((input) => input.addEventListener('change', () => { if (input.checked) { this.state.set('scope', input.value); this.load({ fit: true }); } }));
            ['seismic_start_date', 'seismic_end_date'].forEach((id) => this.root.querySelector(`#${id}`).addEventListener('change', () => this.scheduleDateLoad()));
            this.root.querySelector('#seismic_apply_dates').addEventListener('click', () => this.load({ fit: true })); this.root.querySelector('#seismic_reset').addEventListener('click', () => this.reset());
            this.root.querySelectorAll('[data-sort]').forEach((header) => header.addEventListener('click', () => { const key = header.dataset.sort; this.sort = { key, direction: this.sort.key === key && this.sort.direction === 'desc' ? 'asc' : 'desc' }; this.render(false); }));
        }
        syncDates() { this.state.set('startDate', this.root.querySelector('#seismic_start_date').value); this.state.set('endDate', this.root.querySelector('#seismic_end_date').value); }
        scheduleDateLoad() { this.syncDates(); window.clearTimeout(this.dateTimer); this.dateTimer = window.setTimeout(() => this.load({ fit: true }), 300); }
        syncForm() { const values = this.state.snapshot(); this.root.querySelector(`input[name="seismic_scope"][value="${values.scope}"]`).checked = true; this.root.querySelector('#seismic_start_date').value = values.startDate; this.root.querySelector('#seismic_end_date').value = values.endDate; this.root.querySelectorAll('[data-filter]').forEach((input) => { input.value = values[input.dataset.filter]; }); this.root.querySelectorAll('[data-filter-risk]').forEach((input) => { input.checked = values.riskCodes.includes(input.value); }); }
        reset() { this.state.reset(); this.syncForm(); this.load({ fit: true }); }
        render(fit) { const filtered = EventFilters.apply(this.events, this.state); this.map.render(filtered, { fit }); this.table.render(EventFilters.sort(filtered, this.sort)); this.statistics.render(filtered); this.count.textContent = `${numberFormat.format(filtered.length)} earthquake${filtered.length === 1 ? '' : 's'} shown`; }
        setError(message = '') { this.error.textContent = message; this.error.classList.toggle('d-none', !message); }
        async load({ fit }) {
            this.syncDates(); const { scope, startDate, endDate } = this.state.snapshot();
            if (!startDate || !endDate || startDate > endDate) return this.setError('Choose a valid start and end date.');
            if ((new Date(endDate) - new Date(startDate)) / 86400000 > 90) return this.setError('Choose a date range of 90 days or fewer.');
            this.setError(); this.count.textContent = 'Loading earthquake activity…';
            try {
                const response = await fetch(`${this.apiUrl}?${new URLSearchParams({ scope, start_date: startDate, end_date: endDate })}`, { headers: { Accept: 'application/json' } }); const data = await response.json();
                if (!response.ok) throw new Error(data.error || 'Unable to load earthquake data.');
                this.events = data.features.map((feature) => {
                    const eventTime = new Date(feature.properties.time).getTime();
                    const eventAge = Date.now() - eventTime;
                    const isRecent = Number.isFinite(eventAge) && eventAge >= 0 && eventAge <= this.recentEventHours * 60 * 60 * 1000;
                    return { ...feature.properties, coordinates: feature.geometry.coordinates, longitude: feature.properties.longitude ?? feature.geometry.coordinates[0], latitude: feature.properties.latitude ?? feature.geometry.coordinates[1], is_recent: feature.properties.is_recent ?? isRecent, risk_code: feature.properties.risk_code || String(feature.properties.risk || '').toLowerCase().replace(/\s+/g, '-') };
                });
                this.render(fit);
            } catch (error) { this.events = []; this.render(false); this.setError(error.message || 'Unable to load earthquake data.'); }
        }
    }

    const root = document.querySelector('[data-seismic-root]');
    if (root && window.L) new SeismicExplorer(root);
}());
