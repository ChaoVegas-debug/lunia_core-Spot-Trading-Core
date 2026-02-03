"""
EPOCH D Phase D2: Historical Data Ingestion Tests
Tests persistence, idempotency, pagination, deduplication
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import Mock

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.services.auth.database import Base
from app.services.market_data.models import Candle
from app.services.market_data.models_db import MarketCandle
from app.services.market_data.ingestion import HistoricalDataService, TIMEFRAME_MS
from app.services.market_data.adapters.mock_adapter import MockExchangeAdapter


@pytest.fixture
def db_session():
    """Create in-memory SQLite session for testing"""
    engine = create_engine("sqlite:///memory:", echo=False)
    Base.metadata.create_all(engine)
    
    Session = sessionmaker(bind=engine)
    session = Session()
    
    yield session
    
    session.close()
    engine.dispose()


@pytest.fixture
def mock_adapter():
    """Create mock adapter with deterministic candles"""
    adapter = MockExchangeAdapter("test_exchange")
    return adapter


def test_ingest_inserts_new_rows(db_session, mock_adapter):
    """Ingestion should insert new candle rows"""
    service = HistoricalDataService(db_session)
    
    # Configure mock to return 5 candles
    base_ts = 1609459200000  # 2021-01-01 00:00:00 UTC
    mock_candles = [
        Candle(
            exchange="test_exchange",
            symbol="BTC/USDT",
            timeframe="1m",
            timestamp_ms=base_ts + (i * 60_000),
            open=50000.0 + i,
            high=50100.0 + i,
            low=49900.0 + i,
            close=50000.0 + i,
            volume=100.0
        )
        for i in range(5)
    ]
    
    mock_adapter.configure_error("fetch_ohlcv", None)  # Clear any errors
    original_fetch = mock_adapter.fetch_ohlcv
    
    def mock_fetch(symbol, timeframe, limit=100):
        # Return candles once, then empty
        if not hasattr(mock_fetch, 'called'):
            mock_fetch.called = True
            return mock_candles
        return []
    
    mock_adapter.fetch_ohlcv = mock_fetch
    
    # Ingest
    report = service.ingest_history(
        adapter=mock_adapter,
        exchange="test_exchange",
        symbol="BTC/USDT",
        timeframe="1m",
        start_ms=base_ts,
        end_ms=base_ts + (10 * 60_000),
        limit=100
    )
    
    # Verify
    assert report.rows_seen == 5
    assert report.rows_inserted >= 5  # SQLite may not track updates
    assert report.stopped_reason == "EMPTY_BATCH"
    
    # Check DB
    count = db_session.query(MarketCandle).count()
    assert count == 5


def test_ingest_is_idempotent_upsert(db_session, mock_adapter):
    """Re-ingestion should not create duplicates"""
    service = HistoricalDataService(db_session)
    
    base_ts = 1609459200000
    mock_candles = [
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
    
    def mock_fetch(symbol, timeframe, limit=100):
        if not hasattr(mock_fetch, 'call_count'):
            mock_fetch.call_count = 0
        mock_fetch.call_count += 1
        
        # Return candles on all calls (simulate overlap)
        if mock_fetch.call_count <= 2:
            return mock_candles
        return []
    
    mock_adapter.fetch_ohlcv = mock_fetch
    
    # First ingestion
    report1 = service.ingest_history(
        adapter=mock_adapter,
        exchange="test_exchange",
        symbol="BTC/USDT",
        timeframe="1m",
        start_ms=base_ts,
        end_ms=base_ts + (10 * 60_000)
    )
    
    count_after_first = db_session.query(MarketCandle).count()
    
    # Second ingestion (should be idempotent)
    mock_adapter.fetch_ohlcv = mock_fetch  # Reset
    mock_fetch.call_count = 0
    
    report2 = service.ingest_history(
        adapter=mock_adapter,
        exchange="test_exchange",
        symbol="BTC/USDT",
        timeframe="1m",
        start_ms=base_ts,
        end_ms=base_ts + (10 * 60_000)
    )
    
    count_after_second = db_session.query(MarketCandle).count()
    
    # Count should be the same (no duplicates)
    assert count_after_first == count_after_second
    assert count_after_first == 3


def test_pagination_advances_cursor_and_stops(db_session, mock_adapter):
    """Pagination should advance cursor and stop at end_ms"""
    service = HistoricalDataService(db_session)
    
    base_ts = 1609459200000
    
    # Mock returns 2 batches of 3 candles each
    batch_1 = [
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
    
    batch_2 = [
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
        for i in range(3, 6)
    ]
    
    call_count = [0]
    
    def mock_fetch(symbol, timeframe, limit=100):
        call_count[0] += 1
        if call_count[0] == 1:
            return batch_1
        elif call_count[0] == 2:
            return batch_2
        return []
    
    mock_adapter.fetch_ohlcv = mock_fetch
    
    # Ingest
    report = service.ingest_history(
        adapter=mock_adapter,
        exchange="test_exchange",
        symbol="BTC/USDT",
        timeframe="1m",
        start_ms=base_ts,
        end_ms=base_ts + (10 * 60_000)
    )
    
    # Verify pagination happened
    assert report.batches >= 2
    assert report.rows_seen == 6
    assert report.stopped_reason in ["EMPTY_BATCH", "COMPLETE"]


def test_dedup_on_overlap_batches(db_session, mock_adapter):
    """Overlapping batches should not create duplicates"""
    service = HistoricalDataService(db_session)
    
    base_ts = 1609459200000
    
    # Both batches contain overlapping candles
    batch_1 = [
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
    
    batch_2 = [
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
        for i in range(3, 8)  # Overlap: 3, 4 repeated
    ]
    
    call_count = [0]
    
    def mock_fetch(symbol, timeframe, limit=100):
        call_count[0] += 1
        if call_count[0] == 1:
            return batch_1
        elif call_count[0] == 2:
            return batch_2
        return []
    
    mock_adapter.fetch_ohlcv = mock_fetch
    
    # Ingest
    report = service.ingest_history(
        adapter=mock_adapter,
        exchange="test_exchange",
        symbol="BTC/USDT",
        timeframe="1m",
        start_ms=base_ts,
        end_ms=base_ts + (20 * 60_000)
    )
    
    # Verify no duplicates
    count = db_session.query(MarketCandle).count()
    assert count == 8  # 0-7 unique candles


def test_no_progress_guard_triggers_abort(db_session, mock_adapter):
    """No-progress guard should abort on stuck cursor"""
    service = HistoricalDataService(db_session)
    
    base_ts = 1609459200000
    
    # Mock always returns the same candles (no progress)
    stuck_candles = [
        Candle(
            exchange="test_exchange",
            symbol="BTC/USDT",
            timeframe="1m",
            timestamp_ms=base_ts,
            open=50000.0,
            high=50100.0,
            low=49900.0,
            close=50000.0,
            volume=100.0
        )
    ]
    
    mock_adapter.fetch_ohlcv = lambda *args, **kwargs: stuck_candles
    
    # Ingest (should abort due to no progress)
    report = service.ingest_history(
        adapter=mock_adapter,
        exchange="test_exchange",
        symbol="BTC/USDT",
        timeframe="1m",
        start_ms=base_ts,
        end_ms=base_ts + (10 * 60_000)
    )
    
    # Verify abort
    assert report.stopped_reason == "NO_PROGRESS"


def test_unknown_timeframe_fail_closed(db_session, mock_adapter):
    """Unknown timeframe should raise ValueError"""
    service = HistoricalDataService(db_session)
    
    with pytest.raises(ValueError) as exc_info:
        service.ingest_history(
            adapter=mock_adapter,
            exchange="test_exchange",
            symbol="BTC/USDT",
            timeframe="INVALID",
            start_ms=1609459200000,
            end_ms=1609459260000
        )
    
    assert "Unknown timeframe" in str(exc_info.value)


def test_timeframe_utilities():
    """Verify timeframe to milliseconds mapping"""
    assert TIMEFRAME_MS["1m"] == 60_000
    assert TIMEFRAME_MS["5m"] == 300_000
    assert TIMEFRAME_MS["15m"] == 900_000
    assert TIMEFRAME_MS["1h"] == 3_600_000
    assert TIMEFRAME_MS["4h"] == 14_400_000
    assert TIMEFRAME_MS["1d"] == 86_400_000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
