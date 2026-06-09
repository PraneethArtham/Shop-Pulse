"""
backend/services/crawler/reliance_crawler.py

FIXES:
  1. _get_url() indentation bug fixed — collection URLs now actually used
  2. Playwright waits for price elements before extracting HTML
  3. TTL cache check before crawling
"""
import re
import random
import asyncio
import logging
from urllib.parse import quote_plus, urljoin
from bs4 import BeautifulSoup

from .utils import fetch_html, parse_price, crawl_cache

logger = logging.getLogger("shoppulse.crawler.reliance")

BASE_URL = "https://www.reliancedigital.in"

_CATEGORY_MAP = {
    "air conditioner": "/collection/air-conditioners",
    "split ac":        "/collection/air-conditioners",
    "inverter ac":     "/collection/air-conditioners",
    "window ac":       "/collection/air-conditioners",
    "ac":              "/collection/air-conditioners",
    "refrigerator":    "/collection/refrigerators",
    "fridge":          "/collection/refrigerators",
    "washing machine": "/collection/washing-machines",
    "water purifier":  "/collection/water-purifiers",
    "geyser":          "/collection/geysers",
    "water heater":    "/collection/geysers",
    "microwave":       "/collection/microwave-ovens",
    "air purifier":    "/collection/air-purifiers",
    "trimmer":    "/collection/shavers-trimmers",
    "shaver":     "/collection/shavers-trimmers",
    "headphone":  "/collection/headphones",
    "earphone":   "/collection/headphones",
    "earbuds":    "/collection/headphones",
    "airdopes":   "/collection/headphones",
    "neckband":   "/collection/headphones",
    "tws":        "/collection/headphones",
    "laptop":     "/collection/laptops",
    "mobile":     "/collection/mobiles",
    "phone":      "/collection/mobiles",
    "tv":         "/collection/televisions",
    "television": "/collection/televisions",
    "tablet":     "/collection/tablets",
    "speaker":    "/collection/speakers",
    "soundbar":   "/collection/speakers",
    "camera":     "/collection/cameras",
    "smartwatch": "/collection/smartwatches",
    "watch":      "/collection/smartwatches",
    "keyboard":   "/collection/computer-peripherals",
    "mouse":      "/collection/computer-peripherals",
    "powerbank":  "/collection/power-banks",
    "power bank": "/collection/power-banks",
    "charger":    "/collection/mobile-accessories",
    "router":     "/collection/networking",
    "projector":  "/collection/projectors",
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
        logger.info(f"Reliance: collection URL for '{query}' → {url}")
        return url
    url = f"{BASE_URL}/search?q={quote_plus(query)}"
    logger.info(f"Reliance: search URL for '{query}' → {url}")
    return url


def _parse(html: str, max_results: int) -> list[dict]:
    soup    = BeautifulSoup(html, "html.parser")
    results = []
    seen    = set()

    # PRIMARY: price list table
    table = soup.find("table")
    if table:
        rows = table.find_all("tr")
        for row in rows:
            if len(results) >= max_results:
                break
            cells = row.find_all("td")
            if len(cells) < 3:
                continue
            link = cells[1].find("a")
            if not link:
                continue
            title = link.get_text(strip=True)
            if not title or len(title) < 5:
                continue
            href = link.get("href", "")
            if not href or href in seen:
                continue
            seen.add(href)
            product_url = href if href.startswith("http") else urljoin(BASE_URL, href)
            price       = parse_price(cells[2].get_text())
            results.append({
                "product_name":  title,
                "price":         price,
                "rating":        None,
                "image_url":     None,
                "product_url":   product_url,
                "platform_name": "Reliance Digital",
            })

    # FALLBACK: /product/ links
    if len(results) < max_results:
        for link in soup.find_all("a", href=re.compile(r"/product/")):
            if len(results) >= max_results:
                break
            href = link.get("href", "")
            if not href or href in seen:
                continue
            title = link.get_text(strip=True)
            if not title or len(title) < 5:
                continue
            seen.add(href)
            product_url = href if href.startswith("http") else urljoin(BASE_URL, href)
            price       = None
            container   = link.find_parent(["li", "div", "article"])
            if container:
                ps = container.find(string=re.compile(r"₹\s*[\d,]+"))
                if ps:
                    price = parse_price(str(ps))
            results.append({
                "product_name":  title,
                "price":         price,
                "rating":        None,
                "image_url":     None,
                "product_url":   product_url,
                "platform_name": "Reliance Digital",
            })

    logger.info(f"Reliance: parsed {len(results)} products from {len(html)} byte HTML")
    return results


async def _fetch_with_playwright(url: str) -> str | None:
    """
    Playwright fetch with stealth.
    FIX: Waits for price elements before extracting HTML.
    """
    try:
        from playwright.async_api import async_playwright
        try:
            from playwright_stealth import stealth_async
            has_stealth = True
        except ImportError:
            has_stealth = False

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

            # Wait for product table or product links
            try:
                await page.wait_for_selector(
                    "table tr td a, a[href*='/product/']", timeout=10000
                )
            except Exception:
                logger.warning(f"Reliance: product selector timeout {url[:60]}")

            # FIX: Wait for price elements to load
            try:
                await page.wait_for_selector(
                    "td:has-text('₹'), [class*='price'], [class*='Price']",
                    timeout=5000
                )
            except Exception:
                logger.warning("Reliance: price elements not found — may have missing prices")

            await asyncio.sleep(random.uniform(2.0, 4.0))

            html = await page.content()
            await browser.close()
            logger.info(f"Reliance Playwright: fetched {len(html)} bytes")
            return html

    except ImportError:
        logger.warning("Reliance: Playwright not installed. Run: pip install playwright && playwright install chromium")
        return None
    except Exception as e:
        logger.error(f"Reliance Playwright error: {e}")
        return None


async def crawl_reliance(query: str, max_results: int = 6) -> list[dict]:
    if crawl_cache.is_fresh("reliance", query):
        logger.info(f"Reliance: cache fresh for '{query}' — skipping")
        return []

    url  = _get_url(query)
    html = await _fetch_with_playwright(url)

    if not html:
        logger.warning(f"Reliance: Playwright failed, trying requests for '{query}'")
        html = await fetch_html(url, referer="https://www.reliancedigital.in/")

    if not html:
        logger.warning(f"Reliance: no HTML for '{query}'")
        return []

    results = _parse(html, max_results)
    logger.info(f"Reliance: {len(results)} products for '{query}'")

    if results:
        crawl_cache.mark_crawled("reliance", query)

    return results
