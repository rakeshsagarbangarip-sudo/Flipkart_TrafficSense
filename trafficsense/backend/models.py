"""
models.py — Pydantic schemas for request/response validation
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

# ─── Planned Event ────────────────────────────────────────────────────────────

class PlannedEventSubmit(BaseModel):
    event_cause: str            # construction / public_event / procession / vip_movement / protest
    event_name: str
    organizer_name: Optional[str] = None
    expected_crowd_size: Optional[int] = None
    address: str
    latitude: float
    longitude: float
    corridor: Optional[str] = None
    zone: Optional[str] = None
    junction: Optional[str] = None
    start_datetime: datetime
    end_datetime: datetime
    requires_road_closure: bool = False
    priority: str = "Medium"    # Low / Medium / High
    description: Optional[str] = None
    police_station: Optional[str] = None
    submitted_by: str           # officer id / name

class ApprovalAction(BaseModel):
    admin_id: str
    action: str                 # "approve" or "reject"
    rejection_reason: Optional[str] = None

class MLDecision(BaseModel):
    severity: str
    manpower: int
    barricade_points: List[dict]
    diversion_routes: List[str]
    deployment_notes: str
    risk_score: float

class PlannedFeedback(BaseModel):
    officer_id: str
    actual_manpower_used: int
    actual_barricades: int
    prediction_accurate: bool
    feedback_notes: Optional[str] = None

# ─── Unplanned Event ──────────────────────────────────────────────────────────

class UnplannedEventReport(BaseModel):
    event_cause: str            # vehicle_breakdown / accident / pot_holes / water_logging / tree_fall / others
    address: str
    latitude: float
    longitude: float
    corridor: Optional[str] = None
    zone: Optional[str] = None
    junction: Optional[str] = None
    veh_type: Optional[str] = "unknown"   # lcv / heavy_vehicle / others
    requires_road_closure: bool = False
    priority: str = "High"
    description: Optional[str] = None
    police_station: Optional[str] = None
    reported_by: str            # officer id

class UnplannedResolve(BaseModel):
    officer_id: str

class UnplannedFeedback(BaseModel):
    officer_id: str
    actual_duration_min: float
    actual_manpower_used: int
    actual_barricades: int
    needed_more_manpower: bool
    needed_more_barricades: bool
    prediction_accurate: bool
    feedback_notes: Optional[str] = None

# ─── Response schemas ─────────────────────────────────────────────────────────

class EventResponse(BaseModel):
    id: str
    status: str
    message: str

class DecisionResponse(BaseModel):
    event_id: str
    event_type: str             # planned / unplanned
    severity: str
    manpower: int
    barricade_points: list
    diversion_routes: list
    action: str
    risk_score: float
    confidence: Optional[float] = None
    notes: str
