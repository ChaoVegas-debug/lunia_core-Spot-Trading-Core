"""
EPOCH D Phase D2: Historical Data Ingestion Tests (STANDALONE)
Tests persistence, idempotency, pagination WITHOUT full app loading
"""
import pytest
from datetime import datetime, timedelta, timezone

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from lunia_core.app.services.market_data.models import Candle
from lunia_core.app.services.market_data.ingestion import HistoricalDataService, TIMEFRAME_MS

# Create standalone Base for testing (avoid conftest issues)
TestBase = declarative_base()

# Import and rebind MarketCandle to TestBase
from sqlalchemy import Column, Integer, BigInteger, String, Float, Index, UniqueConstraint

class TestMarketCandle(TestBase):
    """Test-only MarketCandle model"""
    __tablename__ = "market_candles"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    exchange = Column(String(50), nullable=False, index=True)
    symbol = Column(String(50), nullable=False, index=True)
    timeframe = Column(String(10), nullable=False, index=True)
    timestamp_ms = Column(BigInteger, nullable=False, index=True)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)
    received_at_ms = Column(BigInteger, nullable=True)
    
    __table_args__ = (
        UniqueConstraint('exchange', 'symbol', 'timeframe', 'timestamp_ms', name='uq_candle_identity'),
        Index('idx_candle_query', 'exchange', 'symbol', 'timeframe', 'timestamp_ms'),
   )


@pytest.fixture
def db_session():
    """Create in-memory SQLite session for testing"""
    engine = create_engine("sqlite:///:memory:", echo=False)
    TestBase.metadata.create_all(engine)
    
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Monkey-patch service to use TestMarketCandle
    from lunia_core.app.services.market_data import ingestion
    original_model = ingestion.MarketCandle
    ingestion.MarketCandle = TestMarketCandle
    
    yield session
    
    # Restore
    ingestion.MarketCandle = original_model
    session.close()
    engine.dispose()


class SimpleMockAdapter:
    """Simple mock adapter without dependencies"""
    def __init__(self):
        self.call_count = 0
        self.candles_to_return = []
    
    def fetch_ohlcv(self, symbol, timeframe, limit=100):
        self.call_count += 1
        if self.call_count <= len(self.candles_to_return):
            return self.candles_to_return[self.call_count - 1]
        return []


def test_ingest_inserts_new_rows(db_session):
    """Ingestion should insert new candle rows"""
    service = HistoricalDataService(db_session)
    adapter = SimpleMockAdapter()
    
    base_ts = 1609459200000
    candles = [
        Candle(
            exchange="test_exchange",
            symbol="BTC/USDT",
            timeframe="1m",
            timestamp_ms=base_ts + (i * 60_000),
            open=50000.0,
            high=50100.0,
            low=49900.0,
            close=50000.0,
            volume=100.0
        )
        for i in range(5)
    ]
    
    adapter.candles_to_return = [candles]
    
    report = service.ingest_history(
        adapter=adapter,
        exchange="test_exchange",
        symbol="BTC/USDT",
        timeframe="1m",
        start_ms=base_ts,
        end_ms=base_ts + (10 * 60_000)
    )
    
    assert report.rows_seen == 5
    assert report.stopped_reason == "EMPTY_BATCH"
    
    count = db_session.query(TestMarketCandle).count()
    assert count == 5


