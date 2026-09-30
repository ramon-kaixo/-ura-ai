---
description: "Revisor técnico URA — audita planes y código en solo lectura. Emite veredicto GO / GO CON CAMBIOS / NO-GO."
mode: subagent
model: ollama/qwen3.6:27b
permission:
  edit: deny
  bash:
    "git diff *": allow
    "git log *": allow
    "git status *": allow
    "cat *": allow
    "grep *": allow
    "*": deny
---
