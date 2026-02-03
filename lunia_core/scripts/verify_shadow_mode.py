#!/usr/bin/env python3
"""Architecture Verification Script (PHASE 1)

Validates that PHASE 1 shadow mode adheres to constitution:
- No allowed=False returns
- No blocking raises
- No UI imports
- No float usage in risk/
- No Portfolio mutation
"""
import ast
import sys
import re
from pathlib import Path


class ShadowModeVerifier:
    """Automated verification of PHASE 1 constitution compliance."""
    
    def __init__(self, risk_dir: Path):
        self.risk_dir = risk_dir
        self.violations = []
    
    def verify_all(self) -> bool:
        """Run all verification checks.
        
        Returns:
            True if all checks pass, False otherwise
        """
        self.v1_no_allowed_false()
        self.v2_no_blocking_raises()
        self.v3_no_ui_imports()
        self.v4_no_float_usage()
        self.v5_no_portfolio_mutation()
        
        return len(self.violations) == 0
    
    def v1_no_allowed_false(self):
        """V1: No allowed=False returns in risk/gate.py"""
        gate_file = self.risk_dir / "gate.py"
        
        if not gate_file.exists():
            self.violations.append("V1: risk/gate.py not found")
            return
        
        content = gate_file.read_text()
        
        # Check for allowed=False patterns
        patterns = [
            r"allowed\s*=\s*False",
            r"'allowed'\s*:\s*False",
            r'"allowed"\s*:\s*False',
        ]
        
        for pattern in patterns:
            if re.search(pattern, content):
                self.violations.append(
                    f"V1: VIOLATION - Found 'allowed=False' in {gate_file}"
                )
                return
    
    def v2_no_blocking_raises(self):
        """V2: No raises that would stop trading from risk modules"""
        # Allowed raises: TypeError, ValueError for input validation
        # Forbidden: Custom exceptions that block trading
        
        for py_file in self.risk_dir.glob("*.py"):
            if py_file.name == "__init__.py":
                continue
            
            content = py_file.read_text()
            
            # Look for raises that might block trading
            # We allow RuntimeError for constitution violations (crash loudly)
            # We allow TypeError/ValueError for input validation
            forbidden_patterns = [
                r"raise\s+TradingBlockedError",
                r"raise\s+RiskViolationError",
                r"raise\s+ExecutionHaltedError",
            ]
            
            for pattern in forbidden_patterns:
                if re.search(pattern, content):
                    self.violations.append(
                        f"V2: VIOLATION - Found blocking exception in {py_file}"
                    )
    
    def v3_no_ui_imports(self):
        """V3: No UI/frontend/telegram imports in risk/"""
        forbidden_modules = [
            "flask", "fastapi", "django",
            "telegram", "discord",
            "react", "vue", "angular",
            "streamlit", "dash",
        ]
        
        for py_file in self.risk_dir.glob("*.py"):
            content = py_file.read_text()
            
            for module in forbidden_modules:
                patterns = [
                    f"import {module}",
                    f"from {module}",
                ]
                
                for pattern in patterns:
                    if pattern in content:
                        self.violations.append(
                            f"V3: VIOLATION - UI import '{module}' found in {py_file}"
                        )
    
    def v4_no_float_usage(self):
        """V4: No float usage in risk/ computations"""
        for py_file in self.risk_dir.glob("*.py"):
            if py_file.name == "__init__.py":
                continue
            
            try:
                tree = ast.parse(py_file.read_text())
                
                for node in ast.walk(tree):
                    # Check for float() calls
                    if isinstance(node, ast.Call):
                        if isinstance(node.func, ast.Name) and node.func.id == "float":
                            self.violations.append(
                                f"V4: VIOLATION - float() call found in {py_file}"
                            )
                    
                    # Check for float literals in arithmetic
                    if isinstance(node, ast.Constant):
                        if isinstance(node.value, float):
                            # Allow 0.0 for initialization
                            if node.value != 0.0:
                                self.violations.append(
                                    f"V4: VIOLATION - float literal {node.value} in {py_file}"
                                )
            
            except SyntaxError as e:
                self.violations.append(f"V4: Syntax error parsing {py_file}: {e}")
    
    def v5_no_portfolio_mutation(self):
        """V5: No Portfolio-like attribute assignments in risk/"""
        mutation_patterns = [
            r"\.cash\s*=",
            r"\.position\s*=",
            r"\.equity\s*=",
            r"\.balance\s*=",
        ]
        
        for py_file in self.risk_dir.glob("*.py"):
            if py_file.name == "__init__.py":
                continue
            
            content = py_file.read_text()
            
            for pattern in mutation_patterns:
                if re.search(pattern, content):
                    # Check if it's not self._state assignment (allowed internally)
                    if "self._state" not in content[content.find(pattern)-20:content.find(pattern)+20]:
                        self.violations.append(
                            f"V5: VIOLATION - Portfolio mutation pattern '{pattern}' in {py_file}"
                        )
    
    def print_report(self):
        """Print verification report."""
        if self.violations:
            print("❌ PHASE 1 SHADOW MODE VALIDATION FAILED\n")
            print(f"Found {len(self.violations)} violation(s):\n")
            for i, violation in enumerate(self.violations, 1):
                print(f"{i}. {violation}")
            print()
            return False
        else:
            print("✅ PHASE 1 SHADOW MODE VALIDATION PASSED")
            print()
            print("All checks passed:")
            print("  ✓ V1: No allowed=False in gate")
            print("  ✓ V2: No blocking raises")
            print("  ✓ V3: No UI imports")
            print("  ✓ V4: No float usage")
            print("  ✓ V5: No Portfolio mutation")
            print()
            return True


def main():
    """Run architecture verification."""
    risk_dir = Path(__file__).parent.parent / "forensic" / "risk"
    
    if not risk_dir.exists():
        print(f"❌ Risk directory not found: {risk_dir}")
        sys.exit(1)
    
    verifier = ShadowModeVerifier(risk_dir)
    
    success = verifier.verify_all()
    verifier.print_report()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
