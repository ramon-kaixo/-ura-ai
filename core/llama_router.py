#!/usr/bin/env python3
"""
llama_router.py — Router multi-modelo usando llama.cpp (CUDA)
1 solo puerto (8288), enruta al llama-server correcto según modelo.
API compatible con OpenAI /chat/completions.
"""

import argparse
import json
import logging
import os
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("llama_router")

MODELS = {
    "codestral-22b": {
        "path": str(Path.home() / "models/llama-cpp/codestral-22b.gguf"),
        "port": 8289,
        "ngl": 99,
        "ctx": 8192,
    },
    "qwen2.5-coder-q8": {
        "path": str(Path.home() / "models/llama-cpp/qwen2.5-coder-q8_0.gguf"),
        "port": 8290,
        "ngl": 99,
        "ctx": 8192,
    },
    "qwen2.5-coder-32b": {
        "path": str(Path.home() / "models/llama-cpp/qwen2.5-coder-32b.gguf"),
        "port": 8291,
        "ngl": 99,
        "ctx": 8192,
    },
    "kimi-dev": {
        "path": str(Path.home() / "models/kimi-dev/Kimi-Dev-72B-abliterated-Q8_0.gguf"),
        "port": 8292,
        "ngl": 80,
        "ctx": 16384,
    },
}

LLAMA_SERVER = str(Path.home() / "llama.cpp/build_cuda/bin/llama-server")
ROUTER_PORT = 8288
processes: dict[str, subprocess.Popen] = {}


def start_server(name: str, config: dict) -> bool:
    path = config["path"]
    if not os.path.exists(path):
        logger.error(f"GGUF no encontrado: {path}")
        return False

    cmd = [
        LLAMA_SERVER,
        "-m",
        path,
        "--port",
        str(config["port"]),
        "--host",
        "127.0.0.1",
        "-ngl",
        str(config["ngl"]),
        "-c",
        str(config["ctx"]),
        "--mlock",
    ]
    logger.info(f"Iniciando {name} en puerto {config['port']}...")
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        processes[name] = p
        logger.info(f"  {name} PID={p.pid}")
        return True
    except Exception as e:
        logger.error(f"  Error iniciando {name}: {e}")
        return False


def wait_ready(name: str, port: int, timeout: int = 120) -> bool:
    url = f"http://127.0.0.1:{port}/health"
    start = time.time()
    while time.time() - start < timeout:
        try:
            urllib.request.urlopen(url, timeout=3)  # nosec B310
            logger.info(f"  {name} listo ({time.time() - start:.0f}s)")
            return True
        except Exception:
            time.sleep(2)
    logger.error(f"  {name} NO arrancó en {timeout}s")
    return False


def stop_all():
    for name, p in processes.items():
        if p.poll() is None:
            logger.info(f"Parando {name}...")
            p.terminate()
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()


def check_backend(name: str, port: int) -> bool:
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/health")
        urllib.request.urlopen(req, timeout=3)  # nosec B310
        return True
    except Exception:
        return False


def health_handler(environ: dict, start_response) -> list[bytes]:
    status = {}
    for name, config in MODELS.items():
        status[name] = (
            "UP"
            if check_backend(name, config["port"])
            else "DOWN"
            if name in processes
            else "STOPPED"
        )
    body = json.dumps(status, indent=2).encode()
    start_response(
        "200 OK", [("Content-Type", "application/json"), ("Content-Length", str(len(body)))]
    )
    return [body]


def chat_handler(environ: dict, start_response) -> list[bytes]:
    if environ.get("REQUEST_METHOD") != "POST":
        error = json.dumps({"error": "Only POST allowed"}).encode()
        start_response("405 Method Not Allowed", [("Content-Type", "application/json")])
        return [error]
    content_length = int(environ.get("CONTENT_LENGTH", 0))
    body = json.loads(environ["wsgi.input"].read(content_length))
    model = body.get("model", "codestral-22b")

    config = MODELS.get(model)
    if not config:
        error = json.dumps({"error": f"Modelo '{model}' no encontrado"}).encode()
        start_response("404 Not Found", [("Content-Type", "application/json")])
        return [error]

    backend_url = f"http://127.0.0.1:{config['port']}/v1/chat/completions"

    try:
        req = urllib.request.Request(
            backend_url,
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=300) as resp:  # nosec B310
            data = resp.read()
            start_response(
                "200 OK", [("Content-Type", "application/json"), ("Content-Length", str(len(data)))]
            )
            return [data]
    except urllib.error.URLError as e:
        error = json.dumps({"error": f"Backend {model} caído: {e}"}).encode()
        start_response("503 Service Unavailable", [("Content-Type", "application/json")])
        return [error]


def application(environ: dict, start_response) -> list[bytes]:
    path = environ.get("PATH_INFO", "")
    if path == "/health":
        return health_handler(environ, start_response)
    elif path in ("/v1/chat/completions", "/chat/completions"):
        return chat_handler(environ, start_response)
    else:
        body = json.dumps({"error": "Not found"}).encode()
        start_response("404 Not Found", [("Content-Type", "application/json")])
        return [body]


def cleanup_and_exit(signum=None, frame=None, exit_code=0):
    stop_all()
    logger.info("Router detenido.")
    sys.exit(exit_code)


def main():
    import socket
    from wsgiref.simple_server import make_server, WSGIServer

    parser = argparse.ArgumentParser(description="llama.cpp Multi-Model Router")
    parser.add_argument("--models", nargs="*", help="Modelos a cargar (default: todos)")
    parser.add_argument("--port", type=int, default=ROUTER_PORT)
    parser.add_argument("--lock-file", default=str(Path.home() / ".lock" / "llama_router.lock"))
    args = parser.parse_args()

    lock_path = Path(args.lock_file)
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    if lock_path.exists():
        try:
            old_pid = int(lock_path.read_text().strip())
            os.kill(old_pid, 0)
            logger.error(f"Ya existe otra instancia del router (PID {old_pid}). Abortando.")
            sys.exit(1)
        except (ProcessLookupError, ValueError, FileNotFoundError):
            lock_path.unlink(missing_ok=True)

    lock_path.write_text(str(os.getpid()))

    signal.signal(signal.SIGINT, cleanup_and_exit)
    signal.signal(signal.SIGTERM, cleanup_and_exit)

    try:
        models_to_load = args.models if args.models else list(MODELS.keys())
        started = []
        for name in models_to_load:
            config = MODELS[name]
            if start_server(name, config):
                started.append(name)
                time.sleep(1)

        logger.info("Esperando a que los modelos estén listos...")
        ready_count = 0
        for name in started:
            config = MODELS[name]
            if wait_ready(name, config["port"]):
                ready_count += 1

        if ready_count == 0:
            logger.error("Ningún modelo listo después del timeout. Abortando.")
            cleanup_and_exit(exit_code=1)

        logger.info(
            f"Router en http://localhost:{args.port} ({ready_count}/{len(started)} modelos listos)"
        )
        logger.info(f"Modelos: {', '.join(started)}")

        class ReuseAddrWSGIServer(WSGIServer):
            allow_reuse_address = True

            def server_bind(self):
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                for attempt in range(10):
                    try:
                        super().server_bind()
                        return
                    except OSError:
                        time.sleep(0.5)
                super().server_bind()

        server = make_server("0.0.0.0", args.port, application, server_class=ReuseAddrWSGIServer)
        server.serve_forever()
    finally:
        lock_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
