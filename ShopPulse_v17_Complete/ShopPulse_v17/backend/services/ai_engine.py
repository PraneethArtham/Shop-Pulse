"""
backend/services/ai_engine.py

NOTE: This module is available for future use but is NOT currently wired 
into any API routes.

- Per-listing verification: use verification.py (called from product_aggregator.py)
- Price prediction: use price_prediction.py (called from routes/products.py)

The functions here provide product-level (not listing-level) analysis
using direct DB queries. They can be enabled for richer AI endpoints later.
"""

import logging
import statistics
from backend.dbase.supabase_client import supabase

logger = logging.getLogger("shoppulse.ai")


def compute_product_trust_score(master_product_id: str) -> dict:
    """
    Compute a product-level 0–100 trust score by aggregating across all listings.
    More thorough than per-listing scores in verification.py.
    Use this for a /products/{id}/trust-score endpoint if needed.
    """
    try:
        platforms = (
            supabase.table("platform_products")
            .select("platform_product_id, seller_id, price, rating, created_at")
            .eq("master_product_id", master_product_id)
            .execute().data or []
        )
    except Exception as e:
        logger.warning(f"compute_product_trust_score: fetch failed: {e}")
        return {"score": 0, "grade": "N/A", "trust_level": "Unknown"}

    if not platforms:
        return {"score": 0, "grade": "N/A", "trust_level": "Unknown"}

    platform_ids = [p["platform_product_id"] for p in platforms]

    try:
        all_reviews = []
        for pid in platform_ids:
            rows = (
                supabase.table("reviews").select("*")
                .eq("platform_product_id", pid).execute().data or []
            )
            all_reviews.extend(rows)
    except Exception:
        all_reviews = []

    # Review credibility (0–40)
    if all_reviews:
        fake_count = sum(1 for r in all_reviews if r.get("is_fake"))
        legit_pct  = (len(all_reviews) - fake_count) / len(all_reviews)
        sentiments = [r["sentiment_score"] for r in all_reviews if r.get("sentiment_score") is not None]
        sent_var   = min(1.0, statistics.stdev(sentiments) / 0.4) if len(sentiments) >= 2 else 0.5
        review_score = round((legit_pct * 0.7 + sent_var * 0.3) * 40)
    else:
        review_score = 20

    # Price stability (0–15)
    prices = sorted(
        [(p["price"], p["created_at"]) for p in platforms if p.get("price") and p.get("created_at")],
        key=lambda x: x[1]
    )
    if len(prices) >= 3:
        vals = [p[0] for p in prices]
        pct_changes = [
            abs(vals[i] - vals[i-1]) / vals[i-1]
            for i in range(1, len(vals)) if vals[i-1] > 0
        ]
        avg_change  = statistics.mean(pct_changes) if pct_changes else 0
        price_score = round(max(0, 1 - avg_change / 0.20) * 15)
    else:
        price_score = 10

    total = review_score + price_score + 20 + 15  # neutral seller + rating defaults
    total = min(100, max(0, total))
    grade = "A" if total >= 80 else "B" if total >= 65 else "C" if total >= 50 else "D"

    return {
        "score":       total,
        "grade":       grade,
        "trust_level": "High" if total >= 75 else "Medium" if total >= 50 else "Low",
    }
