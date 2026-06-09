"""
backend/routes/reviews.py
"""

from fastapi import APIRouter, HTTPException
from backend.models.schemas import ReviewIn
from backend.services.review_service import (
    add_review,
    get_reviews_for_platform_product,
    get_all_reviews_for_master,
)

router = APIRouter(prefix="/reviews", tags=["Reviews"])


@router.post("", status_code=201)
def create_review(payload: ReviewIn):
    try:
        result = add_review(**payload.model_dump())
        return {"message": "Review added", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/platform/{platform_product_id}")
def get_reviews_by_platform(platform_product_id: str):
    try:
        data = get_reviews_for_platform_product(platform_product_id)
        return {"platform_product_id": platform_product_id, "count": len(data), "reviews": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/product/{master_product_id}")
def get_all_reviews(master_product_id: str):
    try:
        data = get_all_reviews_for_master(master_product_id)
        return {"master_product_id": master_product_id, "count": len(data), "reviews": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
