"""
Create tables in Supabase PostgreSQL.
Uses async databases library (same as the app).
"""
import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import database

TABLES_SQL = """
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
"""


async def create_tables():
    await database.connect()
    # Execute each statement separately
    for statement in TABLES_SQL.strip().split(";"):
        statement = statement.strip()
        if statement:
            await database.execute(statement)
    await database.disconnect()
    print("Tables created!")


if __name__ == "__main__":
    asyncio.run(create_tables())
