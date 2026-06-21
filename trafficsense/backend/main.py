"""
backend/main.py — FastAPI application entrypoint

Run:
    uvicorn main:app --reload --port 8000

Docs:
    http://localhost:8000/docs
"""
import uuid
import json
import csv
import io
import os
import math
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from database import get_db, create_tables, PlannedEvent, UnplannedEvent
from models import (
    PlannedEventSubmit, ApprovalAction, PlannedFeedback,
    UnplannedEventReport, UnplannedResolve, UnplannedFeedback,
)

# ── App init ──────────────────────────────────────────────────────────────────
app = FastAPI(
    title="TrafficSense API",
    description="Event-Driven Congestion Management — Planned & Unplanned",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],    # Restrict in production
    allow_methods=["*"],
    allow_headers=["*"],
)

create_tables()

# Live WebSocket connections (for dashboard real-time feed)
_ws_clients: List[WebSocket] = []

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LOCATION_DATASETS = {
    "planned": DATA_DIR / "planned_events_clean.csv",
    "unplanned": DATA_DIR / "unplanned_events_clean.csv",
}

LOCATION_FIELDS = ("corridor", "zone", "junction", "police_station", "address")
UNKNOWN_VALUES = {"", "unknown", "n/a", "na", "none", "null", "-"}

async def broadcast(event: dict):
    dead = []
    for ws in _ws_clients:
        try:
            await ws.send_json(event)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _ws_clients.remove(ws)


@lru_cache(maxsize=2)
def _load_location_dataset(event_type: str) -> dict:
    csv_path = LOCATION_DATASETS.get(event_type)
    if not csv_path:
        raise HTTPException(400, "event_type must be planned or unplanned")
    if not csv_path.exists():
        raise HTTPException(500, f"Location dataset missing: {csv_path.name}")

    rows = []
    with csv_path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            try:
                lat = float(row["latitude"])
                lng = float(row["longitude"])
            except (TypeError, ValueError, KeyError):
                continue

            if math.isnan(lat) or math.isnan(lng):
                continue

            rows.append({
                "latitude": lat,
                "longitude": lng,
                **{field: (row.get(field) or "").strip() for field in LOCATION_FIELDS},
            })

    if not rows:
        raise HTTPException(500, f"No valid coordinates found in {csv_path.name}")

    latitudes = [row["latitude"] for row in rows]
    longitudes = [row["longitude"] for row in rows]
    return {
        "rows": rows,
        "bounds": {
            "min_latitude": min(latitudes),
            "max_latitude": max(latitudes),
            "min_longitude": min(longitudes),
            "max_longitude": max(longitudes),
        },
    }


def _nearest_location(event_type: str, latitude: float, longitude: float) -> dict:
    dataset = _load_location_dataset(event_type)
    bounds = dataset["bounds"]

    if not (
        bounds["min_latitude"] <= latitude <= bounds["max_latitude"]
        and bounds["min_longitude"] <= longitude <= bounds["max_longitude"]
    ):
        raise HTTPException(
            status_code=422,
            detail={
                "message": f"Coordinates are outside the {event_type} dataset range.",
                "bounds": bounds,
            },
        )

    nearest = _nearest_row(dataset["rows"], latitude, longitude)
    distance_km = _haversine_km(latitude, longitude, nearest["latitude"], nearest["longitude"])
    resolved_fields = {}
    field_sources = {}

    for field in ("corridor", "zone", "junction", "police_station"):
        source = _nearest_field_source(event_type, latitude, longitude, field)
        resolved_fields[field] = source[field] if source else "unknown"
        field_sources[field] = {
            "event_type": source["event_type"],
            "latitude": source["latitude"],
            "longitude": source["longitude"],
            "address": source["address"],
            "distance_km": round(
                _haversine_km(latitude, longitude, source["latitude"], source["longitude"]),
                3,
            ),
        } if source else None

    return {
        "event_type": event_type,
        "input": {"latitude": latitude, "longitude": longitude},
        "matched": {**nearest, **resolved_fields},
        "nearest_place": {
            "address": nearest["address"],
            "latitude": nearest["latitude"],
            "longitude": nearest["longitude"],
            "distance_km": round(distance_km, 3),
        },
        "field_sources": field_sources,
        "distance_km": round(distance_km, 3),
        "bounds": bounds,
    }


