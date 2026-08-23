from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class AdminLoginRequest(BaseModel):
    username: str = Field(..., description="Admin Username")
    password: str = Field(..., description="Admin Password")


class AdminLoginResponse(BaseModel):
    token: str
    token_type: str = "Bearer"
    expires_in_hours: int
    username: str


class OrderStatusUpdate(BaseModel):
    status: str = Field(..., description="New order status")
    notes: Optional[str] = None


class DateRangeFilter(BaseModel):
    range: str = "all"  # today, yesterday, 7d, 30d, all, custom
    start_date: Optional[str] = None  # YYYY-MM-DD
    end_date: Optional[str] = None    # YYYY-MM-DD
