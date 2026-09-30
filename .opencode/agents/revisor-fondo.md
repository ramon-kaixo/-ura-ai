---
description: "Revisor de modo fondo — solo lectura, NO escribe ni edita (protección técnica v1.8). Actúa en modo fondo automático."
mode: subagent
model: ollama/qwen3.6:27b
permission:
  read: allow
  edit: deny
  write: deny
  bash: { "git status": "allow", "git diff *": "allow", "git log *": "allow", "cat *": "allow", "curl *": "allow", "*": "deny" }
---
