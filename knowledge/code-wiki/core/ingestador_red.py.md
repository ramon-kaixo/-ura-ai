# `core/ingestador_red.py`

- **Language:** python
- **Chunks:** 7

## Symbols

### function: `cargar_inventario`
- Line: 37

def cargar_inventario():

### function: `tailscale_ssh`
- Line: 46

def tailscale_ssh(hostname, comando, timeout):
Ejecuta un comando vía Tailscale SSH (sin password, auth criptográfica).

Returns:
    (exit_code, stdout, stderr)

### function: `distribuir_tarea`
- Line: 67

def distribuir_tarea(tarea, archivo):
Distribuye una tarea al dispositivo más adecuado según su perfil.

Lógica de asignación:
  - tarea en TAREAS_PESADAS → ASUS (gx10-64c3)
  - tarea en TAREAS_MEDIAS → Mac mini de Ramón (mac-mini-de-ramon)
  - tarea en TAREAS_LIGERAS → primer dispositivo online con el rol adecuado

### function: `estado_dispositivos`
- Line: 131

def estado_dispositivos():
Verifica estado de todos los dispositivos via ping + SSH.

### function: `main`
- Line: 162

def main():

## Module Overview

Ingestador de Red Global — Tailscale SSH + Distribución de Tareas.

📖 MANUAL DE USO RÁPIDO:
  python3 core/ingestador_red.py --status            # Estado de todos los dispositivos
  python3 core/ingestador_red.py --enviar <tarea> <dispositivo>  # Enviar tarea a un nodo

🔒 GARANTÍAS DE SEGURIDAD:
  - 0 IPs hardcodeadas. Solo nombres MagicDNS (gx10-64c3, mac-mini-de-ramon)
  - 0 passwords en texto plano. Autenticación via Tailscale SSH criptográfico
  - tailscale up --operator=ramon --ssh (ya configurado en el servicio SSH Guard)
  - Conexiones solo a dispositivos en la misma tailnet (100.*)
  - Timeout 30s para evitar bloqueos

Estrategia de distribución de tareas:
  - Tareas PESADAS (refactorizar, entrenar) → ASUS (121GB RAM, GPU Blackwell)
  - Tareas MEDIAS (comprimir, analizar) → Mac mini (16GB RAM)
  - Tareas LIGERAS (monitorear, reportar) → cualquier dispositivo online

## Imports

```
argparse
json
os
pathlib.Path
subprocess
sys
time
```
