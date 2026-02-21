-- Run this in Supabase SQL Editor (https://supabase.com/dashboard > SQL Editor)

CREATE TABLE IF NOT EXISTS stores (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    location TEXT
);

CREATE TABLE IF NOT EXISTS products (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    store_id TEXT REFERENCES stores(id),
    current_stock INTEGER DEFAULT 0,
    avg_daily_sales DOUBLE PRECISION DEFAULT 0,
    safety_stock INTEGER DEFAULT 0,
    lead_time_days INTEGER DEFAULT 7
);

CREATE TABLE IF NOT EXISTS sales_history (
    id TEXT PRIMARY KEY,
    product_id TEXT REFERENCES products(id),
    store_id TEXT REFERENCES stores(id),
    quantity INTEGER NOT NULL,
    unit_price DOUBLE PRECISION NOT NULL,
    total_amount DOUBLE PRECISION NOT NULL,
    sale_date TEXT NOT NULL,
    created_at TEXT DEFAULT NOW()::text
);

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    store_id TEXT REFERENCES stores(id),
    status TEXT DEFAULT 'active',
    created_at TEXT DEFAULT NOW()::text,
    updated_at TEXT DEFAULT NOW()::text
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT REFERENCES conversations(id),
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    intent TEXT,
    agent TEXT,
    created_at TEXT DEFAULT NOW()::text
);
