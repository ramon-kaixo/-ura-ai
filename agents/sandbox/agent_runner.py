#!/usr/bin/env python3
"""agent_runner.py — Punto de entrada para agentes sandbox.

Cada agente recibe:
  --categoria : legal|diseno|programacion|hosteleria
  --input     : ruta al archivo .nervioso/ a procesar (solo lectura)
  --output    : ruta donde escribir resultados

El agente NO tiene red. NO puede escribir fuera de --output.
"""
import argparse
import json
import sys
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--categoria", required=True)
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(json.dumps({"error": "input no encontrado", "path": str(input_path)}))
        sys.exit(1)

    content = input_path.read_text(encoding="utf-8", errors="replace")[:50000]

    # Cargar el módulo de agente específico
    try:
        module = __import__(f"agent_{args.categoria}", fromlist=["process"])
        result = module.process(content, {"categoria": args.categoria})
    except Exception as e:
        result = {"error": str(e), "categoria": args.categoria}

    # Escribir resultado
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"status": "ok", "categoria": args.categoria}))

if __name__ == "__main__":
    main()
