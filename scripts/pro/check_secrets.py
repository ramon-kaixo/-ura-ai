#!/usr/bin/env python3
"""check_secrets.py — Pre-commit hook: detecta secrets hardcodeados."""
import re
import sys

PATTERN = re.compile(r"(sk-or-v1-[A-Za-z0-9]{20,}|apiKey[\"\' ]*:[\"\' ][A-Za-z0-9_-]{20,})")

for filepath in sys.argv[1:]:
    with open(filepath) as f:
        for i, line in enumerate(f, 1):
            if PATTERN.search(line):
                print(f"{filepath}:{i}: possible secret found")
                sys.exit(1)
