from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from sqlalchemy import text
from app.core.config import settings

engine = create_async_engine(
    settings.async_database_url,
    echo=False,
    future=True,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

Base = declarative_base()


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """
    Automatically creates and migrates all tables (orders, order_items, tracking_events)
    in PostgreSQL, adding any missing columns like 'city', 'region', 'is_proxy', etc.
    """
    from app.models.order import Order, OrderItem, TrackingEvent  # Register models

    async with engine.begin() as conn:
        # 1. Create tables if they do not exist
        await conn.run_sync(Base.metadata.create_all)

        # 2. Alter existing 'orders' table to ensure all MaxMind and metadata columns exist
        migration_statements = [
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS city VARCHAR(100);",
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS region VARCHAR(100);",
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS country VARCHAR(50) DEFAULT 'MA';",
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS is_proxy BOOLEAN DEFAULT FALSE;",
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS risk_score NUMERIC(5, 2) DEFAULT 0.00;",
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS user_agent TEXT;",
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS client_ip VARCHAR(50);",
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS event_id VARCHAR(100);",
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS has_upsell BOOLEAN DEFAULT FALSE;",
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS upsell_product VARCHAR(255);",
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS upsell_amount NUMERIC(10, 2) DEFAULT 0.00;",
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS normalized_phone VARCHAR(50);",
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'طلب جديد مؤكد (COD)';",
            
            # Ensure order_items exists
            """
            CREATE TABLE IF NOT EXISTS order_items (
                id SERIAL PRIMARY KEY,
                order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
                product_id VARCHAR(100),
                product_name VARCHAR(255) NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 1,
                unit_price NUMERIC(10, 2) DEFAULT 0.00,
                total_price NUMERIC(10, 2) DEFAULT 0.00,
                is_upsell BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            """,
            
            # Ensure tracking_events exists
            """
            CREATE TABLE IF NOT EXISTS tracking_events (
                id SERIAL PRIMARY KEY,
                order_id INTEGER REFERENCES orders(id) ON DELETE CASCADE,
                event_id VARCHAR(100) NOT NULL,
                event_name VARCHAR(100) NOT NULL DEFAULT 'Purchase',
                meta_status VARCHAR(50) DEFAULT 'pending',
                tiktok_status VARCHAR(50) DEFAULT 'pending',
                snapchat_status VARCHAR(50) DEFAULT 'pending',
                sheets_status VARCHAR(50) DEFAULT 'pending',
                maxmind_status VARCHAR(50) DEFAULT 'completed',
                ip_address VARCHAR(50),
                payload JSONB,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            """,
            
            # Indices
            "CREATE INDEX IF NOT EXISTS idx_orders_order_id ON orders(order_id);",
            "CREATE INDEX IF NOT EXISTS idx_orders_phone ON orders(phone_number);",
            "CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);",
            "CREATE INDEX IF NOT EXISTS idx_tracking_events_order_id ON tracking_events(order_id);",
        ]

        for stmt in migration_statements:
            try:
                await conn.execute(text(stmt))
            except Exception as e:
                print(f"[Migration Notice] {e}")
