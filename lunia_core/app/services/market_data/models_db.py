"""
EPOCH D Phase D2: Market Data Database Models
SQLAlchemy persistence for historical OHLCV candles
"""
from __future__ import annotations

from sqlalchemy import Column, Integer, BigInteger, String, Float, Index, UniqueConstraint

from ..auth.database import Base


class MarketCandle(Base):
    """
    Historical OHLCV candle persistence
    
    Idempotent storage enforced by UNIQUE(exchange, symbol, timeframe, timestamp_ms)
    """
    __tablename__ = "market_candles"
    
    # Primary key
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # Identity fields (UNIQUE constraint)
    exchange = Column(String(50), nullable=False, index=True)
    symbol = Column(String(50), nullable=False, index=True)
    timeframe = Column(String(10), nullable=False, index=True)
    timestamp_ms = Column(BigInteger, nullable=False, index=True)  # Candle open time (UTC ms)
    
    # OHLCV data
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)
    
    # Forensic timestamp
    received_at_ms = Column(BigInteger, nullable=True)  # Local ingestion time
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('exchange', 'symbol', 'timeframe', 'timestamp_ms', name='uq_candle_identity'),
        Index('idx_candle_query', 'exchange', 'symbol', 'timeframe', 'timestamp_ms'),
    )
    
    def __repr__(self):
        return f"<MarketCandle({self.exchange}/{self.symbol} {self.timeframe} @ {self.timestamp_ms})>"
