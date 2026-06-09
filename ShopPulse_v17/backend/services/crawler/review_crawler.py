"""
backend/services/crawler/review_crawler.py

Scrapes customer reviews from platform product pages.
Called by crawl_manager after products are saved.

Per platform:
  Amazon    — fetch /product/{asin}/customer-reviews (static HTML)
  Croma     — Playwright scrolls to reviews section
  Reliance  — Playwright scrolls to reviews section
  BigBasket — aggregate rating + count only (reviews behind login)

Returns list of raw review dicts:
  { review_text, review_rating, platform_name }

Sentiment analysis and fake detection happen in sentiment_engine.py
"""
import re
import asyncio
import random
import logging
from typing import Optional
from bs4 import BeautifulSoup
from .utils import fetch_html, parse_price

logger = logging.getLogger("shoppulse.crawler.reviews")

# Max reviews to scrape per product per platform
MAX_REVIEWS_PER_PLATFORM = 5


# ── Amazon Reviews ─────────────────────────────────────────────
async def scrape_amazon_reviews(asin: str) -> list[dict]:
    """
    Fetch customer reviews from Amazon product review page.
    Amazon renders review HTML statically — no Playwright needed.
    """
    if not asin:
        return []

    url = f"https://www.amazon.in/product-reviews/{asin}?pageNumber=1&sortBy=recent"
    html = await fetch_html(url, referer=f"https://www.amazon.in/dp/{asin}")

    if not html:
        logger.warning(f"Amazon reviews: no HTML for ASIN {asin}")
        return []

    soup    = BeautifulSoup(html, "html.parser")
    reviews = []

    # Amazon review cards
    cards = soup.select("div[data-hook='review']")
    logger.info(f"Amazon reviews: {len(cards)} review cards for ASIN {asin}")

    for card in cards[:MAX_REVIEWS_PER_PLATFORM]:
        try:
            # Rating: "4.0 out of 5 stars"
            rating_el = card.select_one("i[data-hook='review-star-rating'] span.a-icon-alt")
            rating    = None
            if rating_el:
                m = re.match(r"([\d.]+)", rating_el.get_text(strip=True))
                if m:
                    r = float(m.group(1))
                    rating = r if 1.0 <= r <= 5.0 else None

            # Review body
            body_el = card.select_one("span[data-hook='review-body'] span")
            text    = body_el.get_text(strip=True) if body_el else None

            if not rating and not text:
                continue

            reviews.append({
                "review_text":   text,
                "review_rating": rating or 3.0,
                "platform_name": "Amazon",
            })
        except Exception as e:
            logger.debug(f"Amazon review parse error: {e}")
            continue

    logger.info(f"Amazon reviews: scraped {len(reviews)} reviews for ASIN {asin}")
    return reviews


# ── Croma Reviews (Playwright) ─────────────────────────────────
async def scrape_croma_reviews(product_url: str) -> list[dict]:
    """
    Fetch reviews from Croma product page using Playwright.
    Croma renders reviews via JS — need full page render.
    """
    if not product_url:
        return []

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
                viewport={"width": 1366, "height": 768},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                locale="en-IN",
                timezone_id="Asia/Kolkata",
            )
            page = await context.new_page()

            if has_stealth:
                await stealth_async(page)

            await page.goto(product_url, wait_until="domcontentloaded", timeout=30000)

            # Scroll to reviews section
            try:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.6)")
                await asyncio.sleep(random.uniform(1.5, 2.5))

                # Try to find review section
                await page.wait_for_selector(
                    "[class*='review'], [class*='Review'], [data-testid*='review']",
                    timeout=5000
                )
            except Exception:
                logger.warning(f"Croma: review section not found for {product_url[:60]}")
                await browser.close()
                return []

            html  = await page.content()
            await browser.close()

        soup    = BeautifulSoup(html, "html.parser")
        reviews = []

        # Try common Croma review selectors
        rev_containers = (
            soup.select("[class*='review-item']") or
            soup.select("[class*='ReviewItem']") or
            soup.select("[class*='customer-review']")
        )

        for container in rev_containers[:MAX_REVIEWS_PER_PLATFORM]:
            try:
                # Rating — look for star count or numeric rating
                rating = None
                rating_el = container.select_one("[class*='rating'], [class*='Rating'], [class*='star']")
                if rating_el:
                    m = re.search(r"([1-5](?:\.\d)?)", rating_el.get_text())
                    if m:
                        rating = float(m.group(1))

                # Review text
                text_el = container.select_one(
                    "[class*='review-text'], [class*='ReviewText'], [class*='comment'], p"
                )
                text = text_el.get_text(strip=True) if text_el else None

                if not text or len(text) < 5:
                    continue

                reviews.append({
                    "review_text":   text[:500],  # cap at 500 chars
                    "review_rating": rating or 3.0,
                    "platform_name": "Croma",
                })
            except Exception as e:
                logger.debug(f"Croma review parse error: {e}")
                continue

        logger.info(f"Croma reviews: {len(reviews)} reviews from {product_url[:60]}")
        return reviews

    except ImportError:
        logger.warning("Croma reviews: Playwright not installed")
        return []
    except Exception as e:
        logger.error(f"Croma review scrape error: {e}")
        return []


