"""
backend/services/crawler/utils.py
Shared utilities — requests-based HTTP, rotating User-Agents, price parser,
and TTL cache manager.

CHANGES FROM ORIGINAL:
  - Added CrawlCache class — TTL-based caching to reduce crawl frequency
  - Increased human-like delays (was 1.2-2.8s, now 5-12s)
  - Expanded User-Agent list (was 5, now 12)
  - Added more realistic browser headers
"""
import re
import time
import random
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional
from datetime import datetime, timedelta

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger("shoppulse.crawler")
_executor = ThreadPoolExecutor(max_workers=8)

# ── Expanded User-Agent pool ───────────────────────────────────
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36",
]

# ── Accept-Language rotation (looks more human) ───────────────
_ACCEPT_LANGUAGES = [
    "en-IN,en-US;q=0.9,en;q=0.8",
    "en-US,en;q=0.9",
    "en-GB,en;q=0.9,en-US;q=0.8",
    "en-IN,hi;q=0.8,en;q=0.7",
]


# ── TTL Cache Manager ─────────────────────────────────────────
class CrawlCache:
    """
    In-memory TTL cache to track when each platform+query was last crawled.
    Prevents hammering the same site repeatedly.

    Usage:
        cache = CrawlCache(ttl_hours=8)
        if cache.is_fresh("amazon", "trimmer"):
            return  # skip crawl, data is recent
        cache.mark_crawled("amazon", "trimmer")
    """
    def __init__(self, ttl_hours: int = 8):
        self._store: dict[str, datetime] = {}
        self._ttl = timedelta(hours=ttl_hours)

    def _key(self, platform: str, query: str) -> str:
        return f"{platform.lower()}::{query.lower().strip()}"

    def is_fresh(self, platform: str, query: str) -> bool:
        """Returns True if this platform+query was crawled within TTL."""
        key = self._key(platform, query)
        last = self._store.get(key)
        if not last:
            return False
        return (datetime.now() - last) < self._ttl

    def mark_crawled(self, platform: str, query: str):
        """Record that this platform+query was just crawled."""
        self._store[self._key(platform, query)] = datetime.now()

    def invalidate(self, platform: str, query: str):
        """Force re-crawl next time."""
        key = self._key(platform, query)
        self._store.pop(key, None)


# Shared global cache instance (8-hour TTL)
crawl_cache = CrawlCache(ttl_hours=8)


# ── HTTP Session ──────────────────────────────────────────────
def _make_session(referer: str, ua: str) -> requests.Session:
    s = requests.Session()
    retry = Retry(
        total=3, backoff_factor=2.0,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"], raise_on_status=False
    )
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.mount("http://",  HTTPAdapter(max_retries=retry))
    s.headers.update({
        "User-Agent":               ua,
        "Accept":                   "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language":          random.choice(_ACCEPT_LANGUAGES),
        "Accept-Encoding":          "gzip, deflate",
        "Referer":                  referer,
        "Connection":               "keep-alive",
        "DNT":                      "1",
        "Upgrade-Insecure-Requests":"1",
        "Cache-Control":            "max-age=0",
        "Sec-Fetch-Dest":           "document",
        "Sec-Fetch-Mode":           "navigate",
        "Sec-Fetch-Site":           "same-origin",
    })
    return s


def _sync_fetch(url: str, referer: str = "https://www.google.com/") -> Optional[str]:
    """
    Fetch URL with retry and human-like delays.
    Returns HTML string or None.
    """
    for attempt in range(2):
        ua = random.choice(_USER_AGENTS)
        session = _make_session(referer, ua)
        try:
            # Longer, more human-like delays
            delay = random.uniform(5.0, 12.0) if attempt == 0 else random.uniform(10.0, 20.0)
            logger.debug(f"Sleeping {delay:.1f}s before fetch (attempt {attempt+1})")
            time.sleep(delay)

            resp = session.get(url, timeout=25, allow_redirects=True)
            logger.debug(f"[attempt {attempt+1}] {url[:70]} → HTTP {resp.status_code}, {len(resp.content)} bytes")

            if resp.status_code == 200:
                resp.encoding = resp.apparent_encoding or "utf-8"
                html = resp.text
                if len(html) >= 1000:
                    return html
                logger.warning(f"Short response ({len(html)}b) for {url[:60]} — {'retrying' if attempt==0 else 'giving up'}")
                if attempt == 0:
                    continue
                return None

            elif resp.status_code in (403, 429):
                logger.warning(f"Blocked (HTTP {resp.status_code}): {url[:60]}")
                return None

            else:
                logger.warning(f"HTTP {resp.status_code}: {url[:60]}")
                return None

        except requests.exceptions.Timeout:
            logger.warning(f"Timeout (attempt {attempt+1}): {url[:60]}")
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"Connection error (attempt {attempt+1}): {url[:60]}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error: {url[:60]}: {e}")
            return None
        finally:
            session.close()

    return None


async def fetch_html(url: str, referer: str = "https://www.google.com/") -> Optional[str]:
    """Async wrapper — runs _sync_fetch in thread pool so FastAPI stays non-blocking."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _sync_fetch, url, referer)


def parse_price(text: str) -> Optional[float]:
    """Extract numeric price from '₹1,299', '₹ 2,249 (Incl. all Taxes)', '1299.00' etc."""
    if not text:
        return None
    cleaned = re.sub(r"[₹,\s\xa0\u202f]", "", str(text))
    m = re.search(r"\d[\d.]*", cleaned)
    if not m:
        return None
    try:
        val = float(m.group())
        return round(val, 2) if 5 <= val <= 5_000_000 else None
    except ValueError:
        return None
