---
description: "Tester URA — verifica que los tests son reales (RED→GREEN), no se debilitaron, y validan comportamiento real con cobertura ≥80% por módulo."
mode: subagent
model: ollama/qwen3.6:27b
permission:
  edit: deny
  write: deny
  bash:
    "python3 -m pytest *": allow
    "python3 -m pytest * --coverage*": allow
    "python3 -m pytest * -v*": allow
    "python3 -m pytest * -k*": allow
    "coverage run*": allow
    "coverage report*": allow
    "git diff *": allow
    "git log *": allow
    "git status *": allow
    "cat *": allow
    "grep *": allow
    "head *": allow
    "tail *": allow
    "wc *": allow
    "*": deny
---
