"""gatekeeper.py — Capa 4: CLI de control humano."""
from __future__ import annotations
import asyncio, json, sys
from datetime import datetime
from pathlib import Path
import click
from mochila_engine import BASE_DIR
from core.guardians.ast_sentinel import ASTSentinel
from core.sandbox.docker_orchestrator import DockerOrchestrator
from core.cleaner.cold_refactor import ColdRefactor

PD = BASE_DIR / "TOOLS" / "skills_pending"
RP = BASE_DIR / "05_RETROALIMENTACION" / "skills_registry.json"

@click.group()
def ura(): """URA Zero-Patch."""

@ura.command("agency-status")
def agency_status():
    d=ColdRefactor().estado_deuda(); print(f"Deuda pendiente: {d['pend']}")

@ura.command("skill-review")
@click.argument("nombre")
def skill_review(nombre):
    p=PD/f"{nombre}.py"
    if not p.exists(): click.echo(f"'{nombre}' no encontrado."); sys.exit(1)
    c=p.read_text(); v=ASTSentinel().analizar(c,nombre); print(v.resumen()); print(c)

@ura.command("skill-approve")
@click.argument("nombre")
@click.option("--skip-sandbox",is_flag=True)
def skill_approve(nombre,skip_sandbox):
    p=PD/f"{nombre}.py"
    if not p.exists(): click.echo(f"'{nombre}' no encontrado."); sys.exit(1)
    c=p.read_text(); v=ASTSentinel().analizar(c,nombre)
    if not v.ok: click.echo(f"RECHAZADO AST: {v.errs}"); sys.exit(1)
    if not skip_sandbox:
        sb=asyncio.run(DockerOrchestrator().validar(c,nombre))
        if not sb.ok: click.echo(f"RECHAZADO Sandbox: {sb.error}"); sys.exit(1)
    ref=ColdRefactor()
    sp=ref.registrar_deuda(v.debt,nombre,c,v.warns) if v.debt else ref.registrar_limpio(nombre,c)
    _reg(nombre,v,sp); p.unlink(); click.echo(f"'{nombre}' desplegado")

@ura.command("skill-reject")
@click.argument("nombre")
@click.option("--razon",default="Rechazado manualmente")
def skill_reject(nombre,razon):
    p=PD/f"{nombre}.py"
    if p.exists(): p.unlink(); click.echo(f"'{nombre}' rechazado: {razon}")

@ura.command("debt-status")
def debt_status():
    d=ColdRefactor().estado_deuda(); click.echo(f"Deuda: {d['pend']}" if d['pend'] else "Sin deuda.")

@ura.command("debt-clean")
@click.option("--forzar",is_flag=True)
def debt_clean(forzar):
    _ = forzar
    r=asyncio.run(ColdRefactor().ejecutar_tuneladora())
    click.echo(f"Proc: {r['procesados']} | Res: {r['resueltos']}")

def _reg(n,v,sp):
    r={}
    if RP.exists():
        try: r=json.loads(RP.read_text())
        except Exception:
        pass  # expected on missing dir
    r[n]={"path":str(sp),"debt":v.debt,"ts":datetime.now().isoformat()}
    RP.parent.mkdir(parents=1,exist_ok=1); RP.write_text(json.dumps(r,ensure_ascii=0,indent=2))

def registrar_skill_propuesto(nombre,codigo):
    PD.mkdir(parents=1,exist_ok=1); (PD/f"{nombre}.py").write_text(codigo)
    v=ASTSentinel().analizar(codigo,nombre)
    return {"nombre":nombre,"path":str(PD/f"{nombre}.py"),"analisis_ast":{"ok":v.ok,"errs":v.errs,"warns":v.warns,"debt":v.debt},"accion":f"ura skill-review {nombre}"}
