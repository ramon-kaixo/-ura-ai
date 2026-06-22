# URA Disaster Recovery Plan (DRP)

## 1. Escenarios y Procedimientos

### 1.1 Fallo total del disco NVMe
**Síntomas**: Sistema no arranca, I/O errors en dmesg, SMART errors.

**Recuperación**:
1. Arrancar desde USB de recuperación (preparado en `/opt/ura/boot/usb_recovery.img`)
2. Montar nuevo NVMe o SSD externo
3. Restaurar desde backup más reciente:
   ```bash
   # Si Mac está disponible:
   rsync -avz mac:/Users/ramonesnaola/URA/backups_gx10/ /home/ramon/URA/backups/
   # Si no:
   # Usar backup local (pérdida parcial)
   tar xzf /home/ramon/URA/backups/code/ura_*.tar.gz -C /home/ramon/URA/
   tar xzf /home/ramon/URA/backups/config/configs_*.tar.gz -C /
   ```
4. Reinstalar dependencias: `pip install -r requirements.txt`
5. Reconstruir Qdrant desde snapshots:
   ```bash
   docker cp qdrant_*.tar.gz ura-qdrant:/tmp/
   docker exec ura-qdrant tar xzf /tmp/qdrant_*.tar.gz -C /qdrant/
   ```
6. Verificar servicios: `./scripts/pro/health_check.sh`
7. Tiempo estimado: 2-4 horas

### 1.2 Corrupción de software/Qdrant
**Síntomas**: Qdrant no responde, errores de colección, búsquedas vacías.

**Recuperación**:
1. Detener Qdrant: `docker stop ura-qdrant`
2. Restaurar snapshot:
   ```bash
   SNAP=$(ls -t /home/ramon/URA/backups/qdrant/qdrant_*.tar.gz | head -1)
   docker run --rm -v qdrant_storage:/qdrant/storage -v $(dirname $SNAP):/backup alpine tar xzf /backup/$(basename $SNAP) -C /qdrant/storage/
   ```
3. Reiniciar Qdrant: `docker start ura-qdrant`
4. Verificar: `curl http://127.0.0.1:6333/collections`
5. Tiempo estimado: 15-30 min

### 1.3 Pérdida de conectividad de red
**Síntomas**: Servicios internos OK, acceso externo caído.

**Recuperación**:
1. Verificar interfaces: `ip a`
2. Verificar Tailscale: `tailscale status`
3. Ejecutar runbook de red: `python3 -c "from monitor.snc import check_service; check_service('network')"`
4. Si Tailscale caído: `sudo systemctl restart tailscaled`
5. Si ethernet caído: `sudo dhclient eth0`
6. Tiempo estimado: 5-15 min

### 1.4 Ataque de seguridad / compromiso
**Síntomas**: Actividad sospechosa, archivos modificados, procesos desconocidos.

**Recuperación**:
1. Aislar el sistema: `sudo ufw default deny incoming`
2. Rotar todas las claves: `./scripts/pro/rotate_secrets.sh`
3. Auditar acceso: `last -10`, `journalctl -u sshd --since "1 hour ago"`
4. Verificar integridad: `cd /home/ramon/URA/ura_ia_1972 && git status`
5. Restaurar archivos modificados: `git checkout -- .`
6. Notificar al equipo vía Telegram
7. Tiempo estimado: 1-2 horas

### 1.5 Fallo de Ollama/VRAM
**Síntomas**: Modelos no cargan, OOM, latencia extrema.

**Recuperación**:
1. El watchdog de VRAM debe actuar automáticamente (`gpu_recovery.sh`)
2. Si no: `sudo systemctl restart ollama`
3. Verificar VRAM: `nvidia-smi`
4. Reducir modelos cargados: `ollama stop <modelo>`
5. Tiempo estimado: 5-10 min

## 2. Matriz de Responsabilidades

| Rol | Persona | Contacto |
|-----|---------|----------|
| Administrador del sistema | — | Local |
| Recuperación de datos | — | vía Telegram |
| Seguridad | — | vía Telegram |

## 3. Frecuencia de Pruebas

| Prueba | Frecuencia | Última ejecución |
|--------|------------|------------------|
| Health check automático | Cada 5 min | Automático |
| Backup completo | Diario 03:00 | Automático |
| Restauración de backup | Trimestral | — |
| Fire drill (simulación de fallo) | Semestral | — |

## 4. Contactos de Emergencia

- **Canal de alertas**: Telegram (configurado en TELEGRAM_TOKEN)
- **Notificación automática**: SNC + Prometheus Alertmanager
