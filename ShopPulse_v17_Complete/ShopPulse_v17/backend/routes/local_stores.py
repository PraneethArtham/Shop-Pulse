"""
backend/routes/local_stores.py
CHANGES: Full CRUD — GET/PUT/DELETE for stores and products
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from backend.models.schemas import (
    LocalStoreIn, LocalStoreUpdate,
    LocalStoreProductIn, LocalStoreProductUpdate,
)
from backend.services.local_store_service import (
    get_local_stores, get_store_by_id, create_local_store,
    update_store, delete_store,
    add_local_store_product, update_store_product,
    delete_store_product, get_store_products,
    get_local_products_for_master,
)

router = APIRouter(tags=["Local Stores"])


# ── Stores ─────────────────────────────────────────────────────
@router.get("/localstores")
def list_local_stores(search: Optional[str] = Query(None)):
    try:
        data = get_local_stores(search)
        return {"count": len(data), "stores": data}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/localstores/{store_id}")
def get_store(store_id: str):
    try:
        data = get_store_by_id(store_id)
        if not data:
            raise HTTPException(404, "Store not found")
        return data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/localstores", status_code=201)
def add_local_store(payload: LocalStoreIn):
    try:
        result = create_local_store(**payload.model_dump())
        return {"message": "Store registered successfully", "data": result}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.put("/localstores/{store_id}")
def edit_store(store_id: str, payload: LocalStoreUpdate):
    try:
        existing = get_store_by_id(store_id)
        if not existing:
            raise HTTPException(404, "Store not found")
        result = update_store(store_id, **payload.model_dump(exclude_none=True))
        return {"message": "Store updated", "data": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.delete("/localstores/{store_id}")
def remove_store(store_id: str):
    try:
        existing = get_store_by_id(store_id)
        if not existing:
            raise HTTPException(404, "Store not found")
        ok = delete_store(store_id)
        if not ok:
            raise HTTPException(500, "Failed to delete store")
        return {"message": "Store deleted", "store_id": store_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/localstores/{store_id}/products")
def list_store_products(store_id: str):
    try:
        data = get_store_products(store_id)
        return {"store_id": store_id, "count": len(data), "products": data}
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Store Products ──────────────────────────────────────────────
@router.post("/localstoreproducts", status_code=201)
def add_product(payload: LocalStoreProductIn):
    try:
        result = add_local_store_product(**payload.model_dump())
        return {"message": "Product added to store", "data": result}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.put("/localstoreproducts/{local_product_id}")
def edit_store_product(local_product_id: str, payload: LocalStoreProductUpdate):
    try:
        result = update_store_product(local_product_id, **payload.model_dump(exclude_none=True))
        if not result:
            raise HTTPException(404, "Product not found")
        return {"message": "Product updated", "data": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.delete("/localstoreproducts/{local_product_id}")
def remove_store_product(local_product_id: str):
    try:
        ok = delete_store_product(local_product_id)
        if not ok:
            raise HTTPException(500, "Failed to delete product")
        return {"message": "Product removed", "local_product_id": local_product_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/localstoreproducts/{master_product_id}")
def get_local_products_route(master_product_id: str):
    try:
        data = get_local_products_for_master(master_product_id)
        return {"master_product_id": master_product_id, "count": len(data), "local_listings": data}
    except Exception as e:
        raise HTTPException(500, str(e))
