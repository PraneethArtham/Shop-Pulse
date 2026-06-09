"""
backend/routes/sellers.py
"""

from fastapi import APIRouter, HTTPException
from backend.models.schemas import SellerIn
from backend.services.seller_service import get_all_sellers, get_seller, create_seller

router = APIRouter(prefix="/sellers", tags=["Sellers"])


@router.get("")
def list_sellers():
    try:
        data = get_all_sellers()
        return {"count": len(data), "sellers": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", status_code=201)
def add_seller(payload: SellerIn):
    try:
        result = create_seller(**payload.model_dump())
        return {"message": "Seller created", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{seller_id}")
def get_seller_route(seller_id: str):
    try:
        data = get_seller(seller_id)
        if not data:
            raise HTTPException(status_code=404, detail="Seller not found")
        return data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
