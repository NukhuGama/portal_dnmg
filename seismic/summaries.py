"""Provider-neutral summary projections for compact seismic interfaces."""


def build_home_summary(feature_collection):
    """Return the small, stable data contract used by the Home-page card."""
    events = [feature.get("properties", {}) for feature in feature_collection.get("features", [])]
    events.sort(key=lambda event: event.get("time") or "", reverse=True)
    recent_events = [event for event in events if event.get("is_recent")]
    strongest = max(events, key=lambda event: event.get("magnitude") or 0, default=None)

    latest_event = (recent_events or events or [None])[0]
    return {
        "scope": feature_collection.get("metadata", {}).get("scope", "timor-leste"),
        "total_events": len(events),
        "recent_events": len(recent_events),
        "strongest_magnitude": strongest.get("magnitude") if strongest else None,
        "latest_event": _compact_event(latest_event),
    }


def _compact_event(event):
    """Limit the Home contract to fields it actually presents."""
    if event is None:
        return None
    keys = ("place", "time_display", "depth_km", "distance_km", "magnitude", "risk", "risk_code", "color")
    return {key: event.get(key) for key in keys}
