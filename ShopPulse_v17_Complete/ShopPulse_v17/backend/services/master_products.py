"""
backend/services/master_products.py
CHANGE: Added price_asc / price_desc sort to get_products_by_category()
"""
import re
import time
import uuid
from difflib import SequenceMatcher
from collections import defaultdict
from typing import Optional
from backend.dbase.supabase_client import supabase

def _normalise(name: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", "", name.lower())).strip()

def _extract_models(name: str) -> set:
    tokens = _normalise(name).split()
    models = set()
    for t in tokens:
        if re.search(r'[a-z]', t) and re.search(r'\d', t) and len(t) >= 4:
            models.add(t)
        elif re.match(r'^\d{3,}$', t):
            models.add(t)
    return models

def _product_similarity(a: str, b: str) -> float:
    ma, mb = _extract_models(a), _extract_models(b)
    if ma and mb:
        if ma.isdisjoint(mb):
            return 0.0
        return 0.6 + 0.4 * SequenceMatcher(None, _normalise(a), _normalise(b)).ratio()
    return SequenceMatcher(None, _normalise(a), _normalise(b)).ratio()

FUZZY_THRESHOLD = 0.72

_category_cache: list[str] = []
_category_cache_ts: float  = 0.0
_CATEGORY_TTL = 300.0

def get_all_categories() -> list:
    global _category_cache, _category_cache_ts
    now = time.monotonic()
    if _category_cache and (now - _category_cache_ts) < _CATEGORY_TTL:
        return _category_cache
    response = supabase.table("master_products").select("category").execute()
    cats = sorted(list(set(
        item["category"] for item in response.data if item.get("category")
    )))
    _category_cache    = cats
    _category_cache_ts = now
    return cats

def extract_brand(product_name: str) -> str:
    return product_name.split()[0] if product_name else "Unknown"

def get_or_create_master_product(product_name: str, category: str = "General") -> str:
    exact = (
        supabase.table("master_products")
        .select("master_product_id, product_name")
        .ilike("product_name", product_name)
        .limit(1)
        .execute()
    )
    if exact.data:
        return exact.data[0]["master_product_id"]

    candidates = (
        supabase.table("master_products")
        .select("master_product_id, product_name")
        .eq("category", category)
        .limit(200)
        .execute()
        .data
    )
    best_id, best_score = None, 0.0
    for row in candidates:
        score = _product_similarity(product_name, row["product_name"])
        if score > best_score:
            best_score, best_id = score, row["master_product_id"]

    if best_score >= FUZZY_THRESHOLD:
        return best_id

    new_id = str(uuid.uuid4())
    supabase.table("master_products").insert({
        "master_product_id": new_id,
        "product_name":      product_name,
        "brand":             extract_brand(product_name),
        "category":          category,
        "description":       f"{product_name} — aggregated from multiple platforms.",
    }).execute()
    global _category_cache_ts
    _category_cache_ts = 0.0
    return new_id

def _enrich_products(products: list[dict]) -> list[dict]:
    if not products:
        return products
    ids = [p["master_product_id"] for p in products]
    try:
        rows = (
            supabase.table("platform_products")
            .select("master_product_id, platform_name, price, image_url")
            .in_("master_product_id", ids)
            .execute()
            .data or []
        )
    except Exception:
        return products

    by_mid: dict[str, list] = defaultdict(list)
    for r in rows:
        by_mid[r["master_product_id"]].append(r)

    enriched = []
    for p in products:
        mid   = p["master_product_id"]
        plats = by_mid.get(mid, [])
        prices = [r["price"] for r in plats if r.get("price")]
        names  = list(dict.fromkeys(r["platform_name"] for r in plats if r.get("platform_name")))
        image_url = next((r["image_url"] for r in plats if r.get("image_url")), None)
        p["platform_count"] = len(names)
        p["min_price"]      = min(prices) if prices else None
        p["platforms"]      = names
        p["is_deal"]        = len(names) >= 2
        p["image_url"]      = p.get("image_url") or image_url
        enriched.append(p)
    return enriched

def get_products_by_category(
    category: str,
    page: int = 1,
    limit: int = 20,
    sort: Optional[str] = None,
) -> list:
    start = (page - 1) * limit
    query = supabase.table("master_products").select("*").eq("category", category)
    if sort == "name_asc":
        query = query.order("product_name", desc=False)
    elif sort == "name_desc":
        query = query.order("product_name", desc=True)
    # price sort: enrich first, then sort in Python (price is in platform_products)
    products = query.range(start, start + limit - 1).execute().data
    enriched = _enrich_products(products)
    if sort == "price_asc":
        enriched.sort(key=lambda p: p.get("min_price") or float("inf"))
    elif sort == "price_desc":
        enriched.sort(key=lambda p: p.get("min_price") or 0, reverse=True)
    return enriched

def search_products(query: str, page: int = 1, limit: int = 20) -> list:
    start = (page - 1) * limit
    by_name = (
        supabase.table("master_products").select("*")
        .ilike("product_name", f"%{query}%")
        .range(start, start + limit - 1)
        .execute().data
    )
    by_brand = (
        supabase.table("master_products").select("*")
        .ilike("brand", f"%{query}%")
        .range(start, start + limit - 1)
        .execute().data
    )
    seen: dict[str, dict] = {}
    for item in by_name + by_brand:
        mid = item["master_product_id"]
        if mid not in seen:
            seen[mid] = item
    merged = list(seen.values())[:limit]
    return _enrich_products(merged)
