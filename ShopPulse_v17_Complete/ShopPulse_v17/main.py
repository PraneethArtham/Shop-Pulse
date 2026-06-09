"""
main.py — ShopPulse API Entry Point
Run:  uvicorn main:app --reload --port 8000

FIX: CORS now accepts env-configurable origins for production deployment.
FIX: Health check now verifies Supabase connection.
"""
import os
import logging
import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.routes import products, platform_products, local_stores, sellers, reviews

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)-28s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("shoppulse.main")

app = FastAPI(
    title="ShopPulse API",
    description="India price comparison engine — Amazon, Croma, Reliance Digital, BigBasket.",
    version="4.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS — reads from env so works in production too ──────────
_raw_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173"
)
ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request logging middleware ────────────────────────────────
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    try:
        response = await call_next(request)
        ms    = round((time.time() - start) * 1000)
        level = logging.WARNING if response.status_code >= 400 else logging.INFO
        logger.log(level, f"{request.method:6} {request.url.path:40} → {response.status_code} ({ms}ms)")
        return response
    except Exception as e:
        ms = round((time.time() - start) * 1000)
        logger.error(f"{request.method:6} {request.url.path:40} → CRASH ({ms}ms): {e}")
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

@app.exception_handler(Exception)
async def global_error_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "path": str(request.url.path), "type": type(exc).__name__}
    )

# ── Routers ───────────────────────────────────────────────────
app.include_router(products.router)
app.include_router(platform_products.router)
app.include_router(local_stores.router)
app.include_router(sellers.router)
app.include_router(reviews.router)

# ── Health check — now verifies Supabase connection ──────────
@app.get("/", tags=["Health"])
def health():
    db_status = "unknown"
    try:
        from backend.dbase.supabase_client import supabase
        supabase.table("master_products").select("master_product_id").limit(1).execute()
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)[:80]}"

    return {
        "status":     "running",
        "version":    "4.0.0",
        "db":         db_status,
        "cors":       ALLOWED_ORIGINS,
        "api_map": {
            "search":        "GET /search?q=trimmer",
            "product":       "GET /products/{id}",
            "compare":       "GET /compare/{id}",
            "history":       "GET /products/{id}/price-history",
            "predict":       "GET /products/{id}/predict",
            "categories":    "GET /categories",
            "browse":        "GET /products?category=Electronics",
            "crawl_test":    "GET /crawl/test?query=trimmer&platform=all",
            "crawl_trigger": "GET /crawl/trigger?query=trimmer",
            "docs":          "/docs",
        },
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
