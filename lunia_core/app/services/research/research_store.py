"""
Epoch D.1 — Research Store

Thread-safe in-memory storage for research reports.
"""
import threading
from datetime import datetime, timedelta
from typing import Optional

from lunia_core.app.services.research.models import (
    ResearchReport,
    MacroRegime,
    RiskFlag,
    create_default_uncertain_report,
)


class ResearchStore:
    """
    Thread-safe in-memory store for research reports.
    
    GUARANTEES:
    - Thread-safe read/write
    - Staleness detection (expired reports treated as missing)
    - Default UNCERTAIN report when no valid data
    """
    
    def __init__(self):
        self._lock = threading.RLock()
        self._latest: Optional[ResearchReport] = None
    
    def publish(self, report: ResearchReport) -> None:
        """
        Publish new research report.
        
        Thread-safe: Can be called from scheduler thread.
        """
        with self._lock:
            self._latest = report
    
    def get_latest(self, now_utc: datetime) -> ResearchReport:
        """
        Get latest report, or default UNCERTAIN if missing/stale.
        
        Thread-safe: Can be called from multiple consumer threads.
        
        Args:
            now_utc: Current UTC time for staleness check
        
        Returns:
            ResearchReport (may be default UNCERTAIN)
        """
        with self._lock:
            if self._latest is None:
                return self._create_default_uncertain(now_utc)
            
            if self._latest.is_stale(now_utc):
                return self._create_default_uncertain(now_utc)
            
            return self._latest
    
    def _create_default_uncertain(self, now_utc: datetime) -> ResearchReport:
        """Create default UNCERTAIN report for missing/stale data."""
        return create_default_uncertain_report(now_utc)
