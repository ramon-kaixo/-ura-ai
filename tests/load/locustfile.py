"""Load testing para URA — endpoints DOCUMENTADOS en docs/API.md.

Solo se incluyen endpoints verificados (grep sobre el código).
Regla: si un endpoint no está en docs/API.md, NO se incluye.
"""
from locust import HttpUser, between, task


class URAUser(HttpUser):
    wait_time = between(1, 3)

    @task(3)
    def health_check(self):
        """GET /health — health check (documentado)."""
        self.client.get("/health")

    @task(2)
    def models(self):
        """GET /v1/models — modelos LLM (documentado)."""
        self.client.get("/v1/models")

    @task(1)
    def metrics(self):
        """GET /metrics — métricas Prometheus (documentado)."""
        self.client.get("/metrics")