def _nearest_row(rows: list, latitude: float, longitude: float) -> dict:
    return min(
        rows,
        key=lambda row: (row["latitude"] - latitude) ** 2 + (row["longitude"] - longitude) ** 2,
    )


def _nearest_row_with_value(rows: list, latitude: float, longitude: float, field: str) -> Optional[dict]:
    candidates = [row for row in rows if not _is_unknown(row.get(field))]
    if not candidates:
        return None
    return _nearest_row(candidates, latitude, longitude)


def _nearest_field_source(event_type: str, latitude: float, longitude: float, field: str) -> Optional[dict]:
    dataset_order = [event_type] + [kind for kind in LOCATION_DATASETS if kind != event_type]
    best_source = None
    best_distance = None

    for kind in dataset_order:
        dataset = _load_location_dataset(kind)
        source = _nearest_row_with_value(dataset["rows"], latitude, longitude, field)
        if not source:
            continue

        distance = _haversine_km(latitude, longitude, source["latitude"], source["longitude"])
        if best_distance is None or distance < best_distance:
            best_source = {**source, "event_type": kind}
            best_distance = distance

    return best_source


def _is_unknown(value: Optional[str]) -> bool:
    return str(value or "").strip().lower() in UNKNOWN_VALUES


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius_km = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lng2 - lng1)
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _apply_dataset_location(payload, event_type: str) -> dict:
    location = _nearest_location(event_type, payload.latitude, payload.longitude)
    match = location["matched"]
    return {
        "address": payload.address or match["address"],
        "corridor": match["corridor"] or "unknown",
        "zone": match["zone"] or "unknown",
        "junction": match["junction"] or "unknown",
        "police_station": match["police_station"] or "unknown",
    }


@app.get("/location/lookup", tags=["Location"])
def lookup_location(event_type: str, latitude: float, longitude: float):
    """Find the nearest dataset row and return corridor, zone, junction, and station."""
    return _nearest_location(event_type, latitude, longitude)


# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws/live")
async def ws_live(websocket: WebSocket):
    await websocket.accept()
    _ws_clients.append(websocket)
    try:
        while True:
            await websocket.receive_text()  # keep alive
    except WebSocketDisconnect:
        _ws_clients.remove(websocket)


# ═════════════════════════════════════════════════════════════════════════════
# PLANNED EVENTS
# ═════════════════════════════════════════════════════════════════════════════

@app.post("/planned/submit", tags=["Planned Events"])
async def submit_planned_event(payload: PlannedEventSubmit, db: Session = Depends(get_db)):
    """
    Officer submits a planned event (rally, construction, VIP, etc.) for admin approval.
    No ML decision yet — just stores for review.
    """
    event_id = str(uuid.uuid4())
    location = _apply_dataset_location(payload, "planned")
    ev = PlannedEvent(
        id                  = event_id,
        event_cause         = payload.event_cause,
        event_name          = payload.event_name,
        organizer_name      = payload.organizer_name,
        expected_crowd_size = payload.expected_crowd_size,
        address             = location["address"],
        latitude            = payload.latitude,
        longitude           = payload.longitude,
        corridor            = location["corridor"],
        zone                = location["zone"],
        junction            = location["junction"],
        start_datetime      = payload.start_datetime,
        end_datetime        = payload.end_datetime,
        requires_road_closure = payload.requires_road_closure,
        priority            = payload.priority,
        description         = payload.description,
        police_station      = location["police_station"],
        submitted_by        = payload.submitted_by,
        status              = "pending_approval",
    )
    db.add(ev)
    db.commit()

    await broadcast({
        "type":     "planned_submitted",
        "event_id": event_id,
        "cause":    payload.event_cause,
        "address":  location["address"],
        "status":   "pending_approval",
    })

    return {"id": event_id, "status": "pending_approval", "message": "Event submitted for admin review."}


