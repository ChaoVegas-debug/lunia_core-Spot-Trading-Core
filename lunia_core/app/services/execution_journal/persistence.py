"""
Phase 8.2A: Intent Persistence Hook
Fail-safe persistence of IntentProposals to ExecutionJournal
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime
from typing import Dict, Any, Optional

from sqlalchemy.orm import Session

from .models import SignalEvent, SignalType
from .rate_limiter import RateLimiter
from .snapshot_builder import SnapshotBuilder
from ..strategy.models import IntentProposal, SignalSide
from ..market_data.realtime.models import MarketSnapshot

logger = logging.getLogger(__name__)


class IntentPersistenceHook:
    """
    Persistence hook for IntentProposals
    
    HARD LAWS (CRITICAL FOR HFT SURVIVAL):
    - FAIL-SAFE: DB exceptions NEVER propagate to StrategyEngine
    - NON-BLOCKING: Persistence attempt <1ms at p99
    - RATE LIMITED: Max 100 events per (strategy, symbol) per 60s window
    - DEDUP-AWARE: Canonical dedup_key prevents near-simultaneous duplicates
    - NO SECRETS: Never persist API keys, credentials, or PII
    
    Architecture:
    - Synchronous: L1 snapshot capture + DB write (best-effort)
    - Synchronous: L2 deep copy at intent time (immutable capture)
    - Asynchronous: Enqueue to PulseWorker for enrichment & AI dispatch
    """
    
    def __init__(
        self,
        db_session_factory,
        rate_limiter: Optional[RateLimiter] = None,
        snapshot_builder: Optional[SnapshotBuilder] = None,
        pulse_worker=None  # Phase 8.2B: Optional PulseWorker
    ):
        """
        Initialize persistence hook
        
        Args:
            db_session_factory: Callable that returns SQLAlchemy Session
            rate_limiter: Rate limiter (default: 60s window, 100 max)
            snapshot_builder: Snapshot builder (default: standard config)
            pulse_worker: PulseWorker for async processing (Phase 8.2B, optional)
        """
        self.db_session_factory = db_session_factory
        self.rate_limiter = rate_limiter or RateLimiter()
        self.snapshot_builder = snapshot_builder or SnapshotBuilder()
        self.pulse_worker = pulse_worker  # Phase 8.2B
        
        # Stats (for observability)
        self.stats = {
            "total_attempts": 0,
            "successful_persists": 0,
            "rate_limited": 0,
            "db_errors": 0,
            "dedup_skips": 0
        }
        
        logger.info("IntentPersistenceHook initialized")
    
    def persist_intent(
        self,
        intent: IntentProposal,
        snapshot: MarketSnapshot,
        rationale: str = ""
    ) -> Optional[str]:
        """
        Persist IntentProposal to ExecutionJournal

        CRITICAL: This method MUST NOT raise exceptions (fail-safe)
        
        Args:
            intent: IntentProposal from StrategyEngine
            snapshot: MarketSnapshot at intent generation time
            rationale: Additional reasoning (optional)
        
        Returns:
            Signal event ID if persisted, None if skipped/failed
        """
        self.stats["total_attempts"] += 1
        
        try:
            # Rate limiting (O(1) check)
            should_persist, limit_reason = self.rate_limiter.should_persist(
                intent.strategy_id,
                intent.symbol
            )
            
            if not should_persist:
                self.stats["rate_limited"] += 1
                logger.warning(
                    f"Intent persistence skipped: {intent.strategy_id}:{intent.symbol} "
                    f"(rate_limited: {limit_reason})"
                )
                return None
            
            # Build dedup key (canonical, deterministic)
            timestamp = datetime.utcfromtimestamp(intent.created_at_ms / 1000.0)
            timestamp_bucket = int(timestamp.timestamp())  # Floor to second
            
            dedup_key = f"{intent.strategy_id}:{intent.symbol}:{intent.side.value}:{timestamp_bucket}"
            
            # Capture L1 snapshot (sync, in-memory)
            context_snapshot = self.snapshot_builder.build_full_snapshot(
                snapshot=snapshot,
                include_l2=True,  # Capture L2 sync (serialize async in future)
                include_l3=False  # L3 is async-only (not impl in v1)
            )
            
            # Determine snapshot level
            snapshot_level = "L2" if "l2" in context_snapshot else "L1"
            snapshot_truncated = context_snapshot.get("snapshot_meta", {}).get("truncated", False)
            
            # Map IntentProposal.side to SignalType
            signal_type_map = {
                SignalSide.BUY: SignalType.BUY,
                SignalSide.SELL: SignalType.SELL,
                SignalSide.HOLD: SignalType.HOLD
            }
            signal_type = signal_type_map.get(intent.side, SignalType.HOLD)
            
            # Create SignalEvent record
            signal_event = SignalEvent(
                id=str(uuid.uuid4()),
                strategy_id=intent.strategy_id,
                symbol=intent.symbol,
                signal_type=signal_type,
                confidence=intent.signal_strength,
                timestamp=timestamp,
                created_at=datetime.utcnow(),
                deterministic_reasoning=intent.rationale or rationale,
                # Phase 8.2A fields
                dedup_key=dedup_key,
                timestamp_bucket=timestamp_bucket,
                context_snapshot=context_snapshot,
                snapshot_truncated=snapshot_truncated,
                snapshot_level=snapshot_level,
                # Legacy field (backward compat)
                market_context=context_snapshot.get("l1")
            )
            
            # Persist to DB (best-effort, fail-safe)
            db = self.db_session_factory()
            try:
                # Check for duplicate (same dedup_key in last 5 seconds)
                existing = db.query(SignalEvent).filter(
                    SignalEvent.dedup_key == dedup_key,
                    SignalEvent.timestamp_bucket >= timestamp_bucket - 5
                ).first()
                
                if existing:
                    self.stats["dedup_skips"] += 1
                    logger.debug(
                        f"Intent skipped (duplicate): {dedup_key} "
                        f"(existing: {existing.id[:8]})"
                    )
                    db.close()
                    return None
                
                # Insert new record
                db.add(signal_event)
                db.commit()
                
                self.stats["successful_persists"] += 1
                logger.info(
                    f"Intent persisted: {signal_event.id[:8]} "
                    f"{intent.strategy_id}:{intent.symbol}:{signal_type.value} "
                    f"strength={intent.signal_strength:.2f} snapshot={snapshot_level}"
                )
                
                signal_id = signal_event.id
                db.close()
                
                # Phase 8.2B: Enqueue to PulseWorker for async processing
                if self.pulse_worker is not None:
                    try:
                        # Deep copy L2 for async processing (CRITICAL: capture at signal time)
                        from copy import deepcopy
                        from .background_worker import IntentEnvelope
                        
                        l2_bids = [{"price": level.price, "amount": level.amount} for level in snapshot.bids[:10]]
                        l2_asks = [{"price": level.price, "amount": level.amount} for level in snapshot.asks[:10]]
                        
                        envelope = IntentEnvelope(
                            intent_id=signal_id,
                            strategy_id=intent.strategy_id,
                            symbol=intent.symbol,
                            signal_type=signal_type.value,
                            created_at_ms=intent.created_at_ms,
                            timestamp_bucket=timestamp_bucket,
                            dedup_key=dedup_key,
                            l1_snapshot=context_snapshot.get("l1", {}),
                            l2_capture=(l2_bids, l2_asks),  # Deep copy
                            governance_metadata=intent.governance_metadata,
                            rationale=intent.rationale
                        )
                        
                        # Non-blocking enqueue (drop policy handles queue full)
                        self.pulse_worker.enqueue(envelope)
                        
                    except Exception as enqueue_error:
                        # FAIL-SAFE: enqueue errors never propagate
                        logger.error(f"PulseWorker enqueue failed (non-fatal): {enqueue_error}")
                
                return signal_id
                
            except Exception as db_error:
                self.stats["db_errors"] += 1
                logger.error(
                    f"DB persistence failed for {intent.strategy_id}:{intent.symbol}: {db_error}",
                    exc_info=True
                )
                try:
                    db.rollback()
                    db.close()
                except:
                    pass  # Ignore cleanup errors
                return None
        
        except Exception as outer_error:
            # FAIL-SAFE: Catch ALL exceptions (even unexpected ones)
            logger.error(
                f"Intent persistence outer exception for {intent.strategy_id}:{intent.symbol}: {outer_error}",
                exc_info=True
            )
            return None
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get persistence statistics (for observability)
        
        Returns:
            Stats dict with counters
        """
        return {
            **self.stats,
            "success_rate": (
                self.stats["successful_persists"] / self.stats["total_attempts"]
                if self.stats["total_attempts"] > 0 else 0.0
            )
        }
    
    def reset_stats(self):
        """Reset statistics counters"""
        self.stats = {
            "total_attempts": 0,
            "successful_persists": 0,
            "rate_limited": 0,
            "db_errors": 0,
            "dedup_skips": 0
        }
        logger.info("Persistence stats reset")
