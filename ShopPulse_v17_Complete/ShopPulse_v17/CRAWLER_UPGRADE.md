# ShopPulse — Crawler Upgrade Guide

## What Changed

| Platform       | Before                  | After                          |
|----------------|-------------------------|--------------------------------|
| Amazon         | requests + BS4          | requests + BS4 + TTL Cache ✅  |
| BigBasket      | requests + BS4          | requests + BS4 + TTL Cache ✅  |
| Croma          | requests + BS4          | Playwright Stealth + TTL Cache |
| Reliance       | requests + BS4          | Playwright Stealth + TTL Cache |

### Key improvements
- **Playwright Stealth** for Croma + Reliance — renders JavaScript, hides bot signals
- **TTL Cache** for all platforms — skips crawl if data fetched within 8 hours (cuts crawl volume ~80%)
- **Longer delays** — 5–12 seconds between requests (was 1.2–2.8s)
- **Expanded User-Agent pool** — 12 agents instead of 5
- **Automatic fallback** — if Playwright fails, falls back to requests silently

---

## Setup Instructions

### Step 1 — Install dependencies

```bash
pip install -r requirements.txt
```

### Step 2 — Install Playwright browser (one-time only)

```bash
playwright install chromium
```

That's it. No other changes needed.

---

## Files Changed

```
backend/services/crawler/
    utils.py              ← Added CrawlCache class + longer delays + more User-Agents
    amazon_crawler.py     ← Added TTL cache check (rest unchanged)
    bigbasket_crawler.py  ← Added TTL cache check (rest unchanged)
    croma_crawler.py      ← REPLACED with Playwright Stealth version
    reliance_crawler.py   ← REPLACED with Playwright Stealth version

requirements.txt          ← Added playwright + playwright-stealth
```

---

## How TTL Cache Works

When a search for "trimmer" happens:

```
1st search at 10:00 AM → crawls all platforms → saves to DB → marks cache
2nd search at 11:00 AM → cache says "fresh" → skips crawl → reads from DB
3rd search at 7:00 PM  → cache expired (8 hrs) → crawls again → updates DB
```

Result: instead of crawling every search, you crawl once every 8 hours per query.
Amazon/BigBasket barely get hit. Croma/Reliance are only hit by Playwright.

---

## Changing the Cache TTL

In `utils.py`, find this line:

```python
crawl_cache = CrawlCache(ttl_hours=8)
```

Change `8` to whatever hours you want:
- `4` = refresh every 4 hours (more fresh data, more crawls)
- `12` = refresh every 12 hours (less crawls, slightly older data)
- `24` = once per day

---

## If Playwright is Not Available

Both `croma_crawler.py` and `reliance_crawler.py` automatically fall back
to the original `requests`-based fetching if Playwright is not installed.
The app will never crash — it degrades gracefully.

---

## Verifying It Works

Run your FastAPI server and search for any product. Check the logs:

```
# Good — Playwright working
Croma Playwright: fetched 245000 bytes from https://www.croma.com/...

# Good — cache working
Croma: cache fresh for 'trimmer' — skipping crawl

# Fallback — Playwright not installed, using requests
Croma: Playwright not installed. Run: pip install playwright && playwright install chromium
```
