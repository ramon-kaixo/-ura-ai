#!/usr/bin/env python3
"""TPV API Connector — integrates with POS systems via REST API."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from core.api_connector import APIConnector


class TPVApiConnector(APIConnector):
    """Connector for POS (TPV) systems with REST API."""

    def __init__(self, config_path: str | None = None) -> None:
        config_file = config_path or str(
            Path(__file__).resolve().parent.parent / "config" / "tpv_endpoints.json"
        )
        with open(config_file, encoding="utf-8") as fh:
            self.config = json.load(fh)

        api_key = os.getenv("TPV_API_KEY", self.config.get("api_key", ""))
        base_url = os.getenv("TPV_BASE_URL", self.config["base_url"])
        self._timeout = self.config.get("timeout", 10)
        super().__init__(base_url, api_key=api_key)
        self.endpoints = self.config["endpoints"]

    def ventas_hoy(self) -> dict[str, Any]:
        """Gets today's sales data.

        Returns:
            Dictionary with sales information.
        """
        fecha = datetime.now().strftime("%Y-%m-%d")
        endpoint = self.endpoints["ventas_hoy"].format(fecha=fecha)
        return self.get(endpoint)

    def stock(self, producto: str) -> dict[str, Any]:
        """Gets stock level for a product.

        Args:
            producto: Product name or SKU.

        Returns:
            Dictionary with stock information.
        """
        endpoint = self.endpoints["stock_producto"].format(producto=producto)
        return self.get(endpoint)

    def registrar_venta(self, data: dict[str, Any]) -> dict[str, Any]:
        """Registers a new sale.

        Args:
            data: Sale data dictionary.

        Returns:
            Response from the POS system.
        """
        return self.post(self.endpoints["registrar_venta"], data)

    def clientes_hoy(self) -> dict[str, Any]:
        """Gets today's customer count.

        Returns:
            Dictionary with customer information.
        """
        return self.get(self.endpoints["clientes_hoy"])


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.INFO)
    tpv = TPVApiConnector()
    print("Ventas hoy:", tpv.ventas_hoy())
    print("Stock cerveza:", tpv.stock("cerveza"))
    print("Clientes hoy:", tpv.clientes_hoy())
