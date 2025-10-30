#!/usr/bin/env python3
import re
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
MINIMAL = ROOT / "lunia_core/requirements/base_minimal.txt"
PATTERNS = [r"aiogram", r"aihttp", r"aiohttp", r"ai ogram"]

if not MINIMAL.exists():
    print(f"❌ Missing: {MINIMAL}")
    sys.exit(1)

bad = []
for i, line in enumerate(MINIMAL.read_text(encoding="utf-8").splitlines(), start=1):
    for pattern in PATTERNS:
        if re.search(pattern, line, re.IGNORECASE):
            bad.append((i, line.strip()))

if bad:
    print("❌ Forbidden deps/typos found in base_minimal.txt:")
    for ln, text in bad:
        print(f"  line {ln}: {text}")
    sys.exit(1)

print("✅ Preflight OK — minimal profile is Telegram-free.")