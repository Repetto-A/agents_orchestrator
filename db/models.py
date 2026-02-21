from sqlalchemy import Column, Integer, String, Float, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class Store(Base):
    __tablename__ = "stores"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    location = Column(String)


class Product(Base):
    __tablename__ = "products"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    store_id = Column(String, ForeignKey("stores.id"))
    current_stock = Column(Integer, default=0)
    avg_daily_sales = Column(Float, default=0)
    safety_stock = Column(Integer, default=0)
    lead_time_days = Column(Integer, default=7)


class SalesHistory(Base):
    __tablename__ = "sales_history"

    id = Column(String, primary_key=True)
    product_id = Column(String, ForeignKey("products.id"))
    store_id = Column(String, ForeignKey("stores.id"))
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)
    total_amount = Column(Float, nullable=False)
    sale_date = Column(String, nullable=False)
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True)
    store_id = Column(String, ForeignKey("stores.id"))
    status = Column(String, default="active")
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())
    updated_at = Column(String, default=lambda: datetime.utcnow().isoformat())


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True)
    conversation_id = Column(String, ForeignKey("conversations.id"))
    role = Column(String, nullable=False)  # user, assistant
    content = Column(Text, nullable=False)
    intent = Column(String)
    agent = Column(String)
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())
