"""Small transparent scoring helpers for the additive Aegis community and estimate UI."""
from __future__ import annotations
from datetime import datetime, timezone


def confidence_assessment(*, observed_fields: int, fresh_fields: int, target_in_region: bool, trained_model: bool,
                         median_filled: bool, weather_available: bool, discharge_available: bool) -> dict:
    """A deliberately conservative data-coverage indicator, not model accuracy."""
    coverage = max(0, min(3, int(observed_fields))) / 3
    freshness = max(0, min(3, int(fresh_fields))) / 3
    score = round(coverage * 0.6 + freshness * 0.4, 2)
    label = "medium" if target_in_region and trained_model and not median_filled and score >= 0.65 else "low"
    formula = ("0.6 × observed input coverage fraction + 0.4 × recently returned provider fields / 3; "
               "independent-source agreement contributes no points because it cannot be assessed; capped at medium; "
               "low outside approximate Patna coverage, on fallback, or with median-filled inputs.")
    return {"label": label, "score": score, "coverage_fraction": round(coverage, 2),
            "agreement": "not assessable: no independent, comparable local observation feed configured",
            "formula": formula}


def community_trust(item: dict, rows: list[dict], *, now: datetime | None = None) -> tuple[int, float]:
    """Bounded heuristic from crowd feedback, pseudonymous history and age; never verification."""
    now = now or datetime.now(timezone.utc)
    confirms, disputes = int(item.get("confirmations", 0)), int(item.get("disputes", 0))
    created = datetime.fromisoformat(item["created_at"].replace("Z", "+00:00"))
    age_hours = max(0, (now - created.astimezone(timezone.utc)).total_seconds() / 3600)
    reporter = item.get("reporter_id", "")
    history = [row for row in rows if reporter and row.get("reporter_id") == reporter]
    history_confirm = sum(int(row.get("confirmations", 0)) for row in history)
    history_dispute = sum(int(row.get("disputes", 0)) for row in history)
    score = 50 + min(20, confirms * 5) - min(30, disputes * 10) + min(10, history_confirm) - min(15, history_dispute) - min(15, age_hours / 24)
    return round(max(0, min(100, score))), round(age_hours, 1)
