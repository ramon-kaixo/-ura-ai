# Reglas del Sistema

## REGLA 1: Nunca modificar código fuente directamente en GX10
Todo cambio debe pasar por git commit en Mac y git pull en GX10.

## REGLA 2: Siempre ejecutar tests antes de commit
El pipeline bloquea commits con tests rotos.

## REGLA 3: Nunca exponer Ollama a la red externa
Ollama debe escuchar solo en 127.0.0.1. El firewall bloquea el resto.
