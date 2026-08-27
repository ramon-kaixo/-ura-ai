"""E2E Tests — Tests against real URA nodes via Tailscale.

Mark with @pytest.mark.e2e and skip if nodes unreachable.
Run: pytest -m e2e tests/test_e2e.py
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
from urllib.error import URLError

import pytest

# Node endpoints (Tailscale IPs)
GX10_URL = os.environ.get("URA_GX10_URL", "http://100.72.103.12:4097")
MAC_URL = os.environ.get("URA_MAC_URL", "http://100.123.81.101:4097")

e2e = pytest.mark.e2e


def _http_get(url: str, timeout: float = 5.0) -> dict | None:
    try:
        req = urllib.request.Request(url)  # noqa: S310
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            return json.loads(resp.read())
    except (URLError, OSError, TimeoutError, json.JSONDecodeError):
        return None


def _http_post(url: str, data: dict, timeout: float = 5.0) -> dict | None:
    try:
        body = json.dumps(data).encode()
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})  # noqa: S310
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            return json.loads(resp.read())
    except (URLError, OSError, TimeoutError, json.JSONDecodeError):
        return None


def _node_reachable(url: str) -> bool:
    result = _http_get(f"{url}/health", timeout=3.0)
    return result is not None and result.get("status") == "ok"


# ---------------------------------------------------------------------------
# Health & Readiness
# ---------------------------------------------------------------------------


@e2e
class TestGX10Health:
    """Health checks against real GX10 node."""

    @pytest.fixture(autouse=True)
    def _require_gx10(self):
        if not _node_reachable(GX10_URL):
            pytest.skip("GX10 node unreachable via Tailscale")

    def test_health(self):
        data = _http_get(f"{GX10_URL}/health")
        assert data is not None
        assert data["status"] == "ok"

    def test_readiness(self):
        data = _http_get(f"{GX10_URL}/readiness")
        assert data is not None
        assert "ready" in data
        assert "queue_depth" in data

    def test_liveness(self):
        data = _http_get(f"{GX10_URL}/liveness")
        assert data is not None
        assert data["alive"] is True

    def test_stats(self):
        data = _http_get(f"{GX10_URL}/stats")
        assert data is not None
        assert "by_status" in data


@e2e
class TestMacHealth:
    """Health checks against real Mac node."""

    @pytest.fixture(autouse=True)
    def _require_mac(self):
        if not _node_reachable(MAC_URL):
            pytest.skip("Mac node unreachable via Tailscale")

    def test_health(self):
        data = _http_get(f"{MAC_URL}/health")
        assert data is not None
        assert data["status"] == "ok"

    def test_readiness(self):
        data = _http_get(f"{MAC_URL}/readiness")
        assert data is not None
        assert "ready" in data

    def test_liveness(self):
        data = _http_get(f"{MAC_URL}/liveness")
        assert data is not None
        assert data["alive"] is True


# ---------------------------------------------------------------------------
# Task Queue CRUD
# ---------------------------------------------------------------------------


@e2e
class TestTaskQueueE2E:
    """End-to-end task queue operations."""

    @pytest.fixture(autouse=True)
    def _require_node(self):
        if not _node_reachable(GX10_URL):
            pytest.skip("GX10 node unreachable")

    def test_create_list_complete(self):
        # Create task
        task = _http_post(f"{GX10_URL}/tasks", {
            "description": "E2E test task",
            "priority": 0,
            "timeout_seconds": 60,
        })
        assert task is not None
        task_id = task["id"]
        assert task["status"] == "pending"

        # List tasks
        data = _http_get(f"{GX10_URL}/tasks?status=pending")
        assert data is not None
        assert any(t["id"] == task_id for t in data["tasks"])

        # Get task
        fetched = _http_get(f"{GX10_URL}/tasks/{task_id}")
        assert fetched is not None
        assert fetched["id"] == task_id

        # Claim
        claimed = _http_post(f"{GX10_URL}/tasks/{task_id}/claim", {"agent": "e2e-test"})
        assert claimed is not None
        assert claimed["status"] == "assigned"

        # Start
        started = _http_post(f"{GX10_URL}/tasks/{task_id}/start", {})
        assert started is not None
        assert started["status"] == "in_progress"

        # Complete
        completed = _http_post(f"{GX10_URL}/tasks/{task_id}/complete", {"commit_sha": "abc123"})
        assert completed is not None
        assert completed["status"] == "completed"

    def test_task_events(self):
        task = _http_post(f"{GX10_URL}/tasks", {
            "description": "E2E events test",
            "timeout_seconds": 60,
        })
        assert task is not None
        events = _http_get(f"{GX10_URL}/tasks/{task['id']}/events")
        assert events is not None
        assert events["count"] >= 1


# ---------------------------------------------------------------------------
# Node Registry
# ---------------------------------------------------------------------------


@e2e
class TestNodeRegistryE2E:
    """End-to-end node registry operations."""

    @pytest.fixture(autouse=True)
    def _require_node(self):
        if not _node_reachable(GX10_URL):
            pytest.skip("GX10 node unreachable")

    def test_list_nodes(self):
        data = _http_get(f"{GX10_URL}/nodes")
        assert data is not None
        assert "nodes" in data
        assert "self" in data

    def test_register_self(self):
        node_id = os.environ.get("URA_NODE_ID", "e2e-test")
        data = _http_post(f"{GX10_URL}/nodes/register", {
            "node_id": node_id,
            "hostname": "e2e-test-host",
            "tailscale_ip": "192.0.2.1",
            "api_port": 4097,
            "tags": ["e2e"],
        })
        assert data is not None
        assert data["node_id"] == node_id

        # Cleanup
        _http_post(f"{GX10_URL}/nodes/{node_id}", {})  # DELETE


# ---------------------------------------------------------------------------
# Parallel Status
# ---------------------------------------------------------------------------


@e2e
class TestParallelStatus:
    """End-to-end parallel work status."""

    @pytest.fixture(autouse=True)
    def _require_node(self):
        if not _node_reachable(GX10_URL):
            pytest.skip("GX10 node unreachable")

    def test_parallel_status(self):
        data = _http_get(f"{GX10_URL}/parallel/status")
        assert data is not None
        assert "node_id" in data
        assert "branch" in data
