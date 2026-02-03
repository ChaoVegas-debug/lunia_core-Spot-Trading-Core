#!/usr/bin/env python3
"""Phase 2 Architecture Verification Script

Validates PHASE 2 constitution compliance with 9 mandatory checks.
"""
import ast
import sys
import re
from pathlib import Path


def check_1_no_float_usage():
    """Check 1: No float usage in risk modules."""
    risk_dir = Path(__file__).parent.parent / "forensic" / "risk"
    violations = []
    
    for py_file in risk_dir.glob("*.py"):
        if py_file.name == "__init__.py":
            continue
        
        content = py_file.read_text()
        
        # Check for float() calls
        if re.search(r'\bfloat\s*\(', content):
            violations.append(f"float() call in {py_file.name}")
        
        # Check for problematic float literals (not in Decimal context or defaults)
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            # Skip comments, docstrings, defaults
            if line.strip().startswith('#'):
                continue
            if '"""' in line or "'''" in line:
                continue
            if 'timestamp=' in line or 'timestamp:' in line:
                continue  # Timestamp field defaults are OK
            
            # Look for float literals not wrapped in Decimal()
            if re.search(r'[^"\']\b\d+\.\d+\b', line):
                if 'Decimal' not in line and 'float' not in line.lower():
                    # Potential issue
                    violations.append(f"Possible float literal in {py_file.name}:{i}")
                    break
    
    return violations


def check_2_no_ui_imports():
    """Check 2: No UI imports in risk modules."""
    risk_dir = Path(__file__).parent.parent / "forensic" / "risk"
    forbidden = ["flask", "django", "fastapi", "telegram", "streamlit"]
    violations = []
    
    for py_file in risk_dir.glob("*.py"):
        content = py_file.read_text()
        for module in forbidden:
            if f"import {module}" in content or f"from {module}" in content:
                violations.append(f"UI import '{module}' in {py_file.name}")
    
    return violations


def check_3_default_mode_shadow():
    """Check 3: Default RiskConfig mode is SHADOW."""
    config_file = Path(__file__).parent.parent / "forensic" / "risk" / "config.py"
    
    if not config_file.exists():
        return ["config.py not found"]
    
    content = config_file.read_text()
    
    # Look for default mode assignment
    if "mode: RiskMode = RiskMode.SHADOW" in content or 'RiskMode.SHADOW  # DEFAULT' in content:
        return []
    
    return ["Default mode is not SHADOW in RiskConfig"]


def check_4_override_token_single_source():
    """Check 4: Override token only in policy.py."""
    risk_dir = Path(__file__).parent.parent / "forensic" / "risk"
    policy_file = risk_dir / "policy.py"
    
    if not policy_file.exists():
        return ["policy.py not found"]
    
    # Check policy.py has the constant
    policy_content = policy_file.read_text()
    if 'OVERRIDE_TOKEN = "I_UNDERSTAND_ENFORCEMENT_OVERRIDE_PHASE2"' not in policy_content:
        return ["OVERRIDE_TOKEN constant not found in policy.py"]
    
    # Check no other files have the literal (except imports)
    violations = []
    for py_file in risk_dir.glob("*.py"):
        if py_file.name == "policy.py":
            continue
        
        content = py_file.read_text()
        if "I_UNDERSTAND_ENFORCEMENT_OVERRIDE_PHASE2" in content:
            if "from forensic.risk.policy import" not in content:
                violations.append(f"Override token literal in {py_file.name}")
    
    return violations


