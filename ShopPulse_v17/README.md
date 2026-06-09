# ShopPulse v10 🛍️

**India's smart price aggregator** — compare prices across Amazon, Croma, Reliance Digital & BigBasket live.

---

## ✅ Bug Fixes Applied (v9 → v10)

### 🔴 Critical Fixes

| # | File | Bug | Fix |
|---|------|-----|-----|
| 1 | `product_aggregator.py` | **N+1 query problem** — reviews fetched in a `for` loop (1 DB query per listing) | Single batch query for all reviews, joined in Python |
| 2 | `ai_engine.py` | **Duplicate `predict_price()`** — defined in both `ai_engine.py` and `price_prediction.py`; the route only used `price_prediction.py` so `ai_engine.py` version was dead/conflicting code | Removed from `ai_engine.py`; clarified module purpose |
| 3 | `crawl_manager.py` | **General category ran crawlers twice** — both `is_electronics` and `is_grocery` conditions matched `"General"`, adding Amazon/Croma/Reliance to task list twice | Replaced with explicit `_CATEGORY_CRAWLERS` lookup dict |
| 4 | `Breadcrumb.jsx` | **Prop name mismatch** — component expected `crumbs` but `ProductDetails.jsx` passed `items`, giving blank breadcrumbs | Component now accepts both `crumbs` and `items` |
| 5 | `auth.py` | **Demo user never seeded** — Login page advertises `demo@shoppulse.com / demo123` but `_users` dict starts empty; demo login always returned 401 | Added `_seed_demo()` called at module load |

### 🟡 Logic / UX Fixes

| # | File | Bug | Fix |
|---|------|-----|-----|
| 6 | `ProductDetails.jsx` | **Sentiment score comparison wrong** — `sent < -0.3` never true for `0.0–1.0` range, so every review showed 😐 | Fixed to `sent >= 0.7 → 😊, >= 0.4 → 😐, else 😞` |
| 7 | `ProductDetails.jsx` | **`Array.at()` not available** in older browser targets (requires ES2022) | Replaced with explicit index access |
| 8 | `Navbar.jsx` | **Search input not cleared** after submitting — typed query stayed visible | Added `setQ('')` after navigation |
| 9 | `Auth.jsx` + `Auth.module.css` | **Orphaned files** — `Auth.jsx` was never routed in `App.jsx` (`Login.jsx` was used instead) | Deleted both orphaned files |
| 10 | `Navbar.module.css` | **CSS class name mismatch** — JSX used `styles.logoIcon`, CSS defined `.logoEmoji` | Renamed `.logoEmoji` → `.logoIcon` |

### ⚡ Efficiency Improvements

| # | File | Change |
|---|------|--------|
| 11 | `product_aggregator.py` | Reviews and sellers now batch-fetched in **1 query each** instead of N queries per listing |
| 12 | `product_aggregator.py` | Local stores also batch-fetched in **1 query** instead of N queries per store row |
| 13 | `master_products.py` | Category list **cached in-process** with 5-minute TTL (was hitting DB on every `/categories` request) |
| 14 | `master_products.py` | `search_products` dedup now uses a dict (O(1) lookup) instead of a set + list rebuild |
| 15 | `master_products.py` | `_enrich_products` now pulls `image_url` from platform listings and surfaces it on search results |
| 16 | `helpers.js` | `PLATFORM_COLORS` updated to include all 4 active platforms (was missing Croma, Reliance Digital, BigBasket) |
| 17 | `helpers.js` | `CATEGORY_ICONS` updated to include `Grocery` and `PersonalCare` categories |

---

## 📁 Project Structure

