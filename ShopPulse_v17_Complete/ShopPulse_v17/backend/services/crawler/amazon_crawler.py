"""
backend/services/crawler/amazon_crawler.py

Amazon India search results crawler.
UNCHANGED from original — working perfectly.

ADDITIONS:
  - TTL cache check (skip crawl if crawled within 8 hours)
  - Slightly longer delays already handled in utils.py

Confirmed stable selectors:
  Container: div[data-asin][data-component-type='s-search-result']
  Title:     h2 span  OR  .a-size-base-plus  OR  .a-size-medium
  Price:     span.a-price > span.a-offscreen
  Rating:    span.a-icon-alt
  Image:     img.s-image
  URL:       h2 a.a-link-normal[href]  OR  a[href*='/dp/']
"""

import re
import logging
from urllib.parse import quote_plus
from bs4 import BeautifulSoup

from .utils import fetch_html, parse_price, crawl_cache

logger = logging.getLogger("shoppulse.crawler.amazon")

BASE_URL   = "https://www.amazon.in"
SEARCH_URL = BASE_URL + "/s?k={query}"


def _parse(html: str, max_results: int) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    results = []

    cards = soup.select("div[data-asin][data-component-type='s-search-result']")
    logger.info(f"Amazon: {len(cards)} product cards in {len(html)} byte HTML")

    for card in cards:
        if len(results) >= max_results:
            break

        asin = card.get("data-asin", "")
        if not asin:
            continue

        title_el = (
            card.select_one("h2 span")
            or card.select_one(".a-size-base-plus")
            or card.select_one(".a-size-medium")
        )
        title = title_el.get_text(strip=True) if title_el else None
        if not title or len(title) < 5:
            continue

        price_el = card.select_one("span.a-price > span.a-offscreen")
        price = parse_price(price_el.get_text() if price_el else "")

        rating_el = card.select_one("span.a-icon-alt")
        rating = None
        if rating_el:
            m = re.match(r"([\d.]+)", rating_el.get_text(strip=True))
            if m:
                try:
                    r = float(m.group(1))
                    rating = r if 1.0 <= r <= 5.0 else None
                except ValueError:
                    pass

        img_el = card.select_one("img.s-image")
        image_url = img_el.get("src") if img_el else None

        product_url = BASE_URL + "/dp/" + asin

        results.append({
            "product_name":  title,
            "price":         price,
            "rating":        rating,
            "image_url":     image_url,
            "product_url":   product_url,
            "platform_name": "Amazon",
        })
        logger.debug(f"Amazon ✓ '{title[:50]}' ₹{price} ★{rating}")

    return results


async def crawl_amazon(query: str, max_results: int = 6) -> list[dict]:
    # ── TTL Cache check ────────────────────────────────────────
    if crawl_cache.is_fresh("amazon", query):
        logger.info(f"Amazon: cache fresh for '{query}' — skipping crawl")
        return []

    url = SEARCH_URL.format(query=quote_plus(query))
    html = await fetch_html(url, referer="https://www.amazon.in/")
    if not html:
        logger.warning(f"Amazon: no HTML for '{query}'")
        return []

    results = _parse(html, max_results)
    logger.info(f"Amazon: {len(results)} products for '{query}'")

    # ── Mark as crawled ────────────────────────────────────────
    if results:
        crawl_cache.mark_crawled("amazon", query)

    return results
