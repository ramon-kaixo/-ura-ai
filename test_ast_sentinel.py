import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from core.guardians.ast_sentinel import ASTSentinel
def ok(m): print(f"  \033[92m{chr(10003)}\033[0m {m}")
def ng(m): print(f"  \033[91m{chr(10007)}\033[0m {m}"); return 1
s=ASTSentinel(); e=0
v=s.analizar('def f(a:int,b:int)->int:\n """S"""\n return a+b',"b")
if v.ok: ok("Limpio APROBADO")
else: e+=ng(f"P1:{v.errs}")
v=s.analizar('def f():\n try:\n  pass\n except:\n  pass',"m")
if not v.ok: ok("Mal code RECHAZADO")
else: e+=ng("P2: debio rechazar")
v=s.analizar('def f(a,b):\n return a',"s")
if not v.ok: ok("Sin tipos RECHAZADO")
else: e+=ng("P3: debio rechazar")
print("\n"+"="*40)
if e==0: print("\033[92m  TODO OK - revisor funciona\033[0m")
else: print(f"\033[91m  {e} FALLO(S)\033[0m")
if __name__ == "__main__":
    print("="*40); sys.exit(e)
