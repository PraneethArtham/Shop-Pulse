"""
backend/services/sentiment_engine.py

Sentiment analysis + fake review detection for crawled reviews.
Uses vaderSentiment — free, offline, no API key needed.
Works well for Indian English product reviews.

Install: pip install vaderSentiment

Sentiment score: -1.0 (very negative) to +1.0 (very positive)
  >= 0.5  → Positive 😊
  0.0–0.5 → Neutral  😐
  < 0.0   → Negative 😞

Fake detection flags:
  - Review text under 10 chars (too short to be genuine)
  - ALL CAPS (bot signal)
  - Rating inconsistency (5 stars but very negative text, or vice versa)
  - Duplicate text across reviews
"""
import re
import logging
from typing import Optional

logger = logging.getLogger("shoppulse.sentiment")

# ── Load VADER (graceful fallback if not installed) ────────────
try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    _analyzer = SentimentIntensityAnalyzer()
    _VADER_AVAILABLE = True
    logger.info("Sentiment engine: VADER loaded successfully")
except ImportError:
    _analyzer = None
    _VADER_AVAILABLE = False
    logger.warning(
        "vaderSentiment not installed. Sentiment scores will be neutral (0.5). "
        "Run: pip install vaderSentiment"
    )


def analyse_sentiment(text: str) -> float:
    """
    Returns compound sentiment score: -1.0 to +1.0
    Mapped to 0.0–1.0 for storage: (compound + 1) / 2
    0.0 = most negative, 0.5 = neutral, 1.0 = most positive
    """
    if not text or not text.strip():
        return 0.5

    if not _VADER_AVAILABLE:
        return 0.5

    try:
        scores = _analyzer.polarity_scores(text)
        compound = scores["compound"]  # -1.0 to +1.0
        return round((compound + 1) / 2, 4)  # map to 0–1
    except Exception as e:
        logger.warning(f"Sentiment analysis failed: {e}")
        return 0.5


def is_fake_review(
    review_text: Optional[str],
    review_rating: float,
    sentiment_score: float,
    seen_texts: set[str],
) -> bool:
    """
    Returns True if review shows fake/suspicious signals.

    Checks:
    1. Too short (< 10 chars)
    2. ALL CAPS
    3. Rating-sentiment mismatch (5 stars + very negative text, or 1 star + very positive)
    4. Duplicate text
    """
    if not review_text:
        return False

    text = review_text.strip()

    # 1. Too short to be meaningful
    if len(text) < 10:
        return True

    # 2. ALL CAPS (bot signal)
    alpha = re.sub(r'[^a-zA-Z]', '', text)
    if len(alpha) > 5 and alpha == alpha.upper():
        return True

    # 3. Rating-sentiment mismatch
    # High rating (4–5) but very negative sentiment
    if review_rating >= 4.0 and sentiment_score < 0.2:
        return True
    # Low rating (1–2) but very positive sentiment
    if review_rating <= 2.0 and sentiment_score > 0.8:
        return True

    # 4. Duplicate text
    text_lower = text.lower()
    if text_lower in seen_texts:
        return True

    return False


def process_reviews(raw_reviews: list[dict]) -> list[dict]:
    """
    Takes raw review dicts from crawlers and enriches them with:
    - sentiment_score (0–1)
    - is_fake (bool)

    Raw review format from crawlers:
    {
        "review_text":   str or None,
        "review_rating": float (1–5),
        "platform_name": str,   (for logging only)
    }

    Returns enriched list ready for DB insert.
    """
    if not raw_reviews:
        return []

    seen_texts: set[str] = set()
    processed = []

    for rev in raw_reviews:
        text   = (rev.get("review_text") or "").strip() or None
        rating = float(rev.get("review_rating") or 3.0)
        rating = max(1.0, min(5.0, rating))

        sentiment = analyse_sentiment(text) if text else 0.5

        fake = is_fake_review(text, rating, sentiment, seen_texts)

        if text:
            seen_texts.add(text.lower())

        processed.append({
            "review_text":    text,
            "review_rating":  rating,
            "sentiment_score": sentiment,
            "is_fake":        fake,
        })

    pos  = sum(1 for r in processed if r["sentiment_score"] >= 0.6)
    neg  = sum(1 for r in processed if r["sentiment_score"] < 0.4)
    fake = sum(1 for r in processed if r["is_fake"])
    logger.info(
        f"Sentiment: {len(processed)} reviews — "
        f"{pos} positive, {neg} negative, {fake} flagged fake"
    )

    return processed
