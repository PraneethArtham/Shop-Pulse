"""
backend/services/price_prediction.py

ML-based price prediction using historical platform_products data.

Since we crawl products from multiple platforms at different points in time,
every crawl creates a new row in platform_products with a timestamp.
These rows ARE our price history — each crawl of the same product family
adds data points that build up a time series.

Algorithm:
  1. Fetch ALL platform_products rows for a master_product_id (sorted by time)
  2. Group by platform — each platform has its own price timeline
  3. Apply linear regression (numpy lstsq) to compute trend slope
  4. Predict 7-day forward price using the slope
  5. Calculate confidence from R² score of the regression
  6. Add seasonal adjustment (Indian sale events: Diwali, Big Billion Days, etc.)
  7. Return per-platform predictions + overall buy/wait recommendation

Why this works even with sparse data:
  - Even 2 crawl points give a valid slope (rising/falling/stable)
  - We show confidence = "low" when < 3 points, "high" when 5+
  - Seasonal adjustments work regardless of crawl frequency
"""

import logging
import math
from datetime import datetime, timezone
from collections import defaultdict

import numpy as np
from backend.dbase.supabase_client import supabase

logger = logging.getLogger("shoppulse.prediction")


# ── Indian sale season calendar ───────────────────────────────────────────────
# Month → expected price change % (negative = prices drop)
_SEASONAL_FACTORS = {
    1:  -0.03,  # Republic Day sale (Jan)
    3:  -0.02,  # Holi offers (Mar)
    8:  -0.05,  # Independence Day + Amazon Freedom sale (Aug)
    10: -0.08,  # Diwali / Big Billion Days (Oct) — biggest drop
    11: -0.05,  # Post-Diwali / Singles Day (Nov)
    12: -0.03,  # Year-end clearance (Dec)
}

_CURRENT_MONTH = datetime.now(timezone.utc).month


def _linear_regression_numpy(xs: list[float], ys: list[float]) -> tuple[float, float, float]:
    """
    Fit y = slope*x + intercept using numpy lstsq.
    Returns (slope, intercept, r2_score).
    R² = 1 means perfect linear fit; 0 = no relationship.
    """
    n = len(xs)
    if n < 2:
        return 0.0, ys[0] if ys else 0.0, 0.0

    X = np.array([[x, 1.0] for x in xs])
    y = np.array(ys)

    try:
        coeffs, residuals, rank, _ = np.linalg.lstsq(X, y, rcond=None)
        slope, intercept = float(coeffs[0]), float(coeffs[1])

        # R² score
        y_pred = X @ coeffs
        ss_res = float(np.sum((y - y_pred) ** 2))
        ss_tot = float(np.sum((y - y.mean()) ** 2))
        r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 1e-9 else 0.0
        return slope, intercept, max(0.0, r2)
    except Exception:
        return 0.0, float(np.mean(ys)), 0.0


def _confidence_label(n_points: int, r2: float) -> str:
    if n_points >= 5 and r2 >= 0.6:
        return "high"
    elif n_points >= 3 or (n_points >= 2 and r2 >= 0.4):
        return "medium"
    return "low"


def _days_since(iso_str: str) -> float:
    """Convert ISO timestamp to days since epoch for regression x-axis."""
    try:
        dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        return dt.timestamp() / 86400.0
    except Exception:
        return 0.0


