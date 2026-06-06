# OpenCode macOS — Diagnóstico y Solución del Ciclo de Vida

## 1. El Problema: Procesos Zombie + Archivos que se Regeneran

Cuando cierras OpenCode en macOS, la ventana desaparece pero **NO todos los procesos mueren**. Electron (versión 41.2.1) deja hijos huérfanos:

| Proceso | PID | RAM | Persiste al cerrar |
|---------|-----|-----|-------------------|
| Main (GUI) | 13289 | 267 MB | ❌ Muere |
| Renderer | 13854 | 680 MB | ✅ **QUEDA VIVO** |
| NodeService | 13717 | 379 MB | ✅ **QUEDA VIVO** |
| GPU | 13695 | 114 MB | ✅ **QUEDA VIVO** |
| Network | 13696 | 61 MB | ✅ **QUEDA VIVO** |
| Audio | 42413 | 45 MB | ✅ **QUEDA VIVO** |
| Crashpad | 13645 | 9 MB | ✅ **QUEDA VIVO** |

Estos procesos retienen **flock** (file locks) sobre:
- `~/Library/Application Support/ai.opencode.desktop/SingletonSocket`
- `~/Library/Application Support/ai.opencode.desktop/SingletonLock`
- `~/Library/Application Support/ai.opencode.desktop/SingletonCookie`

**El bucle infinito:** Borras `SingletonSocket` → el proceso zombie lo recrea → `rm -rf` falla porque el archivo está bloqueado por un proceso activo.

## 2. Arquitectura Real (vs. el mito de ToDesktop)

OpenCode NO usa ToDesktop. Es **Electron puro** con **Squirrel.framework** (GitHub) para actualizaciones:

```
OpenCode.app (356 MB)
├── Electron Framework.framework/  (versión 41.2.1)
│   └── chrome_crashpad_handler
├── Squirrel.framework/            (actualizaciones automáticas)
│   └── ShipIt                     (se registra en launchd en runtime)
├── OpenCode Helper.app/           (GPU, Network, Node, Audio)
├── OpenCode Helper (GPU).app/
├── OpenCode Helper (Plugin).app/
├── OpenCode Helper (Renderer).app/
└── Resources/app.asar             (93 MB — la app en sí)
```

## 3. Mapa Completo de Archivos (22 rutas)

### App Bundle
```
/Applications/OpenCode.app/                         356 MB
```

### Datos de Usuario (~/Library/Application Support)
```
~/Library/Application Support/ai.opencode.desktop/                 123 MB
├── SingletonSocket → /var/folders/.../SingletonSocket    ← SE REGENERA
├── SingletonLock   → Mini-de-RAMON-13289                 ← LOCK ACTIVO
├── SingletonCookie → 14514413551147951916                ← LOCK HTTP
├── opencode/                                             ← locks de sesión
│   └── locks/
├── opencode.global.dat              29 KB                ← estado persistente
├── opencode.settings                26 B                 ← flag migración
├── opencode.workspace.*.dat         281-424 B            ← estado workspace
├── Cache/                           80 KB                ← Chromium cache
├── Code Cache/                                            ← JS/WASM cache
├── GPUCache/                                              ← shaders GPU
├── logs/ (2 sesiones activas)                             ← logs sesión
├── Crashpad/                                              ← crash reports
├── blob_storage/                                          ← Chrome blob storage
├── Local Storage/  Session Storage/                       ← storage web
├── DIPS  DIPS-wal  Trust Tokens                           ← privacidad
└── Cookies  Cookies-journal                               ← cookies HTTP
```

### Caches
```
~/Library/Caches/ai.opencode.desktop/                    80 KB
~/Library/Caches/ai.opencode.desktop.ShipIt/             8 KB
~/Library/Caches/@opencode-aidesktop-updater/            255 MB
└── pending/opencode-desktop-mac-arm64.zip               132 MB (update sin instalar)
```

### Configuración
```
~/.config/opencode/                                      8 KB
├── opencode.jsonc                                       50 B  (config global)
└── .gitignore                                           63 B
```

### Preferencias y Estado
```
~/Library/Preferences/ai.opencode.desktop.plist          977 B
~/Library/Preferences/ByHost/ai.opencode.desktop.ShipIt.*.plist
~/Library/HTTPStorages/ai.opencode.desktop/              112 KB
~/Library/Application Support/com.apple.sharedfilelist/.../ai.opencode.desktop.sfl4
```

