"""
backend/services/crawler/crawl_manager.py

CHANGES FROM v16:
  - Playwright crawlers (Croma+Reliance) run sequentially
  - Reviews scraped per product and saved via sentiment pipeline
  - Global rate limiter (30/hr)
  - Cache-aware return dict
"""
import asyncio
import logging
import time
import re

from backend.services.product_services import insert_platform_product
from backend.services.sentiment_engine import process_reviews
from backend.services.crawler.review_crawler import (
    scrape_amazon_reviews,
    scrape_croma_reviews,
    scrape_reliance_reviews,
    scrape_bigbasket_reviews,
)
from .amazon_crawler    import crawl_amazon
from .croma_crawler     import crawl_croma
from .reliance_crawler  import crawl_reliance
from .bigbasket_crawler import crawl_bigbasket

logger = logging.getLogger("shoppulse.crawler.manager")

_crawl_locks: dict[str, asyncio.Lock] = {}
_crawl_lock_master = asyncio.Lock()

async def _get_lock(query: str) -> asyncio.Lock:
    async with _crawl_lock_master:
        key = query.lower().strip()
        if key not in _crawl_locks:
            _crawl_locks[key] = asyncio.Lock()
        return _crawl_locks[key]

_RATE_LIMIT_MAX    = 30
_RATE_LIMIT_WINDOW = 3600
_crawl_timestamps: list[float] = []
_rate_lock = asyncio.Lock()

async def _check_rate_limit() -> bool:
    async with _rate_lock:
        now    = time.time()
        cutoff = now - _RATE_LIMIT_WINDOW
        while _crawl_timestamps and _crawl_timestamps[0] < cutoff:
            _crawl_timestamps.pop(0)
        if len(_crawl_timestamps) >= _RATE_LIMIT_MAX:
            logger.warning("CrawlManager: rate limit hit")
            return False
        _crawl_timestamps.append(now)
        return True

_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "Mobiles":      ["phone","mobile","iphone","samsung","oneplus","realme","xiaomi","redmi","oppo","vivo","pixel","motorola"],
    "Laptops":      ["laptop","notebook","macbook","chromebook","thinkpad","vivobook","asus","dell","hp pavilion"],
    "Electronics":  ["headphone","earphone","earbuds","airpods","speaker","trimmer","shaver","smartwatch",
                     "watch","tv","tablet","camera","lens","microphone","keyboard","mouse","router",
                     "projector","soundbar","powerbank","charger"],
    "Grocery":      ["rice","dal","atta","flour","oil","ghee","sugar","salt","spice","masala","pulse",
                     "lentil","tea","coffee","juice","biscuit","chocolate","chips","snack","noodles",
                     "pasta","bread","butter","milk","cheese","yogurt","curd"],
    "PersonalCare": ["shampoo","conditioner","face wash","moisturiser","moisturizer","sunscreen","serum",
                     "lipstick","foundation","perfume","deodorant","soap","body wash","toothpaste",
                     "lotion","toner","cleanser","hair oil","hair color"],
    "Footwear":     ["shoe","sneaker","boot","sandal","slipper","chappal"],
    "Clothing":     ["shirt","t-shirt","jeans","kurta","saree","jacket","hoodie","trouser","legging","dress"],
    "Appliances":   ["air conditioner","ac","split ac","inverter ac","washing machine","refrigerator",
                     "fridge","water purifier","water heater","geyser","ceiling fan","air purifier","dishwasher"],
    "Kitchen":      ["mixer","grinder","pressure cooker","pan","cooker","oven","juicer","toaster","kettle","microwave"],
    "Sports":       ["cricket","football","yoga","gym","fitness","cycle","bicycle","treadmill","dumbbell"],
}

_PLAYWRIGHT_CRAWLERS = {"croma", "reliance"}

_CATEGORY_CRAWLERS: dict[str, list[str]] = {
    "Mobiles":      ["amazon", "croma", "reliance"],
    "Laptops":      ["amazon", "croma", "reliance"],
    "Electronics":  ["amazon", "croma", "reliance"],
    "Grocery":      ["bigbasket", "amazon"],
    "PersonalCare": ["bigbasket", "amazon"],
    "Appliances":   ["amazon", "croma", "reliance"],
    "Footwear":     ["amazon"],
    "Clothing":     ["amazon"],
    "Kitchen":      ["amazon", "croma"],
    "Sports":       ["amazon"],
    "General":      ["amazon", "croma", "reliance", "bigbasket"],
}

_CRAWLER_FNS = {
    "amazon":    crawl_amazon,
    "croma":     crawl_croma,
    "reliance":  crawl_reliance,
    "bigbasket": crawl_bigbasket,
}

_CRAWLER_NAMES = {
    "amazon":    "Amazon",
    "croma":     "Croma",
    "reliance":  "Reliance Digital",
    "bigbasket": "BigBasket",
}


def _detect_category(query: str) -> str:
    q = query.lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(kw in q for kw in keywords):
            return category
    return "General"


