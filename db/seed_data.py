"""
Seed data into Supabase via REST API.
"""
import sys
import os
import random
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import supabase


def seed():
    # --- Stores ---
    stores = [
        {"id": "store-001", "name": "Main Warehouse", "location": "New York"},
        {"id": "store-002", "name": "West Coast Hub", "location": "Los Angeles"},
        {"id": "store-003", "name": "Istanbul Branch", "location": "Istanbul"},
    ]

    for store in stores:
        supabase.table("stores").upsert(store).execute()
    print(f"Inserted {len(stores)} stores")

    # --- Products ---
    products = [
        {"id": "PRD-001", "name": "Wireless Keyboard", "price": 79.99, "store_id": "store-001", "current_stock": 45, "avg_daily_sales": 8.5, "safety_stock": 30, "lead_time_days": 7},
        {"id": "PRD-002", "name": "USB-C Hub", "price": 49.99, "store_id": "store-001", "current_stock": 120, "avg_daily_sales": 3.2, "safety_stock": 20, "lead_time_days": 5},
        {"id": "PRD-003", "name": "Monitor Stand", "price": 129.99, "store_id": "store-002", "current_stock": 28, "avg_daily_sales": 1.8, "safety_stock": 15, "lead_time_days": 10},
        {"id": "PRD-004", "name": "Webcam HD Pro", "price": 149.99, "store_id": "store-003", "current_stock": 12, "avg_daily_sales": 4.2, "safety_stock": 25, "lead_time_days": 7},
        {"id": "PRD-005", "name": "Desk Lamp LED", "price": 34.99, "store_id": "store-003", "current_stock": 95, "avg_daily_sales": 2.1, "safety_stock": 20, "lead_time_days": 4},
        {"id": "PRD-006", "name": "Gaming Mouse", "price": 59.99, "store_id": "store-001", "current_stock": 60, "avg_daily_sales": 5, "safety_stock": 20, "lead_time_days": 6},
        {"id": "PRD-007", "name": "Mechanical Keyboard", "price": 99.99, "store_id": "store-002", "current_stock": 35, "avg_daily_sales": 2.5, "safety_stock": 15, "lead_time_days": 7},
        {"id": "PRD-008", "name": "Laptop Stand", "price": 39.99, "store_id": "store-003", "current_stock": 50, "avg_daily_sales": 3, "safety_stock": 20, "lead_time_days": 5},
        {"id": "PRD-009", "name": "Noise-Cancelling Headphones", "price": 199.99, "store_id": "store-001", "current_stock": 20, "avg_daily_sales": 1.2, "safety_stock": 10, "lead_time_days": 10},
        {"id": "PRD-010", "name": "HDMI Cable", "price": 14.99, "store_id": "store-002", "current_stock": 150, "avg_daily_sales": 7, "safety_stock": 50, "lead_time_days": 3},
    ]

    for product in products:
        supabase.table("products").upsert(product).execute()
    print(f"Inserted {len(products)} products")

    # --- Sales History (last 30 days) ---
    sale_id = 1
    today = datetime.utcnow().date()
    sales_batch = []

    for day_offset in range(30):
        sale_date = (today - timedelta(days=day_offset)).isoformat()
        for product in products:
            avg = product["avg_daily_sales"]
            qty = max(1, int(random.gauss(avg, avg * 0.3)))
            total = round(qty * product["price"], 2)

            sales_batch.append({
                "id": f"SALE-{sale_id:05d}",
                "product_id": product["id"],
                "store_id": product["store_id"],
                "quantity": qty,
                "unit_price": product["price"],
                "total_amount": total,
                "sale_date": sale_date,
                "created_at": datetime.utcnow().isoformat(),
            })
            sale_id += 1

    # Insert in batches of 50 to avoid request size limits
    batch_size = 50
    for i in range(0, len(sales_batch), batch_size):
        batch = sales_batch[i:i + batch_size]
        supabase.table("sales_history").upsert(batch).execute()

    print(f"Inserted {len(sales_batch)} sales records")
    print("Seed complete!")


if __name__ == "__main__":
    seed()
