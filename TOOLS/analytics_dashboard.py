"""analytics_dashboard.py — Dashboard de analítica en terminal."""
import json, statistics
from collections import defaultdict
from pathlib import Path
try:
    from rich.console import Console; from rich.table import Table; from rich.panel import Panel
    from rich.text import Text; from rich import box; from rich.rule import Rule
    HAS_RICH = True
except: HAS_RICH = False
from mochila_engine import BASE_DIR

RETRO_DIR = BASE_DIR / "05_RETROALIMENTACION"
AUDIT_LOG = RETRO_DIR / "audit_log.jsonl"
_console = Console(width=120) if HAS_RICH else None


def _cargar_audit(n_max=2000):
    if not AUDIT_LOG.exists(): return []
    lines = AUDIT_LOG.read_text().strip().splitlines()
    return [json.loads(l) for l in lines[-n_max:]]


def render():
    if not HAS_RICH:
        print("pip install rich para el dashboard")
        return
    entradas = _cargar_audit()
    if not entradas:
        _console.print(Panel("[dim]Sin datos de auditoria todavia.[/dim]", title="URA-Search Analytics"))
        return

    n = len(entradas)
    n_rev = sum(1 for e in entradas if e.get("rev"))
    scores = [e.get("score_fid", 0) for e in entradas if e.get("score_fid", 0) > 0]
    media = statistics.mean(scores) if scores else 0

    _console.print(Rule("[bold]URA-Search v5.0 — Dashboard[/bold]"))
    _console.print(f"[dim]{n} ingestas | Revision: {n_rev} | Score fid medio: {media:.3f}[/dim]\n")

    tabla = Table(box=box.SIMPLE, show_header=True, header_style="bold")
    tabla.add_column("Timestamp", width=20); tabla.add_column("URL", width=45); tabla.add_column("Dominio", width=20)
    tabla.add_column("Score", width=7, justify="right"); tabla.add_column("Rev", width=4, justify="center")
    for e in entradas[-15:]:
        ts = e.get("ts", "")[:19].replace("T", " ")
        url = (e.get("url", "")[:42] + "..") if len(e.get("url", "")) > 42 else e.get("url", "")
        rev = "[yellow]▲[/yellow]" if e.get("rev") else "[green]✓[/green]"
        tabla.add_row(ts, url, e.get("dominio", ""), f"{e.get('score_fid', 0):.2f}", rev)
    _console.print(Panel(tabla, title="Ultimas 15 ingestas"))
    _console.print(f"\n[dim]Audit log: {AUDIT_LOG}[/dim]")


if __name__ == "__main__":
    render()
