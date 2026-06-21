"""
database.py — SQLAlchemy setup with SQLite (swap URL for PostgreSQL in prod)
PostgreSQL: postgresql+psycopg2://user:pass@localhost/trafficsense
"""
from sqlalchemy import create_engine, Column, String, Float, Boolean, DateTime, Text, Integer, Enum
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime, timezone
import enum

DATABASE_URL = "sqlite:///./trafficsense.db"
# For PostgreSQL: DATABASE_URL = "postgresql+psycopg2://user:password@localhost/trafficsense"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ─── Enums ────────────────────────────────────────────────────────────────────

class EventStatus(str, enum.Enum):
    pending_approval = "pending_approval"
    approved = "approved"
    rejected = "rejected"
    active = "active"
    resolved = "resolved"

class Priority(str, enum.Enum):
    Low = "Low"
    Medium = "Medium"
    High = "High"

class SeverityLevel(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"

# ─── Planned Events Table ─────────────────────────────────────────────────────

class PlannedEvent(Base):
    __tablename__ = "planned_events"

    id = Column(String, primary_key=True)
    
    # Submitted by officer
    event_cause         = Column(String, nullable=False)   # construction / public_event / procession / vip_movement / protest
    event_name          = Column(String, nullable=False)
    organizer_name      = Column(String)
    expected_crowd_size = Column(Integer)
    address             = Column(String, nullable=False)
    latitude            = Column(Float, nullable=False)
    longitude           = Column(Float, nullable=False)
    corridor            = Column(String)
    zone                = Column(String)
    junction            = Column(String)
    start_datetime      = Column(DateTime(timezone=True), nullable=False)
    end_datetime        = Column(DateTime(timezone=True), nullable=False)
    requires_road_closure = Column(Boolean, default=False)
    priority            = Column(String)
    description         = Column(Text)
    police_station      = Column(String)
    submitted_by        = Column(String, nullable=False)   # officer id
    submitted_at        = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Admin decision
    status              = Column(String, default=EventStatus.pending_approval)
    approved_by         = Column(String)
    approved_at         = Column(DateTime)
    rejection_reason    = Column(Text)

    # ML engine decision (populated on approval)
    ml_severity         = Column(String)
    ml_manpower         = Column(Integer)
    ml_barricade_points = Column(Text)    # JSON string of lat/lng points
    ml_diversion_routes = Column(Text)    # JSON string of route descriptions
    ml_deployment_notes = Column(Text)
    ml_risk_score       = Column(Float)

    # Post-event feedback
    feedback_submitted  = Column(Boolean, default=False)
    actual_manpower_used = Column(Integer)
    actual_barricades   = Column(Integer)
    prediction_accurate = Column(Boolean)
    feedback_notes      = Column(Text)
    feedback_by         = Column(String)
    feedback_at         = Column(DateTime)

    # Dataset flag
    exported_to_dataset = Column(Boolean, default=False)

# ─── Unplanned Events Table ───────────────────────────────────────────────────

class UnplannedEvent(Base):
    __tablename__ = "unplanned_events"

    id = Column(String, primary_key=True)

    # Reported by officer in real-time
    event_cause     = Column(String, nullable=False)  # vehicle_breakdown / accident / pot_holes / water_logging / tree_fall / others
    address         = Column(String, nullable=False)
    latitude        = Column(Float, nullable=False)
    longitude       = Column(Float, nullable=False)
    corridor        = Column(String)
    zone            = Column(String)
    junction        = Column(String)
    veh_type        = Column(String)   # lcv / heavy_vehicle / others / N/A
    requires_road_closure = Column(Boolean, default=False)
    priority        = Column(String)
    description     = Column(Text)
    police_station  = Column(String)
    reported_by     = Column(String, nullable=False)  # officer id
    start_datetime  = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    start_hour      = Column(Integer)

    # Status
    status          = Column(String, default="active")
    resolved_datetime = Column(DateTime)
    duration_min    = Column(Float)

    # ML engine instant decision
    ml_severity         = Column(String)
    ml_duration_min     = Column(Float)
    ml_action           = Column(Text)       # immediate action text
    ml_nearest_station  = Column(String)
    ml_manpower_needed  = Column(Integer)
    ml_confidence       = Column(Float)

    # Post-resolution feedback
    feedback_submitted  = Column(Boolean, default=False)
    actual_duration_min = Column(Float)
    actual_manpower_used = Column(Integer)
    actual_barricades   = Column(Integer)
    needed_more_manpower = Column(Boolean)
    needed_more_barricades = Column(Boolean)
    prediction_accurate = Column(Boolean)
    feedback_notes      = Column(Text)
    feedback_by         = Column(String)
    feedback_at         = Column(DateTime)

    exported_to_dataset = Column(Boolean, default=False)

def create_tables():
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    create_tables()
    print("✅ Database tables created.")
