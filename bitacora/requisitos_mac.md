# Requisitos para restablecer Mac Mini

## Estado actual
- `mac-mini-de-ramon` (100.123.81.101): Tailscale activo
- SSH: No accesible desde GX10

## Lo que funciona
- rsync Mac→ASUS (sync_to_asus.sh) desde Mac
- Tailscale conexión directa

## Pendiente
1. Copiar SSH key pública de GX10 al Mac
2. Clonar/actualizar repo
3. Ejecutar `deploy/install_opencode_mac.sh`
4. Desplegar `ura-motor` via `deploy_mac.sh --watch`
