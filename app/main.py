from contextlib import asynccontextmanager
from fastapi import FastAPI, Response
from fastapi.responses import PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import init_db
from app.api.v1.orders import router as orders_router
from app.api.v1.admin import router as admin_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.redirects import router as redirects_router


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

    if settings.meta_capi_ready:
        pixel_ids = ", ".join(pixel_id for pixel_id, _token in settings.meta_capi_targets)
        print(f"[Tracking] Meta CAPI: ON — {pixel_ids}")
    else:
        print("[Tracking] Meta CAPI: OFF — add META_PIXEL_ID + META_CAPI_TOKEN")
    print(f"[Tracking] TikTok CAPI: {'ON' if settings.tiktok_capi_ready else 'OFF'}")
    print(f"[Tracking] Snapchat CAPI: {'ON' if settings.snapchat_capi_ready else 'OFF'}")
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
app.include_router(redirects_router, prefix=f"{settings.API_V1_STR}/redirects", tags=["Redirect Killer"])


@app.get("/", tags=["Root"])
async def root():
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "online",
        "docs": "/docs"
    }


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "tracking": {
            "meta": settings.meta_capi_ready,
            "meta_pixels": [pixel_id for pixel_id, _token in settings.meta_capi_targets],
            "tiktok": settings.tiktok_capi_ready,
            "snapchat": settings.snapchat_capi_ready,
        },
    }


@app.get("/robots.txt", response_class=PlainTextResponse, tags=["SEO"])
async def get_robots():
    return "User-agent: *\nAllow: /\nSitemap: https://vitalismaroc.shop/sitemap.xml\n"


@app.get("/sitemap.xml", tags=["SEO"])
async def get_sitemap():
    sitemap_xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://vitalismaroc.shop/</loc>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>
  <url>
    <loc>https://vitalismaroc.shop/collections</loc>
    <changefreq>daily</changefreq>
    <priority>0.9</priority>
  </url>
  <url>
    <loc>https://vitalismaroc.shop/products/hydropure-shower</loc>
    <changefreq>daily</changefreq>
    <priority>0.95</priority>
  </url>
  <url>
    <loc>https://vitalismaroc.shop/products/aurafloss-water-flosser</loc>
    <changefreq>daily</changefreq>
    <priority>0.95</priority>
  </url>
  <url>
    <loc>https://vitalismaroc.shop/products/kneerelief-heated-brace</loc>
    <changefreq>daily</changefreq>
    <priority>0.95</priority>
  </url>
  <url>
    <loc>https://vitalismaroc.shop/products/vitalfit-smart-scale</loc>
    <changefreq>daily</changefreq>
    <priority>0.95</priority>
  </url>
  <url>
    <loc>https://vitalismaroc.shop/about</loc>
    <changefreq>weekly</changefreq>
    <priority>0.7</priority>
  </url>
  <url>
    <loc>https://vitalismaroc.shop/contact</loc>
    <changefreq>monthly</changefreq>
    <priority>0.6</priority>
  </url>
</urlset>"""
    return Response(content=sitemap_xml, media_type="application/xml")