### Proyectos (directorios .opencode/ que quedan huérfanos al desinstalar)
```
<proyecto>/.opencode/           ← creado automáticamente al usar OpenCode
├── agent/<name>.md
├── skill/<name>/SKILL.md
├── plugin/*.ts
└── opencode.json
```

## 4. Solución: Script de Desinstalación Completa

```bash
bash deploy/uninstall_opencode.sh
```

Lo que hace en orden:

| Fase | Acción | Por qué este orden |
|------|--------|-------------------|
| 1 | `pkill -9 -f "OpenCode Helper"` | Mata procesos zombie que retienen locks |
| 2 | `launchctl remove ai.opencode.desktop.ShipIt` | Elimina el updater de launchd |
| 3 | `rm -f SingletonSocket` | Rompe el ciclo de regeneración |
| 4 | `rm -rf ai.opencode.desktop/ .config/opencode/ Caches/` | Limpia datos, caches y config |
| 5 | `rm -rf /Applications/OpenCode.app` | Elimina la app |
| 6 | `find .opencode -type d` | Busca y elimina `.opencode/` en proyectos |

## 5. Recomendaciones para OpenCode (upstream)

Para que el equipo de OpenCode arregle esto de raíz:

1. **Signal handling**: En el `main process` de Electron, capturar `SIGTERM`/`SIGINT`/`window.close()` y propagar kill a TODOS los child processes (GPU, Network, Node, Renderer, Audio) antes de salir.

2. **app.on('will-quit')**: Implementar `app.on('will-quit', () => { ... })` que:
   - Libere todos los `flock` en archivos Singleton
   - Cierre explícitamente SingletonSocket
   - Elimine el lock file al salir

3. **ShipIt cleanup**: El installer de Squirrel debería registrar un launchd plist CON un `LaunchEvents` que se ejecute al desinstalar para limpiar los archivos huérfanos.

4. **No dejar lock files**: SingletonLock y SingletonCookie no deberían persistir después de cerrar la app. Son symlinks que quedan apuntando a nada.

5. **Comando cleanup**: Añadir `opencode cleanup` que:
   - Elimine `.opencode/` del proyecto actual
   - Elimine `opencode.json` si existe
   - Pregunte si quiere borrar la configuración global

## 6. Verificación de Desinstalación Limpia

Después de ejecutar el script, verificar:

```bash
# No deben quedar procesos
ps aux | grep -i opencode | grep -v grep   # → 0 resultados

# No deben quedar archivos
ls -la ~/Library/Application\ Support/ai.opencode.desktop/   # → "No such file"
ls -la ~/.config/opencode/                                   # → "No such file"
ls /Applications/OpenCode.app                                 # → "No such file"

# No deben quedar servicios launchd
launchctl list | grep -i opencode                             # → 0 resultados
```

## 7. Capturas de Pantalla

### Procesos activos de OpenCode (7 procesos, ~1.5 GB RAM)
```
PID   PROC                       RAM    CPU
13289 OpenCode (Main)            267 MB  3.8%
13854 OpenCode Helper (Renderer) 680 MB 44.8% ← El más pesado
13717 OpenCode Helper (Node)     379 MB  1.9%
13695 OpenCode Helper (GPU)      114 MB 27.0%
13696 OpenCode Helper (Network)   61 MB  1.9%
42413 OpenCode Helper (Audio)     45 MB  0.0%
13645 chrome_crashpad_handler      9 MB  0.0%
```

### SingletonSocket – el archivo que se regenera solo
```
SingletonCookie -> 14514413551147951916    ← lock HTTP
SingletonLock   -> Mini-de-RAMON-13289    ← lock de instancia única
SingletonSocket -> /var/folders/.../Socket ← SE REGENERA AL BORRARLO
```

### Espacio total ocupado: ~735 MB
| Ubicación | Tamaño |
|-----------|--------|
| /Applications/OpenCode.app | 356 MB |
| ~/Library/Application Support/ai.opencode.desktop/ | 123 MB |
| ~/Library/Caches/@opencode-aidesktop-updater/ | 255 MB |
| Otras caches y configs | ~5 MB |