@app.get("/planned/pending", tags=["Planned Events"])
def get_pending_planned(db: Session = Depends(get_db)):
    """Admin: list all pending approval requests."""
    events = db.query(PlannedEvent).filter(PlannedEvent.status == "pending_approval").all()
    return [_planned_summary(e) for e in events]


@app.get("/planned/all", tags=["Planned Events"])
def get_all_planned(db: Session = Depends(get_db)):
    events = db.query(PlannedEvent).order_by(PlannedEvent.submitted_at.desc()).all()
    return [_planned_summary(e) for e in events]


@app.get("/planned/{event_id}", tags=["Planned Events"])
def get_planned_event(event_id: str, db: Session = Depends(get_db)):
    ev = db.query(PlannedEvent).filter(PlannedEvent.id == event_id).first()
    if not ev:
        raise HTTPException(404, "Event not found")
    return _planned_detail(ev)

@app.delete("/planned/{event_id}", tags=["Planned Events"])
def delete_planned(event_id: str, db: Session = Depends(get_db)):
    """
    Permanently delete a planned event.
    """
    ev = db.query(PlannedEvent).filter(
        PlannedEvent.id == event_id
    ).first()

    if not ev:
        raise HTTPException(
            status_code=404,
            detail="Event not found"
        )

    db.delete(ev)
    db.commit()

    return {
        "success": True,
        "message": "Planned event deleted successfully",
        "deleted_id": event_id
    }

@app.put("/planned/{event_id}/approve", tags=["Planned Events"])
async def approve_planned_event(event_id: str, payload: ApprovalAction, db: Session = Depends(get_db)):
    """
    Admin approves or rejects a planned event.
    On approval → ML engine generates full deployment plan.
    """
    ev = db.query(PlannedEvent).filter(PlannedEvent.id == event_id).first()
    if not ev:
        raise HTTPException(404, "Event not found")
    if ev.status != "pending_approval":
        raise HTTPException(400, f"Event is already {ev.status}")

    if payload.action == "reject":
        ev.status = "rejected"
        ev.rejection_reason = payload.rejection_reason
        ev.approved_by = payload.admin_id
        ev.approved_at = datetime.now(timezone.utc)
        db.commit()
        return {"status": "rejected"}

    # APPROVE → run ML engine
    try:
        from engine.planned_model import predict as planned_predict
        start_dt = ev.start_datetime
        end_dt   = ev.end_datetime
        duration_hrs = (
            (end_dt - start_dt).total_seconds() / 3600
            if start_dt and end_dt else 4.0
        )
        decision = planned_predict(
            event_cause             = ev.event_cause,
            corridor                = ev.corridor or "unknown",
            zone                    = ev.zone or "unknown",
            priority                = ev.priority or "Medium",
            latitude                = ev.latitude,
            longitude               = ev.longitude,
            start_hour              = start_dt.hour if start_dt else 10,
            day_of_week             = start_dt.weekday() if start_dt else 1,
            requires_road_closure   = ev.requires_road_closure or False,
            expected_duration_hours = duration_hrs,
        )
    except Exception as e:
        # Fallback if models not yet trained
        decision = {
            "severity": "medium",
            "manpower": 6,
            "barricade_points": [
                {"lat": ev.latitude + 0.003, "lng": ev.longitude, "label": "North entry"},
                {"lat": ev.latitude - 0.003, "lng": ev.longitude, "label": "South entry"},
                {"lat": ev.latitude, "lng": ev.longitude + 0.003, "label": "East entry"},
                {"lat": ev.latitude, "lng": ev.longitude - 0.003, "label": "West entry"},
            ],
            "diversion_routes": ["Use parallel service road", "Activate VMS signs 2km upstream"],
            "deployment_notes": f"Deploy officers 2 hours before event. [Fallback — train models first]",
            "risk_score": 0.6,
        }

    ev.status              = "approved"
    ev.approved_by         = payload.admin_id
    ev.approved_at         = datetime.now(timezone.utc)
    ev.ml_severity         = decision["severity"]
    ev.ml_manpower         = decision["manpower"]
    ev.ml_barricade_points = json.dumps(decision["barricade_points"])
    ev.ml_diversion_routes = json.dumps(decision["diversion_routes"])
    ev.ml_deployment_notes = decision["deployment_notes"]
    ev.ml_risk_score       = decision["risk_score"]
    db.commit()

    await broadcast({
        "type":      "planned_approved",
        "event_id":  event_id,
        "severity":  decision["severity"],
        "manpower":  decision["manpower"],
        "address":   ev.address,
    })

    return {"status": "approved", "decision": decision}



