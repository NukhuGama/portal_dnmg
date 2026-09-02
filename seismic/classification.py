"""Shared earthquake classification rules."""

RECENT_EVENT_HOURS = 24

RISK_LEVELS = (
    {"code": "low", "label": "Low", "range": "2.5 - 3.9", "minimum": 2.5, "color": "#198754"},
    {"code": "moderate", "label": "Moderate", "range": "4.0 - 4.9", "minimum": 4.0, "color": "#ffc107"},
    {"code": "high", "label": "High", "range": "5.0 - 5.9", "minimum": 5.0, "color": "#0d6efd"},
    {"code": "very-high", "label": "Very High", "range": "6.0 - 6.9", "minimum": 6.0, "color": "#fd7e14"},
    {"code": "danger", "label": "Danger", "range": ">= 7.0", "minimum": 7.0, "color": "#dc3545"},
)


def risk_for_magnitude(magnitude):
    """Classify a magnitude using the portal's canonical risk thresholds."""
    for level in reversed(RISK_LEVELS):
        if magnitude >= level["minimum"]:
            return level
    return RISK_LEVELS[0]
