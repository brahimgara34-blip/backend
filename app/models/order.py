from sqlalchemy import Column, Integer, String, Boolean, Numeric, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String(50), unique=True, index=True, nullable=False)
    customer_name = Column(String(255), nullable=False)
    phone_number = Column(String(50), nullable=False)
    normalized_phone = Column(String(50), nullable=True)
    items = Column(JSONB, nullable=True) # Direct JSONB storage in orders table
    total_amount = Column(Numeric(10, 2), nullable=False)
    has_upsell = Column(Boolean, default=False)
    upsell_product = Column(String(255), nullable=True)
    upsell_amount = Column(Numeric(10, 2), default=0.00)
    status = Column(String(50), default="طلب جديد مؤكد (COD)")
    event_id = Column(String(100), nullable=True, index=True)
    
    # Geolocation & MaxMind Fraud info
    city = Column(String(100), nullable=True)
    region = Column(String(100), nullable=True)
    country = Column(String(50), nullable=True, default="MA")
    is_proxy = Column(Boolean, default=False)
    risk_score = Column(Numeric(5, 2), nullable=True)
    user_agent = Column(Text, nullable=True)
    client_ip = Column(String(50), nullable=True)
    landing_url = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    order_items = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    tracking_events = relationship(
        "TrackingEvent",
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="selectin"
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(String(100), nullable=True)
    product_name = Column(String(255), nullable=False)
    quantity = Column(Integer, default=1, nullable=False)
    unit_price = Column(Numeric(10, 2), default=0.00)
    total_price = Column(Numeric(10, 2), default=0.00)
    is_upsell = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    order = relationship("Order", back_populates="order_items")


class TrackingEvent(Base):
    __tablename__ = "tracking_events"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=True, index=True)
    event_id = Column(String(100), nullable=False, index=True)
    event_name = Column(String(100), default="Purchase", nullable=False)
    meta_status = Column(String(50), default="pending")
    tiktok_status = Column(String(50), default="pending")
    snapchat_status = Column(String(50), default="pending")
    sheets_status = Column(String(50), default="pending")
    maxmind_status = Column(String(50), default="completed")
    ip_address = Column(String(50), nullable=True)
    payload = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    order = relationship("Order", back_populates="tracking_events")
