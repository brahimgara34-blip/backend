from pydantic_settings import BaseSettings
from typing import List
import re


class Settings(BaseSettings):
    PROJECT_NAME: str = "Vitalis Maroc API"
    VERSION: str = "1.0.7"
    API_V1_STR: str = "/api/v1"
    
    # Database (Default fallback connects to service 'datapase' or 'vitalismaroc_datapase' in Easypanel)
    DATABASE_URL: str = "postgres://postgres:postgres@datapase:5432/vitalismaroc"
    
    # Admin Credentials & Security (Configurable via Environment Variables)
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "vitalis2026admin"
    ADMIN_JWT_SECRET: str = "vitalis_maroc_admin_secure_secret_key_2026_xyz"
    ADMIN_SESSION_HOURS: int = 72

    # Redirect Killer admin (fully separate from /admin)
    REDIRECT_ADMIN_USERNAME: str = "redirectadmin"
    REDIRECT_ADMIN_PASSWORD: str = ""
    REDIRECT_ADMIN_JWT_SECRET: str = "vitalis_redirectkiller_jwt_secret_change_me"
    REDIRECT_ADMIN_SESSION_HOURS: int = 72
    MAXMIND_RISK_THRESHOLD: float = 30.0

    # Webhook
    GOOGLE_SHEET_WEBHOOK_URL: str = "https://script.google.com/macros/s/AKfycbwl0YoETUXCBu2FOvlKtBr3kugSYW9YVnK5iBNWXJFnDT8EIWlC3zOSIdadBwSEP0Jchg/exec"
    
    # MaxMind GeoIP & Fraud Protection
    MAXMIND_ACCOUNT_ID: str = ""
    MAXMIND_LICENSE_KEY: str = ""
    
    # Tracking Meta CAPI
    META_PIXEL_ID: str = ""
    META_CAPI_TOKEN: str = ""
    META_TEST_EVENT_CODE: str = ""
    
    # Tracking TikTok Events API
    TIKTOK_PIXEL_ID: str = ""
    TIKTOK_ACCESS_TOKEN: str = ""
    
    # Tracking Snapchat CAPI
    SNAPCHAT_PIXEL_ID: str = ""
    SNAPCHAT_API_TOKEN: str = ""
    
    # CORS
    ALLOWED_ORIGINS: str = "*"

    @staticmethod
    def _clean(value: str) -> str:
        return (value or "").strip().strip("'\"")

    @property
    def meta_pixel_ids(self) -> List[str]:
        raw = self._clean(self.META_PIXEL_ID).replace(";", ",")
        return [part.strip() for part in raw.split(",") if part.strip()]

    @property
    def meta_capi_tokens(self) -> List[str]:
        raw = self._clean(self.META_CAPI_TOKEN).replace(";", ",")
        return [part.strip() for part in raw.split(",") if part.strip()]

    @property
    def meta_capi_targets(self):
        pixels = self.meta_pixel_ids
        tokens = self.meta_capi_tokens
        if not pixels or not tokens:
            return []
        if len(tokens) == 1:
            return [(pixel_id, tokens[0]) for pixel_id in pixels]
        return list(zip(pixels, tokens))

    @property
    def meta_capi_ready(self) -> bool:
        return bool(self.meta_capi_targets)

    @property
    def tiktok_capi_ready(self) -> bool:
        return bool(self._clean(self.TIKTOK_PIXEL_ID) and self._clean(self.TIKTOK_ACCESS_TOKEN))

    @property
    def snapchat_capi_ready(self) -> bool:
        return bool(self._clean(self.SNAPCHAT_PIXEL_ID) and self._clean(self.SNAPCHAT_API_TOKEN))

    @property
    def cors_origins(self) -> List[str]:
        if self.ALLOWED_ORIGINS.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    @property
    def async_database_url(self) -> str:
        raw_url = self.DATABASE_URL.strip().strip("'\"")
        if not raw_url:
            return ""

        # Normalize driver to postgresql+asyncpg://
        if raw_url.startswith("postgres://"):
            raw_url = "postgresql+asyncpg://" + raw_url[len("postgres://"):]
        elif raw_url.startswith("postgresql://"):
            raw_url = "postgresql+asyncpg://" + raw_url[len("postgresql://"):]

        # Clean any query string parameters that cause asyncpg errors (e.g. sslmode=disable)
        if "?" in raw_url:
            base_url, query_str = raw_url.split("?", 1)
            clean_params = [
                param for param in query_str.split("&")
                if not param.lower().startswith("sslmode") and not param.lower().startswith("ssl")
            ]
            if clean_params:
                raw_url = f"{base_url}?{'&'.join(clean_params)}"
            else:
                raw_url = base_url

        return raw_url

    class Config:
        env_file = ".env"
        extra = "allow"


settings = Settings()
