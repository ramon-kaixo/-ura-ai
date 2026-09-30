# OpenCode — Extensiones: nativo vs comunidad

Referencia para retomar. Documento vivo.

## Tipos de extensión

| Pieza | Qué es | Nativo / Comunidad |
|---|---|---|
| **Agents** | Perfiles con permisos y modelos propios | Nativo |
| **Skills** | Instrucciones que se cargan bajo demanda (`SKILL.md`) | Nativo |
| **Commands** | Atajos tipo `/audit`, `/verify` | Nativo |
| **Tools** | Acciones que el agente ejecuta (bash, edit, read...) | Nativo |
| **Custom tools** | Tools que define el usuario | Nativo el sistema, tú el contenido |
| **MCP servers** | Servidores externos que exponen tools | Nativo el sistema, comunidad los servers |
| **Plugins** | Módulos JS/TS con hooks | Nativo el sistema, comunidad los plugins |

## Lo que URA tiene montado hoy

- **Agentes**: 7 archivos en `.opencode/agents/*.md` reducidos a frontmatter (description, mode, model, permission). Sin prompt propio: OpenCode 1.18.21+ no los inyecta.
- **Commands**: 10 archivos en `.opencode/commands/*.md` (`/audit`, `/verify`, `/check`, `/test`, `/cobertura`, `/orchestrate`, `/status`, `/sync`, `/parallel-status`, `/alarma`).
- **AGENTS.md**: 85 líneas, con la lista de "maletas" (subagentes) y la regla de verificación antes de cerrar.
- **memory.md**: manual en `.opencode/memory.md`. Sin automatización.
- **Plugins**: ninguno. Los intentos (`@fleetingecho`, `working-memory`, `auto-verify`) fallaron o se descartaron.
- **Skills**: ninguna montada.
- **Custom tools**: definidas en config (`memory:read`, `memory:write`, `memory:append`, `memory:search`, `memory:compact`, `memory:export`, `memory:import`, `memory:stats`, `memory:list`, `memory:cleanup`).

## Cosas que se están intentando hacer "de otra forma"

| Objetivo | Cómo se intentó | Alternativa nativa/comunidad |
|---|---|---|
| Memoria persistente automática | Plugins de handoff/memory (rotos) | `@alkdev/open-memory` (npm) o `memory.md` manual |
| Verificación tras cada tarea | Plugin auto-verify (no carga) | Regla en AGENTS.md o skill |
| Contexto entre sesiones | `memory.md` a mano | Skill que lo actualice + `/verify` |

## Piezas sin explotar que ya están disponibles

- **`@explore`** — subagente solo-lectura, rápido, para buscar en el código.
- **`lsp`** (experimental) — inteligencia de código real: definiciones, referencias, jerarquía.
- **Skills** — instrucciones bajo demanda, sin ocupar contexto siempre.
- **Custom tools** — ya definidas para memoria, poco usadas.

## Plugins de comunidad candidatos

| Plugin | Qué hace |
|---|---|
| `opencode-notificator` | Aviso escritorio al terminar/fallar/pedir permiso |
| `opencode-pty` | Procesos en background |
| `oh-my-opencode` | Agentes de fondo, LSP/AST, preconstruidos |

## Prioridad propuesta (a validar)

1. LSP nativo.
2. Skills para verificación y carga de memoria.
3. Custom tools ya existentes.
4. Opcional: `oh-my-opencode`.