@app.post("/planned/{event_id}/feedback", tags=["Planned Events"])
async def planned_feedback(event_id: str, payload: PlannedFeedback, db: Session = Depends(get_db)):
    """
    Officer submits post-event feedback.
    This data is stored in DB and exported to planned dataset for future retraining.
    """
    ev = db.query(PlannedEvent).filter(PlannedEvent.id == event_id).first()
    if not ev:
        raise HTTPException(404, "Event not found")

    ev.feedback_submitted    = True
    ev.actual_manpower_used  = payload.actual_manpower_used
    ev.actual_barricades     = payload.actual_barricades
    ev.prediction_accurate   = payload.prediction_accurate
    ev.feedback_notes        = payload.feedback_notes
    ev.feedback_by           = payload.officer_id
    ev.feedback_at           = datetime.now(timezone.utc)
    db.commit()

    return {"message": "Feedback recorded. This will improve future planned event predictions."}


# ═════════════════════════════════════════════════════════════════════════════
# UNPLANNED EVENTS
# ═════════════════════════════════════════════════════════════════════════════

@app.post("/unplanned/report", tags=["Unplanned Events"])
async def report_unplanned(payload: UnplannedEventReport, db: Session = Depends(get_db)):
    """
    Any officer reports a live incident.
    ML engine makes instant decision — no human approval needed.
    """
    now = datetime.now(timezone.utc)
    event_id = str(uuid.uuid4())
    location = _apply_dataset_location(payload, "unplanned")

    # Instant ML decision
    try:
        from engine.unplanned_model import predict as unplanned_predict
        decision = unplanned_predict(
            event_cause           = payload.event_cause,
            veh_type              = payload.veh_type or "unknown",
            corridor              = location["corridor"],
            zone                  = location["zone"],
            priority              = payload.priority,
            latitude              = payload.latitude,
            longitude             = payload.longitude,
            start_hour            = now.hour,
            day_of_week           = now.weekday(),
            requires_road_closure = payload.requires_road_closure,
        )
    except Exception:
        # Fallback
        decision = {
            "severity":     "medium",
            "duration_min": 45.0,
            "manpower":     4,
            "action":       "Deploy traffic marshal. Assess situation and update.",
            "confidence":   0.7,
        }

    ev = UnplannedEvent(
        id                    = event_id,
        event_cause           = payload.event_cause,
        address               = location["address"],
        latitude              = payload.latitude,
        longitude             = payload.longitude,
        corridor              = location["corridor"],
        zone                  = location["zone"],
        junction              = location["junction"],
        veh_type              = payload.veh_type,
        requires_road_closure = payload.requires_road_closure,
        priority              = payload.priority,
        description           = payload.description,
        police_station        = location["police_station"],
        reported_by           = payload.reported_by,
        start_datetime        = now,
        start_hour            = now.hour,
        status                = "active",
        ml_severity           = decision["severity"],
        ml_duration_min       = decision["duration_min"],
        ml_action             = decision["action"],
        ml_manpower_needed    = decision["manpower"],
        ml_confidence         = decision["confidence"],
    )
    db.add(ev)
    db.commit()

    await broadcast({
        "type":         "unplanned_reported",
        "event_id":     event_id,
        "cause":        payload.event_cause,
        "severity":     decision["severity"],
        "duration_min": decision["duration_min"],
        "manpower":     decision["manpower"],
        "action":       decision["action"],
        "address":      location["address"],
        "lat":          payload.latitude,
        "lng":          payload.longitude,
    })

    return {
        "id":       event_id,
        "status":   "active",
        "decision": decision,
        "message":  f"Incident logged. Action: {decision['action']}"
    }


