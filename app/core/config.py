from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    PROJECT_NAME: str = "Vitalis Maroc API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Database
    DATABASE_URL: str = "postgres://vitalismaroc:vitalismaroc@vitalismaroc_datapase:5432/vitalismaroc?sslmode=disable"
    
    # Webhook
    GOOGLE_SHEET_WEBHOOK_URL: str = ""
    
    # MaxMind GeoIP & Fraud Protection
    MAXMIND_ACCOUNT_ID: str = ""
    MAXMIND_LICENSE_KEY: str = ""
    
    # Tracking Meta CAPI
    META_PIXEL_ID: str = ""
    META_CAPI_TOKEN: str = ""
    
    # Tracking TikTok Events API
    TIKTOK_PIXEL_ID: str = ""
    TIKTOK_ACCESS_TOKEN: str = ""
    
    # Tracking Snapchat CAPI
    SNAPCHAT_PIXEL_ID: str = ""
    SNAPCHAT_API_TOKEN: str = ""
    
    # CORS
    ALLOWED_ORIGINS: str = "https://vitalismaroc.shop,http://localhost:3000,http://127.0.0.1:3000"

    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    @property
    def async_database_url(self) -> str:
        url = self.DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        # remove sslmode parameter for asyncpg if present or adjust
        if "?sslmode=disable" in url:
            url = url.replace("?sslmode=disable", "")
        return url

    class Config:
        env_file = ".env"
        extra = "allow"


settings = Settings()
