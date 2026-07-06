"""ast_sentinel.py — Capa 1"""
from __future__ import annotations
import ast, hashlib, re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_CC = 10; MAX_L = 50
PROH = frozenset({"os.system","subprocess.call","subprocess.Popen","eval","exec","compile","__import__","pickle","marshal"})
DP = [(re.compile(r"#\s*(TODO|FIXME|HACK|WORKAROUND)", re.I), "deuda")]

@dataclass
class V:
    ok: bool; debt: str|None; errs: list[str]; warns: list[str]; m: dict[str,Any]
    ts: str = field(default_factory=lambda: datetime.now(tz=timezone.utc).isoformat())
    def resumen(s):
        e="OK" if s.ok else "FAIL"
        r=[f"[AST] {e}"]+[f"  - {x}" for x in s.errs]+[f"  D {w}" for w in s.warns]
        if s.debt: r.append(f"  DEBT_ID: {s.debt}")
        return "\n".join(r)

class _CV(ast.NodeVisitor):
    def __init__(s): s.c=1
    def visit_If(s,n): s.c+=1;s.generic_visit(n)
    def visit_For(s,n): s.c+=1;s.generic_visit(n)
    def visit_While(s,n): s.c+=1;s.generic_visit(n)
    def visit_ExceptHandler(s,n): s.c+=1;s.generic_visit(n)
    def visit_BoolOp(s,n): s.c+=len(n.values)-1;s.generic_visit(n)

def _cc(f): v=_CV();v.visit(f);return v.c

class ASTSentinel:
    def analizar(s, codigo, nombre="skill", prod=True):
        e=[];w=[];m={}
        try: t=ast.parse(codigo)
        except SyntaxError as ex: return V(False,None,[f"Syntax: {ex}"],[],{})
        fs=[n for n in ast.walk(t) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))]
        m["nf"]=len(fs);mx=0
        for f in fs:
            c=_cc(f);mx=max(mx,c)
            if c>MAX_CC: e.append(f"'{f.name}': CC {c}>{MAX_CC}")
            if prod and f.returns is None: e.append(f"'{f.name}': sin retorno")
            if prod and not ast.get_docstring(f): w.append(f"'{f.name}': sin doc")
            for a in f.args.args:
                if a.annotation is None and a.arg!="self": e.append(f"'{f.name}': arg '{a.arg}' sin tipo")
        m["cc_max"]=mx
        for n in ast.walk(t):
            if isinstance(n,ast.Try):
                for h in n.handlers:
                    if h.type is None: e.append(f"L{h.lineno}: except")
                    if all(isinstance(x,ast.Pass) for x in h.body): e.append(f"L{h.lineno}: pass")
            elif isinstance(n,ast.Global): e.append(f"L{n.lineno}: global")
            elif isinstance(n,ast.Import):
                for a in n.names:
                    if a.name in PROH: e.append(f"import: '{a.name}'")
            elif isinstance(n,ast.ImportFrom):
                for a in n.names:
                    if f"{n.module or ''}.{a.name}" in PROH: e.append(f"import: '{n.module}.{a.name}'")
        for i,l in enumerate(codigo.splitlines(),1):
            for p,ti in DP:
                if p.search(l): w.append(f"L{i}: {ti}")
        for n in ast.walk(t):
            if isinstance(n,ast.Constant) and isinstance(n.value,(int,float)) and n.value not in (0,1,-1,2,True,False):
                w.append(f"L{n.lineno}: magic {n.value}")
        m["lines"]=len(codigo.splitlines())
        d=None
        if w: d=f"0x{hashlib.sha256((codigo+''.join(w)).encode()).hexdigest()[:8]}"
        return V(len(e)==0,d,e,w,m)
