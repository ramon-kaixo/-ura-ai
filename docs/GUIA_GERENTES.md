# Guia Rapida del Sistema URA para Gerentes

## Comandos de voz (decir a la Mac/GX10 con microfono)

- **"URA, repara la red"** → restaura conectividad automaticamente.
- **"URA, monta el disco de backup"** → monta unidad externa.
- **"URA, lanza buzo buzo_red"** → ejecuta analisis de red.
- **"URA, clic en Exportar"** → simula clic en boton por vision (fallback).
- **"URA, escribe hola mundo"** → teclea texto.
- **"URA, informe de consumo de este mes"** → muestra consumos de empleados en barra.
- **"URA, analiza la limpieza de hoy"** → eficiencia del personal de limpieza.
- **"URA, reporta comportamientos no catalogados"** → nuevas actitudes detectadas.
- **"URA, como exporto las ventas?"** → consulta el manual indexado y ejecuta la accion.
- **"URA, +1 punto"** (o "-1 punto") → da recompensa o castigo a la ultima accion (RLHF local).
- **"URA, explora [nombre app]"** → explora la interfaz de una aplicacion y construye mapa de navegacion.
- **"URA, como esta el clima?"** → consulta prediccion meteorologica local.
- **"URA, planifica [objetivo]"** → descompone un objetivo complejo en tareas atomicas.

## Informes automaticos

Cada mes encuentras en `/opt/ura/informes/`:

- `informe_eficiencia_empleados.csv` – tiempos de atencion, pausas, productividad.
- `informe_consumo_barra.csv` – bebidas tomadas por empleado.
- `informe_rotaciones.csv` – platos rotos por persona.
- `informe_almacen.csv` – accesos de repartidores, intentos de robo.
- `informe_mejora_continua.pdf` – sugerencias del sistema para optimizar turnos, personal, etc.

## Que hacer si el sistema escala una decision

- Recibes una notificacion por Telegram o en pantalla.
- Ejemplo: *"Invitacion no autorizada para cliente X. Aprobar?"*
- Responde por voz: *"Si, aprobar"* o *"No, denegar"*.
- Si no respondes en 5 minutos, el sistema deniega la accion por defecto.

## Mantenimiento minimo

- Cada mes, revisa los informes.
- Si una regla no se ajusta a tu politica, edita `/opt/ura/config/legal_rules.json` (cambia numeros como `importe_maximo_euros`).
- Para añadir un manual de una nueva aplicacion, coloca un archivo `.txt`, `.pdf`, `.jpg` o `.mp4` en `/opt/ura/docs/manuales/` y ejecuta `bash /opt/ura/scripts/indexar_manuales_multimodal.sh`.
- El sistema se actualiza solo (`auto_update.sh` diario). Si algo falla, revierte automaticamente.
- Cada 30 minutos URA verifica automaticamente el estado del GX10 y lo repara si es necesario.

## Contactos de emergencia

- Si el sistema se bloquea por completo, reinicia el equipo. Si persiste, restaura desde la ultima copia en `/opt/ura/backups/`.
- Para asistencia tecnica, contacta al administrador del sistema (persona que instalo URA).

## Arquitectura resumida

- **Mac Mini** = Cerebro principal (Laia, autonomia, orquestador, Frigate).
- **GX10 (ASUS X10)** = Motor IA (Ollama, modelos LLM, buzos, n8n).
- **Hetzner VPS** = SearXNG (busqueda web), exit node Tailscale.
- **25 camaras Dahua** → Frigate (deteccion de personas, objetos, eventos).
- **TPV** → API REST (ventas, stock, clientes). Si no hay API real, usa mock local.
