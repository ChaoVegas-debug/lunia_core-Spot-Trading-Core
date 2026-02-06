"""
Epoch D.1 — Research Service

Pull API + Background Scheduler for research cycles.
"""
import threading
import time
import logging
from datetime import datetime, timezone
from typing import Optional

from lunia_core.app.services.research.research_engine import ResearchAgent
from lunia_core.app.services.research.research_store import ResearchStore
from lunia_core.app.services.research.models import ResearchReport

logger = logging.getLogger(__name__)


class ResearchService:
    """
    Research service with pull API and background scheduler.
    
    RESPONSIBILITIES:
    - Provide pull API: get_latest_report()
    - Run background scheduler (non-blocking)
    - Isolate research cycles from execution threads
    
    GUARANTEES:
    - No blocking of execution threads
    - Thread-safe concurrent access
    - Graceful shutdown
    """
    
    def __init__(
        self,
        agent: ResearchAgent,
        store: ResearchStore,
        interval_minutes: int = 15,
    ):
        """
        Initialize research service.
        
        Args:
            agent: ResearchAgent for running cycles
            store: ResearchStore for persistence
            interval_minutes: Cycle interval (default: 15 min)
        """
        self.agent = agent
        self.store = store
        self.interval_minutes = interval_minutes
        self._scheduler_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
    
    def get_latest_report(self, now_utc: Optional[datetime] = None) -> ResearchReport:
        """
        Pull API for consumers (strategies, council).
        
        Thread-safe: Can be called from multiple threads.
        
        Args:
            now_utc: Current UTC time (default: now)
        
        Returns:
            ResearchReport (may be UNCERTAIN if missing/stale)
        """
        if now_utc is None:
            now_utc = datetime.now(timezone.utc)
        return self.store.get_latest(now_utc)
    
    
    def start_scheduler(self) -> None:
        """
        Start background scheduler thread.
        
        Non-blocking: Returns immediately after starting thread.
        Idempotent: Safe to call multiple times.
        """
        if self._scheduler_thread is not None and self._scheduler_thread.is_alive():
            logger.warning("Scheduler already running")
            return
        
        self._stop_event.clear()
        self._scheduler_thread = threading.Thread(
            target=self._run_scheduler,
            daemon=True,
            name="ResearchScheduler"
        )
        self._scheduler_thread.start()
        logger.info(f"Research scheduler started (interval={self.interval_minutes}min)")
    
    def stop_scheduler(self) -> None:
        """
        Stop background scheduler thread.
        
        Blocks until thread exits (graceful shutdown).
        """
        if self._scheduler_thread is None or not self._scheduler_thread.is_alive():
            return
        
        logger.info("Stopping research scheduler...")
        self._stop_event.set()
        self._scheduler_thread.join(timeout=5.0)
        logger.info("Research scheduler stopped")
    
    def _run_scheduler(self) -> None:
        """
        Scheduler loop (runs in background thread).
        
        Executes research cycles at configured interval.
        """
        while not self._stop_event.is_set():
            try:
                now_utc = datetime.now(timezone.utc)
                logger.debug(f"Starting research cycle at {now_utc}")
                
                # Run cycle
                report = self.agent.run_cycle(now_utc)
                
                # Publish to store
                self.store.publish(report)
                
                logger.info(
                    f"RESEARCH_CYCLE_PUBLISHED: regime={report.regime}, "
                    f"confidence={report.confidence:.2f}, "
                    f"flags={report.risk_flags}"
                )
                
            except Exception as e:
                logger.error(f"SCHEDULER_ERROR: {e}", exc_info=True)
            
            # Sleep with early exit on stop signal
            self._stop_event.wait(timeout=self.interval_minutes * 60)
