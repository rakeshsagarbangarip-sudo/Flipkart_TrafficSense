"""
ml/train_unplanned.py
Train model on real unplanned_events_clean.csv

Usage:
    python3 train_unplanned.py --data ../data/unplanned_events_clean.csv

Outputs:
    ../backend/engine/models/unplanned_duration_model.joblib
    ../backend/engine/models/unplanned_severity_model.joblib
    ../backend/engine/models/unplanned_encoders.joblib
"""
import argparse
import os
import sys
import pandas as pd
import numpy as np
import joblib
from sklearn.ensemble import GradientBoostingRegressor, GradientBoostingClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, accuracy_score
from datetime import datetime

MODELS_DIR = os.path.join(os.path.dirname(__file__), "../backend/engine/models")
os.makedirs(MODELS_DIR, exist_ok=True)


def load_and_clean(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    print(f"Loaded {len(df)} rows from {path}")
    
    # Keep only unplanned
    if "event_type" in df.columns:
        df = df[df["event_type"] == "unplanned"].copy()
        print(f"After filtering unplanned: {len(df)} rows")

    # Parse start_datetime
    df["start_datetime"] = pd.to_datetime(df["start_datetime"], utc=True, errors="coerce")
    df["start_hour"] = df["start_datetime"].dt.hour
    df["day_of_week"] = df["start_datetime"].dt.dayofweek

    # Recalculate duration_min where possible
    if "resolved_datetime" in df.columns:
        df["resolved_datetime"] = pd.to_datetime(df["resolved_datetime"], utc=True, errors="coerce")
        mask = df["duration_min"].isna() & df["resolved_datetime"].notna()
        df.loc[mask, "duration_min"] = (
            (df.loc[mask, "resolved_datetime"] - df.loc[mask, "start_datetime"])
            .dt.total_seconds() / 60
        )

    # Remove outliers in duration_min (> 99th percentile)
    if "duration_min" in df.columns:
        p99 = df["duration_min"].quantile(0.99)
        df = df[df["duration_min"] <= p99]

    # Create severity label from priority + duration
    def severity_label(row):
        if row.get("priority") == "High" and row.get("duration_min", 0) > 120:
            return "critical"
        elif row.get("priority") == "High":
            return "high"
        elif row.get("duration_min", 0) > 60:
            return "medium"
        else:
            return "low"

    df["severity"] = df.apply(severity_label, axis=1)

    # Fill categorical NAs
    for col in ["event_cause", "veh_type", "corridor", "zone", "junction", "priority"]:
        if col in df.columns:
            df[col] = df[col].fillna("unknown")

    # Fill numeric NAs
    for col in ["latitude", "longitude", "start_hour", "day_of_week"]:
        if col in df.columns:
            df[col] = df[col].fillna(df[col].median())

    df["requires_road_closure"] = df["requires_road_closure"].fillna(False).astype(int)

    return df


CATEGORICAL_FEATURES = ["event_cause", "veh_type", "corridor", "zone", "priority"]
NUMERIC_FEATURES = ["latitude", "longitude", "start_hour", "day_of_week", "requires_road_closure"]


def encode_features(df: pd.DataFrame, encoders: dict = None, fit: bool = True):
    """Encode categorical features. If fit=True, create and return new encoders."""
    features = CATEGORICAL_FEATURES + NUMERIC_FEATURES
    X = pd.DataFrame()

    if fit:
        encoders = {}

    for col in CATEGORICAL_FEATURES:
        if col not in df.columns:
            df[col] = "unknown"
        if fit:
            le = LabelEncoder()
            X[col] = le.fit_transform(df[col].astype(str))
            encoders[col] = le
        else:
            le = encoders[col]
            # Handle unseen labels
            known = set(le.classes_)
            df[col] = df[col].apply(lambda v: v if str(v) in known else "unknown")
            X[col] = le.transform(df[col].astype(str))

    for col in NUMERIC_FEATURES:
        X[col] = df[col].astype(float) if col in df.columns else 0.0

    return X, encoders


def train(data_path: str):
    df = load_and_clean(data_path)

    # ── Duration model ────────────────────────────────────────────────────
    df_dur = df.dropna(subset=["duration_min"])
    print(f"\nTraining duration model on {len(df_dur)} samples with duration_min...")

    X_dur, encoders = encode_features(df_dur)
    X_dur = X_dur.fillna(X_dur.median())
    y_dur = df_dur["duration_min"].values

    X_train, X_test, y_train, y_test = train_test_split(X_dur, y_dur, test_size=0.2, random_state=42)

    dur_model = GradientBoostingRegressor(
        n_estimators=200, max_depth=5, learning_rate=0.1, random_state=42
    )
    dur_model.fit(X_train, y_train)

    mae = mean_absolute_error(y_test, dur_model.predict(X_test))
    print(f"Duration Model MAE: {mae:.1f} minutes")

    # ── Severity classifier ───────────────────────────────────────────────
    sev_le = LabelEncoder()
    y_sev = sev_le.fit_transform(df_dur["severity"])
    encoders["severity_label"] = sev_le

    X_sev = X_dur.fillna(X_dur.median())  # same features
    Xs_train, Xs_test, ys_train, ys_test = train_test_split(X_sev, y_sev, test_size=0.2, random_state=42)

    sev_model = GradientBoostingClassifier(
        n_estimators=150, max_depth=4, learning_rate=0.1, random_state=42
    )
    sev_model.fit(Xs_train, ys_train)

    acc = accuracy_score(ys_test, sev_model.predict(Xs_test))
    print(f"Severity Model Accuracy: {acc:.2%}")

    # ── Save ──────────────────────────────────────────────────────────────
    joblib.dump(dur_model, os.path.join(MODELS_DIR, "unplanned_duration_model.joblib"))
    joblib.dump(sev_model, os.path.join(MODELS_DIR, "unplanned_severity_model.joblib"))
    joblib.dump(encoders,  os.path.join(MODELS_DIR, "unplanned_encoders.joblib"))

    print(f"\n✅ Models saved to {MODELS_DIR}")
    print("   unplanned_duration_model.joblib")
    print("   unplanned_severity_model.joblib")
    print("   unplanned_encoders.joblib")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, help="Path to unplanned_events_clean.csv")
    args = parser.parse_args()
    train(args.data)
