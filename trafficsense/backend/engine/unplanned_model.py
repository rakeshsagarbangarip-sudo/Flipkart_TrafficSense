"""
backend/engine/unplanned_model.py
Real-time inference for unplanned incidents.
Loads trained models and returns decisions instantly.
"""
import os
import joblib
import numpy as np
from typing import Optional

MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")

_dur_model  = None
_sev_model  = None
_encoders   = None

def _load():
    global _dur_model, _sev_model, _encoders
    if _dur_model is None:
        p = lambda f: os.path.join(MODELS_DIR, f)
        _dur_model = joblib.load(p("unplanned_duration_model.joblib"))
        _sev_model = joblib.load(p("unplanned_severity_model.joblib"))
        _encoders  = joblib.load(p("unplanned_encoders.joblib"))


def _encode_val(col: str, val: str) -> int:
    le = _encoders.get(col)
    if le is None:
        return 0
    known = set(le.classes_)
    val = str(val) if str(val) in known else "unknown"
    return int(le.transform([val])[0])


def predict(
    event_cause: str,
    veh_type: str,
    corridor: str,
    zone: str,
    priority: str,
    latitude: float,
    longitude: float,
    start_hour: int,
    day_of_week: int,
    requires_road_closure: bool,
) -> dict:
    """
    Returns:
        severity, duration_min, manpower, action, nearest_station, confidence
    """
    _load()

    X = np.array([[
        _encode_val("event_cause", event_cause),
        _encode_val("veh_type",    veh_type or "unknown"),
        _encode_val("corridor",    corridor or "unknown"),
        _encode_val("zone",        zone or "unknown"),
        _encode_val("priority",    priority),
        float(latitude),
        float(longitude),
        int(start_hour),
        int(day_of_week),
        int(requires_road_closure),
    ]])

    duration_min = float(_dur_model.predict(X)[0])
    duration_min = max(5.0, round(duration_min, 1))

    sev_idx      = int(_sev_model.predict(X)[0])
    sev_proba    = float(_sev_model.predict_proba(X)[0][sev_idx])
    sev_le       = _encoders["severity_label"]
    severity     = sev_le.inverse_transform([sev_idx])[0]

    # Manpower heuristic from severity + cause
    manpower_map = {
        "critical": 10, "high": 7, "medium": 4, "low": 2,
    }
    manpower = manpower_map.get(severity, 4)
    if requires_road_closure:
        manpower += 3

    # Action recommendation
    actions = {
        "vehicle_breakdown": "Deploy tow vehicle immediately. Place cones 50m upstream. Divert to nearest service lane.",
        "accident":          "Alert ambulance & traffic control. Seal accident zone 100m. Initiate alternate route broadcast.",
        "pot_holes":         "Place warning signage. Reduce speed limit signs. Schedule repair crew.",
        "water_logging":     "Close affected stretch. Deploy pumping unit. Reroute via elevated corridor.",
        "tree_fall":         "Deploy cutting crew immediately. Close both carriageways. Traffic marshal on site.",
        "others":            "Assess on-ground. Deploy traffic marshal. Monitor and update severity.",
    }
    action = actions.get(event_cause, actions["others"])

    return {
        "severity":     severity,
        "duration_min": duration_min,
        "manpower":     manpower,
        "action":       action,
        "confidence":   round(sev_proba, 3),
    }
