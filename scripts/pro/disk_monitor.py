#!/usr/bin/env python3
"""Log CRITICAL si disco > 90%."""

import logging
import shutil

THRESHOLD = 90.0


def check_disk() -> float:
    usage = shutil.disk_usage("/")
    percent = (usage.used / usage.total) * 100
    if percent > THRESHOLD:
        logging.getLogger("ura.disk").critical(f"DISK ALERT: {percent:.1f}% > {THRESHOLD}%")
    else:
        logging.getLogger("ura.disk").info(f"disk: {percent:.1f}% used")
    return percent


if __name__ == "__main__":
    result = check_disk()
    print(f"Disk usage: {result:.1f}%")
