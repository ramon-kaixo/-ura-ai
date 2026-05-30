# Configuracion de Camaras y TPV — Guia Rapida

## 1. Camaras Dahua en Frigate

### 1.1 Editar config frigate
```bash
nano /opt/ura/config/frigate.yml
```

### 1.2 Patrón go2rtc (recomendado para 25 camaras)
Cada camara tiene 2 streams:
- `subtype=0` → Main (4K, para grabar)
- `subtype=1` → Sub (480p, para deteccion)

URL Dahua tipica:
```
rtsp://usuario:pass@IP:554/cam/realmonitor?channel=1&subtype=0
```

go2rtc retransmite localmente para que Frigate no abra 50 conexiones RTSP:
```yaml
go2rtc:
  streams:
    barra1_main: rtsp://user:pass@192.168.1.101:554/cam/realmonitor?channel=1&subtype=0
    barra1_sub:  rtsp://user:pass@192.168.1.101:554/cam/realmonitor?channel=1&subtype=1

cameras:
  barra1:
    ffmpeg:
      inputs:
        - path: rtsp://127.0.0.1:8554/barra1_sub   # deteccion (baja carga)
          roles: [detect]
        - path: rtsp://127.0.0.1:8554/barra1_main  # grabacion (4K)
          roles: [record]
```

### 1.3 Copiar y reiniciar Frigate
```bash
cp /opt/ura/config/frigate.yml /opt/frigate/config/config.yml
docker restart frigate
```

### 1.4 Verificar
```bash
# Web UI
http://localhost:5000

# API stats
curl http://localhost:5000/api/stats | jq '.cameras'

# Logs si algo falla
docker logs frigate --tail 50
```

---

## 2. TPV Real (sustituir mock)

### 2.1 Editar endpoints
```bash
nano /opt/ura/config/tpv_endpoints.json
```
Cambiar:
```json
{
  "base_url": "https://api.tudominio.com/v1",
  "api_key": "${TPV_API_KEY}",
  "endpoints": {
    "ventas_hoy": "/ventas?fecha={fecha}",
    "stock_producto": "/stock/{producto}",
    "registrar_venta": "/ventas",
    "clientes_hoy": "/clientes/activos"
  },
  "timeout": 10
}
```

### 2.2 Añadir API key al .env
```bash
nano /opt/ura/.env
```
```ini
TPV_API_KEY=tu_clave_api_real
TPV_BASE_URL=https://api.tudominio.com/v1
```

### 2.3 Probar conexion
```bash
cd /opt/ura
python3 -c "
from core.connectors.tpv_connector import TPVApiConnector
tpv = TPVApiConnector()
print(tpv.ventas_hoy())
"
```

### 2.4 Detener mock TPV
```bash
# macOS
launchctl unload ~/Library/LaunchAgents/com.ura.mocktpv.plist

# Linux
sudo systemctl stop mock-tpv.service
```

---

## 3. Verificar flujo completo

```bash
# Logs en tiempo real
tail -f /tmp/ura_autonomia.log | grep -E "TPV|Frigate"

# Preguntar a Laia
python3 -c "
from agents.laia_agent import LaiaAgent
LaiaAgent().process_command('URA, cuantos clientes han entrado hoy?')
LaiaAgent().process_command('URA, cual es el stock de cerveza?')
"
```
