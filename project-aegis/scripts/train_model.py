"""Train Patna flood-event research models from local weather and Indian event records."""
from __future__ import annotations

from pathlib import Path
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.metrics import average_precision_score, brier_score_loss, classification_report, roc_auc_score
from sklearn.model_selection import GroupKFold

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "patna_training_dataset.csv"
FEATURES = [
    "rainfall_local_mm",
    "river_discharge_m3s",
    "soil_moisture_local",
    "rainfall_local_mm_sum7d",
    "month_sin",
    "month_cos",
]
HORIZONS = (24, 48, 72)


def _year_grouped_oof(X: pd.DataFrame, y: pd.Series, years: pd.Series):
    """Hold out whole years so adjacent daily windows cannot leak across folds."""
    folds = min(5, int(years.nunique()))
    if folds < 3 or y.sum() < 5 or y.nunique() < 2:
        return None
    oof = np.full(len(y), np.nan)
    splitter = GroupKFold(n_splits=folds)
    for train, test in splitter.split(X, y, groups=years):
        if y.iloc[train].nunique() < 2:
            continue
        model = _new_model()
        model.fit(X.iloc[train], y.iloc[train])
        oof[test] = model.predict_proba(X.iloc[test])[:, 1]
    valid = np.isfinite(oof)
    if valid.sum() < 2 or y.iloc[np.flatnonzero(valid)].nunique() < 2:
        return None
    yy = y.iloc[np.flatnonzero(valid)]
    pp = oof[valid]
    return {
        "method": f"{folds}-fold GroupKFold holding out complete calendar years (exploratory, not independent operational validation)",
        "rows": int(valid.sum()),
        "positive_rows": int(yy.sum()),
        "roc_auc": float(roc_auc_score(yy, pp)),
        "average_precision": float(average_precision_score(yy, pp)),
        "brier_score": float(brier_score_loss(yy, pp)),
        "classification_at_0_5": classification_report(yy, (pp >= 0.5).astype(int), output_dict=True, zero_division=0),
    }


def _new_model():
    return ExtraTreesClassifier(
        n_estimators=300,
        max_depth=9,
        min_samples_leaf=8,
        max_features=0.8,
        class_weight="balanced_subsample",
        random_state=42,
        n_jobs=-1,
    )


def build_and_train_model():
    if not DATA.exists():
        raise FileNotFoundError(f"{DATA} not found. Run scripts/build_patna_dataset.py first.")
    df = pd.read_csv(DATA, parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    missing = set(FEATURES + [f"documented_flood_within_{h}h" for h in HORIZONS]) - set(df.columns)
    if missing:
        raise ValueError(f"Training dataset is missing columns: {sorted(missing)}")

    med = df[FEATURES].replace([np.inf, -np.inf], np.nan).median().fillna(0)
    X = df[FEATURES].replace([np.inf, -np.inf], np.nan).fillna(med)
    models, metrics, counts = {}, {}, {}
    for hours in HORIZONS:
        label = f"documented_flood_within_{hours}h"
        y = df[label].astype(int)
        if y.nunique() < 2 or y.sum() < 5:
            raise RuntimeError(f"Not enough documented Patna event examples for the {hours}h model ({int(y.sum())} positives).")
        metrics[str(hours)] = _year_grouped_oof(X, y, df.date.dt.year)
        model = _new_model()
        model.fit(X, y)
        models[str(hours)] = model
        counts[str(hours)] = {
            "rows": int(len(df)),
            "documented_event_rows": int(y.sum()),
            "non_event_record_rows": int(len(y) - y.sum()),
            "first_date": df.date.min().date().isoformat(),
            "last_date": df.date.max().date().isoformat(),
        }
        print(f"{hours}h: {int(y.sum()):,}/{len(y):,} positive event-window samples")
        if metrics[str(hours)]:
            print(f"  year-grouped OOF ROC-AUC={metrics[str(hours)]['roc_auc']:.4f} average-precision={metrics[str(hours)]['average_precision']:.4f} Brier={metrics[str(hours)]['brier_score']:.4f}")
            event_scores = metrics[str(hours)]["classification_at_0_5"]["1"]
            print(f"  OOF event precision={event_scores['precision']:.2f} recall={event_scores['recall']:.2f} at an uncalibrated 0.5 threshold")
        else:
            print("  Not enough event-bearing years for a defensible cross-validation estimate.")

    first = models["24"]
    artifact = {
        "model": first,
        "model_family": "ExtraTreesClassifier",
        "horizon_models": models,
        "horizon_calibrators": {},
        "probability_calibration": "uncalibrated Extra Trees probabilities; do not interpret as calibrated flood odds",
        "features": FEATURES,
        "label": "documented Bihar/Patna inventory event overlaps the forecast horizon",
        "training_medians": med.to_dict(),
        "training_medians_by_horizon": {str(h): med.to_dict() for h in HORIZONS},
        "source_path": str(DATA),
        "event_source_path": str(ROOT / "data" / "india_flood_inventory_v3.csv"),
        "dataset_rows": len(df),
        "positive_rows": counts["24"]["documented_event_rows"],
        "roc_auc": metrics["24"]["roc_auc"] if metrics["24"] else None,
        "horizon_metrics": metrics,
        "horizon_counts": counts,
        "label_provenance": "Positive labels are time windows overlapping Patna district events documented by the IIT Delhi India Flood Inventory (1967–2023). A negative means no matching event is listed; it is not proof that no flood occurred. Inventory coverage is sparse.",
        "coverage_region": "Patna district, Bihar; single-point weather history",
        "operationally_validated": False,
        "training_notice": "Exploratory local model only. Sparse event labels, an incomplete event inventory, and uncalibrated probabilities make it unsuitable for emergency decisions.",
        "dataset_provenance": json.loads((ROOT / "data" / "patna_training_metadata.json").read_text(encoding="utf-8")),
    }
    output = ROOT / "models" / "aegis_rf_model.pkl"
    joblib.dump(artifact, output)
    print(f"Saved Patna/Bihar research model to {output}")
    return output


if __name__ == "__main__":
    build_and_train_model()