# ── Reliance Digital Reviews (Playwright) ─────────────────────
async def scrape_reliance_reviews(product_url: str) -> list[dict]:
    """
    Fetch reviews from Reliance Digital product page using Playwright.
    """
    if not product_url:
        return []

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
                viewport={"width": 1366, "height": 768},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                locale="en-IN",
                timezone_id="Asia/Kolkata",
            )
            page = await context.new_page()

            if has_stealth:
                await stealth_async(page)

            await page.goto(product_url, wait_until="domcontentloaded", timeout=30000)

            try:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.7)")
                await asyncio.sleep(random.uniform(1.5, 2.5))
                await page.wait_for_selector(
                    "[class*='review'], [class*='Review'], [class*='rating']",
                    timeout=5000
                )
            except Exception:
                logger.warning(f"Reliance: review section not found for {product_url[:60]}")
                await browser.close()
                return []

            html  = await page.content()
            await browser.close()

        soup    = BeautifulSoup(html, "html.parser")
        reviews = []

        rev_containers = (
            soup.select("[class*='review-card']") or
            soup.select("[class*='ReviewCard']") or
            soup.select("[class*='user-review']")
        )

        for container in rev_containers[:MAX_REVIEWS_PER_PLATFORM]:
            try:
                rating = None
                rating_el = container.select_one(
                    "[class*='rating'], [class*='star'], [class*='Score']"
                )
                if rating_el:
                    m = re.search(r"([1-5](?:\.\d)?)", rating_el.get_text())
                    if m:
                        rating = float(m.group(1))

                text_el = container.select_one(
                    "[class*='review-text'], [class*='description'], [class*='comment'], p"
                )
                text = text_el.get_text(strip=True) if text_el else None

                if not text or len(text) < 5:
                    continue

                reviews.append({
                    "review_text":   text[:500],
                    "review_rating": rating or 3.0,
                    "platform_name": "Reliance Digital",
                })
            except Exception as e:
                logger.debug(f"Reliance review parse error: {e}")
                continue

        logger.info(f"Reliance reviews: {len(reviews)} from {product_url[:60]}")
        return reviews

    except ImportError:
        logger.warning("Reliance reviews: Playwright not installed")
        return []
    except Exception as e:
        logger.error(f"Reliance review scrape error: {e}")
        return []


# ── BigBasket Reviews ─────────────────────────────────────────
async def scrape_bigbasket_reviews(product_url: str, rating: Optional[float]) -> list[dict]:
    """
    BigBasket individual reviews are behind login.
    We create a single aggregated review entry using the rating
    already scraped from the category/search page.
    """
    if not rating:
        return []

    # Create a synthetic review entry representing the aggregate rating
    reviews = [{
        "review_text":   None,  # No text — aggregate only
        "review_rating": rating,
        "platform_name": "BigBasket",
    }]

    logger.info(f"BigBasket reviews: synthetic entry with rating {rating}")
    return reviews
