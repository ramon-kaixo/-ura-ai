# Auditoría de Disco — 2026-08-17 (READ-ONLY)

**TASK-20260817-024 · Ejecutor: TERM · Modo auditoría (no se borró/movió nada)**

## Estado del disco

- Dispositivo: `/dev/nvme0n1p2` (ext4) — **963G usados / 777G libres / 56%**
- `sudo` no disponible sin contraseña (rootfs RO en `/run/sudo`): auditoría sin sudo.
  Directorios no legibles por ramon podrían ocultar consumo residual (est. <5%).

## Top 30 — mayores consumos (du -xhd1, verificado 17:09-17:20)

| # | Ruta | Tamaño | Nota |
|---|------|--------|------|
| 1 | `/home/ramon/models` | 273G | GGUF de desarrollo (code_review 112G, kimi-dev 100G, llama-cpp 63G) |
| 2 | `/home/ramon/URA/ollama-models-0326` | 189G | **Copia física** de los blobs de ollama (inodes distintos, verificado) |
| 3 | `/usr/share/ollama/.ollama/models` | 172G | Blobs reales de ollama |
| 4 | `/home/ramon/backups` | 61G | `pre_mitigacion/gx10_models_config_20260514_110659.tar.gz` = 61G |
| 5 | `/opt/modelos` | 47G | GGUF de producción (NO borrar según instrucción) |
| 6 | `/home/ramon/llama.cpp` | 41G | `out-00001-of-00001.gguf` 39G (artefacto de compilación/merge) |
| 7 | `/home/ramon/URA/archives` | 23G | 1077 bundles de tuneladora (`source-*.bundle`, 206M c/u) |
| 8 | `/swap.img` | 16G | Swap del sistema (intocable) |
| 9 | `/test.img` | 10G | **Archivo `data` en la raíz** (mar 18 08:40) — sospechoso de ser basura de pruebas |
| 10 | `/backups` | 6,8G | tars diarios de mayo (`ura_2026-05-*.tar.gz`) |
| 11 | `/home/ramon/URA/backups/assistant` | 5,5G | Snapshots assistant diarios (ago 02-10) |
| 12 | `/home/ramon/.local/share/opencode/opencode.db.bak-20260813` | 5,3G | Backup de la BD opencode |
| 13 | `/var/lib` | 4,5G | snapd 3,8G + apt 232M + kdump 225M |
| 14 | `/home/ramon/.cache/whisper` | 3,6G | `large-v3.pt` 2,9G (redescargable) |
| 15 | `/home/ramon/ura_backups_vault` | 2,3G | Vault tuneladora |
| 16 | `/opt/nvidia` | 2,0G | Drivers (intocable) |
| 17 | `/opt/ura` | 1,5G | Instalación URA |
| 18 | `/home/ramon/URA/ura_ia_1972` | 1,5G | Repo git (incluye 189G? no — ollama-models aparte) |
| 19 | `/var/log` | 1,2G | Rotación pendiente de revisar |
| 20 | `/home/ramon/.npm` | 1,2G | Cache npm |
| 21 | `/home/ramon/URA/backups_gx10` | 1,1G | Backups GX10 |
| 22 | `/home/ramon/.local/lib/python3.12` | 7,9G | site-packages (nvidia cu13 2,8G) |
| 23 | `/home/ramon/docker` | 943M | Contextos docker |
| 24 | `/tmp/pytest-of-ramon` | 759M | Videos de 4,3G ×5 en tests pytest (sobras) |
| 25 | `/zona_trabajo` | 604M | Copia de trabajo |
| 26 | `/home/ramon/.nv` | 794M | Cache NVIDIA |
| 27 | `/home/ramon/snap` | 793M | snap user |
| 28 | `/home/ramon/llama-autoparser` | 719M | Proyecto |
| 29 | `/home/ramon/.opencode` | 434M | Config/sesiones opencode |
| 30 | `/home/ramon/.ura` | 414M | Datos URA |

## Dónde está el consumo "no explicado"

La contabilidad ahora **cierra**: la suma de los niveles 1 coincide con los 963G usados
(antes no explicaba porque `/home/ramon/models`, `/home/ramon/URA` y `/usr/share/ollama`
no se auditaban juntos). No hay espacio perdido por snapshots (ext4, sin btrfs/zfs/lvm).
**El consumo real es duplicación de modelos LLM**, no pérdida de espacio:

### Duplicados físicos confirmados (inodes distintos)