def _dedup_within_platform(products: list[dict]) -> list[dict]:
    by_platform: dict[str, list[dict]] = {}
    for p in products:
        by_platform.setdefault(p.get("platform_name", ""), []).append(p)
    result = []
    for items in by_platform.values():
        seen_urls: set[str] = set()
        for item in items:
            url = item.get("product_url", "")
            if url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)
            result.append(item)
    return result


def _extract_asin(product_url: str) -> str:
    """Extract Amazon ASIN from product URL."""
    if not product_url:
        return ""
    m = re.search(r"/dp/([A-Z0-9]{10})", product_url)
    return m.group(1) if m else ""


async def _fetch_reviews_for_item(item: dict) -> list[dict]:
    """
    Fetch reviews for a single product based on its platform.
    Returns raw review dicts (before sentiment processing).
    """
    platform = item.get("platform_name", "")
    url      = item.get("product_url", "")
    rating   = item.get("rating")

    try:
        if platform == "Amazon":
            asin = _extract_asin(url)
            return await scrape_amazon_reviews(asin)

        elif platform == "Croma":
            return await scrape_croma_reviews(url)

        elif platform == "Reliance Digital":
            return await scrape_reliance_reviews(url)

        elif platform == "BigBasket":
            return await scrape_bigbasket_reviews(url, rating)

    except Exception as e:
        logger.warning(f"Review fetch failed for {platform}: {e}")

    return []


async def run_crawl(query: str, max_per_platform: int = 6, category_hint: str = None) -> dict:
    """
    Returns dict:
      {"status": "cached",  "ids": []}   — all caches fresh, read from DB
      {"status": "crawled", "ids": [...]} — fresh data saved
      {"status": "limited", "ids": []}   — rate limit hit
      {"status": "empty",   "ids": []}   — crawled but nothing saved
    """
    if not await _check_rate_limit():
        return {"status": "limited", "ids": []}

    lock = await _get_lock(query)
    async with lock:
        category     = category_hint if category_hint else _detect_category(query)
        crawler_keys = _CATEGORY_CRAWLERS.get(category, _CATEGORY_CRAWLERS["General"])
        fast_keys    = [k for k in crawler_keys if k not in _PLAYWRIGHT_CRAWLERS]
        slow_keys    = [k for k in crawler_keys if k in _PLAYWRIGHT_CRAWLERS]

        all_products: list[dict] = []
        all_cached = True

        # Fast crawlers in parallel (requests-based)
        if fast_keys:
            fast_results = await asyncio.gather(
                *[_CRAWLER_FNS[k](query, max_per_platform) for k in fast_keys],
                return_exceptions=True,
            )
            for key, result in zip(fast_keys, fast_results):
                if isinstance(result, Exception):
                    logger.error(f"CrawlManager: {_CRAWLER_NAMES[key]} error: {result}")
                elif isinstance(result, list):
                    if result:
                        all_cached = False
                    logger.info(f"CrawlManager: {_CRAWLER_NAMES[key]} → {len(result)} items")
                    all_products.extend(result)

        # Playwright crawlers SEQUENTIALLY
        for key in slow_keys:
            try:
                result = await _CRAWLER_FNS[key](query, max_per_platform)
                if result:
                    all_cached = False
                logger.info(f"CrawlManager: {_CRAWLER_NAMES[key]} → {len(result)} items")
                all_products.extend(result)
            except Exception as e:
                logger.error(f"CrawlManager: {_CRAWLER_NAMES[key]} error: {e}")

        if all_cached and not all_products:
            logger.info(f"CrawlManager: all caches fresh for '{query}'")
            return {"status": "cached", "ids": []}

        deduped = _dedup_within_platform(all_products)
        logger.info(f"CrawlManager: {len(all_products)} total → {len(deduped)} after dedup")

        saved_ids: list[str] = []
        platform_counts: dict[str, int] = {}

        for item in deduped:
            name  = (item.get("product_name") or "").strip()
            price = item.get("price")
            plat  = item.get("platform_name", "")
            if not name or not price:
                continue

            try:
                # Fetch reviews for this product
                raw_reviews  = await _fetch_reviews_for_item(item)
                # Run sentiment analysis + fake detection
                proc_reviews = process_reviews(raw_reviews) if raw_reviews else []

                saved = insert_platform_product(
                    product_name=name,
                    price=price,
                    platform_name=plat,
                    rating=item.get("rating"),
                    product_url=item.get("product_url"),
                    image_url=item.get("image_url"),
                    category=category,
                    reviews=proc_reviews,
                )
                mid = saved.get("master_product_id")
                if mid and mid not in saved_ids:
                    saved_ids.append(mid)
                platform_counts[plat] = platform_counts.get(plat, 0) + 1

            except Exception as e:
                logger.error(f"CrawlManager: insert failed '{name[:40]}': {e}")

        logger.info(f"CrawlManager: saved {platform_counts}")
        return {"status": "crawled" if saved_ids else "empty", "ids": saved_ids}
