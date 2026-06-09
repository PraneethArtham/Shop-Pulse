"""
backend/routes/products.py — Complete API layer

Endpoints:
  GET /search?q=...                        NLP-enhanced smart search
  GET /search/parse                        Show NLP breakdown of a query (no search)
  GET /products?category=...               Browse by category
  GET /products/{id}                       Full product detail + AI scores
  GET /products/{id}/price-history         Price history per platform
  GET /products/{id}/predict               7-day price prediction
  GET /compare/{id}                        Sorted price comparison
  GET /categories                          All categories
  GET /crawl/status?query=...              Poll crawl progress
  GET /crawl/trigger?query=...             Trigger manual crawl
  GET /crawl/test?query=...&platform=...   Test crawlers (no DB write)
"""

import asyncio
import logging
import time
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from backend.services.master_products import get_all_categories, get_products_by_category, search_products
from backend.services.product_aggregator import get_product_full_details
from backend.services.search_with_crawl import smart_search, get_crawl_status
from backend.services.price_history import get_price_history
from backend.services.price_prediction import predict_price
from backend.services.nlp_search import parse_query

logger = logging.getLogger("shoppulse.routes.products")
router = APIRouter(tags=["Products"])


# ── Categories ────────────────────────────────────────────
@router.get("/categories")
def fetch_categories():
    try:
        cats = get_all_categories()
        return {"count": len(cats), "categories": cats}
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Browse ─────────────────────────────────────────────────
@router.get("/products")
def get_products_by_cat(
    category: str = Query(...),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    sort: Optional[str] = Query(None, description='name_asc|name_desc|price_asc|price_desc'),
):
    try:
        data = get_products_by_category(category, page, limit, sort)
        if not data:
            raise HTTPException(404, f"No products found in '{category}'")
        return {"category": category, "page": page, "limit": limit, "count": len(data), "products": data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Sub-routes BEFORE wildcard ─────────────────────────────
@router.get("/products/{master_product_id}/price-history")
def price_history_route(master_product_id: str):
    try:
        return get_price_history(master_product_id)
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/products/{master_product_id}/predict")
def predict_route(master_product_id: str):
    try:
        return predict_price(master_product_id)
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/products/{master_product_id}")
def get_product_details(master_product_id: str):
    try:
        data = get_product_full_details(master_product_id)
        if not data:
            raise HTTPException(404, "Product not found")
        return data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


# ── NLP Parse endpoint (before /search to avoid conflict) ──
@router.get("/search/parse")
def parse_search_query(query: str = Query(..., min_length=1)):
    """
    Returns the full NLP breakdown of a query.
    Shows brand, model, category, price range, intent, attributes, synonyms.
    Used by the frontend to display the 'Understood:' chip row.
    """
    try:
        pq = parse_query(query)
        return {
            "query":        query,
            "intent":       pq.intent,
            "brand":        pq.brand,
            "model":        pq.model_number,
            "category":     pq.category,
            "price_min":    pq.price_min,
            "price_max":    pq.price_max,
            "attributes":   pq.attributes,
            "synonyms":     pq.synonyms_added,
            "search_terms": pq.search_terms,
            "core_terms":   pq.core_terms,
        }
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Smart Search ────────────────────────────────────────────
@router.get("/search")
async def search(
    query: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    force_crawl: bool = Query(False),
):
    """
    NLP-powered smart search.
    Parses natural language queries, applies category + price filters,
    TF-IDF re-ranks results, crawls live platforms on DB miss.
    """
    try:
        result = await smart_search(query, page, limit, force_crawl)
        return result
    except Exception as e:
        logger.error(f"search('{query}'): {e}")
        raise HTTPException(500, str(e))


# ── Compare ─────────────────────────────────────────────────
@router.get("/compare/{master_product_id}")
def compare_prices(master_product_id: str):
    try:
        data = get_product_full_details(master_product_id)
        if not data:
            raise HTTPException(404, "Product not found")

        online = [
            {"source": p["platform_name"], "type": "online", "price": p["price"],
             "rating": p.get("rating"), "url": p.get("product_url"),
             "verification_score": p.get("verification_score", {}).get("score"),
             "seller": p.get("seller", {}).get("seller_name") if p.get("seller") else None}
            for p in data["platform_listings"]
        ]
        local = [
            {"source": i["store"]["store_name"], "type": "local", "price": i["price"],
             "in_stock": i.get("in_stock"), "location": i["store"].get("location")}
            for i in data["local_store_listings"] if i.get("store")
        ]
        all_opts = sorted(online + local, key=lambda x: x["price"] or float("inf"))
        prices   = [o["price"] for o in all_opts if o["price"]]

        return {
            "product":     data["product"],
            "stats":       data.get("stats", {}),
            "best_deal":   all_opts[0] if all_opts else None,
            "all_options": all_opts,
            "max_savings": round(max(prices) - min(prices), 2) if len(prices) >= 2 else 0,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Crawl endpoints ─────────────────────────────────────────
@router.get("/crawl/status")
def crawl_status(query: str = Query(...)):
    return get_crawl_status(query)


@router.get("/crawl/trigger")
async def trigger_crawl(query: str = Query(..., min_length=1)):
    from backend.services.crawler.crawl_manager import run_crawl
    from backend.services.search_with_crawl import _set_status
    _set_status(query, "crawling", "Manual crawl triggered")

    async def _bg():
        try:
            pq     = parse_query(query)
            result = await run_crawl(query, max_per_platform=5, category_hint=pq.category)
            ids    = result.get("ids", [])
            status = result.get("status", "done")
            _set_status(query, "done", f"Done ({status}) — {len(ids)} products saved", len(ids))
        except Exception as e:
            _set_status(query, "error", str(e))

    asyncio.create_task(_bg())
    return {"message": f"Crawl triggered for '{query}'", "poll": f"/crawl/status?query={query}"}


@router.get("/crawl/test")
async def test_crawlers(
    query: str = Query(..., min_length=1),
    platform: str = Query("all"),
):
    """Test individual crawlers without writing to DB."""
    from backend.services.crawler.amazon_crawler    import crawl_amazon
    from backend.services.crawler.croma_crawler     import crawl_croma
    from backend.services.crawler.reliance_crawler  import crawl_reliance
    from backend.services.crawler.bigbasket_crawler import crawl_bigbasket

    plat = platform.lower().strip()

    async def _run(coro):
        t0 = time.time()
        try:
            results = await coro
            return {"status": "ok" if results else "empty", "count": len(results),
                    "time_sec": round(time.time()-t0, 2), "products": results, "error": None}
        except Exception as e:
            return {"status": "error", "count": 0, "time_sec": round(time.time()-t0, 2),
                    "products": [], "error": str(e)}

    tasks = {}
    if plat in ("all", "amazon"):    tasks["Amazon"]           = _run(crawl_amazon(query, 5))
    if plat in ("all", "croma"):     tasks["Croma"]            = _run(crawl_croma(query, 5))
    if plat in ("all", "reliance"):  tasks["Reliance Digital"] = _run(crawl_reliance(query, 5))
    if plat in ("all", "bigbasket"): tasks["BigBasket"]        = _run(crawl_bigbasket(query, 5))
    if not tasks:
        raise HTTPException(400, "Use: all | amazon | croma | reliance | bigbasket")

    # Run Playwright crawlers sequentially to avoid browser crash
    PLAYWRIGHT_PLATFORMS = {"Croma", "Reliance Digital"}
    fast_tasks = {k: v for k, v in tasks.items() if k not in PLAYWRIGHT_PLATFORMS}
    slow_tasks = {k: v for k, v in tasks.items() if k in PLAYWRIGHT_PLATFORMS}

    report = {}
    if fast_tasks:
        fast_results = await asyncio.gather(*fast_tasks.values())
        report.update(dict(zip(fast_tasks.keys(), fast_results)))
    for name, coro in slow_tasks.items():
        report[name] = await coro
    total   = sum(r["count"] for r in report.values())

    return {
        "query": query,
        "nlp":   {  # Show NLP understanding in crawler test too
            "category":   parse_query(query).category,
            "brand":      parse_query(query).brand,
            "search_terms": parse_query(query).search_terms[:3],
        },
        "summary": {
            "total_products": total,
            "working": [p for p, r in report.items() if r["status"] == "ok"],
            "empty":   [p for p, r in report.items() if r["status"] == "empty"],
            "errors":  [p for p, r in report.items() if r["status"] == "error"],
        },
        "platforms": report,
    }
