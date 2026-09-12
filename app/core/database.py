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
    Automatically creates and migrates all tables (orders, order_items, tracking_events, analytics_clicks)
    in PostgreSQL, ensuring no missing columns and no strict constraint failures.
    """
    from app.models.order import Order, OrderItem, TrackingEvent
    from app.models.analytics import ClickEvent
    from app.models.redirect import RedirectRule

    async with engine.begin() as conn:
        # 1. Create tables if they do not exist
        await conn.run_sync(Base.metadata.create_all)

        # 2. Alter existing tables to ensure all columns and indices exist
        migration_statements = [
            # Orders columns
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
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS items JSONB;",
            "ALTER TABLE orders ADD COLUMN IF NOT EXISTS landing_url TEXT;",
            "ALTER TABLE orders ALTER COLUMN items DROP NOT NULL;",
            "ALTER TABLE orders ALTER COLUMN normalized_phone DROP NOT NULL;",
            
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

            # Ensure analytics_clicks exists
            """
            CREATE TABLE IF NOT EXISTS analytics_clicks (
                id SERIAL PRIMARY KEY,
                path VARCHAR(255) NOT NULL DEFAULT '/',
                client_ip VARCHAR(50),
                country VARCHAR(10) DEFAULT 'MA',
                city VARCHAR(100),
                region VARCHAR(100),
                is_proxy BOOLEAN DEFAULT FALSE,
                risk_score NUMERIC(5, 2) DEFAULT 0.00,
                is_valid_morocco BOOLEAN DEFAULT TRUE,
                referrer VARCHAR(500),
                user_agent TEXT,
                session_id VARCHAR(100),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            """,
            
            """
            CREATE TABLE IF NOT EXISTS redirect_rules (
                id SERIAL PRIMARY KEY,
                slug VARCHAR(80) UNIQUE NOT NULL,
                destination VARCHAR(500) NOT NULL,
                label VARCHAR(255),
                note TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            """,
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_redirect_rules_slug ON redirect_rules(slug);",

            # Indices for lightning-fast queries
            "CREATE INDEX IF NOT EXISTS idx_orders_order_id ON orders(order_id);",
            "CREATE INDEX IF NOT EXISTS idx_orders_phone ON orders(phone_number);",
            "CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at);",
            "CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);",
            "CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);",
            "CREATE INDEX IF NOT EXISTS idx_tracking_events_order_id ON tracking_events(order_id);",
            "CREATE INDEX IF NOT EXISTS idx_analytics_clicks_created_at ON analytics_clicks(created_at);",
            "CREATE INDEX IF NOT EXISTS idx_analytics_clicks_valid ON analytics_clicks(is_valid_morocco);",
            "CREATE INDEX IF NOT EXISTS idx_analytics_clicks_path ON analytics_clicks(path);",
        ]

        for stmt in migration_statements:
            try:
                await conn.execute(text(stmt))
            except Exception as e:
                print(f"[Migration Notice] {e}")
