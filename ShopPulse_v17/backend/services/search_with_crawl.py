"""
backend/services/search_with_crawl.py
NLP-enhanced smart search — v4

FIXES:
  - Handles new run_crawl() dict return {"status", "ids"}
  - "cached" status → skip crawl, read from DB directly (no "0 results" bug)
  - "limited" status → serve from DB silently
  - "empty" status → still re-search DB (other crawlers may have saved data)
"""
import asyncio
import logging
from backend.services.master_products import search_products
from backend.services.crawler.crawl_manager import run_crawl
from backend.services.nlp_search import parse_query, filter_by_price, rank_results, ParsedQuery

logger = logging.getLogger("shoppulse.search")

_crawl_status: dict[str, dict] = {}


def get_crawl_status(query: str) -> dict:
    return _crawl_status.get(query.lower().strip(), {"status": "idle", "query": query})


def _set_status(query: str, status: str, message: str = "", count: int = 0):
    _crawl_status[query.lower().strip()] = {
        "status": status, "query": query, "message": message, "count": count,
    }


def _filter_by_category(products: list[dict], pq: ParsedQuery) -> list[dict]:
    if not pq.category or pq.category == "General":
        return products
    matched = [p for p in products if p.get("category") == pq.category]
    return matched if matched else products


def _pick_crawl_term(pq: ParsedQuery) -> str:
    terms = pq.search_terms or [pq.raw]
    multi_word = [t for t in terms if len(t.split()) > 1]
    if multi_word:
        return multi_word[0]
    return terms[0]


def _search_with_terms(terms: list[str], page: int, limit: int, pq: ParsedQuery) -> list[dict]:
    seen_ids: set[str] = set()
    best_results: list[dict] = []
    for term in terms:
        raw_results = search_products(term, page, limit)
        if not raw_results:
            continue
        unique = []
        for r in raw_results:
            mid = r.get("master_product_id")
            if mid and mid not in seen_ids:
                seen_ids.add(mid)
                unique.append(r)
        if not unique:
            continue
        filtered = _filter_by_category(unique, pq)
        if filtered:
            best_results.extend(filtered)
            if len(best_results) >= limit:
                break
    return best_results[:limit]


async def smart_search(
    query: str,
    page: int = 1,
    limit: int = 20,
    force_crawl: bool = False,
) -> dict:
    query        = query.strip()
    pq           = parse_query(query)
    search_terms = pq.search_terms if pq.search_terms else [query]
    crawl_term   = _pick_crawl_term(pq)

    # ── Step 1: DB search (skip if force_crawl) ───────────────
    if not force_crawl:
        raw = _search_with_terms(search_terms, page, limit, pq)
        if raw:
            price_filtered = filter_by_price(raw, pq)
            ranked         = rank_results(price_filtered if price_filtered else raw, pq)
            logger.info(f"smart_search: DB hit '{query}' → {len(ranked)} results")
            return {
                "query":           query,
                "parsed":          _pq_summary(pq),
                "source":          "db",
                "count":           len(ranked),
                "results":         ranked[:limit],
                "crawl_triggered": False,
                "message":         f"Found {len(ranked)} results.",
            }

    # ── Step 2: Crawl ──────────────────────────────────────────
    logger.info(f"smart_search: DB miss '{query}' — crawling '{crawl_term}'")
    _set_status(query, "crawling", f"Searching live for '{crawl_term}'…")

    try:
        crawl_result = await run_crawl(
            crawl_term,
            max_per_platform=6,
            category_hint=pq.category,
        )
        status = crawl_result.get("status", "empty")

        # Cache was fresh — all data already in DB, just read it
        if status == "cached":
            _set_status(query, "done", "Serving from cache")
            fresh = _search_with_terms(search_terms, page, limit, pq)
            price_filtered = filter_by_price(fresh, pq)
            ranked = rank_results(price_filtered if price_filtered else fresh, pq)
            return {
                "query":           query,
                "parsed":          _pq_summary(pq),
                "source":          "db",
                "count":           len(ranked),
                "results":         ranked[:limit],
                "crawl_triggered": False,
                "message":         f"Found {len(ranked)} results (cached).",
            }

        # Rate limited — serve what we have in DB
        if status == "limited":
            _set_status(query, "done", "Rate limit — showing cached results")
            raw = _search_with_terms(search_terms, page, limit, pq)
            price_filtered = filter_by_price(raw, pq)
            ranked = rank_results(price_filtered if price_filtered else raw, pq)
            return {
                "query":           query,
                "parsed":          _pq_summary(pq),
                "source":          "db",
                "count":           len(ranked),
                "results":         ranked[:limit],
                "crawl_triggered": False,
                "message":         f"Found {len(ranked)} results.",
            }

        saved_ids = crawl_result.get("ids", [])
        _set_status(query, "done", f"Found {len(saved_ids)} new products", len(saved_ids))

    except Exception as e:
        logger.error(f"smart_search: crawl error: {e}")
        _set_status(query, "error", str(e))
        fallback       = _search_with_terms(search_terms, page, limit, pq)
        price_filtered = filter_by_price(fallback, pq)
        ranked         = rank_results(price_filtered if price_filtered else fallback, pq)
        return {
            "query":           query,
            "parsed":          _pq_summary(pq),
            "source":          "db",
            "count":           len(ranked),
            "results":         ranked[:limit],
            "crawl_triggered": True,
            "message":         f"Crawl failed. Showing {len(ranked)} cached results.",
        }

    # ── Step 3: Re-search after crawl ─────────────────────────
    fresh          = _search_with_terms(search_terms, page, limit, pq)
    price_filtered = filter_by_price(fresh, pq)
    ranked         = rank_results(price_filtered if price_filtered else fresh, pq)

    return {
        "query":           query,
        "parsed":          _pq_summary(pq),
        "source":          "crawled",
        "count":           len(ranked),
        "results":         ranked[:limit],
        "crawl_triggered": True,
        "message":         f"Live data fetched — {len(ranked)} results found.",
    }


def _pq_summary(pq: ParsedQuery) -> dict:
    return {
        "intent":       pq.intent,
        "brand":        pq.brand,
        "model":        pq.model_number,
        "category":     pq.category,
        "price_min":    pq.price_min,
        "price_max":    pq.price_max,
        "attributes":   pq.attributes,
        "synonyms":     pq.synonyms_added[:3],
        "search_terms": pq.search_terms[:4],
    }
