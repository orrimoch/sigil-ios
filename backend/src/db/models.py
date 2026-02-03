"""
Database models for Sigil.
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, BigInteger
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class Stock(Base):
    """Stock universe table."""
    
    __tablename__ = "stocks"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    sector = Column(String(100))
    industry = Column(String(100))
    market_cap = Column(BigInteger)
    currency = Column(String(10), default="USD")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            "id": self.id,
            "ticker": self.ticker,
            "name": self.name,
            "sector": self.sector,
            "industry": self.industry,
            "market_cap": self.market_cap,
            "currency": self.currency,
            "is_active": self.is_active,
        }


class Score(Base):
    """Weekly stock scores table."""
    
    __tablename__ = "scores"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_id = Column(Integer, nullable=False, index=True)
    score_date = Column(DateTime, nullable=False, index=True)
    
    # Composite score (0-100)
    composite_score = Column(Float)
    
    # Component scores (0-100)
    fundamental_score = Column(Float)
    sentiment_score = Column(Float)
    macro_score = Column(Float)
    technical_score = Column(Float)
    
    # Signal: 'buy', 'hold', 'sell'
    signal = Column(String(10))
    
    created_at = Column(DateTime, default=datetime.utcnow)


class Position(Base):
    """Portfolio positions table."""
    
    __tablename__ = "positions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    stock_id = Column(Integer, nullable=False)
    
    quantity = Column(Float, default=0)
    avg_cost = Column(Float, default=0)
    
    is_paper = Column(Boolean, default=True)
    opened_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)


class Order(Base):
    """Trading orders table."""
    
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    stock_id = Column(Integer, nullable=False)
    
    side = Column(String(10))  # 'buy' or 'sell'
    order_type = Column(String(20))  # 'market', 'limit'
    quantity = Column(Float)
    limit_price = Column(Float, nullable=True)
    
    status = Column(String(20), default="pending")  # 'pending', 'filled', 'cancelled'
    fill_price = Column(Float, nullable=True)
    
    is_paper = Column(Boolean, default=True)
    ibkr_order_id = Column(String(50), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    filled_at = Column(DateTime, nullable=True)