def test_ingest_is_idempotent(db_session):
    """Re-ingestion should not create duplicates"""
    service = HistoricalDataService(db_session)
    adapter = SimpleMockAdapter()
    
    base_ts = 1609459200000
    candles = [
        Candle(
            exchange="test_exchange",
            symbol="BTC/USDT",
            timeframe="1m",
            timestamp_ms=base_ts + (i * 60_000),
            open=50000.0,
            high=50100.0,
            low=49900.0,
            close=50000.0,
            volume=100.0
        )
        for i in range(3)
    ]
    
    # First ingestion
    adapter.candles_to_return = [candles]
    report1 = service.ingest_history(
        adapter=adapter,
        exchange="test_exchange",
        symbol="BTC/USDT",
        timeframe="1m",
        start_ms=base_ts,
        end_ms=base_ts + (10 * 60_000)
    )
    
    count_after_first = db_session.query(TestMarketCandle).count()
    
    # Second ingestion (reset adapter)
    adapter.call_count = 0
    adapter.candles_to_return = [candles]
    
    report2 = service.ingest_history(
        adapter=adapter,
        exchange="test_exchange",
        symbol="BTC/USDT",
        timeframe="1m",
        start_ms=base_ts,
        end_ms=base_ts + (10 * 60_000)
    )
    
    count_after_second = db_session.query(TestMarketCandle).count()
    
    # No duplicates
    assert count_after_first == count_after_second == 3


def test_pagination_stops_at_empty_batch(db_session):
    """Pagination should stop when adapter returns empty batch"""
    service = HistoricalDataService(db_session)
    adapter = SimpleMockAdapter()
    
    base_ts = 1609459200000
    batch1 = [Candle(
        exchange="test_exchange",
        symbol="BTC/USDT",
        timeframe="1m",
        timestamp_ms=base_ts + (i * 60_000),
        open=50000.0,
        high=50100.0,
        low=49900.0,
        close=50000.0,
        volume=100.0
    ) for i in range(3)]
    
    batch2 = [Candle(
        exchange="test_exchange",
        symbol="BTC/USDT",
        timeframe="1m",
        timestamp_ms=base_ts + (i * 60_000),
        open=50000.0,
        high=50100.0,
        low=49900.0,
        close=50000.0,
        volume=100.0
    ) for i in range(3, 6)]
    
    adapter.candles_to_return = [batch1, batch2]
    
    report = service.ingest_history(
        adapter=adapter,
        exchange="test_exchange",
        symbol="BTC/USDT",
        timeframe="1m",
        start_ms=base_ts,
        end_ms=base_ts + (20 * 60_000)
    )
    
    assert report.batches == 2
    assert report.rows_seen == 6
    assert report.stopped_reason == "EMPTY_BATCH"


def test_no_progress_guard_triggers(db_session):
    """No-progress guard should abort on stuck cursor"""
    service = HistoricalDataService(db_session)
    adapter = SimpleMockAdapter()
    
    base_ts = 1609459200000
    stuck_candles = [Candle(
        exchange="test_exchange",
        symbol="BTC/USDT",
        timeframe="1m",
        timestamp_ms=base_ts,
        open=50000.0,
        high=50100.0,
        low=49900.0,
        close=50000.0,
        volume=100.0
    )]
    
    # Always return same candle (no progress)
    adapter.candles_to_return = [stuck_candles] * 10
    
    report = service.ingest_history(
        adapter=adapter,
        exchange="test_exchange",
        symbol="BTC/USDT",
        timeframe="1m",
        start_ms=base_ts,
        end_ms=base_ts + (10 * 60_000)
    )
    
    assert report.stopped_reason == "NO_PROGRESS"


def test_unknown_timeframe_fails(db_session):
    """Unknown timeframe should raise ValueError"""
    service = HistoricalDataService(db_session)
    adapter = SimpleMockAdapter()
    
    with pytest.raises(ValueError) as exc_info:
        service.ingest_history(
            adapter=adapter,
            exchange="test_exchange",
            symbol="BTC/USDT",
            timeframe="INVALID",
            start_ms=1609459200000,
            end_ms=1609459260000
        )
    
    assert "Unknown timeframe" in str(exc_info.value)


def test_timeframe_mapping():
    """Verify timeframe milliseconds mapping"""
    assert TIMEFRAME_MS["1m"] == 60_000
    assert TIMEFRAME_MS["5m"] == 300_000
    assert TIMEFRAME_MS["1h"] == 3_600_000
    assert TIMEFRAME_MS["1d"] == 86_400_000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
