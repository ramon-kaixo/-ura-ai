# Estado de seguridad ACLs Tailscale — 2026-09-08

## Hallazgo (verificado por agente Build)
La policy activa en la consola Tailscale es la **DEFAULT abierta**:
- 1 sola regla: permite TODO el rango CGNAT (100.64.0.0/10) a TODOS los puertos de cualquier nodo.
- El `tag:worker` SÍ está aplicado a mac-mini-de-ramon (visible en status), pero **sin efecto** porque no hay reglas restrictivas.

## Impacto
- Cualquier nodo del tailnet puede acceder a TODOS los puertos de GX10 (9090, 9091, 8003, 3080, 2222, etc.) — no solo los permitidos.
- El aislamiento perimetral documentado en `tailscale-acls.json` NO está activo.

## Acción requerida (consola Tailscale — humano)
1. Abrir https://login.tailscale.com/admin/acls (cuenta barkaixo@gmail.com)
2. Reemplazar la policy por el contenido de:
   `scripts/pro/tailscale-policy-paste.json`
3. Guardar (Save)
4. Verificar: en la Mac ejecutar:
   `tailscale debug netmap | grep -A5 PacketFilterRules`
   Debe mostrar MÚLTIPLES reglas (no solo la default abierta)

## Archivos de referencia
- `scripts/pro/tailscale-policy-paste.json` — policy JSON puro lista para pegar
- `scripts/pro/tailscale-acls.json` — versión documentada con comentarios

## Verificación 2026-09-08 04:05 (segunda ronda)
- El tag:worker SÍ está aplicado a mac-mini-de-ramon (confirmado local y desde GX10).
- PERO la policy de ACLs sigue siendo la DEFAULT abierta (1 regla: *:0-65535).
- Los puertos NO permitidos (9090, 8003, 3080, 2222...) SIGUEN accesibles.
- Conclusión: se aplicó el tag pero NO se reemplazó la policy en la consola.
  En Tailscale, un tag sin reglas restrictivas NO limita nada (default = permitir todo entre nodos del tailnet).
