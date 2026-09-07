---
id: TASK-20260828-unificacion-agentes
fecha: 2026-08-28
solicitante: RAMON
descripcion: Auditoría de históricos de modificaciones + unificación de agentes OpenCode en todas las instancias + limpieza referencias nodo Windows legacy
objetivo: Que GX10 (desktop + web headless) y Mac (desktop + web headless TERM) tengan exactamente los mismos agentes, documentando qué cambió, cuándo y por qué, y eliminando las referencias al inexistente nodo ASUS Windows (caja0/POS).
instrucciones: PARTE 1: auditar historial git (opencode.json, .opencode/agents/, coordination.json, configs, .gitignore) y registrar motivos por commit. PARTE 2: listar agentes por instancia, comparar, definir conjunto canónico y sincronizar (.opencode/agents/ + configs globales/proyecto). PARTE 3: eliminar refs a caja0/ASUS-Windows y normalizar ASUS=GX10. Verificar todas las instancias.
restricciones: Gates: ruff (solo si Python tocado), python3 scripts/pro/verify_protocol.py, git status --short. No tocar tests/código prod sin justificación. Commit en rama ia/TASK-20260828-unificacion-agentes.
estado: DONE
canal: RAMON
agente_web: 
agente_terminal: TERM (ejecutor)
revisor: WEB (revisor)
reserva: [.opencode/agents,opencode.json,config/dispositivos.json,scripts/pro/maquinas.sh,scripts/pro/tailscale-acls.json,docs/architecture/REFERENCIA_GX10.md,AGENTS.md]
commit_base: 47b64276
contexto: URA usa 2 nodos OpenCode (GX10=ASUS=DGX Spark; Mac=Mini-de-RAMON). No existe Windows en URA; 'caja0' era ref a POS legacy.
cambios:
  - ".opencode/agents/build.md (nuevo) — agente build primary qwen3-coder:30b-mejorado all-tools"
  - ".opencode/agents/revisor-fondo.md (nuevo) — subagente solo-lectura (write/edit/bash deny, v1.8)"
  - ".opencode/agents/orchestrator.md — modelo ollama/qwen3.6:27b -> ollama/qwen3-coder:30b-mejorado"
  - "opencode.json (proyecto) — default_agent coder -> general; mcp codewiki retirado (quedó en globales)"
  - "~/.config/opencode/opencode.json (GX10 global) — coder all-tools; orchestrator write/edit false; default_agent general; añadido build"
  - "~/.config/opencode/opencode-web.json (GX10 web) — orchestrator webfetch/websearch false (alineación)"
  - "Mac global ~/.config/opencode/opencode.json — bloque agent canónico (general/coder/orchestrator/build), default_agent general, model -mejorado"
  - "Mac global ~/Library/Application Support/opencode/opencode.json — bloque agent canónico idéntico"
  - "Mac proyecto ~/URA/opencode.json — default_agent general"
  - "AGENTS.md — ura-telemetry-pos.ps1 descrito legacy (sin caja0)"
  - "scripts/pro/maquinas.sh — bloque caja0 eliminado"
  - "scripts/pro/tailscale-acls.json — regla tag:pos, tagOwners.pos y hosts pos eliminados"
  - "docs/architecture/REFERENCIA_GX10.md — flujo POS genérico, sin caja0/MagicDNS"
  - "scripts/pro/ura-telemetry-pos.ps1 — header normalizado a nodo externo legacy"
  - "INFORME_INVESTIGACION_OPENCODE_20260828.md — regenerado (secciones 4,5,10,11)"
  - "docs/udo/tasks/TASK-20260828-unificacion-agentes.md (este expediente)"
commits: []
analisis: Ver INFORME_INVESTIGACION_OPENCODE_20260828.md §1-7 y §11 (historial). Clave: (a) los agentes de proyecto viven en .opencode/agents/ (git -> idénticos por construcción); (b) las configs JSON globales divergían por nodo (coder sin task/webfetch/websearch en GX10 desktop; default_agent coder; build solo en web; Mac con dos configs globales en conflicto); (c) se unificó a conjunto canónico (general/coder/orchestrator/build primary + revisor/calidad-cobertura/revisor-fondo) con modelo ollama/qwen3-coder:30b-mejorado y orchestrator/revisor-fondo sin escritura; (d) verificado con opencode agent list v1.18.23 en GX10 y Mac (misma lista y mismas reglas); (e) nodo Windows no existe: caja0 = POS legacy; refs limpiadas, salvo config/dispositivos.json (archivo inmutable chattr +i -> requiere sudo) y artefactos históricos/auto-regenerados (attic, .nervioso).
validacion: opencode agent list idéntico (names+mods+reglas) en GX10 y Mac; JSONs validados (python json.load); agentes .md copiados al worktree Mac para paridad inmediata; configs globales ambas sesiones verificadas por ssh.
verificar: 1) [pendiente humano] sudo chattr -i config/dispositivos.json y eliminar entrada caja0. 2) [pendiente humano] sudo systemctl restart opencode.service (web GX10 carga opencode-web.json alineado). 3) reiniciar OpenCode.app Mac cuando convenga. 4) §10 recom. 4-6 (baseURL Tailscale, .opencode/project.json, checkpoint WAL).
requisitos: 
pendientes:
  - "sudo chattr -i config/dispositivos.json + borrar entrada caja0"
  - "sudo systemctl restart opencode.service (web GX10)"
  - "revisar ROLES_OPENCODE.md vs estado final"
resultado: Todas las instancias (GX10 desktop, GX10 web, Mac desktop, Mac web) convergen al conjunto canónico de agentes; referencias caja0/ASUS-Windows eliminadas de scripts/configs/documentación; INFORME actualizado con historial completo. Pendiente verificable remoto solo lo que requiere sudo/root.
resultado_web: 
resultado_terminal: 
revision: 
historial:
  - "2026-08-28T20:30 | PLANNED | creada por RAMON con partición en 3 partes"
  - "2026-08-28T20:40 | IN_PROGRESS | rama ia/TASK-20260828-unificacion-agentes creada (base 47b64276)"
  - "2026-08-28T20:50 | IN_PROGRESS | Parte 1: historial git (opencode.json 7 commits, agents 6 commits, coordination.json 10+, .gitignore, dispositivos.json)" 
  - "2026-08-28T21:00 | IN_PROGRESS | Parte 2: conjunto canónico definido; build.md + revisor-fondo.md creados; orchestrator.md modelo actualizado; configs GX10 (global+web) y Mac (2 globales+proyecto) alineadas"
  - "2026-08-28T21:05 | IN_PROGRESS | Verificación: opencode agent list idéntico en GX10 y Mac (11+builtins); reglas clave validadas (orchestrator/revisor-fondo deny)"
  - "2026-08-28T21:10 | IN_PROGRESS | Parte 3: caja0 limpiado en AGENTS.md, maquinas.sh, tailscale-acls.json, REFERENCIA_GX10.md, ura-telemetry-pos.ps1. BLOQUEADO config/dispositivos.json (chattr +i)"
  - "2026-08-28T21:15 | REVIEW | expediente + INFORME regenerado (secciones 4,5,10,11)"
  - "2026-08-28T21:20 | DONE | REVISION por WEB hecha; gates verdes (verify_protocol OK, git status revisado, sin Python tocado -> ruff no aplica). Pendientes documentados en verificar."