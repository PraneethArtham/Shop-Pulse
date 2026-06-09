"""
scrapping.py — ShopPulse Multi-Platform Scraper
Scrapes Amazon, Flipkart, and Meesho and saves products to Supabase.

Usage:
    python scrapping.py --query "sony headphones" --category "Electronics"
    python scrapping.py --query "iphone 15" --platforms amazon flipkart
    python scrapping.py --headless  (no browser window)
    python scrapping.py             (interactive mode)
"""

import time
import random
import re
import argparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

from backend.services.product_services import insert_platform_product


# ── Utilities ─────────────────────────────────────────────────────────────────

def make_driver(headless: bool = False) -> webdriver.Chrome:
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    return webdriver.Chrome(options=options)


def sleep(lo: float = 4, hi: float = 7):
    time.sleep(random.uniform(lo, hi))


def parse_price(text: str) -> float | None:
    if not text:
        return None
    try:
        return float(re.sub(r"[₹,\s]", "", text))
    except ValueError:
        return None


# ══════════════════════════════════════════════════════════════════════════════
# AMAZON
# ══════════════════════════════════════════════════════════════════════════════

def scrape_amazon(driver, query: str, category: str, max_results: int = 5):
    print("\n" + "═" * 55)
    print("  AMAZON SCRAPING")
    print("═" * 55)

    driver.get(f"https://www.amazon.in/s?k={query.replace(' ', '+')}")
    sleep(5, 8)

    links = [
        el.get_attribute("href")
        for el in driver.find_elements(By.CSS_SELECTOR, "a.a-link-normal.s-no-outline")
        if el.get_attribute("href") and "sspa" not in el.get_attribute("href")
    ][:max_results]

    for url in links:
        print(f"\n  [Amazon] {url[:75]}...")
        try:
            driver.get(url)
            sleep(4, 7)

            # Title
            try:
                title = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "productTitle"))
                ).text.strip()
            except Exception:
                title = "Unknown Product"

            # Price
            price_text = ""
            try:
                price_text = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "span.a-offscreen"))
                ).text
            except Exception:
                pass
            if not price_text:
                soup = BeautifulSoup(driver.page_source, "html.parser")
                span = soup.find("span", class_="a-offscreen")
                if span:
                    price_text = span.text

            # Rating
            try:
                rating_text = driver.find_element(
                    By.XPATH, "//span[@data-hook='rating-out-of-text']"
                ).text
                rating = float(rating_text.split()[0])
            except Exception:
                rating = None

            # Image
            try:
                image_url = driver.find_element(By.ID, "landingImage").get_attribute("src")
            except Exception:
                image_url = None

            price = parse_price(price_text)
            print(f"  ✓ {title[:55]} | ₹{price} | ★{rating}")

            insert_platform_product(
                product_name=title,
                price=price,
                platform_name="Amazon",
                rating=rating,
                product_url=url,
                image_url=image_url,
                category=category,
            )
        except Exception as e:
            print(f"  ✗ Error: {e}")
        sleep(3, 6)


# ══════════════════════════════════════════════════════════════════════════════
# FLIPKART
# ══════════════════════════════════════════════════════════════════════════════

