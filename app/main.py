from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from app.core.config import settings
from app.core.database import engine
from app.api.v1.orders import router as orders_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"==================================================")
    print(f"[Startup] {settings.PROJECT_NAME} v{settings.VERSION} starting...")
    print(f"[Database URL] {settings.async_database_url.split('@')[-1] if '@' in settings.async_database_url else 'Configured'}")
    
    # Test database connectivity
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        print("[Database Check] Connection to PostgreSQL is ACTIVE & HEALTHY! ✅")
    except Exception as e:
        print(f"[Database Warning] Could not connect to PostgreSQL: {e} ❌")
        print(f"[Hint] Verify DATABASE_URL in Easypanel Environment tab.")

    print(f"==================================================")
    yield
    print("[Shutdown] Cleaning up server resources...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan
)

# Robust CORS Configuration: Allow all origins so no order is ever blocked by CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(orders_router, prefix=settings.API_V1_STR, tags=["Orders"])


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION
    }
