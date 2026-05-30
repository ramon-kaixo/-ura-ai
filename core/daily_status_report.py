#!/usr/bin/env python3
"""
scripts/daily_status_report.py - Informe diario de estado del sistema URA
Genera STATUS.md en lenguaje claro para usuarios no técnicos.
"""

import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent


def _check_service(name: str, port: int) -> str:
    import socket

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            result = s.connect_ex(("localhost", port))
            return "✅ Funcionando" if result == 0 else "❌ Detenido"
    except Exception:
        return "❓ Desconocido"


def _check_docker_containers() -> list[dict]:
    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}\t{{.Status}}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        containers = []
        for line in result.stdout.strip().splitlines():
            if "\t" in line:
                name, status = line.split("\t", 1)
                icon = "✅" if "Up" in status else "❌"
                containers.append({"name": name, "status": f"{icon} {status}"})
        return containers
    except Exception:
        return []


def _check_module(module_path: str) -> str:
    return "✅ OK" if Path(ROOT / module_path).exists() else "❌ Falta"


def _check_db(db_path: str) -> str:
    p = ROOT / db_path
    if not p.exists():
        return "❌ No existe"
    size = p.stat().st_size
    return f"✅ OK ({size // 1024} KB)"


def generate_status_report() -> str:
    now = datetime.now()
    lines = [
        "# Estado del Sistema URA",
        f"**Fecha:** {now.strftime('%d/%m/%Y %H:%M')}",
        "",
        "---",
        "",
        "## Servicios Principales",
        "",
        "| Servicio | Puerto | Estado |",
        "|----------|--------|--------|",
        f"| API URA v2 | 5000 | {_check_service('API URA v2', 5000)} |",
        f"| Ollama (IA local) | 11434 | {_check_service('Ollama', 11434)} |",
        f"| n8n (automatización) | 5678 | {_check_service('n8n', 5678)} |",
        f"| Redis | 6379 | {_check_service('Redis', 6379)} |",
        f"| Prometheus | 9090 | {_check_service('Prometheus', 9090)} |",
        f"| Grafana | 3000 | {_check_service('Grafana', 3000)} |",
        "",
    ]

    containers = _check_docker_containers()
    if containers:
        lines += [
            "## Contenedores Docker",
            "",
            "| Contenedor | Estado |",
            "|-----------|--------|",
        ]
        for c in containers:
            lines.append(f"| {c['name']} | {c['status']} |")
        lines.append("")

    lines += [
        "## Módulos Críticos",
        "",
        "| Módulo | Estado |",
        "|--------|--------|",
        f"| Agente Policía | {_check_module('core/agente_policia_v2.py')} |",
        f"| Memoria Semántica | {_check_module('core/semantic_memory.py')} |",
        f"| Motor ReAct | {_check_module('core/react_engine.py')} |",
        f"| Bóveda | {_check_module('core/boveda_manager.py')} |",
        f"| Guardián de Cambios | {_check_module('core/change_guardian.py')} |",
        f"| Gestor de Puertos | {_check_module('core/port_manager.py')} |",
        "",
        "## Bases de Datos",
        "",
        "| Base de Datos | Estado |",
        "|--------------|--------|",
        f"| board.db | {_check_db('data/board.db')} |",
        f"| Índice Bóveda | {_check_db('sandbox/Boveda/indice.db')} |",
        "",
        "---",
        "",
        "_Informe generado automáticamente al arrancar URA_",
    ]

    return "\n".join(lines)


def save_status_report() -> Path:
    report = generate_status_report()
    output_path = ROOT / "STATUS.md"
    output_path.write_text(report, encoding="utf-8")
    return output_path


if __name__ == "__main__":
    path = save_status_report()
    print(f"Informe guardado en: {path}")
    print()
    print(path.read_text())
