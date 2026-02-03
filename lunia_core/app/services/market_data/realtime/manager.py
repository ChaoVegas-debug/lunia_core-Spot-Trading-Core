"""
EPOCH D Phase D3.1: Real-Time Market Data Engine
Async-safe snapshot manager with L2 integrity guards, staleness detection, startup barrier
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Dict, Optional, Set
from copy import deepcopy

from .models import (
    MarketSnapshot,
    SnapshotState,
    TickerUpdate,
    OrderBookL2,
    PriceLevel
)
from .buffers import BoundedBuffer
from .interfaces import IWebSocketClient
from .synchronous import ThreadSafeSnapshotCache


logger = logging.getLogger(__name__)


class RealTimeMarketDataEngine:
    """
    Real-time market data engine with fail-closed semantics
    
    Features:
    - Async-safe (asyncio.Lock for all snapshot access)
    - L2 integrity guards (crossed book, price validation, ordering)
    - Staleness detection (configurable threshold)
    - Startup barrier (await_ready per symbol)
    - Symbol-level isolation
    - Graceful shutdown with task cleanup
    - Zero execution side effects (read-only)
    
    State Model:
    - VALID: Fresh + L2-consistent
    - STALE: Timeout OR disconnect OR partial data
    - INVALID: L2 integrity violation
    """
    
    # Configuration
    DEFAULT_STALENESS_THRESHOLD_MS = 5000  # 5 seconds
    DEFAULT_BUFFER_SIZE = 1000
    DEFAULT_L2_DEPTH = 20
    
    def __init__(
        self,
        client: IWebSocketClient,
        staleness_threshold_ms: int = DEFAULT_STALENESS_THRESHOLD_MS,
        buffer_size: int = DEFAULT_BUFFER_SIZE,
        l2_depth: int = DEFAULT_L2_DEPTH
    ):
        """
        Initialize engine
        
        Args:
            client: WebSocket client implementation
            staleness_threshold_ms: Staleness threshold (default 5000ms)
            buffer_size: Update buffer size per symbol
            l2_depth: L2 order book depth
        """
        self.client = client
        self.staleness_threshold_ms = staleness_threshold_ms
        self.buffer_size = buffer_size
        self.l2_depth = l2_depth
        
        # Per-symbol state
        self._snapshots: Dict[str, MarketSnapshot] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._ticker_buffers: Dict[str, BoundedBuffer[TickerUpdate]] = {}
        self._orderbook_buffers: Dict[str, BoundedBuffer[OrderBookL2]] = {}
        self._tasks: Dict[str, Set[asyncio.Task]] = {}
        self._ready_events: Dict[str, asyncio.Event] = {}
        
        # Sync cache for thread-safe access from sync worker
        self._sync_cache = ThreadSafeSnapshotCache()
        
        # Lifecycle
        self._active = False
        self._shutdown_event = asyncio.Event()
    
    async def start(
        self,
        exchange: str,
        symbols: list[str],
        market_type: str = "spot"
    ):
        """
        Start engine and subscribe to symbols
        
        Args:
            exchange: Exchange ID
            symbols: List of trading pairs
            market_type: Market type ("spot", "swap", "future")
        """
        if self._active:
            raise RuntimeError("Engine already started")
        
        self._active = True
        logger.info(f"Starting RealTimeMarketDataEngine: {exchange} {market_type} {symbols}")
        
        # Connect client
        await self.client.connect(exchange, market_type)
        
        # Initialize per-symbol state
        for symbol in symbols:
            # Create snapshot (STALE by default)
            self._snapshots[symbol] = MarketSnapshot(
                exchange=exchange,
                symbol=symbol,
                market_type=market_type,
                last_update_ms=int(time.time() * 1000),
                snapshot_state=SnapshotState.STALE
            )
            
            # Create lock
            self._locks[symbol] = asyncio.Lock()
            
            # Create buffers
            self._ticker_buffers[symbol] = BoundedBuffer(self.buffer_size)
            self._orderbook_buffers[symbol] = BoundedBuffer(self.buffer_size)
            
            # Create ready event
            self._ready_events[symbol] = asyncio.Event()
            
            # Spawn tasks
            self._tasks[symbol] = set()
            
            ticker_task = asyncio.create_task(
                self._ticker_loop(symbol),
                name=f"ticker_{symbol}"
            )
            orderbook_task = asyncio.create_task(
                self._orderbook_loop(symbol),
                name=f"orderbook_{symbol}"
            )
            staleness_task = asyncio.create_task(
                self._staleness_monitor(symbol),
                name=f"staleness_{symbol}"
            )
            
            self._tasks[symbol].add(ticker_task)
            self._tasks[symbol].add(orderbook_task)
            self._tasks[symbol].add(staleness_task)
        
        logger.info(f"Engine started: {len(symbols)} symbols active")
    
    async def stop(self):
        """
        Stop engine and clean up tasks
        
        - Cancel all tasks
        - Mark all snapshots STALE
        - Disconnect client
        """
        if not self._active:
            return
        
        logger.info("Stopping RealTimeMarketDataEngine")
        self._active = False
        self._shutdown_event.set()
        
        # Cancel all tasks
        all_tasks = []
        for symbol_tasks in self._tasks.values():
            all_tasks.extend(symbol_tasks)
        
        for task in all_tasks:
            task.cancel()
        
        # Wait for cancellation with timeout
        if all_tasks:
            await asyncio.gather(*all_tasks, return_exceptions=True)
        
        # Mark all snapshots STALE
        for symbol in self._snapshots.keys():
            async with self._locks[symbol]:
                self._snapshots[symbol].snapshot_state = SnapshotState.STALE
        
        # Disconnect client
        await self.client.disconnect()
        
        logger.info("Engine stopped")
    
    async def _ticker_loop(self, symbol: str):
        """
        Ticker update loop for a symbol
        
        Args:
            symbol: Trading pair
        """
        try:
            async for update in self.client.watch_ticker(symbol):
                if not self._active:
                    break
                
                # Buffer update
                self._ticker_buffers[symbol].append(update)
                
                # Apply to snapshot
                await self._apply_ticker_update(symbol, update)
        
        except asyncio.CancelledError:
            logger.debug(f"Ticker loop cancelled: {symbol}")
        except Exception as e:
            logger.error(f"Ticker loop error: {symbol}: {e}", exc_info=True)
            # Mark snapshot STALE on error
            async with self._locks[symbol]:
                self._snapshots[symbol].snapshot_state = SnapshotState.STALE
    
    async def _orderbook_loop(self, symbol: str):
        """
        Order book update loop for a symbol
        
        Args:
            symbol: Trading pair
        """
        try:
            async for update in self.client.watch_order_book(symbol, limit=self.l2_depth):
                if not self._active:
                    break
                
                # Buffer update
                self._orderbook_buffers[symbol].append(update)
                
                # Validate and apply to snapshot
                await self._apply_orderbook_update(symbol, update)
        
        except asyncio.CancelledError:
            logger.debug(f"Orderbook loop cancelled: {symbol}")
        except Exception as e:
            logger.error(f"Orderbook loop error: {symbol}: {e}", exc_info=True)
            # Mark snapshot STALE on error
            async with self._locks[symbol]:
                self._snapshots[symbol].snapshot_state = SnapshotState.STALE
    
    async def _staleness_monitor(self, symbol: str):
        """
        Monitor staleness for a symbol
        
        Checks every second if snapshot has exceeded staleness threshold.
        
        Args:
            symbol: Trading pair
        """
        try:
            while self._active:
                await asyncio.sleep(1.0)
                
                now_ms = int(time.time() * 1000)
                
                async with self._locks[symbol]:
                    snapshot = self._snapshots[symbol]
                    
                    # Check staleness
                    age_ms = now_ms - snapshot.last_update_ms
                    
                    if age_ms > self.staleness_threshold_ms:
                        if snapshot.snapshot_state == SnapshotState.VALID:
                            logger.warning(f"Snapshot stale: {symbol} (age={age_ms}ms)")
                            snapshot.snapshot_state = SnapshotState.STALE
        
        except asyncio.CancelledError:
            logger.debug(f"Staleness monitor cancelled: {symbol}")
    
    async def _apply_ticker_update(self, symbol: str, update: TickerUpdate):
        """
        Apply ticker update to snapshot (atomic, locked)
        
        Args:
            symbol: Trading pair
            update: Ticker update
        """
        async with self._locks[symbol]:
            snapshot = self._snapshots[symbol]
            
            # Monotonic timestamp guard
            if update.timestamp_ms is not None:
                if snapshot.last_exchange_ts is not None:
                    if update.timestamp_ms < snapshot.last_exchange_ts:
                        logger.warning(f"Non-monotonic ticker timestamp: {symbol}")
                        snapshot.snapshot_state = SnapshotState.STALE
                        return
            
            # Update ticker data
            snapshot.bid = update.bid
            snapshot.ask = update.ask
            snapshot.last = update.last
            
            # Compute mid price
            if update.bid is not None and update.ask is not None:
                snapshot.mid_price = (update.bid + update.ask) / 2.0
            
            # Update timestamps
            snapshot.last_update_ms = update.received_at_ms
            if update.timestamp_ms:
                snapshot.last_exchange_ts = update.timestamp_ms
                snapshot.system_latency_ms = update.received_at_ms - update.timestamp_ms
            
            # Mark has_ticker
            snapshot.has_ticker = True
            
            # Increment version
            snapshot.version += 1
            
            # Recompute snapshot state
            self._recompute_snapshot_state(snapshot)
            
            # Push to sync cache (for thread-safe worker access)
            self._sync_cache.update(symbol, snapshot)
            # Set ready if VALID
            if snapshot.snapshot_state == SnapshotState.VALID:
                self._ready_events[symbol].set()
    
    async def _apply_orderbook_update(self, symbol: str, update: OrderBookL2):
        """
        Apply order book update to snapshot (atomic, locked, validated)
        
        Args:
            symbol: Trading pair
            update: Order book update
        """
        # Validate L2 integrity BEFORE acquiring lock
        try:
            self._validate_l2_integrity(update)
        except ValueError as e:
            logger.error(f"L2 integrity violation: {symbol}: {e}")
            async with self._locks[symbol]:
                self._snapshots[symbol].snapshot_state = SnapshotState.INVALID
            return
        
        async with self._locks[symbol]:
            snapshot = self._snapshots[symbol]
            
            # Monotonic timestamp guard
            if update.timestamp_ms is not None:
                if snapshot.last_exchange_ts is not None:
                    if update.timestamp_ms < snapshot.last_exchange_ts:
                        logger.warning(f"Non-monotonic orderbook timestamp: {symbol}")
                        snapshot.snapshot_state = SnapshotState.STALE
                        return
            
            # Update L2 data
            snapshot.bids = update.bids[:self.l2_depth]
            snapshot.asks = update.asks[:self.l2_depth]
            
            # Update timestamps
            snapshot.last_update_ms = update.received_at_ms
            if update.timestamp_ms:
                snapshot.last_exchange_ts = update.timestamp_ms
                snapshot.system_latency_ms = update.received_at_ms - update.timestamp_ms
            
            # Mark has_orderbook
            snapshot.has_orderbook = True
            
            # Increment version
            snapshot.version += 1
            
            # Recompute snapshot state
            self._recompute_snapshot_state(snapshot)
            
            # Push to sync cache (for thread-safe worker access)
            self._sync_cache.update(symbol, snapshot)
            # Set ready if VALID
            if snapshot.snapshot_state == SnapshotState.VALID:
                self._ready_events[symbol].set()
    
    def _validate_l2_integrity(self, update: OrderBookL2):
        """
        Validate L2 integrity (FAIL-CLOSED)
        
        Checks:
        - Best bid < best ask (no crossed book)
        - All prices > 0
        - All amounts > 0
        - Bids strictly descending
        - Asks strictly ascending
        - No duplicate price levels
        
        Args:
            update: Order book update
        
        Raises:
            ValueError: L2 integrity violation
        """
        # Check crossed book
        if update.bids and update.asks:
            best_bid = update.bids[0].price
            best_ask = update.asks[0].price
            
            if best_bid >= best_ask:
                raise ValueError(f"Crossed book: bid={best_bid} >= ask={best_ask}")
        
        # Check bids
        seen_bid_prices = set()
        for i, bid in enumerate(update.bids):
            # Price/amount > 0
            if bid.price <= 0 or bid.amount <= 0:
                raise ValueError(f"Invalid bid: price={bid.price}, amount={bid.amount}")
            
            # No duplicates
            if bid.price in seen_bid_prices:
                raise ValueError(f"Duplicate bid price: {bid.price}")
            seen_bid_prices.add(bid.price)
            
            # Strictly descending
            if i > 0:
                if bid.price >= update.bids[i - 1].price:
                    raise ValueError(f"Bids not descending: {bid.price} >= {update.bids[i-1].price}")
        
        # Check asks
        seen_ask_prices = set()
        for i, ask in enumerate(update.asks):
            # Price/amount > 0
            if ask.price <= 0 or ask.amount <= 0:
                raise ValueError(f"Invalid ask: price={ask.price}, amount={ask.amount}")
            
            # No duplicates
            if ask.price in seen_ask_prices:
                raise ValueError(f"Duplicate ask price: {ask.price}")
            seen_ask_prices.add(ask.price)
            
            # Strictly ascending
            if i > 0:
                if ask.price <= update.asks[i - 1].price:
                    raise ValueError(f"Asks not ascending: {ask.price} <= {update.asks[i-1].price}")
    
    def _recompute_snapshot_state(self, snapshot: MarketSnapshot):
        """
        Recompute snapshot state based on current data
        
        Logic:
        - If missing ticker OR orderbook → STALE (partial data)
        - If crossed book → INVALID
        - Otherwise → VALID
        
        Args:
            snapshot: Snapshot to update
        """
        # Partial data check
        if not snapshot.has_ticker or not snapshot.has_orderbook:
            snapshot.snapshot_state = SnapshotState.STALE
            return
        
        # Crossed book check (at snapshot level)
        if snapshot.bid is not None and snapshot.ask is not None:
            if snapshot.bid >= snapshot.ask:
                logger.error(f"Crossed book in snapshot: {snapshot.symbol} bid={snapshot.bid} >= ask={snapshot.ask}")
                snapshot.snapshot_state = SnapshotState.INVALID
                return
        
        # All checks passed
        snapshot.snapshot_state = SnapshotState.VALID
    
    async def get_snapshot(self, symbol: str) -> Optional[MarketSnapshot]:
        """
        Get market snapshot for symbol (deep copy, async-safe)
        
        Args:
            symbol: Trading pair
        
        Returns:
            MarketSnapshot (deep copy) or None if symbol not tracked
        """
        if symbol not in self._snapshots:
            return None
        
        async with self._locks[symbol]:
            return deepcopy(self._snapshots[symbol])
    
    async def wait_until_ready(self, symbol: str, timeout: float = 30.0) -> bool:
        """
        Wait until snapshot is VALID (startup barrier)
        
        Args:
            symbol: Trading pair
            timeout: Timeout in seconds
        
        Returns:
            True if ready, False if timeout
        """
        if symbol not in self._ready_events:
            return False
        
        try:
            await asyncio.wait_for(
                self._ready_events[symbol].wait(),
                timeout=timeout
            )
            return True
        except asyncio.TimeoutError:
            logger.warning(f"Ready timeout: {symbol} after {timeout}s")
            return False
    
    async def get_health(self) -> dict:
        """
        Get health metrics (internal observability)
        
        Returns:
            Health dict with per-symbol and aggregate stats
        """
        health = {
            "active": self._active,
            "symbols": {},
            "aggregate": {
                "total_symbols": len(self._snapshots),
                "valid_count": 0,
                "stale_count": 0,
                "invalid_count": 0
            }
        }
        
        for symbol, lock in self._locks.items():
            async with lock:
                snapshot = self._snapshots[symbol]
                
                symbol_health = {
                    "state": snapshot.snapshot_state.value,
                    "version": snapshot.version,
                    "has_ticker": snapshot.has_ticker,
                    "has_orderbook": snapshot.has_orderbook,
                    "last_update_ms": snapshot.last_update_ms,
                    "age_ms": int(time.time() * 1000) - snapshot.last_update_ms,
                    "system_latency_ms": snapshot.system_latency_ms,
                    "ticker_buffer_dropped": self._ticker_buffers[symbol].dropped_count,
                    "orderbook_buffer_dropped": self._orderbook_buffers[symbol].dropped_count
                }
                
                health["symbols"][symbol] = symbol_health
                
                # Aggregate stats
                if snapshot.snapshot_state == SnapshotState.VALID:
                    health["aggregate"]["valid_count"] += 1
                elif snapshot.snapshot_state == SnapshotState.STALE:
                    health["aggregate"]["stale_count"] += 1
                else:
                    health["aggregate"]["invalid_count"] += 1
        
        return health
    
    def get_sync_cache(self) -> ThreadSafeSnapshotCache:
        """
        Get sync cache for thread-safe access from sync worker
        
        Returns:
            ThreadSafeSnapshotCache instance
        """
        return self._sync_cache
