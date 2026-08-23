from sqlalchemy import Column, Integer, String, Boolean, Numeric, DateTime, Text
from sqlalchemy.sql import func
from app.core.database import Base


class ClickEvent(Base):
    __tablename__ = "analytics_clicks"

    id = Column(Integer, primary_key=True, index=True)
    path = Column(String(255), nullable=False, default="/", index=True)
    client_ip = Column(String(50), nullable=True, index=True)
    country = Column(String(10), nullable=True, default="MA")
    city = Column(String(100), nullable=True)
    region = Column(String(100), nullable=True)
    is_proxy = Column(Boolean, default=False)
    risk_score = Column(Numeric(5, 2), default=0.00)
    is_valid_morocco = Column(Boolean, default=True, index=True)
    referrer = Column(String(500), nullable=True)
    user_agent = Column(Text, nullable=True)
    session_id = Column(String(100), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
