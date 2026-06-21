"""
ml/train_planned.py
Train model on real planned_events_clean.csv

Usage:
    python3 train_planned.py --data ../data/planned_events_clean.csv

Outputs:
    ../backend/engine/models/planned_severity_model.joblib
    ../backend/engine/models/planned_manpower_model.joblib
    ../backend/engine/models/planned_encoders.joblib
"""
import argparse
import os
import pandas as pd
import numpy as np
import joblib
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, mean_absolute_error

MODELS_DIR = os.path.join(os.path.dirname(__file__), "../backend/engine/models")
os.makedirs(MODELS_DIR, exist_ok=True)

CATEGORICAL_FEATURES = ["event_cause", "corridor", "zone", "priority"]
NUMERIC_FEATURES     = ["latitude", "longitude", "start_hour", "day_of_week",
                         "requires_road_closure", "expected_duration_hours"]


def load_and_clean(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    print(f"Loaded {len(df)} rows from {path}")

    if "event_type" in df.columns:
        df = df[df["event_type"] == "planned"].copy()
        print(f"After filtering planned: {len(df)} rows")

    # Parse datetimes
    df["start_datetime"] = pd.to_datetime(df["start_datetime"], utc=True, errors="coerce")
    df["end_datetime"]   = pd.to_datetime(df["end_datetime"],   utc=True, errors="coerce")

    df["start_hour"]    = df["start_datetime"].dt.hour.fillna(10)
    df["day_of_week"]   = df["start_datetime"].dt.dayofweek.fillna(1)

    # Expected duration (hours)
    df["expected_duration_hours"] = (
        (df["end_datetime"] - df["start_datetime"]).dt.total_seconds() / 3600
    ).clip(0, 48).fillna(4.0)

    # Severity label: based on event_cause + road_closure + priority
    def severity_label(row):
        high_causes = {"procession", "vip_movement", "protest", "public_event"}
        if row.get("requires_road_closure") and row.get("event_cause") in high_causes:
            return "critical"
        elif row.get("priority") == "High":
            return "high"
        elif row.get("event_cause") in high_causes:
            return "medium"
        else:
            return "low"

    df["severity"] = df.apply(severity_label, axis=1)

    # Estimate manpower needed (rule-based ground truth for training)
    def manpower_estimate(row):
        base = {"construction": 4, "public_event": 8, "procession": 12,
                "vip_movement": 6, "protest": 15, "vehicle_breakdown": 2}.get(
                row.get("event_cause", ""), 4)
        if row.get("requires_road_closure"):
            base += 4
        if row.get("priority") == "High":
            base += 3
        return base

    df["manpower_needed"] = df.apply(manpower_estimate, axis=1)

    # Fill NAs
    for col in CATEGORICAL_FEATURES:
        if col in df.columns:
            df[col] = df[col].fillna("unknown")
        else:
            df[col] = "unknown"

    for col in ["latitude", "longitude"]:
        if col in df.columns:
            df[col] = df[col].fillna(df[col].median())

    df["requires_road_closure"] = df["requires_road_closure"].fillna(False).astype(int)

    return df


def encode_features(df, encoders=None, fit=True):
    X = pd.DataFrame()

    if fit:
        encoders = {}

    for col in CATEGORICAL_FEATURES:
        if fit:
            le = LabelEncoder()
            X[col] = le.fit_transform(df[col].astype(str))
            encoders[col] = le
        else:
            le = encoders[col]
            known = set(le.classes_)
            df[col] = df[col].apply(lambda v: v if str(v) in known else "unknown")
            X[col] = le.transform(df[col].astype(str))

    for col in NUMERIC_FEATURES:
        X[col] = df[col].astype(float)

    return X, encoders


def train(data_path: str):
    df = load_and_clean(data_path)

    X, encoders = encode_features(df)

    # ── Severity classifier ───────────────────────────────────────────────
    sev_le = LabelEncoder()
    y_sev = sev_le.fit_transform(df["severity"])
    encoders["severity_label"] = sev_le

    Xs_train, Xs_test, ys_train, ys_test = train_test_split(X, y_sev, test_size=0.2, random_state=42)
    sev_model = RandomForestClassifier(n_estimators=200, max_depth=6, random_state=42)
    sev_model.fit(Xs_train, ys_train)
    acc = accuracy_score(ys_test, sev_model.predict(Xs_test))
    print(f"Severity Model Accuracy: {acc:.2%}")

    # ── Manpower regressor ────────────────────────────────────────────────
    y_man = df["manpower_needed"].values
    Xm_train, Xm_test, ym_train, ym_test = train_test_split(X, y_man, test_size=0.2, random_state=42)
    man_model = RandomForestRegressor(n_estimators=200, max_depth=6, random_state=42)
    man_model.fit(Xm_train, ym_train)
    mae = mean_absolute_error(ym_test, man_model.predict(Xm_test))
    print(f"Manpower Model MAE: {mae:.1f} officers")

    # ── Save ──────────────────────────────────────────────────────────────
    joblib.dump(sev_model, os.path.join(MODELS_DIR, "planned_severity_model.joblib"))
    joblib.dump(man_model, os.path.join(MODELS_DIR, "planned_manpower_model.joblib"))
    joblib.dump(encoders,  os.path.join(MODELS_DIR, "planned_encoders.joblib"))

    print(f"\n✅ Models saved to {MODELS_DIR}")
    print("   planned_severity_model.joblib")
    print("   planned_manpower_model.joblib")
    print("   planned_encoders.joblib")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, help="Path to planned_events_clean.csv")
    args = parser.parse_args()
    train(args.data)
