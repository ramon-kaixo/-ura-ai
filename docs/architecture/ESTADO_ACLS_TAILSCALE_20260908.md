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
