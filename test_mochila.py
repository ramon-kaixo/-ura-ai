import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "core"))
from mochila_engine import MochilaEngine, FaseID, TipoPipeline

def ok(m): print(f"  \033[92m{chr(10003)}\033[0m {m}")
def ng(m): print(f"  \033[91m{chr(10007)}\033[0m {m}")

async def main():
    e=0
    try:
        m=MochilaEngine.nueva("https://ejemplo.com/img.jpg",TipoPipeline.IMAGEN,"p")
        assert m.url=="https://ejemplo.com/img.jpg"; assert m.tipo==TipoPipeline.IMAGEN
        ok("Mochila creada")
    except Exception as ex: ng(f"P1:{ex}"); e+=1
    try:
        m.reg_r(motor_id="m1",latencia_ms=120.5)
        assert m.red["motor_id"]=="m1"; ok("Red OK")
    except Exception as ex: ng(f"P2:{ex}"); e+=1
    try:
        m.reg_h(sha256="abc123")
        assert m.hashes["sha256"]=="abc123"; ok("Hashes OK")
    except Exception as ex: ng(f"P3:{ex}"); e+=1
    try:
        p=Path("/tmp/pm/m.json"); m.guardar(p); assert p.exists(); ok("Guardado")
    except Exception as ex: ng(f"P4:{ex}"); e+=1
    try:
        m2=MochilaEngine.cargar(p); assert m2.id==m.id; ok("Cargado OK")
    except Exception as ex: ng(f"P5:{ex}"); e+=1
    try:
        async with m.fase(FaseID.F1_ROUTER) as c: c.dt["r"]="ok"
        assert m.fc(FaseID.F1_ROUTER); ok("Fase ejecutada")
    except Exception as ex: ng(f"P6:{ex}"); e+=1
    print("\n"+"="*40)
    if e==0: print("\033[92m  TODO OK - la mochila funciona\033[0m")
    else: print(f"\033[91m  {e} FALLO(S)\033[0m")
    print("="*40); return e

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