@app.get("/unplanned/active", tags=["Unplanned Events"])
def get_active_unplanned(db: Session = Depends(get_db)):
    events = db.query(UnplannedEvent).filter(UnplannedEvent.status == "active").all()
    return [_unplanned_summary(e) for e in events]


@app.get("/unplanned/all", tags=["Unplanned Events"])
def get_all_unplanned(db: Session = Depends(get_db)):
    events = db.query(UnplannedEvent).order_by(UnplannedEvent.start_datetime.desc()).limit(200).all()
    return [_unplanned_summary(e) for e in events]


@app.put("/unplanned/{event_id}/resolve", tags=["Unplanned Events"])
async def resolve_unplanned(event_id: str, payload: UnplannedResolve, db: Session = Depends(get_db)):
    ev = db.query(UnplannedEvent).filter(UnplannedEvent.id == event_id).first()
    if not ev:
        raise HTTPException(404, "Incident not found")

    now = datetime.now(timezone.utc)
    ev.status = "resolved"
    ev.resolved_datetime = now
    if ev.start_datetime:
        ev.duration_min = (now - ev.start_datetime).total_seconds() / 60
    db.commit()

    await broadcast({"type": "unplanned_resolved", "event_id": event_id})

    return {"status": "resolved", "duration_min": ev.duration_min}

@app.delete("/unplanned/{event_id}", tags=["Unplanned Events"])
def delete_unplanned(event_id: str, db: Session = Depends(get_db)):
    """
    Permanently delete an unplanned incident from the database.
    """

    ev = db.query(UnplannedEvent).filter(
        UnplannedEvent.id == event_id
    ).first()

    if not ev:
        raise HTTPException(
            status_code=404,
            detail="Incident not found"
        )

    db.delete(ev)
    db.commit()

    return {
        "success": True,
        "message": "Incident deleted successfully",
        "deleted_id": event_id
    }

@app.post("/unplanned/{event_id}/feedback", tags=["Unplanned Events"])
async def unplanned_feedback(event_id: str, payload: UnplannedFeedback, db: Session = Depends(get_db)):
    """
    Officer feedback after resolution — stored for model retraining.
    Captures: actual duration, manpower gaps, barricade needs.
    """
    ev = db.query(UnplannedEvent).filter(UnplannedEvent.id == event_id).first()
    if not ev:
        raise HTTPException(404, "Incident not found")

    ev.feedback_submitted      = True
    ev.actual_duration_min     = payload.actual_duration_min
    ev.actual_manpower_used    = payload.actual_manpower_used
    ev.actual_barricades       = payload.actual_barricades
    ev.needed_more_manpower    = payload.needed_more_manpower
    ev.needed_more_barricades  = payload.needed_more_barricades
    ev.prediction_accurate     = payload.prediction_accurate
    ev.feedback_notes          = payload.feedback_notes
    ev.feedback_by             = payload.officer_id
    ev.feedback_at             = datetime.now(timezone.utc)
    db.commit()

    return {"message": "Feedback stored. Improves future unplanned incident predictions."}


# ═════════════════════════════════════════════════════════════════════════════
# DATA EXPORT for retraining
# ═════════════════════════════════════════════════════════════════════════════

@app.get("/export/planned", tags=["Data Export"])
def export_planned_dataset(db: Session = Depends(get_db)):
    """
    Export planned events with feedback as CSV — use to retrain planned model.
    Planned and unplanned are NEVER mixed in exports.
    """
    events = db.query(PlannedEvent).filter(PlannedEvent.feedback_submitted == True).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id", "event_type", "event_cause", "event_name", "address", "latitude", "longitude",
        "corridor", "zone", "junction", "start_datetime", "end_datetime",
        "requires_road_closure", "priority", "expected_crowd_size",
        "ml_severity", "ml_manpower", "ml_risk_score",
        "actual_manpower_used", "actual_barricades", "prediction_accurate", "feedback_notes"
    ])
    for e in events:
        writer.writerow([
            e.id, "planned", e.event_cause, e.event_name, e.address,
            e.latitude, e.longitude, e.corridor, e.zone, e.junction,
            e.start_datetime, e.end_datetime, e.requires_road_closure, e.priority,
            e.expected_crowd_size, e.ml_severity, e.ml_manpower, e.ml_risk_score,
            e.actual_manpower_used, e.actual_barricades, e.prediction_accurate, e.feedback_notes
        ])
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=planned_dataset_export.csv"}
    )


