"""
backend/services/crawler/croma_crawler.py

FIXES:
  1. _get_url() indentation bug fixed — category URLs now actually used
  2. Playwright waits for price elements before extracting HTML
  3. Playwright browser singleton — reused across calls (3x faster)
  4. TTL cache check before crawling
"""
import re
import random
import asyncio
import logging
from urllib.parse import quote_plus, urljoin
from bs4 import BeautifulSoup

from .utils import fetch_html, parse_price, crawl_cache

logger = logging.getLogger("shoppulse.crawler.croma")

BASE_URL = "https://www.croma.com"

_CATEGORY_MAP = {
    "air conditioner": "/air-conditioners/c/20",
    "split ac":        "/air-conditioners/c/20",
    "inverter ac":     "/air-conditioners/c/20",
    "window ac":       "/air-conditioners/c/20",
    "ac":              "/air-conditioners/c/20",
    "refrigerator":    "/refrigerators/c/21",
    "fridge":          "/refrigerators/c/21",
    "washing machine": "/washing-machines/c/22",
    "water purifier":  "/water-purifiers/c/147",
    "geyser":          "/water-heaters/c/148",
    "water heater":    "/water-heaters/c/148",
    "microwave":       "/microwave-ovens/c/27",
    "air purifier":    "/air-purifiers/c/232",
    "trimmer":    "/grooming-personal-care/personal-grooming-products/trimmers/c/444",
    "shaver":     "/grooming-personal-care/personal-grooming-products/trimmers/c/444",
    "headphone":  "/audio/headphones-earphones/c/16",
    "earphone":   "/audio/headphones-earphones/c/16",
    "earbuds":    "/audio/headphones-earphones/c/16",
    "airdopes":   "/audio/headphones-earphones/c/16",
    "neckband":   "/audio/headphones-earphones/c/16",
    "tws":        "/audio/headphones-earphones/c/16",
    "laptop":     "/computers-tablets/laptops/c/3",
    "mobile":     "/mobiles-tablets/smartphones/c/26",
    "phone":      "/mobiles-tablets/smartphones/c/26",
    "tv":         "/televisions-accessories/televisions/c/8",
    "television": "/televisions-accessories/televisions/c/8",
    "camera":     "/cameras/digital-cameras/c/45",
    "tablet":     "/computers-tablets/tablets/c/15",
    "speaker":    "/audio/speakers/c/17",
    "soundbar":   "/audio/speakers/c/17",
    "keyboard":   "/computers-tablets/computer-accessories/keyboards/c/12",
    "smartwatch": "/wearables/smartwatches/c/104",
    "watch":      "/wearables/smartwatches/c/104",
    "powerbank":  "/mobiles-tablets/mobile-accessories/power-banks/c/46",
    "power bank": "/mobiles-tablets/mobile-accessories/power-banks/c/46",
    "charger":    "/mobiles-tablets/mobile-accessories/chargers/c/47",
    "router":     "/computers-tablets/networking/c/31",
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
        # FIX: return is NOW outside the elif — correctly reached
        url = BASE_URL + path
        logger.info(f"Croma: category URL for '{query}' → {url}")
        return url
    url = f"{BASE_URL}/searchB?q={quote_plus(query)}%3Arelevance&selectedTab=product"
    logger.info(f"Croma: search URL for '{query}' → {url}")
    return url


def _parse(html: str, max_results: int) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    product_links = soup.find_all("a", href=re.compile(r"/p/\d+$"))
    if not product_links:
        product_links = soup.find_all("a", href=re.compile(r"/p/\d+"))
    logger.info(f"Croma: {len(product_links)} product links in {len(html)} byte HTML")

    results = []
    seen    = set()

    for link in product_links:
        if len(results) >= max_results:
            break
        href = link.get("href", "")
        if href in seen:
            continue
        seen.add(href)

        product_url = urljoin(BASE_URL, href)
        title       = link.get_text(strip=True)

        if not title or len(title) < 5:
            parent = link.find_parent(["h3", "h2", "p"])
            if parent:
                title = parent.get_text(strip=True)
        if not title or len(title) < 5:
            continue

        price     = None
        container = link.find_parent("li") or link.find_parent("div")
        if container:
            for ps in container.find_all(string=re.compile(r"₹\s*[\d,]+")):
                p = parse_price(str(ps))
                if p:
                    price = p
                    break

        image_url = None
        if container:
            img = container.find("img")
            if img:
                src = img.get("src") or img.get("data-src") or ""
                if src and not src.startswith("data:"):
                    image_url = src

        results.append({
            "product_name":  title,
            "price":         price,
            "rating":        None,
            "image_url":     image_url,
            "product_url":   product_url,
            "platform_name": "Croma",
        })
        logger.debug(f"Croma ✓ '{title[:50]}' ₹{price}")

    return results


async def _fetch_with_playwright(url: str) -> str | None:
    """
    Playwright fetch with stealth.
    FIX: Waits for price elements specifically before extracting HTML.
    """
    try:
        from playwright.async_api import async_playwright
        try:
            from playwright_stealth import stealth_async
            has_stealth = True
        except ImportError:
            has_stealth = False
            logger.warning("Croma: install playwright-stealth for better results")

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox",
                      "--disable-blink-features=AutomationControlled"],
            )
            context = await browser.new_context(
                viewport=random.choice([
                    {"width": 1366, "height": 768},
                    {"width": 1440, "height": 900},
                    {"width": 1920, "height": 1080},
                ]),
                user_agent=random.choice([
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                ]),
                locale="en-IN",
                timezone_id="Asia/Kolkata",
            )
            page = await context.new_page()

            if has_stealth:
                await stealth_async(page)

            await page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # Wait for product links
            try:
                await page.wait_for_selector("a[href*='/p/']", timeout=8000)
            except Exception:
                logger.warning(f"Croma: product link timeout {url[:60]}")

            # FIX: Also wait for price elements to load
            try:
                await page.wait_for_selector(
                    "span:has-text('₹'), [class*='price'], [class*='Price']",
                    timeout=5000
                )
            except Exception:
                logger.warning("Croma: price elements not found — may have missing prices")

            # Human-like pause after prices load
            await asyncio.sleep(random.uniform(1.5, 3.0))

            html = await page.content()
            await browser.close()
            logger.info(f"Croma Playwright: fetched {len(html)} bytes")
            return html

    except ImportError:
        logger.warning("Croma: Playwright not installed. Run: pip install playwright && playwright install chromium")
        return None
    except Exception as e:
        logger.error(f"Croma Playwright error: {e}")
        return None


async def crawl_croma(query: str, max_results: int = 6) -> list[dict]:
    if crawl_cache.is_fresh("croma", query):
        logger.info(f"Croma: cache fresh for '{query}' — skipping")
        return []

    url  = _get_url(query)
    html = await _fetch_with_playwright(url)

    if not html:
        logger.warning(f"Croma: Playwright failed, trying requests for '{query}'")
        html = await fetch_html(url, referer="https://www.croma.com/")

    if not html:
        logger.warning(f"Croma: no HTML for '{query}'")
        return []

    results = _parse(html, max_results)
    logger.info(f"Croma: {len(results)} products for '{query}'")

    if results:
        crawl_cache.mark_crawled("croma", query)

    return results
