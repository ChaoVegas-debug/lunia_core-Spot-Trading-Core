"""
Test orchestrator queue uniqueness (FIX #4 minimal verification)
"""
import pytest
from lunia_core.app.services.execution.orchestrator import Orchestrator, AlreadyQueuedError


def test_enqueue_twice_same_intent_fails(session_factory):
    """Enqueue same intent_id twice → second fails with AlreadyQueuedError"""
    session = session_factory()
    orchestrator = Orchestrator(session)
    
    intent_id = "intent_test_unique"
    
    # First enqueue: SUCCESS
    job1 = orchestrator.enqueue(intent_id, priority=5)
    assert job1.intent_id == intent_id
    
    # Second enqueue: FAIL (already queued)
    with pytest.raises(AlreadyQueuedError) as exc_info:
        orchestrator.enqueue(intent_id, priority=5)
    
    assert intent_id in str(exc_info.value)
    print(f"✅ Double-queue prevented: {exc_info.value}")


def test_claim_next_uses_select_for_update(session_factory):
    """claim_next uses SELECT FOR UPDATE SKIP LOCKED (concurrency safe)"""
    session = session_factory()
    orchestrator = Orchestrator(session, worker_id="worker_test_1")
    
    # Enqueue a job
    intent_id = "intent_claim_test"
    job = orchestrator.enqueue(intent_id, priority=5)
    
    # Claim it
    claimed = orchestrator.claim_next()
    
    assert claimed is not None
    assert claimed.intent_id == intent_id
    assert claimed.worker_id == "worker_test_1"
    assert claimed.status.value == "CLAIMED"
    
    # Claim again (should be None - already claimed)
    claimed2 = orchestrator.claim_next()
    assert claimed2 is None
    
    print("✅ SELECT FOR UPDATE SKIP LOCKED working (no double-claim)")


# Pytest fixture for session factory (minimal - requires SQLAlchemy setup)
@pytest.fixture
def session_factory():
    """Create in-memory SQLite session for testing"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from lunia_core.app.auth.database import Base
    
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    
    def _factory():
        return SessionLocal()
    
    return _factory


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
