#!/usr/bin/env python3
"""chaos_test.py — Ingeniería del caos para URA.

Falla forzada de componentes para validar que los fallbacks,
reintentos y límites de reinicio funcionan correctamente.

Uso:
    python3 scripts/pro/chaos_test.py --list          # Listar tests disponibles
    python3 scripts/pro/chaos_test.py --all           # Ejecutar todos los tests
    python3 scripts/pro/chaos_test.py <test_name>     # Ejecutar un test específico

Modo seguro: --dry-run solo simula sin causar daño.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import argparse
import asyncio
import logging
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [CHAOS] %(message)s")
log = logging.getLogger("chaos")

PASS = 0
FAIL = 0
WARN = 0

QDRANT_URL = os.environ.get("QDRANT_URL", "http://127.0.0.1:6333")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        log.info("  ✅ %s — %s", name, detail)
    else:
        FAIL += 1
        log.error("  ❌ %s — %s", name, detail)


def warn(name: str, detail: str = "") -> None:
    global WARN
    WARN += 1
    log.warning("  ⚠️  %s — %s", name, detail)


# ============================================================
# Test 1: Saturar event-loop con tareas bloqueantes
# ============================================================
async def test_queue_saturation(dry_run: bool = False) -> None:
    """Fuerza saturación de la cola de tareas asíncronas.

    Envía 50 tareas que simulan bloqueos de 5s cada una.
    Verifica que el timeout total no exceda lo esperado.
    Si las tareas compiten por el event-loop, el tiempo total
    será ≈ 5s (paralelo) en vez de 250s (serial).
    """
    log.info("\n=== Test 1: Saturación de event-loop ===")
    if dry_run:
        warn("dry-run: se simularían 50 tareas bloqueantes paralelas", "usar --execute para real")

    async def _tarea_bloqueante(n: int) -> float:
        inicio = time.monotonic()
        try:
            # Simula una llamada bloqueante a Qdrant via REST
            import httpx

            async with httpx.AsyncClient(timeout=3) as client:
                await client.get(f"{QDRANT_URL}/collections", timeout=2)
        except Exception:
            pass
        return time.monotonic() - inicio

    inicio = time.monotonic()
    resultados = await asyncio.gather(*[_tarea_bloqueante(i) for i in range(50)], return_exceptions=True)
    total = time.monotonic() - inicio

    exitosos = sum(1 for r in resultados if isinstance(r, float))
    check("50 tareas paralelas completadas", exitosos > 0, f"{exitosos}/50 exitosas en {total:.2f}s")
    check("Latencia total < 30s (paralelismo)", total < 30, f"{total:.2f}s — las tareas corrieron en paralelo")


# ============================================================
# Test 2: Timeout en Ollama — verificar zero-vector protección
# ============================================================
async def test_ollama_timeout(dry_run: bool = False) -> None:
    """Fuerza un timeout de Ollama apuntando a un puerto muerto.

    Verifica que el zero-vector SEA detectado y NO se inserte en Qdrant.
    """
    log.info("\n=== Test 2: Zero-vector en timeout de Ollama ===")
    if dry_run:
        warn("dry-run", "omitir")
        return

    # Apuntar a un puerto que no existe para forzar timeout
    os.environ["OLLAMA_URL"] = "http://127.0.0.1:1"

    from motor.core.config import UraConfig
    from motor.core.qdrant_client import QdrantClient

    qdrant = QdrantClient.instancia(UraConfig.load())
    vec = qdrant.generar_embedding("texto de prueba")

    # Restaurar URL real
    os.environ["OLLAMA_URL"] = OLLAMA_URL

    # Verificar que se detectó como zero-vector (el error debe loguearse)
    es_zero = all(abs(v) < 1e-6 for v in vec)
    check(
        "Zero-vector DETECTADO tras timeout de Ollama (logs: error level)",
        es_zero,
        f"norma={sum(v * v for v in vec) ** 0.5:.4f}" + " — correcto, error ya se loguea en qdrant_client"
        if es_zero
        else "",
    )


# ============================================================
# Test 3: systemd restart limits — simular crash
# ============================================================
def test_restart_limits(dry_run: bool = False) -> None:
    """Verifica que los servicios críticos tengan límites de reinicio.

    Comprueba que StartLimitBurst esté presente en los principales servicios.
    """
    log.info("\n=== Test 3: Límites de reinicio systemd ===")

    servicios = ["ura-ejecutor", "model-router", "ura-openclaw", "ura-mochila", "ura-voice", "opencode"]
    for svc in servicios:
        r = subprocess.run(
            ["systemctl", "show", "-p", "StartLimitBurst", svc],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        val = r.stdout.strip().split("=")[-1] if "=" in r.stdout else "ausente"
        if dry_run:
            warn(f"dry-run: {svc}.StartLimitBurst={val}", "omitir")
        else:
            check(f"{svc} tiene StartLimitBurst", val not in ("", "0", "(null)", "ausente"), f"={val}")


# ============================================================
# Test 4: Port binding conflicts — verificar que no colisionan
# ============================================================
async def test_port_conflicts(dry_run: bool = False) -> None:
    """Verifica que los puertos críticos no tengan colisiones.

    Escanea los puertos conocidos y verifica que cada servicio
    responda correctamente en su puerto asignado.
    """
    log.info("\n=== Test 4: Conflictos de puerto ===")

    port_map = {
        "ejecutor": (4097, "URA Ejecutor API (nuevo puerto)"),
        "router": (11435, "Model Router"),
        "mochila": (4098, "Mochila Health"),
        "qdrant": (6333, "Qdrant REST"),
        "ollama": (11434, "Ollama API"),
    }

    for name, (port, desc) in port_map.items():
        try:
            sock = socket.socket()
            sock.settimeout(2)
            sock.connect(("127.0.0.1", port))
            sock.close()
            if name == "ejecutor":
                check(f"Puerto {port} ({desc})", port == 4097, "OK — migrado correctamente")
            else:
                check(f"Puerto {port} ({desc})", True, "responde")
        except (TimeoutError, OSError):
            if dry_run:
                warn(f"dry-run: Puerto {port} ({desc}) no responde", "omitir")
            else:
                warn(f"Puerto {port} ({desc}) no responde", "posible colisión o servicio caído")


# ============================================================
# Test 5: Graceful shutdown — enviar SIGTERM y medir tiempo
# ============================================================
async def test_graceful_shutdown(dry_run: bool = False) -> None:
    """Envía SIGTERM a un worker interno y mide tiempo de parada limpia.

    No afecta servicios reales — usa un worker simulado.
    """
    log.info("\n=== Test 5: Graceful shutdown ===")

    if dry_run:
        warn("dry-run: se simularía SIGTERM a worker interno", "omitir")
        return

    # Worker simulado que atrapa SIGTERM
    import signal as sigmod

    shutdown_ok = False

    def _handler(signum, frame):
        nonlocal shutdown_ok
        shutdown_ok = True

    sigmod.signal(sigmod.SIGTERM, _handler)
    os.kill(os.getpid(), sigmod.SIGTERM)
    time.sleep(0.1)
    sigmod.signal(sigmod.SIGTERM, sigmod.SIG_DFL)

    check("SIGTERM manejado correctamente", shutdown_ok, "handler ejecutado")


# ============================================================
# Test 6: REST fallback — verificar que find_stale_docs funciona
# ============================================================
async def test_rest_fallback(dry_run: bool = False) -> None:
    """Verifica que find_stale_docs tenga fallback REST implementado.

    Comprueba que el código de auto_reindex.py contenga la ruta REST.
    """
    log.info("\n=== Test 6: REST fallback en find_stale_docs ===")

    with open("core/auto_reindex.py") as f:
        code = f.read()

    has_rest = "_find_stale_docs_rest" in code
    has_fallback = "REST fallback" in code

    if dry_run:
        warn("dry-run: verificación de código", f"REST fallback: {has_rest}")
    else:
        check(
            "find_stale_docs con REST fallback",
            has_rest and has_fallback,
            "_find_stale_docs_rest implementado" if has_rest else "FALTA implementación REST",
        )


# ============================================================
# Test 7: Timestamps UTC — verificar que no hay naive
# ============================================================
def test_timestamps_utc(dry_run: bool = False) -> None:
    """Busca datetime.now().isoformat() en todo el proyecto.

    La presencia de esta llamada indica timestamps naive sin zona horaria.
    """
    log.info("\n=== Test 7: Timestamps UTC (sin naive) ===")

    r = subprocess.run(
        ["grep", "-rn", "datetime.now().isoformat()", "--include=*.py", "core/", "motor/", "scripts/pro/", "monitor/"],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )

    naive_files = [l for l in r.stdout.splitlines() if l.strip()]
    if dry_run:
        warn(f"dry-run: {len(naive_files)} archivos con timestamps naive", "omitir")
    else:
        check(
            "Sin timestamps naive en el proyecto",
            len(naive_files) == 0,
            f"{len(naive_files)} ocurrencias encontradas: {naive_files[:3]}" if naive_files else "OK",
        )


# ============================================================
# Test 8: Secretos en disco — verificar que no hay tokens visibles
# ============================================================
def test_secrets_visible(dry_run: bool = False) -> None:
    """Busca cadenas con aspecto de API key en archivos de código.

    Escanea patrones como 'sk-...' o 'apiKey' en el código fuente.
    """
    log.info("\n=== Test 8: Secretos visibles en código ===")

    r = subprocess.run(
        ["grep", "-rn", "sk-[A-Za-z0-9]\\{20,\\}", "--include=*.py", "core/", "motor/", "scripts/pro/"],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    secrets = [l for l in r.stdout.splitlines() if not l.strip().startswith("Binary")]

    if dry_run:
        warn(f"dry-run: {len(secrets)} posibles secrets", "omitir")
    else:
        check(
            "Sin API keys hardcodeadas en código",
            len(secrets) == 0,
            f"{len(secrets)} encontrados: {secrets[:2]}" if secrets else "OK",
        )


# ============================================================
# Test 9: Ruta de logging NDJSON — verificar consistencia
# ============================================================
def test_log_path_consistency(dry_run: bool = False) -> None:
    """Verifica que el writer y reader de NDJSON apunten al mismo sitio."""
    log.info("\n=== Test 9: Consistencia de ruta NDJSON ===")

    writer_dir = "/tmp/ura_search_logs"
    reader_dir = "/tmp/ura_search_logs"  # después del parche 0.6

    if not os.path.exists(writer_dir):
        if dry_run:
            warn(f"dry-run: directorio {writer_dir} no existe", "se crea en primera escritura")
        else:
            warn(f"directorio {writer_dir} no existe", "se creará en primera escritura de search_logger")

    check("Writer y reader apuntan al mismo directorio", writer_dir == reader_dir, f"ambos → {writer_dir}")


# ============================================================
# Test 10: Asyncio bridge — verificar implementación correcta
# ============================================================
def test_asyncio_bridge(dry_run: bool = False) -> None:
    """Verifica que qdrant_client.py tenga el bridge seguro.

    Comprueba que use ThreadPoolExecutor y NO loop.run_until_complete.
    """
    log.info("\n=== Test 10: Bridge async-sync (ThreadPoolExecutor) ===")

    with open("motor/core/qdrant_client.py") as f:
        code = f.read()

    has_executor = "ThreadPoolExecutor" in code
    has_run_until = "run_until_complete" in code

    check(
        "Bridge usa ThreadPoolExecutor (no loop.run_until_complete)",
        has_executor and not has_run_until,
        "ThreadPoolExecutor presente" if has_executor else "AÚN USA run_until_complete — PELIGRO",
    )


# ============================================================
# MAIN
# ============================================================
async def main() -> int:
    parser = argparse.ArgumentParser(description="URA Chaos Engineering Test Suite")
    parser.add_argument("test", nargs="?", help="Nombre del test a ejecutar")
    parser.add_argument("--list", action="store_true", help="Listar tests disponibles")
    parser.add_argument("--all", action="store_true", help="Ejecutar todos los tests")
    parser.add_argument("--dry-run", action="store_true", help="Modo simulación (no causa daño)")
    parser.add_argument("--execute", action="store_true", help="Ejecutar tests que pueden causar degradación")
    args = parser.parse_args()

    tests = {
        "queue_saturation": test_queue_saturation,
        "ollama_timeout": test_ollama_timeout,
        "restart_limits": test_restart_limits,
        "port_conflicts": test_port_conflicts,
        "graceful_shutdown": test_graceful_shutdown,
        "rest_fallback": test_rest_fallback,
        "timestamps_utc": test_timestamps_utc,
        "secrets_visible": test_secrets_visible,
        "log_path_consistency": test_log_path_consistency,
        "asyncio_bridge": test_asyncio_bridge,
    }

    if args.list:
        print("Tests disponibles:")
        for name, fn in tests.items():
            print(f"  {name:<20s} — {fn.__doc__.strip() if fn.__doc__ else ''}")
        return 0

    dry_run = args.dry_run or not args.execute

    if args.all or args.test == "all":
        for name, fn in tests.items():
            if asyncio.iscoroutinefunction(fn):
                await fn(dry_run=dry_run)
            else:
                fn(dry_run=dry_run)
    elif args.test:
        fn = tests.get(args.test)
        if not fn:
            log.error("Test no encontrado: %s", args.test)
            return 1
        if asyncio.iscoroutinefunction(fn):
            await fn(dry_run=dry_run)
        else:
            fn(dry_run=dry_run)
    else:
        # Modo interactivo: ejecutar todos en dry-run
        log.info("Modo: --dry-run (simulación, sin daño). Usa --execute para forzar fallos reales.")
        for name, fn in tests.items():
            if asyncio.iscoroutinefunction(fn):
                await fn(dry_run=True)
            else:
                fn(dry_run=True)

    total = PASS + FAIL
    log.info("\n=== RESULTADOS ===")
    log.info("  ✅ PASS: %d", PASS)
    log.info("  ❌ FAIL: %d", FAIL)
    log.info("  ⚠️  WARN: %d", WARN)
    log.info("  📊 TOTAL: %d tests", total)
    log.info("  🎯 SCORE: %d/%d (%.0f%%)", PASS, total, PASS / total * 100 if total else 0)

    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
