"""Entrypoint para python3 -m core.model_router."""

from path_setup import setup_path

setup_path()

from core.model_router.cli import main

main()
