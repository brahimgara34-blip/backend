from pydantic import BaseModel, Field
from typing import Optional


class ClickRecordRequest(BaseModel):
    path: str = Field(default="/", description="Visited URL path")
    referrer: Optional[str] = Field(default=None, description="HTTP Referrer")
    session_id: Optional[str] = Field(default=None, description="Client Session Fingerprint")


class ClickRecordResponse(BaseModel):
    status: str = "recorded"
    is_valid_morocco: bool = True
    city: Optional[str] = None
    country: Optional[str] = None
    is_proxy: bool = False
