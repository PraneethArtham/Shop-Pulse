"""
backend/services/product_aggregator.py

Full product aggregation pipeline — fixed N+1 query problem.
Previously: fetched reviews in a per-listing loop (N queries).
Now: fetches ALL reviews for the product in ONE query, then joins in Python.
"""

import logging
from collections import defaultdict
from backend.dbase.supabase_client import supabase
from backend.services.verification import compute_verification_score

logger = logging.getLogger("shoppulse.aggregator")


def _safe_fetch_one(table: str, col: str, val: str) -> dict | None:
    try:
        res = supabase.table(table).select("*").eq(col, val).limit(1).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        logger.warning(f"_safe_fetch_one({table}, {col}={val}): {e}")
        return None


def get_product_full_details(master_product_id: str) -> dict | None:
    # ── 1. Master product ──────────────────────────────────
    product = _safe_fetch_one("master_products", "master_product_id", master_product_id)
    if not product:
        return None

    # ── 2. All platform listings in one query ──────────────
    try:
        platform_rows = (
            supabase.table("platform_products")
            .select("*")
            .eq("master_product_id", master_product_id)
            .execute()
            .data or []
        )
    except Exception as e:
        logger.error(f"platform_products query failed: {e}")
        platform_rows = []

    # ── 3. Batch-fetch all reviews (single query) ──────────
    platform_ids = [p["platform_product_id"] for p in platform_rows]
    reviews_by_platform: dict[str, list] = defaultdict(list)
    if platform_ids:
        try:
            all_reviews = (
                supabase.table("reviews")
                .select("*")
                .in_("platform_product_id", platform_ids)
                .order("created_at", desc=True)
                .execute()
                .data or []
            )
            for r in all_reviews:
                reviews_by_platform[r["platform_product_id"]].append(r)
        except Exception as e:
            logger.warning(f"reviews batch-fetch failed: {e}")

    # ── 4. Batch-fetch sellers ─────────────────────────────
    seller_ids = list({p["seller_id"] for p in platform_rows if p.get("seller_id")})
    sellers_by_id: dict[str, dict] = {}
    if seller_ids:
        try:
            seller_rows = (
                supabase.table("sellers")
                .select("*")
                .in_("seller_id", seller_ids)
                .execute()
                .data or []
            )
            sellers_by_id = {s["seller_id"]: s for s in seller_rows}
        except Exception as e:
            logger.warning(f"sellers batch-fetch failed: {e}")

    # ── 5. Assemble platform data ──────────────────────────
    platform_data = []
    for item in platform_rows:
        pid = item["platform_product_id"]
        item["seller"]  = sellers_by_id.get(item.get("seller_id") or "")
        item["reviews"] = reviews_by_platform.get(pid, [])
        item["verification_score"] = compute_verification_score(item)
        platform_data.append(item)

    platform_data.sort(key=lambda x: x.get("price") or float("inf"))

    # ── 6. Aggregated stats ────────────────────────────────
    prices  = [p["price"] for p in platform_data if p.get("price")]
    ratings = [p["rating"] for p in platform_data if p.get("rating")]
    all_reviews_flat = [r for p in platform_data for r in p.get("reviews", [])]
    review_ratings = [r["review_rating"] for r in all_reviews_flat if r.get("review_rating")]

    stats = {
        "platform_count":   len(platform_data),
        "best_price":       min(prices) if prices else None,
        "worst_price":      max(prices) if prices else None,
        "max_savings":      round(max(prices) - min(prices), 2) if len(prices) >= 2 else 0,
        "avg_rating":       round(sum(ratings) / len(ratings), 2) if ratings else None,
        "review_count":     len(all_reviews_flat),
        "avg_review_score": round(sum(review_ratings) / len(review_ratings), 2) if review_ratings else None,
        "fake_review_count":sum(1 for r in all_reviews_flat if r.get("is_fake")),
    }

    # ── 7. Local stores ────────────────────────────────────
    try:
        local_rows = (
            supabase.table("local_store_products")
            .select("*")
            .eq("master_product_id", master_product_id)
            .execute()
            .data or []
        )
    except Exception:
        local_rows = []

    # Batch-fetch stores
    store_ids = list({item["store_id"] for item in local_rows if item.get("store_id")})
    stores_by_id: dict[str, dict] = {}
    if store_ids:
        try:
            store_rows = (
                supabase.table("local_stores")
                .select("*")
                .in_("store_id", store_ids)
                .execute()
                .data or []
            )
            stores_by_id = {s["store_id"]: s for s in store_rows}
        except Exception as e:
            logger.warning(f"local_stores batch-fetch failed: {e}")

    local_data = []
    for item in local_rows:
        item["store"]    = stores_by_id.get(item.get("store_id") or "")
        qty = item.get("stock_quantity")
        item["in_stock"] = bool(qty and qty > 0)
        local_data.append(item)

    return {
        "product":              product,
        "stats":                stats,
        "platform_listings":    platform_data,
        "local_store_listings": local_data,
    }