```
ShopPulse/
├── main.py                          # FastAPI entry point — middleware, routers, error handler
├── requirements.txt
├── .env                             # SUPABASE_URL + SUPABASE_KEY
│
├── backend/
│   ├── routes/
│   │   ├── products.py              # /search /products /compare /categories /crawl/*
│   │   ├── auth.py                  # /auth/register /auth/login /auth/me /auth/logout
│   │   ├── platform_products.py     # /platformproducts CRUD
│   │   ├── local_stores.py          # /localstores /localstoreproducts
│   │   ├── sellers.py               # /sellers CRUD
│   │   └── reviews.py               # /reviews CRUD
│   │
│   ├── services/
│   │   ├── master_products.py       # Fuzzy dedup, category cache, search enrichment
│   │   ├── product_aggregator.py    # Full product detail — batch queries, no N+1
│   │   ├── verification.py          # Per-listing trust score (0-100, no DB calls)
│   │   ├── price_prediction.py      # 7-day price forecast per platform
│   │   ├── price_history.py         # Price history grouped by platform
│   │   ├── search_with_crawl.py     # DB-first smart search + auto-crawl fallback
│   │   ├── product_services.py      # Platform product CRUD
│   │   ├── ai_engine.py             # Product-level trust score (available for future endpoints)
│   │   └── crawler/
│   │       ├── crawl_manager.py     # Parallel crawler orchestration — fixed duplicate platform bug
│   │       ├── utils.py             # HTTP fetch + price parser
│   │       ├── amazon_crawler.py
│   │       ├── croma_crawler.py
│   │       ├── reliance_crawler.py
│   │       └── bigbasket_crawler.py
│   │
│   └── dbase/
│       └── supabase_client.py       # Supabase connection
│
└── frontend/
    └── src/
        ├── App.jsx                  # Routes + providers
        ├── pages/
        │   ├── Home.jsx             # Hero + search + categories + features
        │   ├── Search.jsx           # Smart search with live crawl banner
        │   ├── ProductDetails.jsx   # Full product — prices, prediction, history, reviews
        │   ├── Category.jsx         # Browse by category with pagination
        │   ├── Login.jsx            # Auth (login + register + demo account)
        │   └── CrawlerTest.jsx      # Dev tool — test crawlers without DB writes
        ├── components/
        │   ├── Navbar.jsx           # Search + auth user menu
        │   ├── ProductCard.jsx      # Card with platform dots + deal ribbon
        │   ├── Breadcrumb.jsx       # Accepts both `crumbs` and `items` props
        │   ├── Loader.jsx           # Spinner + CardSkeleton
        │   └── EmptyState.jsx
        ├── context/
        │   ├── AuthContext.js       # Login/register/logout state
        │   └── CartContext.js       # Wishlist state
        └── utils/
            ├── api.js               # All API calls — auth token injection
            └── helpers.js           # formatPrice, renderStars, PLATFORM_COLORS, CATEGORY_ICONS
```

---

## ⚙️ Setup

### 1. Supabase
1. Create a project at [supabase.com](https://supabase.com)
2. SQL Editor → run the schema (see Supabase docs)
3. Copy **Project URL** and **service_role key** into `.env`

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-service-role-key
```

### 2. Backend
```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
# OR: python main.py
```
API docs: **http://localhost:8000/docs**

### 3. Frontend
```bash
cd frontend
npm install
npm start
```
App: **http://localhost:3000**

---

## 🔌 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Health check + API map |
| GET | `/categories` | All product categories (cached 5 min) |
| GET | `/products?category=Electronics` | Browse by category (sort, pagination) |
| GET | `/products/{id}` | Full product detail + verification scores |
| GET | `/products/{id}/price-history` | Price history per platform |
| GET | `/products/{id}/predict` | 7-day price forecast |
| GET | `/search?query=trimmer` | Smart search (DB-first, crawls on miss) |
| GET | `/compare/{id}` | Sorted price comparison across all platforms |
| GET | `/crawl/status?query=...` | Poll crawl progress |
| GET | `/crawl/trigger?query=...` | Trigger manual crawl |
| GET | `/crawl/test?query=...&platform=all` | Test crawlers (no DB write) |
| POST | `/auth/register` | Register new user |
| POST | `/auth/login` | Login (returns JWT) |
| GET | `/auth/me` | Get current user |

---

## 🧠 Architecture

```
User Search
    │
    ▼
/search?query=trimmer
    │
    ├─ DB hit?  → return cached results instantly
    │
    └─ DB miss → CrawlManager
                    │
                    ├── Amazon     ┐
                    ├── Croma      ├── parallel asyncio.gather()
                    ├── Reliance   │
                    └── BigBasket  ┘ (based on detected category)
                    │
                    ▼
              master_products (fuzzy dedup)
                    │
                    ▼
              platform_products (one row per listing)
                    │
                    ▼
              /search results (enriched with min_price, platforms[])
```

---

## 🔒 Auth Notes

- JWT is stateless — tokens expire in 24 hours
- In-memory user store resets on server restart (replace with Supabase `users` table for production)
- Demo credentials: `demo@shoppulse.com` / `demo123` (seeded on startup)
