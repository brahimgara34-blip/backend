-- =========================================================================
-- Vitalis Maroc™ — Database Migration 001: Admin Dashboard & Analytics
-- =========================================================================
-- تشغيل هذا الملف ينشئ جميع الجداول والمؤشرات الإضافية للوحة التحكم الإدارية
-- وتتبع النقرات المفلترة لزوار المغرب (Clean Moroccan IPs - No VPN).
-- =========================================================================

-- 1. جدول الطلبات (Orders) — التأكد من وجود كافة الحقول
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    order_id VARCHAR(50) UNIQUE NOT NULL,
    customer_name VARCHAR(255) NOT NULL,
    phone_number VARCHAR(50) NOT NULL,
    normalized_phone VARCHAR(50),
    items JSONB,
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
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. جدول عناصر الطلب (Order Items)
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

-- 3. جدول أحداث التتبع والـ CAPI (Tracking Events)
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

-- 4. جدول نقرات وزيارات المتجر وتصفية الـ VPN (Analytics Clicks)
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

-- 5. المؤشرات السريعة لتسريع استعلامات لوحة التحكم (Indexes)
CREATE INDEX IF NOT EXISTS idx_orders_order_id ON orders(order_id);
CREATE INDEX IF NOT EXISTS idx_orders_phone ON orders(phone_number);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at);
CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_tracking_events_order_id ON tracking_events(order_id);
CREATE INDEX IF NOT EXISTS idx_analytics_clicks_created_at ON analytics_clicks(created_at);
CREATE INDEX IF NOT EXISTS idx_analytics_clicks_valid ON analytics_clicks(is_valid_morocco);
CREATE INDEX IF NOT EXISTS idx_analytics_clicks_path ON analytics_clicks(path);
