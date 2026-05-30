#!/usr/bin/env python3
"""
URA API Entry Point for Docker
Simple entry point without GUI dependencies
"""

import os
import sys

print("URA API Docker Container Started")
print(f"Python version: {sys.version}")
print(f"Working directory: {os.getcwd()}")
print("URA API is running in headless mode (no GUI)")

# Keep container running
try:
    while True:
        import time

        time.sleep(60)
except KeyboardInterrupt:
    print("Shutting down...")
