"""PLUGIN wrapper para ReuseDetector (plugin_registry solo escanea scripts/pro/)."""

PLUGIN = {"name": "reuse_detector", "phase": "pre", "timeout": 60, "priority": 100, "capability": "quality", "args": ["index"]}

if __name__ == "__main__":
    import sys
    from scripts.pro.reuse.reuse import main
    sys.exit(main())