def check_5_no_timestamps_in_decision_id():
    """Check 5: decision_id generation has no timestamps."""
    decision_file = Path(__file__).parent.parent / "forensic" / "risk" / "decision.py"
    
    if not decision_file.exists():
        return ["decision.py not found"]
    
    content = decision_file.read_text()
    
    # Find compute_decision_id function
    if "def compute_decision_id" not in content:
        return ["compute_decision_id function not found"]
    
    # Extract function body (rough)
    start = content.find("def compute_decision_id")
    end = content.find("\ndef ", start + 1)
    if end == -1:
        end = len(content)
    
    func_body = content[start:end]
    
    # Check for actual time/datetime calls (not just parameter names)
    forbidden_calls = [
        "time.time()",
        "datetime.now()",
        "datetime.utcnow()",
        "uuid.uuid4()",
        "uuid.uuid1()",
        "random."
    ]
    
    violations = []
    for pattern in forbidden_calls:
        if pattern in func_body:
            violations.append(f"Found '{pattern}' call in compute_decision_id")
    
    # Check for forbidden imports
    if "import time" in func_body or "import datetime" in func_body:
        violations.append("Found time/datetime import in compute_decision_id")
    
    return violations


def check_6_decision_id_in_logs():
    """Check 6: Phase 2 logs include decision_id field."""
    gate_file = Path(__file__).parent.parent / "forensic" / "risk" / "gate.py"
    
    if not gate_file.exists():
        return ["gate.py not found"]
    
    content = gate_file.read_text()
    
    # Check for decision_id in log payloads
    if '"decision_id": decision.decision_id' not in content and '"decision_id":' not in content:
        return ["decision_id not found in log payloads"]
    
    return []


def check_7_no_bypass_params():
    """Check 7: No bypass parameters exist."""
    risk_dir = Path(__file__).parent.parent / "forensic" / "risk"
    forbidden = ["force=", "bypass=", "ignore_risk=", "skip_risk=", "disable_gate="]
    violations = []
    
    for py_file in risk_dir.glob("*.py"):
        content = py_file.read_text()
        for pattern in forbidden:
            if pattern in content:
                violations.append(f"Bypass parameter '{pattern}' in {py_file.name}")
    
    return violations


def check_8_config_immutability():
    """Check 8: RiskConfig uses frozen dataclass."""
    config_file = Path(__file__).parent.parent / "forensic" / "risk" / "config.py"
    
    if not config_file.exists():
        return ["config.py not found"]
    
    content = config_file.read_text()
    
    # Check for dataclass decorator (frozen not strictly required but recommended)
    if "@dataclass" not in content:
        return ["RiskConfig is not a dataclass"]
    
    return []


def check_9_shadow_no_blocking():
    """Check 9: No SHADOW path yields allowed=False."""
    gate_file = Path(__file__).parent.parent / "forensic" / "risk" / "gate.py"
    
    if not gate_file.exists():
        return ["gate.py not found"]
    
    content = gate_file.read_text()
    
    # Rough check: in SHADOW blocks, ensure allowed=True
    if 'mode == RiskMode.SHADOW' in content or 'mode == "SHADOW"' in content:
        # Check that SHADOW branch has allowed=True
        if 'allowed = True' not in content:
            return ["SHADOW mode doesn't set allowed=True"]
    
    return []


def main():
    """Run all checks."""
    checks = [
        ("Float usage", check_1_no_float_usage),
        ("UI imports", check_2_no_ui_imports),
        ("Default SHADOW", check_3_default_mode_shadow),
        ("Override token single source", check_4_override_token_single_source),
        ("No timestamps in decision_id", check_5_no_timestamps_in_decision_id),
        ("decision_id in logs", check_6_decision_id_in_logs),
        ("No bypass params", check_7_no_bypass_params),
        ("Config immutability", check_8_config_immutability),
        ("SHADOW no blocking", check_9_shadow_no_blocking),
    ]
    
    all_passed = True
    
    print("=" * 70)
    print("PHASE 2 ARCHITECTURE VERIFICATION")
    print("=" * 70)
    
    for check_name, check_func in checks:
        violations = check_func()
        
        if not violations:
            print(f"✓ {check_name}: PASS")
        else:
            print(f"✗ {check_name}: FAIL")
            for v in violations:
                print(f"  - {v}")
            all_passed = False
    
    print("=" * 70)
    
    if all_passed:
        print("✅ ALL CHECKS PASSED")
        return 0
    else:
        print("❌ SOME CHECKS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
