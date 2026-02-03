"""Core Integrity Enforcement (PHASE 8 - BOOT-TIME VERIFICATION)

Verifies sealed Core integrity at application startup.
"""
import sys
import logging
from pathlib import Path
from typing import Dict, Tuple, List

logger = logging.getLogger(__name__)


def verify_core_integrity(manifest_path: str = "lunia_core/forensic/core_seal/manifest.json") -> Tuple[bool, List[str]]:
    """Verify core integrity against manifest.
    
    Returns:
        (ok, mismatches)
    """
    # Import seal_core functions
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "scripts"))
    
    try:
        from seal_core import load_manifest, verify_manifest
        
        manifest = load_manifest()
        ok, mismatches = verify_manifest(manifest)
        
        return (ok, mismatches)
    except FileNotFoundError as e:
        return (False, [f"MANIFEST_MISSING: {e}"])
    except Exception as e:
        return (False, [f"VERIFICATION_ERROR: {e}"])


def enforce_boot_integrity():
    """Enforce boot-time integrity check (FAIL-CLOSED).
    
    Exits with code 1 if seal is broken, unless ALLOW_UNSEALED_CORE=1.
    """
    import os
    
    # Check for dev override
    if os.getenv("ALLOW_UNSEALED_CORE") == "1":
        logger.critical("[CORE_SEAL_BYPASS] ALLOW_UNSEALED_CORE=1 - RUNNING WITH UNSEALED CORE")
        logger.critical(f"[CORE_SEAL_BYPASS] Timestamp={__import__('datetime').datetime.utcnow().isoformat()}Z")
        logger.critical(f"[CORE_SEAL_BYPASS] PID={os.getpid()}")
        return
    
    # Verify integrity
    ok, mismatches = verify_core_integrity()
    
    if not ok:
        logger.critical("[CORE_SEAL_BROKEN] Integrity check FAILED")
        logger.critical(f"[CORE_SEAL_BROKEN] Mismatches: {len(mismatches)}")
        for mismatch in mismatches:
            logger.critical(f"[CORE_SEAL_BROKEN]   - {mismatch}")
        logger.critical("[CORE_SEAL_BROKEN] REFUSING TO START")
        sys.exit(1)
    
    logger.info(f"[CORE_SEAL_OK] Integrity verified: {len(ok)} files")
