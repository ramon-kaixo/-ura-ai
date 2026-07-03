#!/usr/bin/env python3
"""Knowledge Engine — entry point.

Delega en knowledge/engine/cli.py (thin CLI).
Toda la lógica vive en knowledge/engine/{compiler,collector,reader,verifier}.py.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from knowledge.engine.cli import main

if __name__ == "__main__":
    sys.exit(main())
