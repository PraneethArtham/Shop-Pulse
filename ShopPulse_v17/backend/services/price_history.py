"""
backend/services/price_history.py
FIX: Added LIMIT 30 per platform — was fetching all rows ever.
"""
from backend.dbase.supabase_client import supabase

_MAX_POINTS_PER_PLATFORM = 30

def get_price_history(master_product_id: str) -> dict:
    try:
        rows = (
            supabase.table("platform_products")
            .select("platform_name, price, created_at, product_url")
            .eq("master_product_id", master_product_id)
            .order("created_at", desc=False)
            .execute()
            .data or []
        )
    except Exception:
        return {"summary": _empty_summary()}

    by_platform: dict[str, list] = {}
    all_prices: list[float] = []

    for row in rows:
        price = row.get("price")
        if not price:
            continue
        plat = row.get("platform_name", "Unknown")
        date = row.get("created_at", "")
        by_platform.setdefault(plat, []).append({"price": price, "date": date})
        all_prices.append(price)

    # Keep only last N points per platform
    for plat in by_platform:
        by_platform[plat] = by_platform[plat][-_MAX_POINTS_PER_PLATFORM:]

    if not all_prices:
        return {"summary": _empty_summary()}

    current_prices = [hist[-1]["price"] for hist in by_platform.values() if hist]
    current_lowest  = min(current_prices) if current_prices else None
    all_time_low    = min(all_prices)
    all_time_high   = max(all_prices)
    savings_vs_high = round(all_time_high - current_lowest, 2) if current_lowest else 0
    savings_pct     = round((savings_vs_high / all_time_high) * 100, 1) if all_time_high else 0
    is_all_time_low = (current_lowest == all_time_low) if current_lowest else False

    return {
        **by_platform,
        "summary": {
            "current_lowest":  current_lowest,
            "all_time_low":    all_time_low,
            "all_time_high":   all_time_high,
            "savings_vs_high": savings_vs_high,
            "savings_pct":     savings_pct,
            "is_all_time_low": is_all_time_low,
        }
    }

def _empty_summary() -> dict:
    return {
        "current_lowest": None, "all_time_low": None,
        "all_time_high": None, "savings_vs_high": 0,
        "savings_pct": 0, "is_all_time_low": False,
    }
