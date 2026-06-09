"""
backend/routes/platform_products.py
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from backend.models.schemas import PlatformProductIn
from backend.services.product_services import (
    get_all_platform_products,
    insert_platform_product,
    delete_platform_product,
)

router = APIRouter(prefix="/platformproducts", tags=["Platform Products"])


@router.get("")
def list_platform_products(
    platform: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    sort: Optional[str] = Query(None),
):
    try:
        data = get_all_platform_products(platform, page, limit, sort)
        return {"platform": platform, "page": page, "limit": limit, "count": len(data), "products": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", status_code=201)
def create_platform_product(payload: PlatformProductIn):
    try:
        result = insert_platform_product(**payload.model_dump())
        return {"message": "Platform product created", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{platform_product_id}")
def remove_platform_product(platform_product_id: str):
    try:
        delete_platform_product(platform_product_id)
        return {"message": "Deleted", "platform_product_id": platform_product_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
