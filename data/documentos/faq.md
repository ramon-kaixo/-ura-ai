# FAQ URA

## ¿Cómo funciona el router?
El router clasifica el mensaje del usuario por palabras clave y selecciona el modelo más adecuado entre los disponibles en Ollama.

## ¿Qué hace el mantenimiento?
Limpia Docker, cache de pip, logs antiguos y archivos temporales. Se ejecuta en GX10.

## ¿Cómo sé si GX10 está vivo?
Usa `ura.py status` o `make doctor`. El SNC monitorea continuamente.
