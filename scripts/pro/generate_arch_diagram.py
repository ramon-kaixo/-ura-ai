#!/usr/bin/env python3
"""generate_arch_diagram.py — Genera diagrama Mermaid de la arquitectura URA.
Salida: docs/architecture.md.
"""

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
OUTPUT = ROOT / "docs" / "architecture.md"


def get_systemd_services() -> list[dict]:
    services = []
    r = subprocess.run(
        ["systemctl", "list-units", "--type=service", "--all", "--no-legend"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    for line in r.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 4:
            name = parts[0].removesuffix(".service")
            state = parts[2]
            services.append({"name": name, "state": state})
    return services


def get_docker_containers() -> list[dict]:
    containers = []
    r = subprocess.run(
        ["docker", "ps", "-a", "--format", "{{.Names}}\t{{.Status}}"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    for line in r.stdout.splitlines():
        if "\t" in line:
            name, status = line.split("\t", 1)
            containers.append({"name": name, "status": status})
    return containers


def get_git_branches() -> list[str]:
    r = subprocess.run(["git", "branch", "--list"], capture_output=True, text=True, cwd=ROOT, check=False)  # noqa: S607
    return [b.strip().removeprefix("* ") for b in r.stdout.splitlines() if b.strip()]


def generate() -> None:  # noqa: C901, PLR0915
    services = get_systemd_services()
    containers = get_docker_containers()
    branches = get_git_branches()

    _ura_related = {"ura", "ollama", "opencode", "qdrant", "model-router", "llama"}
    ura_services = [s for s in services if any(k in s["name"] for k in _ura_related)]
    ura_containers = [c for c in containers if "ura" in c["name"] or "qdrant" in c["name"]]

    lines = []
    lines.append("# URA Architecture Diagram")
    lines.append(
        f"*Auto-generated: {subprocess.run(['date', '-Iseconds'], capture_output=True, text=True, check=False).stdout.strip()}*",  # noqa: E501, S607
    )
    lines.append("")
    lines.append("```mermaid")
    lines.append("graph TB")
    lines.append("")
    lines.append("  subgraph GX10[NVIDIA GX10 Grace Blackwell]")
    lines.append("")

    # Systemd services
    lines.append("    subgraph SYSTEMD[systemd Services]")
    for s in sorted(ura_services, key=lambda x: x["name"]):
        emoji = "🟢" if s["state"] == "active" else "🔴"
        lines.append(f"      {s['name'].replace('-', '_')}[{emoji} {s['name']}]")
    lines.append("    end")
    lines.append("")

    # Docker containers
    if ura_containers:
        lines.append("    subgraph DOCKER[Docker Containers]")
        for c in sorted(ura_containers, key=lambda x: x["name"]):
            emoji = "🟢" if "Up" in c["status"] else "🔴"
            lines.append(f"      docker_{c['name'].replace('-', '_')}[{emoji} {c['name']}]")
        lines.append("    end")
        lines.append("")

    # Git branches
    lines.append("    subgraph GIT[Git Repository]")
    for b in sorted(branches):
        lines.append(f"      branch_{b.replace('/', '_').replace('-', '_')}[🌿 {b}]")  # noqa: PERF401
    lines.append("    end")
    lines.append("")

    # Connections
    for s in ura_services:
        sname = s["name"].replace("-", "_")
        port = ""
        if "ollama" in s["name"]:
            port = " :11434"
        elif "opencode" in s["name"]:
            port = " :8081"
        elif "qdrant" in s["name"]:
            port = " :6333"
        elif "executor" in s["name"] or "ejecutor" in s["name"]:
            port = " :4096"
        elif "model-router" in s["name"]:
            port = " :11435"
        elif "detector" in s["name"]:
            port = " :9092"
        lines.append(f"      {sname}{port}")

    lines.append("")
    lines.append("  end")
    lines.append("```")
    lines.append("")
    lines.append("## System Status")
    lines.append("")
    lines.append("| Service | Status | Port |")
    lines.append("|---------|--------|------|")
    for s in sorted(ura_services, key=lambda x: x["name"]):
        emoji = "✅" if s["state"] == "active" else "❌"
        port = {
            "ollama": "11434",
            "opencode": "8081",
            "qdrant": "6333",
            "executor": "4096",
            "ejecutor": "4096",
            "model-router": "11435",
            "detector": "9092",
            "agent-hierarchy": "-",
            "audit": "8000",
            "contraste": "8001",
            "go2rtc": "8554",
        }.get(re.sub(r"^ura-", "", s["name"]), "?")
        lines.append(f"| {emoji} {s['name']} | {s['state']} | {port} |")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    generate()
