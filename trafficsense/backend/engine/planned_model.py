"""
backend/engine/planned_model.py
Pre-event inference: severity, manpower, barricade zones, diversion routes.
Called when admin approves a planned event.
"""
import os
import joblib
import json
import math
import numpy as np
from datetime import datetime

MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")

_sev_model  = None
_man_model  = None
_encoders   = None

def _load():
    global _sev_model, _man_model, _encoders
    if _sev_model is None:
        p = lambda f: os.path.join(MODELS_DIR, f)
        _sev_model = joblib.load(p("planned_severity_model.joblib"))
        _man_model = joblib.load(p("planned_manpower_model.joblib"))
        _encoders  = joblib.load(p("planned_encoders.joblib"))


def _encode_val(col: str, val: str) -> int:
    le = _encoders.get(col)
    if le is None:
        return 0
    known = set(le.classes_)
    val = str(val) if str(val) in known else "unknown"
    return int(le.transform([val])[0])


def _generate_barricade_points(lat: float, lng: float, radius_km: float = 0.3) -> list:
    """Generate 4 barricade suggestion points around the event location."""
    d = radius_km / 111.0  # degrees
    return [
        {"lat": round(lat + d, 6),  "lng": round(lng, 6),      "label": "North entry"},
        {"lat": round(lat - d, 6),  "lng": round(lng, 6),      "label": "South entry"},
        {"lat": round(lat, 6),      "lng": round(lng + d, 6),  "label": "East entry"},
        {"lat": round(lat, 6),      "lng": round(lng - d, 6),  "label": "West entry"},
    ]


def _generate_diversions(event_cause: str, corridor: str, severity: str) -> list:
    """Generate diversion route descriptions based on corridor and event type."""
    generic = [
        f"Divert traffic from {corridor or 'main corridor'} via parallel service road",
        "Activate variable message signs 2km upstream",
        "Alert Waze/Google Maps via traffic API for re-routing",
    ]
    if severity in ("critical", "high"):
        generic.append("Close entry ramps within 500m of event zone")
        generic.append("Deploy motorcycle outriders for VIP/ambulance priority lane")
    return generic


def predict(
    event_cause: str,
    corridor: str,
    zone: str,
    priority: str,
    latitude: float,
    longitude: float,
    start_hour: int,
    day_of_week: int,
    requires_road_closure: bool,
    expected_duration_hours: float,
) -> dict:
    """
    Returns full pre-event deployment plan.
    """
    _load()

    X = np.array([[
        _encode_val("event_cause", event_cause),
        _encode_val("corridor",    corridor or "unknown"),
        _encode_val("zone",        zone or "unknown"),
        _encode_val("priority",    priority),
        float(latitude),
        float(longitude),
        int(start_hour),
        int(day_of_week),
        int(requires_road_closure),
        float(expected_duration_hours),
    ]])

    sev_idx   = int(_sev_model.predict(X)[0])
    sev_le    = _encoders["severity_label"]
    severity  = sev_le.inverse_transform([sev_idx])[0]
    risk_proba = float(_sev_model.predict_proba(X)[0][sev_idx])

    manpower = int(round(_man_model.predict(X)[0]))
    manpower = max(2, manpower)

    barricade_pts = _generate_barricade_points(latitude, longitude)
    diversions    = _generate_diversions(event_cause, corridor, severity)

    deployment_notes = (
        f"Deploy {manpower} officers at least 2 hours before start. "
        f"Severity assessed as '{severity}'. "
        + ("Implement full road closure protocol. " if requires_road_closure else "")
        + f"Expected impact duration: {expected_duration_hours:.1f} hrs."
    )

    return {
        "severity":         severity,
        "manpower":         manpower,
        "barricade_points": barricade_pts,
        "diversion_routes": diversions,
        "deployment_notes": deployment_notes,
        "risk_score":       round(risk_proba, 3),
    }
