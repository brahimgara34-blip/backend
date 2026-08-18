from sqlalchemy import Column, Integer, String, Boolean, Numeric, DateTime, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from app.core.database import Base


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String(50), unique=True, index=True, nullable=False)
    customer_name = Column(String(255), nullable=False)
    phone_number = Column(String(50), nullable=False)
    normalized_phone = Column(String(50), nullable=False)
    items = Column(JSONB, nullable=False)
    total_amount = Column(Numeric(10, 2), nullable=False)
    has_upsell = Column(Boolean, default=False)
    upsell_product = Column(String(255), nullable=True)
    upsell_amount = Column(Numeric(10, 2), default=0.00)
    status = Column(String(50), default="طلب جديد مؤكد")
    event_id = Column(String(100), nullable=True)
    user_agent = Column(Text, nullable=True)
    client_ip = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
