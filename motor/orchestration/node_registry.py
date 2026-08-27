"""Node Registry — multi-node discovery and health checking.

Allows URA nodes (Mac, GX10 Desktop, GX10 Web) to discover and monitor each other
via Tailscale IPs. Each node maintains a registry of known peers and periodically
checks their health.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.request
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any
from urllib.error import URLError

log = logging.getLogger(__name__)

_REGISTRY_FILE = Path(os.environ.get("URA_NODE_REGISTRY", ".ura/node_registry.json"))
_HEALTH_CHECK_INTERVAL_S = 30.0
_HEALTH_CHECK_TIMEOUT_S = 5.0


class NodeStatus(StrEnum):
    ONLINE = "online"
    DEGRADED = "degraded"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


@dataclass
class NodeInfo:
    """Information about a known peer node."""

    node_id: str
    hostname: str
    tailscale_ip: str
    api_port: int = 4097
    status: NodeStatus = NodeStatus.UNKNOWN
    last_seen: float = 0.0  # timestamp
    last_latency_ms: float = 0.0
    consecutive_failures: int = 0
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "hostname": self.hostname,
            "tailscale_ip": self.tailscale_ip,
            "api_port": self.api_port,
            "status": self.status.value,
            "last_seen": self.last_seen,
            "last_latency_ms": self.last_latency_ms,
            "consecutive_failures": self.consecutive_failures,
            "tags": self.tags,
        }

    @property
    def api_url(self) -> str:
        return f"http://{self.tailscale_ip}:{self.api_port}"


class NodeRegistry:
    """Registry of known URA nodes with health monitoring.

    - Persists to .ura/node_registry.json
    - Periodic health checks via HTTP GET /health
    - Thread-safe operations
    """

    def __init__(
        self,
        registry_file: Path | None = None,
        check_interval_s: float = _HEALTH_CHECK_INTERVAL_S,
        check_timeout_s: float = _HEALTH_CHECK_TIMEOUT_S,
    ) -> None:
        self._file = registry_file or _REGISTRY_FILE
        self._check_interval_s = check_interval_s
        self._check_timeout_s = check_timeout_s
        self._nodes: dict[str, NodeInfo] = {}
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._load()

    def _load(self) -> None:
        """Load registry from disk."""
        if not self._file.exists():
            return
        try:
            data = json.loads(self._file.read_text())
            for nid, info in data.get("nodes", {}).items():
                self._nodes[nid] = NodeInfo(
                    node_id=nid,
                    hostname=info.get("hostname", ""),
                    tailscale_ip=info.get("tailscale_ip", ""),
                    api_port=info.get("api_port", 4097),
                    status=NodeStatus(info.get("status", "unknown")),
                    last_seen=info.get("last_seen", 0.0),
                    last_latency_ms=info.get("last_latency_ms", 0.0),
                    consecutive_failures=info.get("consecutive_failures", 0),
                    tags=info.get("tags", []),
                )
            log.info("[NODE_REGISTRY] Loaded %d nodes from %s", len(self._nodes), self._file)
        except Exception as e:
            log.warning("[NODE_REGISTRY] Failed to load %s: %s", self._file, e)

    def _save(self) -> None:
        """Persist registry to disk."""
        try:
            self._file.parent.mkdir(parents=True, exist_ok=True)
            data = {"nodes": {nid: n.to_dict() for nid, n in self._nodes.items()}}
            self._file.write_text(json.dumps(data, indent=2))
        except Exception as e:
            log.warning("[NODE_REGISTRY] Failed to save %s: %s", self._file, e)

    def register(
        self,
        node_id: str,
        hostname: str,
        tailscale_ip: str,
        api_port: int = 4097,
        tags: list[str] | None = None,
    ) -> NodeInfo:
        """Register or update a peer node."""
        with self._lock:
            if node_id in self._nodes:
                node = self._nodes[node_id]
                node.hostname = hostname
                node.tailscale_ip = tailscale_ip
                node.api_port = api_port
                if tags is not None:
                    node.tags = tags
            else:
                node = NodeInfo(
                    node_id=node_id,
                    hostname=hostname,
                    tailscale_ip=tailscale_ip,
                    api_port=api_port,
                    tags=tags or [],
                )
                self._nodes[node_id] = node
            self._save()
            log.info("[NODE_REGISTRY] Registered node: %s (%s)", node_id, tailscale_ip)
            return node

    def unregister(self, node_id: str) -> bool:
        """Remove a node from the registry."""
        with self._lock:
            if node_id in self._nodes:
                del self._nodes[node_id]
                self._save()
                log.info("[NODE_REGISTRY] Unregistered node: %s", node_id)
                return True
            return False

    def get(self, node_id: str) -> NodeInfo | None:
        """Get a node by ID."""
        with self._lock:
            return self._nodes.get(node_id)

    def list_all(self) -> list[NodeInfo]:
        """List all registered nodes."""
        with self._lock:
            return list(self._nodes.values())

    def _probe_node(self, node: NodeInfo) -> NodeStatus:
        """Health-check a single node via HTTP GET /health."""
        start = time.monotonic()
        try:
            req = urllib.request.Request(f"{node.api_url}/health")  # noqa: S310
            with urllib.request.urlopen(req, timeout=self._check_timeout_s) as resp:  # noqa: S310
                data = json.loads(resp.read())
                latency = (time.monotonic() - start) * 1000
                node.last_latency_ms = round(latency, 1)
                node.last_seen = time.time()
                node.consecutive_failures = 0
                return NodeStatus.ONLINE
        except (URLError, OSError, TimeoutError, json.JSONDecodeError):
            node.consecutive_failures += 1
            if node.consecutive_failures >= 3:
                return NodeStatus.OFFLINE
            return NodeStatus.DEGRADED

    def check_health(self, node_id: str | None = None) -> dict[str, Any]:
        """Check health of one or all nodes. Returns status summary."""
        results: dict[str, Any] = {}
        with self._lock:
            nodes_to_check = (
                [self._nodes[node_id]] if node_id and node_id in self._nodes else list(self._nodes.values())
            )

        for node in nodes_to_check:
            new_status = self._probe_node(node)
            with self._lock:
                old_status = node.status
                node.status = new_status
                if new_status != old_status:
                    log.warning(
                        "[NODE_REGISTRY] Node %s: %s → %s",
                        node.node_id, old_status.value, new_status.value,
                    )
            results[node.node_id] = {
                "status": node.status.value,
                "latency_ms": node.last_latency_ms,
                "consecutive_failures": node.consecutive_failures,
            }

        with self._lock:
            self._save()
        return results

    def _check_loop(self) -> None:
        """Background loop for periodic health checks."""
        while not self._stop.is_set():
            try:
                self.check_health()
            except Exception as e:
                log.error("[NODE_REGISTRY] Health check error: %s", e)
            self._stop.wait(timeout=self._check_interval_s)

    def start_checker(self) -> None:
        """Start background health checker."""
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._check_loop, daemon=True, name="node-registry-checker")
        self._thread.start()
        log.info("[NODE_REGISTRY] Health checker started (interval=%.0fs)", self._check_interval_s)

    def stop_checker(self) -> None:
        """Stop background health checker."""
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
