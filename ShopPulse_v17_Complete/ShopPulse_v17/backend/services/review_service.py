"""
backend/services/review_service.py

CHANGES:
  - add_review() now checks for duplicate before inserting
  - save_crawled_reviews() — new batch save function for crawler pipeline
  - get_all_reviews_for_master() — fixed N+1 query (one call per platform_product was N queries)
"""
import uuid
import logging
from typing import Optional
from backend.dbase.supabase_client import supabase

logger = logging.getLogger("shoppulse.reviews")


def add_review(
    platform_product_id: str,
    review_rating: float,
    review_text: Optional[str] = None,
    sentiment_score: Optional[float] = None,
    is_fake: bool = False,
) -> dict:
    # Deduplication: skip if same text already exists for this platform_product
    if review_text:
        try:
            existing = (
                supabase.table("reviews")
                .select("review_id")
                .eq("platform_product_id", platform_product_id)
                .ilike("review_text", review_text[:200])
                .limit(1)
                .execute()
            )
            if existing.data:
                logger.debug(f"Review duplicate skipped for {platform_product_id[:12]}")
                return existing.data[0]
        except Exception:
            pass  # If check fails, still try to insert

    data = {
        "review_id":           str(uuid.uuid4()),
        "platform_product_id": platform_product_id,
        "review_text":         review_text,
        "review_rating":       review_rating,
        "sentiment_score":     sentiment_score,
        "is_fake":             is_fake,
    }
    supabase.table("reviews").insert(data).execute()
    return data


def save_crawled_reviews(
    platform_product_id: str,
    processed_reviews: list[dict],
) -> int:
    """
    Batch-save reviews from the crawler pipeline.
    processed_reviews should already have sentiment_score and is_fake
    (computed by sentiment_engine.process_reviews()).
    Returns count of reviews saved.
    """
    saved = 0
    for rev in processed_reviews:
        try:
            add_review(
                platform_product_id=platform_product_id,
                review_rating=rev.get("review_rating", 3.0),
                review_text=rev.get("review_text"),
                sentiment_score=rev.get("sentiment_score"),
                is_fake=rev.get("is_fake", False),
            )
            saved += 1
        except Exception as e:
            logger.warning(f"Failed to save review: {e}")
    return saved


def get_reviews_for_platform_product(platform_product_id: str) -> list:
    return (
        supabase.table("reviews")
        .select("*")
        .eq("platform_product_id", platform_product_id)
        .order("created_at", desc=True)
        .execute()
        .data or []
    )


def get_all_reviews_for_master(master_product_id: str) -> list:
    """
    FIX: Previously had N+1 — one query per platform_product.
    Now: fetch all platform_product_ids first, then one batch review query.
    """
    platform_products = (
        supabase.table("platform_products")
        .select("platform_product_id, platform_name")
        .eq("master_product_id", master_product_id)
        .execute()
        .data or []
    )

    if not platform_products:
        return []

    platform_map = {
        pp["platform_product_id"]: pp["platform_name"]
        for pp in platform_products
    }
    ids = list(platform_map.keys())

    # Single batch query for all reviews
    try:
        all_reviews = (
            supabase.table("reviews")
            .select("*")
            .in_("platform_product_id", ids)
            .order("created_at", desc=True)
            .execute()
            .data or []
        )
    except Exception as e:
        logger.warning(f"Batch review fetch failed: {e}")
        return []

    for r in all_reviews:
        r["platform_name"] = platform_map.get(r["platform_product_id"], "Unknown")

    return all_reviews
