-- PostgreSQL Database Schema for Vitalis Maroc
-- Auto-generated and synchronized with FastAPI & SQLAlchemy models

CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    order_id VARCHAR(50) UNIQUE NOT NULL,
    customer_name VARCHAR(255) NOT NULL,
    phone_number VARCHAR(50) NOT NULL,
    normalized_phone VARCHAR(50) NOT NULL,
    total_amount NUMERIC(10, 2) NOT NULL,
    has_upsell BOOLEAN DEFAULT FALSE,
    upsell_product VARCHAR(255),
    upsell_amount NUMERIC(10, 2) DEFAULT 0.00,
    status VARCHAR(50) DEFAULT 'طلب جديد مؤكد (COD)',
    event_id VARCHAR(100),
    city VARCHAR(100),
    region VARCHAR(100),
    country VARCHAR(50) DEFAULT 'MA',
    is_proxy BOOLEAN DEFAULT FALSE,
    risk_score NUMERIC(5, 2) DEFAULT 0.00,
    user_agent TEXT,
    client_ip VARCHAR(50),
    landing_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

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

CREATE TABLE IF NOT EXISTS redirect_rules (
    id SERIAL PRIMARY KEY,
    slug VARCHAR(80) UNIQUE NOT NULL,
    destination VARCHAR(500) NOT NULL,
    label VARCHAR(255),
    note TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indices for rapid querying
CREATE INDEX IF NOT EXISTS idx_orders_order_id ON orders(order_id);
CREATE INDEX IF NOT EXISTS idx_orders_phone ON orders(phone_number);
CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_tracking_events_order_id ON tracking_events(order_id);
CREATE INDEX IF NOT EXISTS idx_tracking_events_event_id ON tracking_events(event_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_redirect_rules_slug ON redirect_rules(slug);
