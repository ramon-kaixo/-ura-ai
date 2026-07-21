#!/usr/bin/env python3
"""Model Router Enhanced — entrypoint para systemd y ejecución directa."""

from path_setup import setup_path

setup_path()

from core.model_router.cli import main  # noqa: E402

if __name__ == "__main__":
    main()
