#!/usr/bin/env python3
import re
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
MINIMAL = ROOT / "lunia_core/requirements/base_minimal.txt"
PATTERNS = [r"aiogram", r"aiohttp", r"aio+gram", r"ai+ogram"]


if not MINIMAL.exists():
    print(f"❌ Missing: {MINIMAL}")
    sys.exit(1)

bad = []
for lineno, line in enumerate(MINIMAL.read_text(encoding="utf-8").splitlines(), start=1):
    for pattern in PATTERNS:
        if re.search(pattern, line, re.IGNORECASE):
            bad.append((lineno, line.strip()))

if bad:
    print("❌ Forbidden deps in base_minimal.txt:")
    for lineno, text in bad:
        print(f"   line {lineno}: {text}")
    sys.exit(1)

print("✅ Preflight OK — minimal profile clean.")
