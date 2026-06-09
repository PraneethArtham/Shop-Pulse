"""
backend/services/verification.py  (Issue 6 — AI verification score)

Computes a 0–100 trust score for a platform listing combining:
  1. Review credibility  — ratio of non-fake reviews, review count
  2. Rating consistency  — how close product rating is to review avg
  3. Price stability     — placeholder (improves with price history data)
  4. Seller reputation   — seller rating if available

Used in product_aggregator.get_product_full_details() per listing.
"""
import logging

logger = logging.getLogger("shoppulse.verification")


def compute_verification_score(platform_item: dict) -> dict:
    """
    Returns:
      {
        "score": 0-100,
        "grade": "A"/"B"/"C"/"D",
        "breakdown": { review_credibility, rating_consistency, seller_rep, price_signal },
        "flags": ["High fake review ratio", ...],
      }
    """
    flags = []

    # ── 1. Review credibility (0–40 pts) ──────────────────
    reviews      = platform_item.get("reviews", [])
    total_rev    = len(reviews)
    fake_count   = sum(1 for r in reviews if r.get("is_fake"))
    real_count   = total_rev - fake_count
    fake_ratio   = fake_count / total_rev if total_rev else 0

    if fake_ratio > 0.4:
        flags.append("High fake review ratio")
    if total_rev == 0:
        rev_score = 20   # neutral — no reviews yet
    else:
        base       = min(real_count / 10, 1.0)   # more real reviews → better
        fake_pen   = fake_ratio * 30              # penalty for fake reviews
        rev_score  = round((base * 40) - fake_pen)
        rev_score  = max(0, min(40, rev_score))

    # ── 2. Rating consistency (0–25 pts) ──────────────────
    product_rating = platform_item.get("rating")
    review_ratings = [r["review_rating"] for r in reviews if r.get("review_rating")]
    avg_review     = sum(review_ratings) / len(review_ratings) if review_ratings else None

    if product_rating and avg_review:
        diff = abs(product_rating - avg_review)
        if diff > 1.5:
            flags.append("Rating inconsistency detected")
        consistency = max(0, 25 - int(diff * 10))
    elif product_rating:
        consistency = 15   # some signal, no reviews to compare
    else:
        consistency = 10   # no rating at all

    # ── 3. Seller reputation (0–20 pts) ───────────────────
    seller        = platform_item.get("seller")
    seller_rating = float(seller["seller_rating"]) if seller and seller.get("seller_rating") else None

    if seller_rating:
        seller_score = round((seller_rating / 5.0) * 20)
    else:
        seller_score = 10   # neutral — no seller info

    # ── 4. Price signal (0–15 pts) ────────────────────────
    # Has product URL and price = legit listing
    has_url   = bool(platform_item.get("product_url"))
    has_price = bool(platform_item.get("price"))
    price_sig = 15 if (has_url and has_price) else (8 if has_price else 0)

    total = rev_score + consistency + seller_score + price_sig
    total = max(0, min(100, total))

    grade = "A" if total >= 80 else "B" if total >= 60 else "C" if total >= 40 else "D"

    return {
        "score": total,
        "grade": grade,
        "breakdown": {
            "review_credibility": rev_score,
            "rating_consistency": consistency,
            "seller_reputation":  seller_score,
            "price_signal":       price_sig,
        },
        "flags": flags,
    }
