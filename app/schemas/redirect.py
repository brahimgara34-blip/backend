from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class RedirectLoginRequest(BaseModel):
    username: str
    password: str


class RedirectLoginResponse(BaseModel):
    token: str
    token_type: str = "Bearer"
    expires_in_hours: int
    username: str


class RedirectCreateSchema(BaseModel):
    slug: str = Field(min_length=2, max_length=80)
    destination: str = Field(min_length=1, max_length=500)
    label: Optional[str] = None
    note: Optional[str] = None


class RedirectUpdateSchema(BaseModel):
    slug: Optional[str] = Field(default=None, min_length=2, max_length=80)
    destination: Optional[str] = Field(default=None, min_length=1, max_length=500)
    label: Optional[str] = None
    note: Optional[str] = None


class RedirectResponseSchema(BaseModel):
    id: int
    slug: str
    destination: str
    label: Optional[str] = None
    note: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
