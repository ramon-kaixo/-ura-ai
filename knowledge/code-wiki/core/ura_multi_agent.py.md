# `core/ura_multi_agent.py`

- **Language:** python
- **Chunks:** 9

## Symbols

### class: `Telemetria`
- Line: 56

class Telemetria:
Sistema de telemetría en tiempo real.
Methods: hardware, red, llm_stats, f821_count, reporte_completo

### class: `Conciencia`
- Line: 160

class Conciencia:
Memoria unificada del sistema. Archivo: .nervioso/conciencia.json.
Methods: leer, _nuevo, escribir, actualizar_proceso, registrar_error, nivel_error

### class: `AgenteOrquestador`
- Line: 235

class AgenteOrquestador:
Decide qué acción tomar según el estado del sistema. Modelo: Qwen 14B.
Methods: decidir, _contar_pendientes

### class: `AgenteEjecutor`
- Line: 283

class AgenteEjecutor:
Refactoriza funciones grandes. Modelo: DeepSeek 6.7B.
Methods: ejecutar

### class: `AgenteReparador`
- Line: 346

class AgenteReparador:
Repara errores en 3 niveles: determinista → LLM rápido → LLM potente.
Methods: reparar, _nivel_1, _nivel_2, _nivel_3

### class: `SelfHealingLoop`
- Line: 501

class SelfHealingLoop:
Bucle completo: DETECTAR → AISLAR → REPARAR → VALIDAR → ACTUALIZAR.
Methods: __init__, ejecutar

### function: `main`
- Line: 603

def main():

## Module Overview

URA Multi-Agent System — Boilerplate de Arquitectura Autónoma.

📖 MANUAL DE USO RÁPIDO:
  python3 core/ura_multi_agent.py                     # Iniciar bucle principal
  python3 core/ura_multi_agent.py --modo orquestar    # Solo orquestar (decidir)
  python3 core/ura_multi_agent.py --modo reparar      # Solo reparar errores
  python3 core/ura_multi_agent.py --modo ciclo        # Ciclo completo (detectar→reparar→validar)

🔒 ARQUITECTURA:
  3 Agentes:
    ORQUESTADOR (Qwen 14B): Decide qué hacer según estado del sistema
    EJECUTOR (DeepSeek 6.7B): Refactoriza funciones grandes
    REPARADOR (auto_reglas + LLM): Repara errores en 3 niveles

  Bucle de auto-arreglo:
    DETECTAR → AISLAR → REPARAR (3 niveles) → VALIDAR → ACTUALIZAR

  Estado compartido: .nervioso/conciencia.json
  Telemetría: RAM, CPU, tokens, F821, modelos disponibles

## Imports

```
argparse
ast
datetime.datetime
json
os
pathlib.Path
psutil
shutil
subprocess
sys
threading
time
urllib.request
```
