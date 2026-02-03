"""
EPOCH C: Orchestrator Service
DB-backed execution queue with worker coordination
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from .models import ExecutionQueue, QueueStatus, WorkerHeartbeat
from ..proposal.models import ExecutionIntent


class QueueFullError(Exception):
    """Queue is at capacity"""
    pass


class AlreadyQueuedError(Exception):
    """Intent already in queue"""
    pass


class Orchestrator:
    """
    Execution queue orchestrator
    
    Responsibilities:
    - Enqueue validated ExecutionIntents
    - Worker lease management
    - Stuck job detection and re-lease
    - Dead-letter queue (max retries exceeded)
    """
    
    MAX_QUEUE_SIZE = 1000
    LEASE_TTL_SECONDS = 60
    HEARTBEAT_TTL_SECONDS = 30
    
    def __init__(self, session: Session, worker_id: Optional[str] = None):
        self.session = session
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
    
    def enqueue(
        self,
        intent_id: str,
        priority: int = 5
    ) -> ExecutionQueue:
        """
        Enqueue ExecutionIntent for processing
        
        Args:
            intent_id: ExecutionIntent.id
            priority: Priority (0-10, higher = more urgent)
        
        Returns:
            ExecutionQueue entry
        
        Raises:
            AlreadyQueuedError: If intent already in queue
            QueueFullError: If queue at capacity
        """
        # Check if already queued
        existing = self.session.query(ExecutionQueue).filter(
            ExecutionQueue.intent_id == intent_id
        ).first()
        
        if existing and existing.status != QueueStatus.COMPLETED:
            raise AlreadyQueuedError(f"Intent {intent_id} already in queue with status {existing.status}")
        
        # Check queue capacity
        queue_size = self.session.query(ExecutionQueue).filter(
            ExecutionQueue.status.in_([QueueStatus.PENDING, QueueStatus.CLAIMED, QueueStatus.PROCESSING])
        ).count()
        
        if queue_size >= self.MAX_QUEUE_SIZE:
            raise QueueFullError(f"Queue at capacity ({queue_size}/{self.MAX_QUEUE_SIZE})")
        
        # Create queue entry
        queue_entry = ExecutionQueue(
            id=str(uuid.uuid4()),
            intent_id=intent_id,
            status=QueueStatus.PENDING,
            priority=priority,
            enqueued_at=datetime.utcnow()
        )
        
        self.session.add(queue_entry)
        self.session.commit()
        
        return queue_entry
    
    def claim_next(self) -> Optional[ExecutionQueue]:
        """
        Claim next available job (highest priority, oldest first)
        
        Atomic UPDATE with lease acquisition.
        
        Returns:
            ExecutionQueue entry if claimed, None if queue empty
        """
        # Release expired leases first
        self._release_expired_leases()
        
        # Find next PENDING job (or expired lease that was re-set to PENDING)
        # Use SELECT FOR UPDATE SKIP LOCKED for concurrency
        job = self.session.query(ExecutionQueue).filter(
            and_(
                ExecutionQueue.status == QueueStatus.PENDING,
                or_(
                    ExecutionQueue.lease_until.is_(None),
                    ExecutionQueue.lease_until < datetime.utcnow()
                )
            )
        ).order_by(
            ExecutionQueue.priority.desc(),
            ExecutionQueue.enqueued_at.asc()
        ).with_for_update(skip_locked=True).first()
        
        if not job:
            return None
        
        # Claim it
        job.status = QueueStatus.CLAIMED
        job.worker_id = self.worker_id
        job.claimed_at = datetime.utcnow()
        job.lease_until = datetime.utcnow() + timedelta(seconds=self.LEASE_TTL_SECONDS)
        
        self.session.commit()
        
        return job
    
    def heartbeat(self, job_id: str) -> bool:
        """
        Extend lease on a claimed job (heartbeat)
        
        Args:
            job_id: ExecutionQueue.id
        
        Returns:
            True if heartbeat successful, False if job no longer owned
        """
        job = self.session.query(ExecutionQueue).filter(
            ExecutionQueue.id == job_id
        ).with_for_update().first()
        
        if not job or job.worker_id != self.worker_id:
            return False
        
        # Extend lease
        job.lease_until = datetime.utcnow() + timedelta(seconds=self.LEASE_TTL_SECONDS)
        self.session.commit()
        
        # Update worker heartbeat
        self._update_worker_heartbeat()
        
        return True
    
    def complete(self, job_id: str) -> bool:
        """
        Mark job as completed
        
        Args:
            job_id: ExecutionQueue.id
        
        Returns:
            True if successful
        """
        job = self.session.query(ExecutionQueue).filter(
            ExecutionQueue.id == job_id
        ).with_for_update().first()
        
        if not job or job.worker_id != self.worker_id:
            return False
        
        job.status = QueueStatus.COMPLETED
        job.completed_at = datetime.utcnow()
        
        self.session.commit()
        
        return True
    
    def fail(
        self,
        job_id: str,
        error_code: str,
        error_message: str,
        retry: bool = True
    ) -> bool:
        """
        Mark job as failed (with optional retry)
        
        Args:
            job_id: ExecutionQueue.id
            error_code: Machine-readable error code
            error_message: Human-readable error message
            retry: If True, increment attempts and re-queue (if < max_attempts)
        
        Returns:
            True if successful
        """
        job = self.session.query(ExecutionQueue).filter(
            ExecutionQueue.id == job_id
        ).with_for_update().first()
        
        if not job or job.worker_id != self.worker_id:
            return False
        
        job.attempts += 1
        job.last_error_code = error_code
        job.last_error_message = error_message
        
        if retry and job.attempts < job.max_attempts:
            # Re-queue for retry
            job.status = QueueStatus.PENDING
            job.lease_until = None
            job.worker_id = None
        else:
            # Dead-letter: max retries exceeded
            job.status = QueueStatus.FAILED
            job.completed_at = datetime.utcnow()
        
        self.session.commit()
        
        return True
    
    def _release_expired_leases(self) -> int:
        """
        Release expired leases (stuck workers)
        
        Returns:
            Number of leases released
        """
        expired_jobs = self.session.query(ExecutionQueue).filter(
            and_(
                ExecutionQueue.status.in_([QueueStatus.CLAIMED, QueueStatus.PROCESSING]),
                ExecutionQueue.lease_until < datetime.utcnow()
            )
        ).all()
        
        for job in expired_jobs:
            job.status = QueueStatus.PENDING
            job.lease_until = None
            job.worker_id = None
        
        if expired_jobs:
            self.session.commit()
        
        return len(expired_jobs)
    
    def _update_worker_heartbeat(self) -> None:
        """Update this worker's heartbeat timestamp"""
        heartbeat = self.session.query(WorkerHeartbeat).filter(
            WorkerHeartbeat.worker_id == self.worker_id
        ).first()
        
        if heartbeat:
            heartbeat.last_heartbeat_at = datetime.utcnow()
        else:
            import socket
            heartbeat = WorkerHeartbeat(
                worker_id=self.worker_id,
                last_heartbeat_at=datetime.utcnow(),
                version="1.0.0",
                hostname=socket.gethostname()
            )
            self.session.add(heartbeat)
        
        self.session.commit()
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """
        Get queue statistics
        
        Returns:
            Dict with pending, claimed, processing, completed, failed counts
        """
        stats = {}
        for status in QueueStatus:
            count = self.session.query(ExecutionQueue).filter(
                ExecutionQueue.status == status
            ).count()
            stats[status.value.lower()] = count
        
        # Active workers
        active_threshold = datetime.utcnow() - timedelta(seconds=self.HEARTBEAT_TTL_SECONDS)
        active_workers = self.session.query(WorkerHeartbeat).filter(
            WorkerHeartbeat.last_heartbeat_at > active_threshold
        ).count()
        
        stats["active_workers"] = active_workers
        
        return stats
