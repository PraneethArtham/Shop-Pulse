"""
backend/services/seller_service.py

Actual DB columns: seller_id, seller_name, seller_rating, created_at
NOTE: There is NO platform_name column on the sellers table.
"""

import uuid
from typing import Optional
from backend.dbase.supabase_client import supabase


def get_all_sellers() -> list:
    # BUG FIX: removed platform filter — no platform_name column on sellers
    return supabase.table("sellers").select("*").execute().data or []


def get_seller(seller_id: str) -> dict | None:
    # BUG FIX: safe limit(1) instead of .single() which throws on 0 rows
    try:
        res = (
            supabase.table("sellers")
            .select("*")
            .eq("seller_id", seller_id)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None
    except Exception:
        return None


def create_seller(
    seller_name: str,
    seller_rating: Optional[float] = None,
) -> dict:
    # BUG FIX: removed platform_name from query and insert
    existing = (
        supabase.table("sellers")
        .select("seller_id")
        .ilike("seller_name", seller_name)
        .execute()
        .data
    )
    if existing:
        return existing[0]

    data = {
        "seller_id": str(uuid.uuid4()),
        "seller_name": seller_name,
        "seller_rating": seller_rating,
    }
    supabase.table("sellers").insert(data).execute()
    return data