@app.get("/export/unplanned", tags=["Data Export"])
def export_unplanned_dataset(db: Session = Depends(get_db)):
    """
    Export unplanned incidents with feedback as CSV — use to retrain unplanned model.
    """
    events = db.query(UnplannedEvent).filter(UnplannedEvent.feedback_submitted == True).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id", "event_type", "event_cause", "address", "latitude", "longitude",
        "corridor", "zone", "junction", "veh_type", "requires_road_closure",
        "priority", "start_datetime", "start_hour",
        "ml_severity", "ml_duration_min", "ml_manpower_needed", "ml_confidence",
        "actual_duration_min", "actual_manpower_used", "actual_barricades",
        "needed_more_manpower", "needed_more_barricades", "prediction_accurate", "feedback_notes"
    ])
    for e in events:
        writer.writerow([
            e.id, "unplanned", e.event_cause, e.address, e.latitude, e.longitude,
            e.corridor, e.zone, e.junction, e.veh_type, e.requires_road_closure,
            e.priority, e.start_datetime, e.start_hour,
            e.ml_severity, e.ml_duration_min, e.ml_manpower_needed, e.ml_confidence,
            e.actual_duration_min, e.actual_manpower_used, e.actual_barricades,
            e.needed_more_manpower, e.needed_more_barricades,
            e.prediction_accurate, e.feedback_notes
        ])
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=unplanned_dataset_export.csv"}
    )


@app.get("/")
def root():
    return {
        "message": "TrafficSense API is running successfully",
        "docs": "/docs",
        "health": "/health"
    }
# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
def health():
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _planned_summary(e: PlannedEvent) -> dict:
    return {
        "id": e.id, "event_cause": e.event_cause, "event_name": e.event_name,
        "address": e.address, "latitude": e.latitude, "longitude": e.longitude,
        "start_datetime": str(e.start_datetime), "status": e.status,
        "priority": e.priority, "ml_severity": e.ml_severity, "ml_manpower": e.ml_manpower,
        "feedback_submitted": e.feedback_submitted,
    }

def _planned_detail(e: PlannedEvent) -> dict:
    d = _planned_summary(e)
    d.update({
        "organizer_name": e.organizer_name, "expected_crowd_size": e.expected_crowd_size,
        "end_datetime": str(e.end_datetime), "corridor": e.corridor, "zone": e.zone,
        "requires_road_closure": e.requires_road_closure, "description": e.description,
        "ml_barricade_points": json.loads(e.ml_barricade_points) if e.ml_barricade_points else [],
        "ml_diversion_routes": json.loads(e.ml_diversion_routes) if e.ml_diversion_routes else [],
        "ml_deployment_notes": e.ml_deployment_notes, "ml_risk_score": e.ml_risk_score,
        "approved_by": e.approved_by, "approved_at": str(e.approved_at),
        "actual_manpower_used": e.actual_manpower_used, "feedback_notes": e.feedback_notes,
    })
    return d

def _unplanned_summary(e: UnplannedEvent) -> dict:
    return {
        "id": e.id, "event_cause": e.event_cause, "address": e.address,
        "latitude": e.latitude, "longitude": e.longitude,
        "start_datetime": str(e.start_datetime), "status": e.status,
        "priority": e.priority, "veh_type": e.veh_type,
        "ml_severity": e.ml_severity, "ml_duration_min": e.ml_duration_min,
        "ml_manpower_needed": e.ml_manpower_needed, "ml_action": e.ml_action,
        "ml_confidence": e.ml_confidence, "duration_min": e.duration_min,
        "feedback_submitted": e.feedback_submitted,
    }
