#!/usr/bin/env python3
"""URA Multi-Agent System — wrapper de compatibilidad hacia atrás.

Reexporta todo desde core.agents package.
"""

from core.agents import *  # noqa: F403
from core.agents.cli import main

if __name__ == "__main__":
    main()
