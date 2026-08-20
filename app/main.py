from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1.orders import router as orders_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"[Startup] {settings.PROJECT_NAME} v{settings.VERSION} started successfully.")
    yield
    print("[Shutdown] Cleaning up server resources...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan
)

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins or ["*"],
    allow_credentials=True,
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