def scrape_flipkart(driver, query: str, category: str, max_results: int = 5):
    print("\n" + "═" * 55)
    print("  FLIPKART SCRAPING")
    print("═" * 55)

    driver.get(f"https://www.flipkart.com/search?q={query.replace(' ', '+')}")
    sleep(5, 8)

    try:
        driver.find_element(By.XPATH, "//button[contains(text(),'✕')]").click()
        sleep(1, 2)
    except Exception:
        pass

    seen = set()
    links = []
    for el in driver.find_elements(By.XPATH, "//a[contains(@href,'/p/')]"):
        href = el.get_attribute("href")
        if href and href not in seen:
            seen.add(href)
            links.append(href)
        if len(links) >= max_results:
            break

    for url in links:
        print(f"\n  [Flipkart] {url[:75]}...")
        try:
            driver.get(url)
            sleep(4, 7)

            try:
                title = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "span.VU-ZEz"))
                ).text.strip()
            except Exception:
                title = "Unknown Product"

            try:
                price = parse_price(driver.find_element(By.CSS_SELECTOR, "div.Nx9bqj").text)
            except Exception:
                price = None

            try:
                rating = float(driver.find_element(By.CSS_SELECTOR, "div.XQDdHH").text)
            except Exception:
                rating = None

            try:
                image_url = driver.find_element(By.CSS_SELECTOR, "img._396cs4").get_attribute("src")
            except Exception:
                image_url = None

            print(f"  ✓ {title[:55]} | ₹{price} | ★{rating}")

            insert_platform_product(
                product_name=title,
                price=price,
                platform_name="Flipkart",
                rating=rating,
                product_url=url,
                image_url=image_url,
                category=category,
            )
        except Exception as e:
            print(f"  ✗ Error: {e}")
        sleep(3, 6)


# ══════════════════════════════════════════════════════════════════════════════
# MEESHO
# ══════════════════════════════════════════════════════════════════════════════

def scrape_meesho(driver, query: str, category: str, max_results: int = 5):
    print("\n" + "═" * 55)
    print("  MEESHO SCRAPING")
    print("═" * 55)

    driver.get(f"https://www.meesho.com/search?q={query.replace(' ', '%20')}")
    sleep(5, 9)

    hrefs = list({
        el.get_attribute("href")
        for el in driver.find_elements(By.XPATH, "//a[contains(@href,'/p/')]")
        if el.get_attribute("href")
    })[:max_results]

    for url in hrefs:
        print(f"\n  [Meesho] {url[:75]}...")
        try:
            driver.get(url)
            sleep(4, 7)

            soup = BeautifulSoup(driver.page_source, "html.parser")

            title_el = soup.find("h1")
            title = title_el.text.strip() if title_el else "Unknown Product"

            price_el = soup.find("h5", string=re.compile(r"₹"))
            price = parse_price(price_el.text) if price_el else None

            rating_el = soup.find("span", string=re.compile(r"^\d\.\d$"))
            try:
                rating = float(rating_el.text) if rating_el else None
            except Exception:
                rating = None

            img_el = soup.find("img", {"alt": re.compile(r"product", re.I)})
            image_url = img_el["src"] if img_el else None

            print(f"  ✓ {title[:55]} | ₹{price} | ★{rating}")

            insert_platform_product(
                product_name=title,
                price=price,
                platform_name="Meesho",
                rating=rating,
                product_url=url,
                image_url=image_url,
                category=category,
            )
        except Exception as e:
            print(f"  ✗ Error: {e}")
        sleep(3, 6)


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="ShopPulse Scraper")
    parser.add_argument("--query", "-q", type=str, help="Product search query")
    parser.add_argument("--category", "-c", type=str, default="General")
    parser.add_argument("--max", "-n", type=int, default=5, help="Max results per platform")
    parser.add_argument("--headless", action="store_true", help="Run headlessly")
    parser.add_argument(
        "--platforms", "-p", nargs="+",
        choices=["amazon", "flipkart", "meesho"],
        default=["amazon", "flipkart", "meesho"],
    )
    args = parser.parse_args()

    query = args.query or input("Enter product name: ").strip()
    if not query:
        print("No query provided.")
        return

    print(f"\n🚀 ShopPulse Scraper")
    print(f"   Query:     {query}")
    print(f"   Category:  {args.category}")
    print(f"   Platforms: {', '.join(args.platforms)}")
    print(f"   Max/plat:  {args.max}")

    driver = make_driver(headless=args.headless)
    try:
        if "amazon" in args.platforms:
            scrape_amazon(driver, query, args.category, args.max)
        if "flipkart" in args.platforms:
            scrape_flipkart(driver, query, args.category, args.max)
        if "meesho" in args.platforms:
            scrape_meesho(driver, query, args.category, args.max)
    finally:
        driver.quit()
        print("\n✅ Done — all platforms scraped & saved to database.\n")


if __name__ == "__main__":
    main()
