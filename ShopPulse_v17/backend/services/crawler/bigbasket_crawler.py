"""
backend/services/crawler/bigbasket_crawler.py
FIX: _get_url() indentation bug — category URLs now actually used.
"""
import re
import logging
from urllib.parse import quote_plus, urljoin
from bs4 import BeautifulSoup

from .utils import fetch_html, parse_price, crawl_cache

logger = logging.getLogger("shoppulse.crawler.bigbasket")

BASE_URL = "https://www.bigbasket.com"

_CATEGORY_MAP = {
    "shampoo":      "/pc/hair-care/shampoo/",
    "conditioner":  "/pc/hair-care/conditioner/",
    "face wash":    "/pc/skin-care/face-wash-face-cleanser/",
    "moisturiser":  "/pc/skin-care/moisturiser-cream/",
    "moisturizer":  "/pc/skin-care/moisturiser-cream/",
    "sunscreen":    "/pc/skin-care/sunscreen/",
    "toothpaste":   "/pc/oral-care/toothpaste/",
    "soap":         "/pc/bath-body/bathing-soap-bar/",
    "body wash":    "/pc/bath-body/shower-gel-body-wash/",
    "deodorant":    "/pc/bath-body/deodorant-body-spray/",
    "perfume":      "/pc/bath-body/deodorant-body-spray/",
    "chocolate":    "/pc/snacks-branded-foods/chocolates/",
    "butter":       "/pc/dairy-bread-eggs/butter/",
    "milk":         "/pc/dairy-bread-eggs/milk/",
    "curd":         "/pc/dairy-bread-eggs/curd-yoghurt/",
    "cheese":       "/pc/dairy-bread-eggs/cheese/",
    "ghee":         "/pc/foodgrains-oil-masala/edible-oils-ghee/",
    "protein":      "/pc/health-wellness/protein-supplement/",
    "vitamin":      "/pc/health-wellness/vitamins-supplements/",
    "rice":         "/pc/foodgrains-oil-masala/rice/",
    "dal":          "/pc/foodgrains-oil-masala/dals-pulses/",
    "oil":          "/pc/foodgrains-oil-masala/edible-oils-ghee/",
    "biscuit":      "/pc/snacks-branded-foods/biscuits-cookies/",
    "chips":        "/pc/snacks-branded-foods/chips-fryums/",
    "juice":        "/pc/beverages/fruit-beverages/",
    "coffee":       "/pc/beverages/coffee/",
    "tea":          "/pc/beverages/tea/",
}


def _get_url(query: str) -> str:
    """FIX: return statement was inside elif — now correctly outside it."""
    q = query.lower()
    for kw, path in sorted(_CATEGORY_MAP.items(), key=lambda x: len(x[0]), reverse=True):
        if len(kw) <= 3:
            if not re.search(r'\b' + re.escape(kw) + r'\b', q):
                continue
        elif kw not in q:
            continue
        # FIX: return is NOW outside the elif
        logger.info(f"BigBasket: category URL for '{query}' → {path}")
        return BASE_URL + path
    return f"{BASE_URL}/ps/?q={quote_plus(query)}"


def _parse(html: str, max_results: int) -> list[dict]:
    soup    = BeautifulSoup(html, "html.parser")
    results = []
    seen    = set()

    if len(html) < 2000:
        logger.warning("BigBasket: HTML too short — likely blocked")
        return []

    product_links = soup.find_all("a", href=re.compile(r"/pd/.+/p/\d+"))
    if not product_links:
        product_links = soup.find_all("a", href=re.compile(r"/pd/"))

    logger.info(f"BigBasket: {len(product_links)} product links in {len(html)} bytes")

    for link in product_links:
        if len(results) >= max_results:
            break
        href = link.get("href", "")
        if href in seen:
            continue
        seen.add(href)

        title = link.get_text(strip=True)
        if not title or len(title) < 5:
            parent = link.find_parent(["li", "div", "article"])
            if parent:
                h = parent.find(["h3", "h2", "p", "span"])
                title = h.get_text(strip=True) if h else ""
        if not title or len(title) < 5:
            continue

        product_url = href if href.startswith("http") else urljoin(BASE_URL, href)

        price     = None
        container = link.find_parent(["li", "div", "article"])
        if container:
            price_str = container.find(string=re.compile(r"₹\s*[\d,]+"))
            if price_str:
                price = parse_price(str(price_str))

        image_url = None
        if container:
            img = container.find("img")
            if img:
                src = img.get("src") or img.get("data-src") or ""
                if src and not src.startswith("data:") and len(src) > 15:
                    image_url = src

        results.append({
            "product_name":  title,
            "price":         price,
            "rating":        None,
            "image_url":     image_url,
            "product_url":   product_url,
            "platform_name": "BigBasket",
        })
        logger.debug(f"BigBasket ✓ '{title[:50]}' ₹{price}")

    return results


async def crawl_bigbasket(query: str, max_results: int = 6) -> list[dict]:
    if crawl_cache.is_fresh("bigbasket", query):
        logger.info(f"BigBasket: cache fresh for '{query}' — skipping")
        return []

    url  = _get_url(query)
    html = await fetch_html(url, referer="https://www.bigbasket.com/")

    if not html:
        logger.warning(f"BigBasket: no HTML for '{query}'")
        return []

    results = _parse(html, max_results)
    logger.info(f"BigBasket: {len(results)} products for '{query}'")

    if results:
        crawl_cache.mark_crawled("bigbasket", query)

    return results