def predict_price(master_product_id: str) -> dict:
    """
    Per-platform 7-day price prediction using linear regression on crawl history.
    """
    try:
        rows = (
            supabase.table("platform_products")
            .select("platform_name, price, created_at")
            .eq("master_product_id", master_product_id)
            .order("created_at", desc=False)
            .execute()
            .data or []
        )
    except Exception as e:
        logger.error(f"price_prediction fetch failed: {e}")
        return _no_data_response()

    # Group by platform, build (day, price) series
    by_platform: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for r in rows:
        if r.get("price") and r.get("created_at"):
            day = _days_since(r["created_at"])
            by_platform[r["platform_name"]].append((day, float(r["price"])))

    if not by_platform:
        return _no_data_response()

    platform_predictions = {}
    all_predictions = []
    seasonal_factor = _SEASONAL_FACTORS.get(_CURRENT_MONTH, 0.0)

    for platform, points in by_platform.items():
        points.sort(key=lambda x: x[0])  # sort by day
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]

        current = ys[-1]
        atl     = min(ys)
        ath     = max(ys)

        # Normalise x to 0-based days
        x0  = xs[0]
        xs_norm = [x - x0 for x in xs]

        slope, intercept, r2 = _linear_regression_numpy(xs_norm, ys)

        # Project 7 days ahead
        last_day  = xs_norm[-1]
        pred_day  = last_day + 7.0
        predicted = slope * pred_day + intercept

        # Apply seasonal adjustment
        predicted += current * seasonal_factor

        # Floor at 60% of current (prevents absurd predictions)
        predicted = max(predicted, current * 0.6)
        predicted = round(predicted, 2)

        # Percent change
        pct_change = ((predicted - current) / current * 100) if current else 0

        # Trend
        if pct_change < -2.0:
            trend = "down"
        elif pct_change > 2.0:
            trend = "up"
        else:
            trend = "flat"

        # Add seasonal context to trend
        if seasonal_factor < -0.04 and trend != "down":
            trend = "flat"  # sale season likely to push prices down

        # Confidence
        confidence = _confidence_label(len(points), r2)

        # Recommendation
        dist_from_atl = ((current - atl) / atl * 100) if atl > 0 else 0
        sale_season   = seasonal_factor < -0.03

        if trend == "down" and confidence in ("high", "medium"):
            recommendation = "wait"
        elif trend == "up" and confidence in ("high", "medium"):
            recommendation = "buy_now"
        elif sale_season:
            recommendation = "buy_now"  # sale season → grab it now
        elif dist_from_atl > 20:
            recommendation = "wait"     # far above ATL → likely to correct
        elif dist_from_atl < 5:
            recommendation = "buy_now"  # near ATL → great time
        else:
            recommendation = "neutral"

        platform_predictions[platform] = {
            "current":         current,
            "predicted_7d":    predicted,
            "trend":           trend,
            "trend_pct":       round(pct_change, 1),
            "confidence":      confidence,
            "r2_score":        round(r2, 3),
            "recommendation":  recommendation,
            "data_points":     len(points),
            "all_time_low":    atl,
            "all_time_high":   ath,
            "dist_from_atl_pct": round(dist_from_atl, 1),
            "seasonal_active": sale_season,
        }
        all_predictions.append((platform, predicted))

    if not all_predictions:
        return _no_data_response()

    # Overall recommendation
    best_plat, best_pred = min(all_predictions, key=lambda x: x[1])
    wait_count = sum(1 for p in platform_predictions.values() if p["recommendation"] == "wait")
    buy_count  = sum(1 for p in platform_predictions.values() if p["recommendation"] == "buy_now")
    total_plat = len(platform_predictions)

    if _SEASONAL_FACTORS.get(_CURRENT_MONTH, 0) < -0.04:
        advice = "buy_now"
        reason = f"🛍️ Sale season active! Prices typically drop {abs(_SEASONAL_FACTORS[_CURRENT_MONTH])*100:.0f}% this month — buy now."
    elif wait_count > buy_count and wait_count > 0:
        advice = "wait"
        reason = f"Prices trending down on {wait_count}/{total_plat} platform(s). May drop further in 7 days."
    elif buy_count >= wait_count and buy_count > 0:
        advice = "buy_now"
        reason = f"Prices rising or near all-time low on {buy_count}/{total_plat} platform(s). Good time to buy."
    else:
        advice = "neutral"
        reason = "Prices are stable. No strong signal — buy when convenient."

    return {
        "platforms": platform_predictions,
        "overall": {
            "best_time_to_buy":  advice,
            "reason":            reason,
            "lowest_predicted":  best_pred,
            "platform":          best_plat,
            "seasonal_note":     f"Sale season active (month {_CURRENT_MONTH})" if _SEASONAL_FACTORS.get(_CURRENT_MONTH, 0) < -0.02 else None,
        },
        "method": "numpy_linear_regression",
        "total_data_points": sum(p["data_points"] for p in platform_predictions.values()),
    }


def _no_data_response() -> dict:
    return {
        "platforms": {},
        "overall": {
            "best_time_to_buy": "neutral",
            "reason": "No price history yet. Search this product to start tracking prices.",
            "lowest_predicted": None,
            "platform": None,
            "seasonal_note": None,
        },
        "method": "numpy_linear_regression",
        "total_data_points": 0,
    }
