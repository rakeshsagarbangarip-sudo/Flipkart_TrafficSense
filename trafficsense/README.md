# TrafficSense — Event-Driven Congestion Management System

Real-time traffic congestion forecasting and response platform for Bengaluru.

---

## Architecture Overview

```
trafficsense/
├── backend/          # FastAPI REST API + WebSocket server
│   ├── main.py       # App entrypoint
│   ├── models.py     # Pydantic schemas
│   ├── database.py   # SQLite (swap to PostgreSQL in prod)
│   ├── routes/
│   │   ├── planned.py    # Planned event submission + approval
│   │   ├── unplanned.py  # Live incident reporting
│   │   ├── decisions.py  # ML engine decisions
│   │   └── feedback.py   # Post-resolution officer feedback
│   └── engine/
│       ├── planned_model.py    # Planned event ML model
│       └── unplanned_model.py  # Unplanned incident ML model
│
├── ml/
│   ├── train_planned.py      # Train planned model
│   ├── train_unplanned.py    # Train unplanned model
│   └── feature_engineering.py
│
├── frontend/         # React + Vite dashboard
│   └── src/
│       ├── pages/
│       │   ├── PlannedPortal.jsx   # Officer submits event for approval
│       │   ├── LiveIncident.jsx    # Officer reports live incident
│       │   ├── Dashboard.jsx       # Live map + decisions
│       │   └── Feedback.jsx        # Post-resolution feedback
│       └── components/
│
└── data/
    ├── planned_events.db     # SQLite (auto-created)
    ├── unplanned_events.db
    └── feedback.db
```

---

## System Flow

### Planned Events (Pre-event)
```
Officer logs planned event → Portal submission → 
Admin approval → ML engine decision (manpower/barricades/diversions) → 
Event executed → Officer submits feedback → 
Stored in planned_dataset.csv for future model retraining
```

### Unplanned Events (Real-time)
```
Any officer reports incident on-ground → 
Instant ML decision (severity/duration/action) → 
Deployed officers resolve → Feedback submitted → 
Stored in unplanned_dataset.csv for future model retraining
```

---

## Prerequisites

```bash
Python 3.10+
Node.js 18+
pip
npm
```

---

## Installation

### 1. Clone / navigate to project
```bash
cd trafficsense
```

### 2. Backend setup
```bash
cd backend
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Train ML models (uses your real datasets)
```bash
cd ../ml
python3 train_unplanned.py --data ../data/unplanned_events_clean.csv
python3 train_planned.py   --data ../data/planned_events_clean.csv
# Models saved to: ../backend/engine/models/
```

### 4. Start backend API
```bash
cd ../backend
uvicorn main:app --reload --port 8000
# API docs: http://localhost:8000/docs
# WebSocket: ws://localhost:8000/ws/live
```

### 5. Frontend setup
```bash
cd ../frontend
npm install
npm run dev
# Dashboard: http://localhost:5173
```

---

## API Endpoints

### Planned Events
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/planned/submit` | Officer submits event permission request |
| GET  | `/planned/pending` | Admin views pending requests |
| PUT  | `/planned/{id}/approve` | Admin approves → triggers ML decision |
| GET  | `/planned/{id}/decision` | Get ML-generated deployment plan |

### Unplanned Events
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/unplanned/report` | Officer reports live incident |
| GET  | `/unplanned/active` | All active incidents |
| PUT  | `/unplanned/{id}/resolve` | Mark incident resolved |

### Feedback
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/feedback/planned/{id}` | Post-event officer feedback |
| POST | `/feedback/unplanned/{id}` | Post-resolution feedback |

### Data Export (for retraining)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET  | `/export/planned` | Download planned dataset CSV |
| GET  | `/export/unplanned` | Download unplanned dataset CSV |

---

## Data Flow for Future Model Retraining

Every resolved event stores:
- All input features used
- Decision made by the engine
- Officer feedback (actual manpower used, barricades placed, was prediction accurate)

```bash
# Export and retrain monthly
python3 ml/train_planned.py --data data/exports/planned_feedback.csv
python3 ml/train_unplanned.py --data data/exports/unplanned_feedback.csv
```

Planned and unplanned data are ALWAYS stored in separate tables/CSV files.
Never merge them — different features, different actions, different models.
