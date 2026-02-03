#!/usr/bin/env python3
"""Core Seal Generator & Verifier (PHASE 8 - IMMUTABILITY ENFORCEMENT)

Generates deterministic manifest of Core files and verifies integrity.
"""
import os
import sys
import json
import hashlib
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple


# Core files that MUST be sealed (relative to repo root)
SEALED_PATHS = [
    "lunia_core/forensic/risk/gate.py",
    "lunia_core/forensic/risk/ledger.py",
    "lunia_core/forensic/risk/config.py",
    "lunia_core/forensic/risk/audit.py",
    "lunia_core/forensic/risk/store.py",
    "lunia_core/forensic/risk/hot_reload.py",
    "lunia_core/forensic/api/auth.py",
    "lunia_core/forensic/api/keyring.py",
    "lunia_core/forensic/api/break_glass.py",
    "lunia_core/forensic/api/admin_governance_routes.py",
    "lunia_core/forensic/api/risk_routes.py",
    "lunia_core/forensic/api/emergency_routes.py",
    "lunia_core/forensic/api/serialization.py",
    "lunia_core/forensic/api/errors.py",
]

MANIFEST_PATH = "lunia_core/forensic/core_seal/manifest.json"


def find_repo_root() -> Path:
    """Find repository root deterministically."""
    current = Path(__file__).resolve().parent.parent
    # Look for marker files
    if (current / "lunia_core").exists():
        return current
    raise RuntimeError("Cannot determine repo root")


def compute_file_hash(filepath: Path) -> str:
    """Compute SHA256 hash of file in binary mode."""
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def generate_manifest() -> Dict:
    """Generate deterministic manifest."""
    repo_root = find_repo_root()
    
    file_hashes = {}
    for rel_path in sorted(SEALED_PATHS):  # Deterministic order
        abs_path = repo_root / rel_path
        if not abs_path.exists():
            raise FileNotFoundError(f"Sealed file missing: {rel_path}")
        
        # Normalize to POSIX paths
        normalized_path = Path(rel_path).as_posix()
        file_hashes[normalized_path] = compute_file_hash(abs_path)
    
    manifest = {
        "version": 1,
        "created_at": "2026-01-21T22:45:00Z",
        "algorithm": "sha256",
        "root_dir": ".",
        "files": file_hashes
    }
    
    return manifest


def verify_manifest(manifest: Dict) -> Tuple[bool, List[str]]:
    """Verify manifest against current files.
    
    Returns:
        (ok, mismatched_files)
    """
    repo_root = find_repo_root()
    mismatches = []
    
    for rel_path, expected_hash in manifest["files"].items():
        abs_path = repo_root / rel_path
        
        if not abs_path.exists():
            mismatches.append(f"{rel_path}: MISSING")
            continue
        
        actual_hash = compute_file_hash(abs_path)
        if actual_hash != expected_hash:
            mismatches.append(f"{rel_path}: HASH_MISMATCH (expected={expected_hash[:8]}..., actual={actual_hash[:8]}...)")
    
    return (len(mismatches) == 0, mismatches)


def write_manifest(manifest: Dict):
    """Write manifest atomically."""
    repo_root = find_repo_root()
    manifest_path = repo_root / MANIFEST_PATH
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Atomic write
    fd, temp_path = tempfile.mkstemp(
        dir=str(manifest_path.parent),
        prefix=".manifest.",
        suffix=".tmp"
    )
    
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(manifest, f, indent=2, sort_keys=True, separators=(',', ':'))
            f.flush()
            os.fsync(f.fileno())
        
        os.rename(temp_path, manifest_path)
        
        try:
            dir_fd = os.open(manifest_path.parent, os.O_RDONLY)
            os.fsync(dir_fd)
            os.close(dir_fd)
        except (OSError, AttributeError):
            pass
    except Exception as e:
        try:
            os.unlink(temp_path)
        except:
            pass
        raise RuntimeError(f"Failed to write manifest: {e}")


def load_manifest() -> Dict:
    """Load manifest from disk."""
    repo_root = find_repo_root()
    manifest_path = repo_root / MANIFEST_PATH
    
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")
    
    with open(manifest_path, 'r') as f:
        return json.load(f)


def main():
    if len(sys.argv) < 2:
        print("Usage: seal_core.py [--write|--verify|--print]")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "--write":
        manifest = generate_manifest()
        write_manifest(manifest)
        print(f"✓ Manifest written: {len(manifest['files'])} files sealed")
    
    elif cmd == "--verify":
        manifest = load_manifest()
        ok, mismatches = verify_manifest(manifest)
        
        if ok:
            print(f"✓ Seal intact: {len(manifest['files'])} files verified")
            sys.exit(0)
        else:
            print(f"✗ Seal broken: {len(mismatches)} mismatches")
            for m in mismatches:
                print(f"  - {m}")
            sys.exit(1)
    
    elif cmd == "--print":
        manifest = load_manifest()
        print(json.dumps(manifest, indent=2, sort_keys=True))
    
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
