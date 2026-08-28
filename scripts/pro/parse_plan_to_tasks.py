#!/usr/bin/env python3
"""parse_plan_to_tasks.py — Parsea un plan markdown y crea tareas en el orquestador.

Uso:
    python3 parse_plan_to_tasks.py <plan_file.md> [--node NODE] [--dry-run]
    echo "### Tarea 1\n..." | python3 parse_plan_to_tasks.py -

Formato esperado del plan (markdown):
    ## Título del plan

    ### Sprint 1 — Nombre
    - [ ] Tarea 1: descripción
    - [ ] Tarea 2: descripción

    ### Sprint 2 — Nombre
    1. Tarea 3: descripción
    2. Tarea 4: descripción

    O también:
    ## Tarea: Nombre
    Prioridad: alta
    Nodo: gx10
    Descripción: ...

Reglas de parsing:
    - ## o ### = separador de fase/bloque
    - - [ ] o número + punto = tarea individual
    - Líneas con "Prioridad:", "Nodo:", "Timeout:" = metadatos de la tarea anterior
    - Líneas vacías separan tareas
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.error import URLError


@dataclass
class TaskSpec:
    """Especificación de una tarea parseada del plan."""

    title: str
    description: str = ""
    phase: str = ""
    priority: int = 0
    node_id: str = ""
    timeout_seconds: int = 1800
    context_json: str = "{}"


PRIORITY_MAP = {
    "alta": 10,
    "high": 10,
    "critica": 10,
    "critical": 10,
    "media": 5,
    "medium": 5,
    "baja": 0,
    "low": 0,
}


def _finalize(
    tasks: list[TaskSpec],
    current_task: TaskSpec | None,
    description_lines: list[str],
) -> TaskSpec | None:
    """Cierra la tarea pendiente, la anexa a la lista y devuelve None."""
    if current_task is None:
        return None
    if description_lines:
        current_task.description = "\n".join(description_lines).strip()
    elif not current_task.description:
        current_task.description = current_task.title
    tasks.append(current_task)
    return None


def parse_plan(content: str) -> list[TaskSpec]:
    """Parsea markdown del plan en lista de TaskSpec."""
    tasks: list[TaskSpec] = []
    current_phase = ""
    current_task: TaskSpec | None = None
    description_lines: list[str] = []

    for line in content.splitlines():
        stripped = line.strip()

        # Phase headers (## or ###)
        if re.match(r"^#{2,3}\s+", stripped):
            current_task = _finalize(tasks, current_task, description_lines)
            description_lines = []
            current_phase = re.sub(r"^#{2,3}\s+", "", stripped)
            continue

        # Task items: - [ ] or 1. or -
        task_match = re.match(r"^(?:-\s*\[.\]\s*|\d+\.\s+)(.+)", stripped)
        if task_match:
            current_task = _finalize(tasks, current_task, description_lines)
            description_lines = []

            title = task_match.group(1).strip()
            # Remove trailing colon if present
            title = title.rstrip(":")
            current_task = TaskSpec(title=title, phase=current_phase)
            continue

        # Metadata lines
        if current_task and stripped:
            meta_match = re.match(r"^(Prioridad|Priority|Nodo|Node|Timeout|Tiempo):\s*(.+)", stripped, re.IGNORECASE)
            if meta_match:
                key, value = meta_match.group(1).lower(), meta_match.group(2).strip()
                if key in ("prioridad", "priority"):
                    current_task.priority = PRIORITY_MAP.get(value.lower(), 5)
                elif key in ("nodo", "node"):
                    current_task.node_id = value
                elif key in ("timeout", "tiempo"):
                    with contextlib.suppress(ValueError):
                        current_task.timeout_seconds = int(value)
                continue

        # Description continuation
        if current_task and stripped:
            description_lines.append(stripped)

    # Last task
    _finalize(tasks, current_task, description_lines)

    return tasks



def resolve_node_url(node_id: str, default_url: str, registry_url: str = "") -> str:
    """Resolve a node_id to its API URL using the node registry."""
    if not node_id or node_id == "any":
        return default_url
    # Try to get registry from the default URL's node
    if registry_url:
        try:
            body = json.dumps({}).encode()
            req = urllib.request.Request(f"{registry_url}/nodes/{node_id}", headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                node = json.loads(resp.read())
                return f"http://{node['tailscale_ip']}:{node['api_port']}"
        except (URLError, OSError, json.JSONDecodeError, KeyError):
            pass
    # Fallback: try GX10 as known registry
    for known_url in ["http://100.72.103.12:4097", "http://localhost:4097"]:
        try:
            req = urllib.request.Request(f"{known_url}/nodes/{node_id}")
            with urllib.request.urlopen(req, timeout=3) as resp:
                node = json.loads(resp.read())
                return f"http://{node['tailscale_ip']}:{node['api_port']}"
        except (URLError, OSError, json.JSONDecodeError, KeyError):
            continue
    return default_url

def create_task(api_url: str, task: TaskSpec, dry_run: bool = False,
                api_key: str = "", source_node: str = "") -> dict | None:

    """Crea una tarea en el orquestador via API."""
    payload = {
        "description": f"[{task.phase}] {task.title}" if task.phase else task.title,
        "plan_phase": task.phase,
        "priority": task.priority,
        "timeout_seconds": task.timeout_seconds,
        "node_id": task.node_id,
        "context_json": json.dumps({"plan_task": task.title, "plan_phase": task.phase}),
    }

    if dry_run:
        print(f"  [DRY-RUN] Would create: {task.title}")
        print(f"    Phase: {task.phase}")
        print(f"    Priority: {task.priority}")
        print(f"    Node: {task.node_id or 'any'}")
        print(f"    Timeout: {task.timeout_seconds}s")
        return None

    # Determine endpoint: sync if target is remote, create if local
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key

    is_remote = source_node and task.node_id and task.node_id != source_node
    if is_remote:
        # Remote task — use sync endpoint (don't create locally)
        endpoint = f"{api_url}/tasks/sync"
        payload["source_node"] = source_node
        payload["source_task_id"] = f"{source_node}-{task.title[:20]}"
    else:
        # Local task
        endpoint = f"{api_url}/tasks"

    try:
        body = json.dumps(payload).encode()
        req = urllib.request.Request(endpoint, data=body, headers=headers)  # noqa: S310
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
            result = json.loads(resp.read())
            return result
    except (URLError, OSError, json.JSONDecodeError) as e:
        print(f"  [ERROR] Failed to create task '{task.title}': {e}", file=sys.stderr)
        return None


def main():
    parser = argparse.ArgumentParser(description="Parse plan and create tasks in orchestrator")
    parser.add_argument("plan", help="Plan file (markdown) or - for stdin")
    parser.add_argument(
        "--url", default=os.environ.get("URA_ORCHESTRATOR_URL", "http://localhost:4097"), help="Orchestrator API URL"
    )
    parser.add_argument("--node", default="", help="Default node for tasks without explicit node")
    parser.add_argument("--dry-run", action="store_true", help="Show tasks without creating them")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument("--distribute", action="store_true", help="Distribute tasks to remote nodes via sync endpoint")
    parser.add_argument("--api-key", default=os.environ.get("URA_API_KEY", ""), help="API key for authentication")
    args = parser.parse_args()

    # Read plan
    if args.plan == "-":
        content = sys.stdin.read()
    else:
        with Path(args.plan).open() as f:
            content = f.read()

    # Parse
    tasks = parse_plan(content)
    if not tasks:
        print("No tasks found in plan.", file=sys.stderr)
        sys.exit(1)

    # Apply default node
    for t in tasks:
        if not t.node_id:
            t.node_id = args.node

    print(f"Found {len(tasks)} tasks in plan.\n")

    # Determine source node for distribution
    source_node = ""
    if args.distribute:
        source_node = args.node or os.environ.get("URA_NODE_ID", "unknown")
        print(f"Distributing from node: {source_node}\n")

    # Create tasks
    results = []
    for i, task in enumerate(tasks, 1):
        print(f"{i}/{len(tasks)}: {task.title}")
        # Resolve the target URL based on node_id
        target_url = resolve_node_url(task.node_id, args.url, args.url)
        result = create_task(target_url, task, args.dry_run,
                           api_key=args.api_key, source_node=source_node)

        if result:
            status = result.get("status", "unknown")
            task_id = result.get("task_id", result.get("id", "?"))
            is_remote = source_node and task.node_id and task.node_id != source_node
            label = "synced" if is_remote else "local"
            print(f"  -> {status} ({label}): {task_id} [→{task.node_id or 'any'}]")
            results.append(result)
        elif not args.dry_run:
            print("  -> FAILED")

    print(f"\nDone. {len(results)}/{len(tasks)} tasks created.")

    if args.json:
        print(json.dumps({"created": len(results), "total": len(tasks), "tasks": results}, indent=2))


if __name__ == "__main__":
    main()
