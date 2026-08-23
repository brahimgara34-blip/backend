from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import init_db
from app.api.v1.orders import router as orders_router
from app.api.v1.admin import router as admin_router
from app.api.v1.analytics import router as analytics_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"==================================================")
    print(f"[Startup] {settings.PROJECT_NAME} v{settings.VERSION} is starting...")
    
    # Automatically create / verify tables in whatever database is configured in DATABASE_URL
    try:
        print("[Startup] Connecting to database and creating tables (orders, order_items, tracking_events, analytics_clicks)...")
        await init_db()
        print("✅ [Database Connected & Ready] Tables and indices are verified and ready!")
    except Exception as e:
        print(f"❌ [Database Connection Error]: {e}")
        print(f"👉 Please ensure DATABASE_URL in Easypanel Environment matches your PostgreSQL service.")

    print(f"==================================================")
    yield
    print("[Shutdown] Cleaning up server resources...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan
)

# Robust CORS Configuration: Allow all origins so no order or tracking call is ever blocked by CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(orders_router, prefix=settings.API_V1_STR, tags=["Orders"])
app.include_router(admin_router, prefix=f"{settings.API_V1_STR}/admin", tags=["Admin Dashboard"])
app.include_router(analytics_router, prefix=f"{settings.API_V1_STR}/analytics", tags=["Analytics & Clicks"])


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION
    }
