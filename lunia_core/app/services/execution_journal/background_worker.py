"""
Phase 8.2B: PulseWorker - Async Nervous System Background Worker
Production-grade async intent processing with bounded queue and fail-safe semantics
"""
from __future__ import annotations

import json
import logging
import queue
import threading
import time
from copy import deepcopy
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PAYLOAD CONTRACT (IMMUTABLE)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass(frozen=True)
class IntentEnvelope:
    """
    Immutable payload for async intent processing
    
    CRITICAL: l2_capture MUST be a deep copy captured synchronously at signal time
    Worker MUST NEVER re-read live orderbook
    """
    intent_id: Optional[str]
    strategy_id: str
    symbol: str
    signal_type: str  # BUY / SELL / HOLD
    created_at_ms: int
    timestamp_bucket: int
    dedup_key: str
    l1_snapshot: Dict[str, Any]  # already captured synchronously
    l2_capture: Tuple[List[Dict], List[Dict]]  # (bids, asks) DEEP COPY
    governance_metadata: Optional[Dict[str, Any]] = None
    rationale: Optional[str] = None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CONFIGURATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class NervousConfig:
    """PulseWorker configuration knobs"""
    enabled: bool = True
    queue_maxsize: int = 1000
    drop_policy: str = "drop_newest"  # only supported policy
    worker_threads: int = 1  # single-threaded for v1
    enable_ai_after_noise_gate: bool = False  # DEFAULT OFF
    shutdown_timeout_ms: int = 5000
    max_snapshot_size_bytes: int = 10240  # 10KB hard limit
    nervous_enable_market_state: bool = True  # Phase 8.3: market enrichment (DEFAULT ON, fail-safe)
    market_state_timeout_ms: int = 10  # Soft limit for market enrichment latency
    ai_dispatch_timeout_seconds: int = 10  # AI Gateway dispatch timeout (async bridge)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PULSE WORKER (PRODUCTION-GRADE)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class PulseWorker:
    """
    Async Nervous System Background Worker
    
    Responsibilities:
    1. Receive intents from bounded queue (non-blocking enqueue)
    2. Enrich snapshots (L2 from captured data + L3 best-effort)
    3. Enforce 10KB memory bound (truncation priority: L3 → L2 → never L1)
    4. Run Noise Gate evaluation
    5. Optional AI Gateway dispatch (DEFAULT OFF, gate order preserved)
    6. Update ExecutionJournal DB async
    
    HARD LAWS:
    - NEVER blocks trading path (queue.put_nowait with drop policy)
    - L2 captured synchronously, serialized asynchronously
    - DB errors logged but never fatal
    - Graceful shutdown with timeout
    - Metrics exposed for observability
    """
    
    def __init__(
        self,
        db_session_factory,
        snapshot_builder,
        noise_gate,
        config: Optional[NervousConfig] = None,
        ai_gateway=None,  # Phase 8.2C: AIGateway for synapse activation
        market_state_aggregator=None  # Phase 8.3: MarketStateAggregator (optional)
    ):
        """
        Initialize PulseWorker
        
        Args:
            db_session_factory: Callable that returns SQLAlchemy Session
            snapshot_builder: SnapshotBuilder instance
            noise_gate: NoiseGate instance
            config: NervousConfig (optional)
            ai_gateway: AI Gateway instance (Phase 8.2C, optional)
            market_state_aggregator: MarketStateAggregator (Phase 8.3, optional)
        """
        self.db_session_factory = db_session_factory
        self.snapshot_builder = snapshot_builder
        self.noise_gate = noise_gate
        self.config = config or NervousConfig()
        self.ai_gateway = ai_gateway
        self.market_state_aggregator = market_state_aggregator  # Phase 8.3
        
        # Phase 8.2C: Async/Sync bridge for AIGateway in threading.Thread
        self._ai_event_loop: Optional[Any] = None
        self._ai_loop_thread: Optional[threading.Thread] = None
        
        if ai_gateway is not None:
            # Check if gateway has async methods
            import inspect
            import asyncio
            
            # Detect async capability
            has_async_analyze = (
                hasattr(ai_gateway, 'analyze_signal') and
                inspect.iscoroutinefunction(ai_gateway.analyze_signal)
            )
            
            if has_async_analyze:
                # Create dedicated event loop and run it in daemon thread
                self._ai_event_loop = asyncio.new_event_loop()
                
                def _run_loop():
                    """Run event loop in background thread"""
                    asyncio.set_event_loop(self._ai_event_loop)
                    self._ai_event_loop.run_forever()
                
                self._ai_loop_thread = threading.Thread(
                    target=_run_loop,
                    daemon=True,
                    name="ai-event-loop"
                )
                self._ai_loop_thread.start()
                logger.info("PulseWorker: Async bridge initialized for AIGateway")
            else:
                logger.info("PulseWorker: Sync AIGateway detected, no bridge needed")
        
        # Bounded queue with drop policy
        self.queue = queue.Queue(maxsize=self.config.queue_maxsize)
        
        # Worker thread
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # Metrics
        self.metrics = {
            "nervous_enqueued_total": 0,
            "nervous_dropped_total": 0,
            "nervous_processed_total": 0,
            "nervous_db_errors_total": 0,
            # Phase 8.3: Market enrichment metrics
            "nervous_market_state_enabled_total": 0,
            "nervous_market_state_built_total": 0,
            "nervous_market_state_empty_total": 0,
            "nervous_market_state_errors_total": 0,
            "nervous_market_state_timeout_total": 0,
            "nervous_noise_gate_block_total": {},
            "nervous_ai_dispatched_total": 0,
            "nervous_ai_errors_total": 0
        }
        
        self._metrics_lock = threading.Lock()
        
        logger.info(
            f"PulseWorker initialized (queue_max={self.config.queue_maxsize}, "
            f"ai_enabled={self.config.enable_ai_after_noise_gate}, "
            f"ai_gateway={'connected' if ai_gateway else 'none'})"
        )
    
    def enqueue(self, envelope: IntentEnvelope) -> bool:
        """
        Enqueue intent envelope (non-blocking, drop policy)
        
        CRITICAL: This method MUST NOT block. Violations = production failure.
        
        Args:
            envelope: IntentEnvelope with deep-copied L2 capture
        
        Returns:
            True if enqueued, False if dropped
        """
        if not self.config.enabled:
            return False
        
        try:
            # Non-blocking put (fails immediately if queue full)
            self.queue.put_nowait(envelope)
            
            with self._metrics_lock:
                self.metrics["nervous_enqueued_total"] += 1
            
            return True
            
        except queue.Full:
            # DROP POLICY: log and increment metric, never block
            logger.warning(
                f"PulseWorker queue full ({self.config.queue_maxsize}), "
                f"dropped intent {envelope.dedup_key}"
            )
            
            with self._metrics_lock:
                self.metrics["nervous_dropped_total"] += 1
            
            return False
    
    def start(self):
        """
        Start worker thread (idempotent)
        """
        if self._thread is not None and self._thread.is_alive():
            logger.warning("PulseWorker already running")
            return
        
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._worker_loop,
            name="PulseWorker",
            daemon=True  # Daemon thread, won't block app shutdown
        )
        self._thread.start()
        logger.info("PulseWorker started")
    
    def stop(self, timeout_sec: float = 5.0):
        """
        Stop worker thread gracefully
        
        Args:
            timeout_sec: Max time to wait for worker to finish
        """
        if self._thread is None or not self._thread.is_alive():
            logger.info("PulseWorker not running")
            return
        
        logger.info(f"Stopping PulseWorker (timeout={timeout_sec}s)...")
        self._stop_event.set()
        
        self._thread.join(timeout=timeout_sec)
        
        if self._thread.is_alive():
            logger.warning(
                f"PulseWorker did not stop within {timeout_sec}s "
                f"(daemon thread will terminate on app exit)"
            )
        else:
            logger.info("PulseWorker stopped gracefully")
        
        # Stop async event loop if present
        if self._ai_event_loop is not None and self._ai_loop_thread is not None:
            try:
                self._ai_event_loop.call_soon_threadsafe(self._ai_event_loop.stop)
                logger.debug("Async event loop stopped")
            except Exception as e:
                logger.warning(f"Failed to stop async event loop: {e}")
    
    def drain_queue(self, timeout_sec: float = 2.0):
        """
        Best-effort queue drain during shutdown
        
        Args:
            timeout_sec: Max time to spend draining
        """
        start_time = time.time()
        drained = 0
        
        while not self.queue.empty() and (time.time() - start_time) < timeout_sec:
            try:
                envelope = self.queue.get_nowait()
                self._process_envelope(envelope)
                drained += 1
            except queue.Empty:
                break
            except Exception as e:
                logger.error(f"Error draining queue: {e}")
                break
        
        if drained > 0:
            logger.info(f"Drained {drained} items from queue during shutdown")
    
    def _worker_loop(self):
        """
        Main worker loop (single-threaded)
        
        Responsibilities:
        1. RECEIVE from queue
        2. ENRICH snapshot (L2 from captured data + L3)
        3. UPDATE DB
        4. RUN Noise Gate
        5. DISPATCH to AI (optional)
        6. INCREMENT metrics
        """
        logger.info("PulseWorker loop started")
        
        while not self._stop_event.is_set():
            try:
                # RECEIVE: timeout allows checking stop_event periodically
                try:
                    envelope = self.queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                
                # PROCESS: fail-safe, never fatal
                try:
                    self._process_envelope(envelope)
                except Exception as e:
                    logger.error(
                        f"Error processing envelope {envelope.dedup_key}: {e}",
                        exc_info=True
                    )
                finally:
                    self.queue.task_done()
                    
            except Exception as outer_e:
                logger.error(f"Worker loop outer exception: {outer_e}", exc_info=True)
        
        logger.info("PulseWorker loop stopped")
    
    def _process_envelope(self, envelope: IntentEnvelope):
        """
        Process single intent envelope (fail-safe)
        
        Args:
            envelope: IntentEnvelope to process
        """
        # STEP 1: Enrich snapshot (L2 from captured data + L3)
        enriched_snapshot = self._enrich_snapshot(envelope)
        
        # STEP 1.5: Enrich market_state (Phase 8.3 - optional, fail-safe)
        market_state = self._enrich_market_state(envelope, enriched_snapshot)
        
        # STEP 2: Update DB (fail-safe) — retrieve signal_event for AI dispatch
        db_signal_event = self._update_db(envelope, enriched_snapshot, market_state)
        
        # STEP 3: Noise Gate evaluation
        should_analyze, block_reason = self._evaluate_noise_gate(envelope)
        
        # STEP 4: Optional AI dispatch (Phase 8.2C)
        if should_analyze and self.config.enable_ai_after_noise_gate and db_signal_event is not None:
            self._dispatch_to_ai_gateway(envelope, enriched_snapshot, db_signal_event)
        
        # STEP 5: Metrics
        with self._metrics_lock:
            self.metrics["nervous_processed_total"] += 1
    
    def _enrich_snapshot(self, envelope: IntentEnvelope) -> Dict[str, Any]:
        """
        Enrich snapshot with L2 (from captured data) + L3
        
        Args:
            envelope: IntentEnvelope with l2_capture
        
        Returns:
            Enriched snapshot dict with L1/L2/L3
        """
        # Start with L1 (already complete from sync capture)
        enriched = {
            "snapshot_meta": {
                "timestamp_ms": envelope.created_at_ms,
                "snapshot_version": 0,  # Unknown in async context
                "truncated": False,
                "truncation_reason": None
            },
            "l1": envelope.l1_snapshot
        }
        
        # Build L2 from captured data (CRITICAL: NOT from live orderbook)
        bids_data, asks_data = envelope.l2_capture
        
        l2 = {
            "level": "L2",
            "orderbook_top_n": {
                "n": len(bids_data),
                "bids": bids_data,
                "asks": asks_data
            },
            "imbalance": self._calculate_imbalance(bids_data, asks_data),
            "liquidity_gaps": None,  # Simplified for v1
            "micro_volatility": None  # Not available
        }
        
        enriched["l2"] = l2
        
        # Build L3 (best-effort, mostly None for v1)
        enriched["l3"] = {
            "level": "L3",
            "portfolio_exposure": None,
            "system_pnl": None,
            "defcon_level": None,
            "system_uptime_seconds": None,
            "correlation_matrix_signature": None
        }
        
        # Enforce 10KB memory bound
        enriched = self._enforce_memory_bound(enriched)
        
        return enriched
    
    def _calculate_imbalance(
        self,
        bids: List[Dict],
        asks: List[Dict]
    ) -> Optional[float]:
        """Calculate orderbook imbalance"""
        if not bids or not asks:
            return None
        
        bid_vol = sum(b.get("amount", 0) for b in bids)
        ask_vol = sum(a.get("amount", 0) for a in asks)
        
        total_vol = bid_vol + ask_vol
        if total_vol == 0:
            return None
        
        return (bid_vol - ask_vol) / total_vol
    
    def _enforce_memory_bound(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enforce 10KB hard limit with truncation priority
        
        Priority:
        1. Drop L3
        2. Reduce L2 orderbook depth
        3. NEVER drop L1
        """
        serialized = json.dumps(snapshot)
        size_bytes = len(serialized.encode('utf-8'))
        
        if size_bytes <= self.config.max_snapshot_size_bytes:
            return snapshot
        
        logger.warning(f"Snapshot size {size_bytes} bytes exceeds limit, truncating...")
        
        # Priority 1: Drop L3
        if "l3" in snapshot:
            snapshot.pop("l3")
            snapshot["snapshot_meta"]["truncated"] = True
            snapshot["snapshot_meta"]["truncation_reason"] = "l3_dropped"
            
            serialized = json.dumps(snapshot)
            size_bytes = len(serialized.encode('utf-8'))
            
            if size_bytes <= self.config.max_snapshot_size_bytes:
                return snapshot
        
        # Priority 2: Reduce L2 orderbook depth
        if "l2" in snapshot and "orderbook_top_n" in snapshot["l2"]:
            for depth in [5, 2]:
                snapshot["l2"]["orderbook_top_n"]["bids"] = snapshot["l2"]["orderbook_top_n"]["bids"][:depth]
                snapshot["l2"]["orderbook_top_n"]["asks"] = snapshot["l2"]["orderbook_top_n"]["asks"][:depth]
                snapshot["l2"]["orderbook_top_n"]["n"] = depth
                snapshot["snapshot_meta"]["truncation_reason"] = f"l2_reduced_to_{depth}"
                
                serialized = json.dumps(snapshot)
                size_bytes = len(serialized.encode('utf-8'))
                
                if size_bytes <= self.config.max_snapshot_size_bytes:
                    return snapshot
            
            # Still too large: drop L2 entirely
            snapshot.pop("l2")
            snapshot["snapshot_meta"]["truncation_reason"] = "l2_dropped"
        
        # L1 NEVER dropped (preserve at all costs)
        return snapshot
    
    def _enrich_market_state(
        self,
        envelope: IntentEnvelope,
        enriched_snapshot: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Enrich with market_state using MarketStateAggregator (Phase 8.3)
        
        FAIL-SAFE SEMANTICS:
        - If aggregator is None → return {}
        - If feature flag disabled → return {}
        - If missing data or timeout → return {}
        - Exceptions never propagate
        
        Args:
            envelope: IntentEnvelope
            enriched_snapshot: Enriched snapshot dict
        
        Returns:
            market_state dict or empty dict
        """
        # Check feature flag
        if not self.config.nervous_enable_market_state:
            with self._metrics_lock:
                self.metrics["nervous_market_state_empty_total"] += 1
            return {}
        
        # Check aggregator available
        if self.market_state_aggregator is None:
            with self._metrics_lock:
                self.metrics["nervous_market_state_empty_total"] += 1
            return {}
        
        with self._metrics_lock:
            self.metrics["nervous_market_state_enabled_total"] += 1
        
        try:
            # Import locally to avoid circular dependency
            from ..market_enrichment import MarketStateAggregator
            
            # Build minimal snapshot object for aggregator
            # NOTE: In production, you'd pass real historical data
            mock_snapshot = type('obj', (object,), {
                'mid_price': envelope.l1_snapshot.get('price', {}).get('mid', 0.0),
                'bid': envelope.l1_snapshot.get('price', {}).get('bid', 0.0),
                'ask': envelope.l1_snapshot.get('price', {}).get('ask', 0.0),
                'bids': envelope.l2_capture[0] if envelope.l2_capture else [],
                'asks': envelope.l2_capture[1] if envelope.l2_capture else []
            })()
            
            # Time-budget enforcement (soft limit)
            start_ms = time.perf_counter() * 1000
            
            market_state = self.market_state_aggregator.aggregate_market_state(
                symbol=envelope.symbol,
                snapshot=mock_snapshot,
                historical_data=None  # TODO: Wire up real candle/volume history in Phase 9
            )
            
            elapsed_ms = (time.perf_counter() * 1000) - start_ms
            
            # Check timeout budget (soft limit, log only)
            if elapsed_ms > self.config.market_state_timeout_ms:
                logger.warning(
                    f"Market enrichment exceeded budget: {elapsed_ms:.2f}ms > "
                    f"{self.config.market_state_timeout_ms}ms for {envelope.symbol}",
                    extra={"symbol": envelope.symbol, "elapsed_ms": elapsed_ms}
                )
                with self._metrics_lock:
                    self.metrics["nervous_market_state_timeout_total"] += 1
            
            # Success
            with self._metrics_lock:
                self.metrics["nervous_market_state_built_total"] += 1
            
            return market_state
        
        except Exception as e:
            # Fail-safe: log and return empty (never crash)
            logger.warning(
                f"Market enrichment error for {envelope.symbol}: {e}",
                extra={"symbol": envelope.symbol, "dedup_key": envelope.dedup_key},
                exc_info=False  # Don't spam with traces
            )
            
            with self._metrics_lock:
                self.metrics["nervous_market_state_errors_total"] += 1
            
            return {}
    
    def _update_db(self, envelope: IntentEnvelope, enriched_snapshot: Dict[str, Any], market_state: Dict[str, Any] = None):
        """
        Update SignalEvent in DB with enriched snapshot and market_state (fail-safe)
        
        Args:
            envelope: IntentEnvelope
            enriched_snapshot: Enriched snapshot dict
            market_state: Market enrichment dict (Phase 8.3, optional)
        
        Returns:
            SignalEvent if found and updated, else None
        """
        if envelope.intent_id is None:
            logger.debug(f"No intent_id, skipping DB update for {envelope.dedup_key}")
            return None
        
        db = self.db_session_factory()
        try:
            # Import here to avoid circular dependency
            from .models import SignalEvent
            
            # Find existing SignalEvent by intent_id
            signal_event = db.query(SignalEvent).filter(
                SignalEvent.id == envelope.intent_id
            ).first()
            
            if signal_event is not None:
                # Update with enriched snapshot
                signal_event.context_snapshot = enriched_snapshot
                signal_event.snapshot_level = "L3" if "l3" in enriched_snapshot else "L2" if "l2" in enriched_snapshot else "L1"
                signal_event.snapshot_truncated = enriched_snapshot.get("snapshot_meta", {}).get("truncated", False)
                
                # Phase 8.3: Update market_state (nullable)
                if market_state:
                    signal_event.market_state = market_state
                
                db.commit()
                logger.debug(f"Updated SignalEvent {envelope.intent_id[:8]} with enriched snapshot")
                db.close()
                return signal_event
            else:
                logger.warning(f"SignalEvent {envelope.intent_id[:8]} not found for dedup_key {envelope.dedup_key}")
                db.close()
                return None
            
        except Exception as db_error:
            logger.error(
                f"DB update failed for {envelope.dedup_key}: {db_error}",
                exc_info=True
            )
            
            with self._metrics_lock:
                self.metrics["nervous_db_errors_total"] += 1
            
            try:
                db.rollback()
                db.close()
            except:
                pass  # Ignore cleanup errors
            
            return None
    
    def _evaluate_noise_gate(self, envelope: IntentEnvelope) -> Tuple[bool, str]:
        """
        Evaluate Noise Gate and log decision
        
        Args:
            envelope: IntentEnvelope
        
        Returns:
            (should_analyze, block_reason) tuple
        """
        # Extract feature vector for novelty check (optional)
        feature_vector = {
            "signal_type": hash(envelope.signal_type) % 100 / 100.0,
            "timestamp_bucket": envelope.timestamp_bucket % 1000 / 1000.0
        }
        
        # Evaluate
        should_analyze, block_reason = self.noise_gate.should_analyze(
            strategy_id=envelope.strategy_id,
            symbol=envelope.symbol,
            signal_type=envelope.signal_type,
            confidence=envelope.l1_snapshot.get("price", {}).get("mid", 0.5),  # Proxy
            regime=None,  # Not available in v1
            feature_vector=feature_vector
        )
        
        # Log decision (structured, no secrets)
        log_data = {
            "intent_id": envelope.intent_id[:8] if envelope.intent_id else None,
            "dedup_key": envelope.dedup_key,
            "decision": "PASS" if should_analyze else "BLOCK",
            "block_reason": block_reason if not should_analyze else None
        }
        
        if should_analyze:
            logger.info(f"Noise gate PASS: {json.dumps(log_data)}")
        else:
            logger.info(f"Noise gate BLOCK: {json.dumps(log_data)}")
            
            with self._metrics_lock:
                key = f"reason_{block_reason}"
                if key not in self.metrics["nervous_noise_gate_block_total"]:
                    self.metrics["nervous_noise_gate_block_total"][key] = 0
                self.metrics["nervous_noise_gate_block_total"][key] += 1
        
        return should_analyze, block_reason
    
    def _reconstruct_ai_context(self, envelope: IntentEnvelope, db_signal_event) -> Dict[str, Any]:
        """
        Reconstruct AI context from envelope and DB signal_event
        
        CRITICAL: AI must see exactly what strategy saw at signal time
        
        Args:
            envelope: IntentEnvelope with frozen L1/L2 captures
            db_signal_event: SignalEvent from DB with enriched snapshot
        
        Returns:
            AI context dict matching AIGateway expected format
        """
        return {
            "signal_id": db_signal_event.id,
            "strategy_id": envelope.strategy_id,
            "symbol": envelope.symbol,
            "timestamp_ms": envelope.created_at_ms,
            "market_snapshot": {
                "l1": envelope.l1_snapshot,
                "orderbook": {
                    "bids": envelope.l2_capture[0],
                    "asks": envelope.l2_capture[1]
                },
                "enriched": db_signal_event.context_snapshot if db_signal_event else None
            },
            "market_state": db_signal_event.market_state if db_signal_event and hasattr(db_signal_event, 'market_state') else {},  # Phase 8.3
            "system_state": {
                "regime": None,     # Phase 9
                "exposure": None,   # Phase 9
                "defcon": None      # Phase 9
            },
            "governance_metadata": envelope.governance_metadata or {},
            "rationale": envelope.rationale or "",
            "shadow_mode": True  # HARD FLOOR: ALWAYS TRUE (Phase 8.3 requirement)
        }
    
    def _dispatch_to_ai_gateway(
        self,
        envelope: IntentEnvelope,
        enriched_snapshot: Dict[str, Any],
        db_signal_event
    ):
        """
        Dispatch to AI Gateway with full governance chain preservation
        
        GATE ORDER (NON-BYPASSABLE):
        KillSwitch → BudgetGovernor → CircuitBreaker → TieredRouter → Provider
        
        CRITICAL:
        - Shadow mode ALWAYS enabled
        - Async/sync bridge for thread safety
        - Fail-safe (exceptions never crash worker)
        - Fire-and-forget (no blocking)
        
        Args:
            envelope: IntentEnvelope
            enriched_snapshot: Enriched snapshot dict
            db_signal_event: SignalEvent from DB
        """
        if self.ai_gateway is None:
            logger.debug("AI Gateway not configured, skipping dispatch")
            return
        
        try:
            # Verify governance enabled (KillSwitch)
            if hasattr(self.ai_gateway, 'governance_config'):
                if not self.ai_gateway.governance_config.ai_global_enabled:
                    logger.debug("AI globally disabled via KillSwitch, skipping dispatch")
                    return
            
            # Reconstruct context
            ai_context = self._reconstruct_ai_context(envelope, db_signal_event)
            
            # Signal payload
            signal_payload = {
                "strategy_id": envelope.strategy_id,
                "symbol": envelope.symbol,
                "signal_type": envelope.signal_type,
                "timestamp_ms": envelope.created_at_ms,
                "signal_strength": envelope.l1_snapshot.get("price", {}).get("mid", 0.5)  # Proxy
            }
            
            # Dispatch with async/sync bridge
            if self._ai_event_loop is not None and self._ai_loop_thread is not None:
                # Async gateway — use event loop bridge
                import asyncio
                
                async def _async_dispatch():
                    return await self.ai_gateway.analyze_signal(signal_payload, ai_context)
                
                # Submit coroutine to event loop running in background thread (fire-and-forget)
                future = asyncio.run_coroutine_threadsafe(
                    _async_dispatch(),
                    self._ai_event_loop
                )
                
                # Fire-and-forget (no wait)
                logger.debug(f"AI dispatch async queued: {envelope.dedup_key}")
                
            else:
                # Sync gateway — direct call
                self.ai_gateway.analyze_signal(signal_payload, ai_context)
                logger.debug(f"AI dispatch sync completed: {envelope.dedup_key}")
            
            with self._metrics_lock:
                self.metrics["nervous_ai_dispatched_total"] += 1
            
        except Exception as ai_error:
            logger.error(
                f"AI_DISPATCH_FAILED: {envelope.dedup_key}: {ai_error}",
                exc_info=True
            )
            
            with self._metrics_lock:
                self.metrics["nervous_ai_errors_total"] += 1
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get current metrics (thread-safe)
        
        Returns:
            Metrics dict with counters and queue size
        """
        with self._metrics_lock:
            return {
                **self.metrics,
                "queue_size_current": self.queue.qsize()
            }
    
    def reset_metrics(self):
        """Reset metrics (for testing)"""
        with self._metrics_lock:
            self.metrics = {
                "nervous_enqueued_total": 0,
                "nervous_dropped_total": 0,
                "nervous_processed_total": 0,
                "nervous_db_errors_total": 0,
                "nervous_noise_gate_block_total": {},
                "nervous_ai_dispatched_total": 0,
                "nervous_ai_errors_total": 0
            }
        logger.info("PulseWorker metrics reset")
