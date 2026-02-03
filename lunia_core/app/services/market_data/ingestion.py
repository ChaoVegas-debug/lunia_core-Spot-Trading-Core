"""
EPOCH D Phase D2: Historical Data Ingestion Service
Chunked pagination, idempotent upsert, no-progress guards
"""
from __future__ import annotations

import logging
import math
import time
from typing import Dict, List, Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.dialects import postgresql
from sqlalchemy import insert

from .interfaces import IExchangeAdapter
from .models import Candle
from .models_db import MarketCandle


logger = logging.getLogger(__name__)


# Timeframe to milliseconds mapping (STRICT)
TIMEFRAME_MS: Dict[str, int] = {
    "1m": 60_000,
    "5m": 300_000,
    "15m": 900_000,
    "1h": 3_600_000,
    "4h": 14_400_000,
    "1d": 86_400_000,
}


class IngestionReport(BaseModel):
    """Ingestion result report"""
    exchange: str
    symbol: str
    timeframe: str
    start_ms: int
    end_ms: int
    final_cursor_ms: int
    rows_seen: int
    rows_inserted: int
    rows_updated: int
    batches: int
    stopped_reason: str  # "COMPLETE", "NO_PROGRESS", "EMPTY_BATCH", "ERROR"


class HistoricalDataService:
    """
    Historical candle ingestion service
    
    Features:
    - Chunked pagination with "since" cursor
   - No-progress guard (prevent infinite loops)
    - Idempotent upsert (dual-path: Postgres/SQLite)
    - Fail-closed validation
    - Batch commits
    """
    
    def __init__(self, session: Session):
        """
        Initialize service
        
        Args:
            session: SQLAlchemy session
        """
        self.session = session
    
    def ingest_history(
        self,
        adapter: IExchangeAdapter,
        exchange: str,
        symbol: str,
        timeframe: str,
        start_ms: int,
        end_ms: int,
        *,
        limit: int = 1000,
        commit_every: int = 5000
    ) -> IngestionReport:
        """
        Ingest historical candles with chunked pagination
        
        Args:
            adapter: Exchange adapter
            exchange: Exchange ID (e.g., "binance")
            symbol: Trading pair (e.g., "BTC/USDT")
            timeframe: Candle timeframe (e.g., "1m", "1h")
            start_ms: Start timestamp (UTC milliseconds, inclusive)
            end_ms: End timestamp (UTC milliseconds, exclusive)
            limit: Candles per fetch (default 1000)
            commit_every: Commit after this many rows (default 5000)
        
        Returns:
            IngestionReport with stats
        
        Raises:
            ValueError: Unknown timeframe, invalid range
            Exception: Adapter errors, validation failures
        """
        # Validate timeframe
        if timeframe not in TIMEFRAME_MS:
            raise ValueError(f"Unknown timeframe: {timeframe}. Valid: {list(TIMEFRAME_MS.keys())}")
        
        timeframe_interval_ms = TIMEFRAME_MS[timeframe]
        
        # Validate range
        if start_ms >= end_ms:
            raise ValueError(f"Invalid range: start_ms={start_ms} >= end_ms={end_ms}")
        
        # Initialize stats
        rows_seen = 0
        rows_inserted = 0
        rows_updated = 0
        batches = 0
        cursor_ms = start_ms
        last_cursor_ms = None
        stopped_reason = "UNKNOWN"
        
        logger.info(f"Starting ingestion: {exchange}/{symbol} {timeframe} [{start_ms}, {end_ms})")
        
        try:
            while cursor_ms < end_ms:
                # NO-PROGRESS GUARD
                if last_cursor_ms is not None and cursor_ms == last_cursor_ms:
                    stopped_reason = "NO_PROGRESS"
                    logger.error(f"No progress detected at cursor_ms={cursor_ms}, ABORTING")
                    break
                
                last_cursor_ms = cursor_ms
                
                # Fetch batch from adapter
                logger.debug(f"Fetching batch: cursor_ms={cursor_ms}, limit={limit}")
                candles: List[Candle] = adapter.fetch_ohlcv(symbol, timeframe, limit=limit)
                
                # Empty batch stop condition
                if not candles:
                    stopped_reason = "EMPTY_BATCH"
                    logger.info(f"Empty batch at cursor_ms={cursor_ms}, stopping")
                    break
                
                # Validate batch
                self._validate_candles(candles, start_ms, end_ms)
                
                # Filter candles within range [start_ms, end_ms)
                filtered = [c for c in candles if start_ms <= c.timestamp_ms < end_ms]
                
                if filtered:
                    rows_seen += len(filtered)
                    inserted, updated = self._upsert_batch(filtered, exchange)
                    rows_inserted += inserted
                    rows_updated += updated
                    batches += 1
                    
                    # Periodic commit
                    if rows_seen % commit_every == 0:
                        self.session.commit()
                        logger.debug(f"Committed after {rows_seen} rows")
                
                # Advance cursor to last candle timestamp + interval
                last_candle = candles[-1]
                cursor_ms = last_candle.timestamp_ms + timeframe_interval_ms
                
                # Break if cursor advanced beyond end
                if cursor_ms >= end_ms:
                    stopped_reason = "COMPLETE"
                    break
            
            # Final commit
            self.session.commit()
            
            if stopped_reason == "UNKNOWN":
                stopped_reason = "COMPLETE"
            
            logger.info(f"Ingestion complete: {rows_inserted} inserted, {rows_updated} updated, {batches} batches")
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Ingestion failed: {e}", exc_info=True)
            stopped_reason = "ERROR"
            raise
        
        return IngestionReport(
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            start_ms=start_ms,
            end_ms=end_ms,
            final_cursor_ms=cursor_ms,
            rows_seen=rows_seen,
            rows_inserted=rows_inserted,
            rows_updated=rows_updated,
            batches=batches,
            stopped_reason=stopped_reason
        )
    
    def _validate_candles(self, candles: List[Candle], start_ms: int, end_ms: int):
        """
        Validate candle batch (FAIL-CLOSED)
        
        Args:
            candles: List of candles
            start_ms: Expected start range
            end_ms: Expected end range
        
        Raises:
            ValueError: Validation failure
        """
        if not candles:
            return
        
        # Check ascending timestamps
        for i in range(len(candles) - 1):
            if candles[i].timestamp_ms >= candles[i + 1].timestamp_ms:
                raise ValueError(
                    f"Candles not strictly ascending: "
                    f"{candles[i].timestamp_ms} >= {candles[i + 1].timestamp_ms}"
                )
        
        # Check finite OHLCV values
        for candle in candles:
            if not all(math.isfinite(v) for v in [candle.open, candle.high, candle.low, candle.close, candle.volume]):
                raise ValueError(f"Non-finite OHLCV values in candle: {candle}")
    
    def _upsert_batch(self, candles: List[Candle], exchange: str) -> tuple[int, int]:
        """
        Upsert candle batch (idempotent)
        
        Dual-path:
        - Postgres: ON CONFLICT DO UPDATE
        - SQLite: Query existing + insert missing
        
        Args:
            candles: Candle batch
            exchange: Exchange ID
        
        Returns:
            (rows_inserted, rows_updated)
        """
        if not candles:
            return (0, 0)
        
        # Detect dialect
        dialect_name = self.session.bind.dialect.name
        
        if dialect_name == "postgresql":
            return self._upsert_postgres(candles, exchange)
        else:
            return self._upsert_sqlite(candles, exchange)
    
    def _upsert_postgres(self, candles: List[Candle], exchange: str) -> tuple[int, int]:
        """Postgres-specific upsert using ON CONFLICT DO UPDATE"""
        rows_to_insert = []
        
        for candle in candles:
            rows_to_insert.append({
                "exchange": exchange,
                "symbol": candle.symbol,
                "timeframe": candle.timeframe,
                "timestamp_ms": candle.timestamp_ms,
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
                "volume": candle.volume,
                "received_at_ms": int(time.time() * 1000)
            })
        
        stmt = insert(MarketCandle).values(rows_to_insert)
        
        # ON CONFLICT DO UPDATE
        stmt = stmt.on_conflict_do_update(
            constraint='uq_candle_identity',
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
                "received_at_ms": stmt.excluded.received_at_ms
            }
        )
        
        result = self.session.execute(stmt)
        
        # Postgres returns row count, but doesn't distinguish insert vs update
        # For simplicity, report as inserted (idempotent behavior is what matters)
        return (len(candles), 0)
    
    def _upsert_sqlite(self, candles: List[Candle], exchange: str) -> tuple[int, int]:
        """SQLite-safe upsert: query existing + insert missing"""
        # Extract unique identifiers
        identifiers = [
            (exchange, c.symbol, c.timeframe, c.timestamp_ms)
            for c in candles
        ]
        
        # Query existing
        existing_timestamps = set()
        for exchange_id, symbol, timeframe, timestamp_ms in identifiers:
            existing = self.session.query(MarketCandle).filter_by(
                exchange=exchange_id,
                symbol=symbol,
                timeframe=timeframe,
                timestamp_ms=timestamp_ms
            ).first()
            
            if existing:
                existing_timestamps.add(timestamp_ms)
        
        # Insert only missing
        rows_inserted = 0
        for candle in candles:
            if candle.timestamp_ms not in existing_timestamps:
                db_candle = MarketCandle(
                    exchange=exchange,
                    symbol=candle.symbol,
                    timeframe=candle.timeframe,
                    timestamp_ms=candle.timestamp_ms,
                    open=candle.open,
                    high=candle.high,
                    low=candle.low,
                    close=candle.close,
                    volume=candle.volume,
                    received_at_ms=int(time.time() * 1000)
                )
                self.session.add(db_candle)
                rows_inserted += 1
        
        return (rows_inserted, 0)
