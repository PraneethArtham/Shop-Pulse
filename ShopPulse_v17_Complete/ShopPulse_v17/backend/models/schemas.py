"""
backend/models/schemas.py
CHANGES: Added validation to LocalStoreIn, LocalStoreProductIn, LocalStoreUpdate, LocalStoreProductUpdate
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional
import re


class MasterProductOut(BaseModel):
    master_product_id: str
    product_name: str
    brand: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None


class SellerIn(BaseModel):
    seller_name: str
    seller_rating: Optional[float] = None


class PlatformProductIn(BaseModel):
    product_name: str
    price: float
    platform_name: str
    seller_id: Optional[str] = None
    rating: Optional[float] = None
    product_url: Optional[str] = None
    image_url: Optional[str] = None
    category: str = "General"


class ReviewIn(BaseModel):
    platform_product_id: str
    review_text: Optional[str] = None
    review_rating: float = Field(..., ge=1, le=5)
    sentiment_score: Optional[float] = None
    is_fake: bool = False


class LocalStoreIn(BaseModel):
    store_name: str  = Field(..., min_length=2, max_length=100)
    location:   str  = Field(..., min_length=3, max_length=200)
    phone:      Optional[str] = None
    store_rating: Optional[float] = Field(None, ge=1.0, le=5.0)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        if v is None:
            return v
        digits = re.sub(r"[\s\-\(\)\+]", "", v)
        if not digits.isdigit() or len(digits) < 7 or len(digits) > 15:
            raise ValueError("Phone must be 7–15 digits")
        return v

    @field_validator("store_name")
    @classmethod
    def validate_name(cls, v):
        if not v.strip():
            raise ValueError("Store name cannot be blank")
        return v.strip()


class LocalStoreUpdate(BaseModel):
    store_name:   Optional[str]   = Field(None, min_length=2, max_length=100)
    location:     Optional[str]   = Field(None, min_length=3, max_length=200)
    phone:        Optional[str]   = None
    store_rating: Optional[float] = Field(None, ge=1.0, le=5.0)


class LocalStoreProductIn(BaseModel):
    master_product_id: str
    store_id:          str
    product_name:      str  = Field(..., min_length=2, max_length=200)
    price:             float = Field(..., gt=0, le=10_000_000)
    stock_quantity:    int   = Field(0, ge=0)


class LocalStoreProductUpdate(BaseModel):
    price:          Optional[float] = Field(None, gt=0, le=10_000_000)
    stock_quantity: Optional[int]   = Field(None, ge=0)
    product_name:   Optional[str]   = Field(None, min_length=2, max_length=200)
