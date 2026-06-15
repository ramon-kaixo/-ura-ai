#!/usr/bin/env python3
"""run_tuneladora.py — Entry-point cron nocturno."""
from __future__ import annotations
import sys; from pathlib import Path
R=Path(__file__).resolve().parent
if str(R) not in sys.path: sys.path.insert(0,str(R))
import argparse,asyncio,logging
from datetime import datetime

def log():
    l=logging.getLogger("tuneladora"); l.setLevel(logging.INFO)
    if l.handlers: return l
    h=logging.StreamHandler(sys.stdout); h.setFormatter(logging.Formatter("[%(asctime)s] %(message)s",datefmt="%Y-%m-%d %H:%M:%S")); l.addHandler(h)
    try:
        from mochila_engine import BASE_DIR
        p=BASE_DIR/"05_RETROALIMENTACION"/"tuneladora.log"; p.parent.mkdir(parents=1,exist_ok=1)
        l.addHandler(logging.FileHandler(str(p),encoding="utf-8"))
    except Exception:
        pass  # expected if no args
    return l

def ci(l):
    import importlib
    ok=True
    for m in ["mochila_engine","core.guardians.ast_sentinel","core.sandbox.docker_orchestrator","core.cleaner.cold_refactor"]:
        try: importlib.import_module(m); l.info(f"  OK: {m}")
        except ModuleNotFoundError as e: l.error(f"FALTA: {m} - {e}"); ok=False
    return ok

async def run(dry,l):
    from core.cleaner.cold_refactor import ColdRefactor
    r=ColdRefactor(); e=r.estado_deuda(); l.info(f"Deuda: {e['pend']} pend")
    if e['pend']==0: l.info("Sin deuda."); return 0
    if dry: l.info(f"[DRY] Pend: {e['skills']}"); return 0
    res=await r.ejecutar_tuneladora(); l.info(f"Res: {res}"); return 0

def main():
    a=argparse.ArgumentParser(); a.add_argument("--dry-run",action="store_true"); args=a.parse_args()
    l=log(); l.info("="*60); l.info(f"Raiz: {R}")
    if not ci(l): return 2
    return asyncio.run(run(args.dry_run,l))

if __name__=="__main__": sys.exit(main())
