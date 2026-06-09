"""
backend/services/local_store_service.py

CHANGES:
  - get_local_products_for_master() — fixed N+1 (batch query)
  - get_local_stores() — returns product_count per store
  - New: get_store_by_id(), update_store(), delete_store()
  - New: update_store_product(), delete_store_product()
  - New: get_store_products() — all products for a single store
"""
import uuid
import logging
from typing import Optional
from backend.dbase.supabase_client import supabase

logger = logging.getLogger("shoppulse.local_stores")


def get_local_stores(search: Optional[str] = None) -> list:
    """Returns all stores with product_count."""
    query = supabase.table("local_stores").select("*")
    if search:
        query = query.ilike("location", f"%{search}%")
    stores = query.execute().data or []

    if not stores:
        return []

    # Batch-fetch product counts
    store_ids = [s["store_id"] for s in stores]
    try:
        prod_rows = (
            supabase.table("local_store_products")
            .select("store_id")
            .in_("store_id", store_ids)
            .execute()
            .data or []
        )
        counts: dict[str, int] = {}
        for r in prod_rows:
            sid = r["store_id"]
            counts[sid] = counts.get(sid, 0) + 1
    except Exception:
        counts = {}

    for s in stores:
        s["product_count"] = counts.get(s["store_id"], 0)

    return stores


def get_store_by_id(store_id: str) -> Optional[dict]:
    try:
        res = (
            supabase.table("local_stores")
            .select("*")
            .eq("store_id", store_id)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None
    except Exception as e:
        logger.warning(f"get_store_by_id failed: {e}")
        return None


def create_local_store(
    store_name: str,
    location: str,
    phone: Optional[str] = None,
    store_rating: Optional[float] = None,
) -> dict:
    data = {
        "store_id":    str(uuid.uuid4()),
        "store_name":  store_name,
        "location":    location,
        "phone":       phone,
        "store_rating": store_rating,
    }
    supabase.table("local_stores").insert(data).execute()
    return data


def update_store(
    store_id: str,
    store_name: Optional[str] = None,
    location: Optional[str] = None,
    phone: Optional[str] = None,
    store_rating: Optional[float] = None,
) -> Optional[dict]:
    updates = {}
    if store_name  is not None: updates["store_name"]   = store_name
    if location    is not None: updates["location"]      = location
    if phone       is not None: updates["phone"]         = phone
    if store_rating is not None: updates["store_rating"] = store_rating

    if not updates:
        return get_store_by_id(store_id)

    try:
        res = (
            supabase.table("local_stores")
            .update(updates)
            .eq("store_id", store_id)
            .execute()
        )
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"update_store failed: {e}")
        return None


def delete_store(store_id: str) -> bool:
    try:
        supabase.table("local_store_products").delete().eq("store_id", store_id).execute()
        supabase.table("local_stores").delete().eq("store_id", store_id).execute()
        return True
    except Exception as e:
        logger.error(f"delete_store failed: {e}")
        return False


def add_local_store_product(
    master_product_id: str,
    store_id: str,
    product_name: str,
    price: float,
    stock_quantity: int = 0,
) -> dict:
    data = {
        "local_product_id":  str(uuid.uuid4()),
        "master_product_id": master_product_id,
        "store_id":          store_id,
        "product_name":      product_name,
        "price":             price,
        "stock_quantity":    stock_quantity,
    }
    supabase.table("local_store_products").insert(data).execute()
    return data


def update_store_product(
    local_product_id: str,
    price: Optional[float] = None,
    stock_quantity: Optional[int] = None,
    product_name: Optional[str] = None,
) -> Optional[dict]:
    updates = {}
    if price          is not None: updates["price"]          = price
    if stock_quantity is not None: updates["stock_quantity"]  = stock_quantity
    if product_name   is not None: updates["product_name"]   = product_name

    if not updates:
        return None

    try:
        res = (
            supabase.table("local_store_products")
            .update(updates)
            .eq("local_product_id", local_product_id)
            .execute()
        )
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"update_store_product failed: {e}")
        return None


def delete_store_product(local_product_id: str) -> bool:
    try:
        supabase.table("local_store_products").delete().eq("local_product_id", local_product_id).execute()
        return True
    except Exception as e:
        logger.error(f"delete_store_product failed: {e}")
        return False


def get_store_products(store_id: str) -> list:
    """All products listed by a specific store."""
    items = (
        supabase.table("local_store_products")
        .select("*")
        .eq("store_id", store_id)
        .execute()
        .data or []
    )
    for item in items:
        qty = item.get("stock_quantity")
        item["in_stock"] = bool(qty and qty > 0)
    return items


def get_local_products_for_master(master_product_id: str) -> list:
    """FIX: was N+1 queries. Now batch-fetches all stores in one query."""
    items = (
        supabase.table("local_store_products")
        .select("*")
        .eq("master_product_id", master_product_id)
        .execute()
        .data or []
    )
    if not items:
        return []

    store_ids = list({item["store_id"] for item in items if item.get("store_id")})
    stores_by_id: dict[str, dict] = {}
    if store_ids:
        try:
            store_rows = (
                supabase.table("local_stores")
                .select("*")
                .in_("store_id", store_ids)
                .execute()
                .data or []
            )
            stores_by_id = {s["store_id"]: s for s in store_rows}
        except Exception as e:
            logger.warning(f"Batch store fetch failed: {e}")

    result = []
    for item in items:
        item["store"]    = stores_by_id.get(item.get("store_id") or "", None)
        qty              = item.get("stock_quantity")
        item["in_stock"] = bool(qty and qty > 0)
        result.append(item)
    return result
