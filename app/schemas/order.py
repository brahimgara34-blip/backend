from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class OrderItemSchema(BaseModel):
    id: Optional[str] = None
    sku: Optional[str] = None
    name: str
    quantity: int = Field(default=1, ge=1)
    price: Optional[float] = 0.0


class OrderCreateSchema(BaseModel):
    orderId: str
    customerName: str
    phoneNumber: str
    items: List[OrderItemSchema]
    totalAmount: float
    hasUpsell: bool = False
    upsellProduct: Optional[str] = None
    upsellAmount: Optional[float] = 0.0
    eventId: Optional[str] = None
    landingUrl: Optional[str] = None
    url: Optional[str] = None


class OrderResponseSchema(BaseModel):
    id: int
    order_id: str
    customer_name: str
    phone_number: str
    total_amount: float
    city: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = "maroc"
    status: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