| Grupo | Copias | Total | Recuperable |
|-------|--------|-------|-------------|
| Blobs ollama: `/usr/share/ollama/.ollama/models` vs `/home/ramon/URA/ollama-models-0326` | 2 | ~361G | ~172-189G (una de las dos) |
| Qwen2.5-Coder-32B-Q8: `/home/ramon/Qwen2.5-Coder-32B-Instruct-Q8_0.gguf` + `models/llama-cpp/qwen2.5-coder-q8_0.gguf` + `models/code_review/Qwen2.5-Coder-32B-Instruct-Q8_0.gguf` | 3×33G | ~99G | ~66G |
| qwen2.5-coder-32b Q4_K_M: `/opt/modelos/` ×2 + `models/llama-cpp/` + blob ollama | 4×19G | ~76G | ~57G (sin tocar /opt) |
| codestral-22b: `models/llama-cpp/` + blob | 2×12G | ~24G | ~12G |
| DeepSeek-Coder-V2-Lite: code_review Q8+Q4 + blob | 3 | ~37G | ~13G |
| Kimi-Dev-72B: Q8 77G + IQ4 29G (kimi-dev) | 2 variantes | 106G | decisión humana |

### Otros candidatos claros

| Ruta | Tamaño | Riesgo |
|------|--------|--------|
| `/home/ramon/backups/pre_mitigacion/gx10_models_config_20260514_110659.tar.gz` | 61G | Backup de mayo ya superado; mover a otro disco o borrar |
| `/test.img` (raíz, `data`, mar 2026) | 10G | BAJO — archivo de prueba huérfano |
| `llama.cpp/out-00001-of-00001.gguf` | 39G | MEDIO — artefacto de merge; verificar si es la salida final |
| `opencode.db.bak-20260813` | 5,3G | BAJO — backup de BD de hace 4 días |
| `URA/archives` (1077 bundles) | 23G | MEDIO — tuneladora; conservar últimos 10, borrar resto |
| `/backups/ura_2026-05-*.tar.gz` | 6,8G | BAJO — 3 meses de antigüedad |
| `URA/backups/assistant` (8 snapshots) | 5,5G | BAJO — conservar últimos 2 |
| `.cache/whisper/large-v3.pt` | 2,9G | BAJO — redescargable |
| `/tmp/pytest-of-ramon` (v.mp4 ×5) | 759M | BAJO — sobras de pytest |
| `*-partial` en blobs ollama | 134M | BAJO — descargas incompletas |

## Plan de limpieza priorizado (PROPUESTO — no ejecutado)

| # | Acción | Recupera | Riesgo | Autorización |
|---|--------|----------|--------|--------------|
| 1 | Eliminar `/test.img` (raíz) | 10G | BAJO | Ramón |
| 2 | Borrar tar pre_mitigacion (mayo) o mover a disco externo | 61G | BAJO | Ramón |
| 3 | Decidir copia única de blobs ollama (`/home/ramon/URA/ollama-models-0326` vs `/usr/share/ollama`); borrar la otra previa verificación de que ollama apunta a la superviviente | 172-189G | **ALTO** (verificar `OLLAMA_MODELS`) | Ramón |
| 4 | Consolidar Qwen2.5-Coder-32B-Q8 (3 copias → 1 en models/) | 66G | MEDIO | Ramón |
| 5 | Depurar `models/code_review` (conservar lo usado por router) | ~30G | MEDIO | Ramón |
| 6 | `llama.cpp/out-00001-of-00001.gguf`: confirmar uso y borrar si es intermedio | 39G | MEDIO | Ramón |
| 7 | Podar `URA/archives` a últimos 10 bundles | ~21G | MEDIO | Ramón |
| 8 | Borrar `opencode.db.bak-20260813` | 5,3G | BAJO | Ramón |
| 9 | `/backups` mayo + `backups/assistant` (>2 últimos) | ~10G | BAJO | Ramón |
| 10 | `whisper large-v3.pt` + `*-partial` + pytest tmp | ~4G | BAJO | Ramón |

**Recuperación total estimada: 380-420G** (sin tocar `/opt/modelos`, swap, drivers ni el repo).

**NO HACER**: borrar `/opt/modelos`, `/swap.img`, blobs de ollama activos sin verificar `OLLAMA_MODELS`,
ningún modelo mientras haya un trabajo activo, nada sin autorización explícita por ítem.

## Limitaciones de la auditoría

- Sin `sudo` (rootfs RO en `/run/sudo`): `/root`, partes de `/var/lib` no auditables por ramon.
- `md5sum` de comparación de GGUF de 33G no ejecutado (timeout); duplicados inferidos por nombre/tamaño/uso.
- No se comprobó qué modelos usa el Model Router actualmente (requiere consultar config del router).

## Verificación

- `verify_protocol.py`: OK.
- Solo se crearon este informe y la entrada en coordination.json (TASK-20260817-024).
- Ningún archivo fue borrado, movido ni modificado.
