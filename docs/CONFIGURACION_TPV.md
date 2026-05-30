# Configuracion del Conector TPV en URA

## 1. Editar archivo de endpoints

```bash
nano /opt/ura/config/tpv_endpoints.json
```

Estructura del archivo:

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

### Campos requeridos

| Campo | Descripcion | Ejemplo |
|-------|-------------|---------|
| `base_url` | URL base de la API de tu TPV | `https://api.tudominio.com/v1` |
| `api_key` | Clave de acceso (se lee del .env) | `${TPV_API_KEY}` |
| `endpoints` | Rutas para cada operacion | Ver tabla inferior |
| `timeout` | Segundos maximos de espera | `10` |

### Endpoints disponibles

| Endpoint | Metodo | Parametros | Uso en URA |
|----------|--------|------------|------------|
| `ventas_hoy` | GET | `fecha` (YYYY-MM-DD) | Informes, prediccion personal |
| `stock_producto` | GET | `producto` (nombre/SKU) | Regla 8 (alertas stock bajo) |
| `registrar_venta` | POST | JSON con datos venta | Registro automatizado |
| `clientes_hoy` | GET | Ninguno | Contador afluencia |

## 2. Añadir API key al entorno

```bash
nano /opt/ura/.env
```

Añadir o modificar:

```ini
TPV_API_KEY=tu_clave_api_real
TPV_BASE_URL=https://api.tudominio.com/v1
```

> **Nota:** Si `TPV_BASE_URL` esta definido en `.env`, sobrescribe el valor del JSON.

## 3. Probar la integracion

### Prueba rapida desde terminal

```bash
cd /opt/ura
python3 -c "from core.connectors.tpv_connector import TPVApiConnector; print(TPVApiConnector().ventas_hoy())"
```

**Respuesta esperada (JSON):**
```json
{"fecha": "2026-05-19", "total": 1250.50, "num_ventas": 42, "clientes": 38}
```

### Prueba de stock

```bash
python3 -c "from core.connectors.tpv_connector import TPVApiConnector; tpv=TPVApiConnector(); print(tpv.stock('cerveza'))"
```

**Respuesta esperada:**
```json
{"producto": "cerveza", "cantidad": 48, "umbral": 10, "bajo": false}
```

### Prueba de clientes

```bash
python3 -c "from core.connectors.tpv_connector import TPVApiConnector; tpv=TPVApiConnector(); print(tpv.clientes_hoy())"
```

## 4. Detener el mock TPV (si estaba activo)

```bash
# macOS
launchctl unload ~/Library/LaunchAgents/com.ura.mocktpv.plist

# Linux
sudo systemctl stop mock-tpv.service
sudo systemctl disable mock-tpv.service
```

## 5. Verificar que URA usa datos reales

### Logs en tiempo real

```bash
tail -f /tmp/ura_autonomia.log | grep -E "TPV|stock|ventas"
```

### Preguntas de voz que usan el TPV

| Comando | Fuente de datos |
|---------|-----------------|
| "URA, cuanto hemos vendido hoy?" | TPV `ventas_hoy()` |
| "URA, cuanto stock de cerveza queda?" | TPV `stock('cerveza')` |
| "URA, cuantos clientes han venido?" | TPV `clientes_hoy()` + Frigate |

## 6. Solucion de problemas

| Error | Causa | Solucion |
|-------|-------|----------|
| `Connection refused` | TPV no accesible | Verificar URL y firewall |
| `401 Unauthorized` | API key incorrecta | Revisar `.env` y `tpv_endpoints.json` |
| `404 Not Found` | Endpoint incorrecto | Verificar rutas en documentacion del TPV |
| `Timeout` | TPV lento o caido | Aumentar `timeout` en JSON |
| Mock responde en vez del real | Mock TPV activo | Detener mock (paso 4) |

## 7. TPs compatibles

URA funciona con cualquier TPV que exponga una API REST. Ejemplos:

| TPV | Tipo | Notas |
|-----|------|-------|
| Hosteltel | Cloud | API REST documentada |
| TPV Innova | Local | Requiere modulo API |
| Square | Cloud | API estandar |
| Lightspeed | Cloud | REST + OAuth |
| Custom | Cualquiera | Adaptar endpoints en JSON |

Si tu TPV no tiene API REST, se puede usar el conector ODBC o leer directamente la base de datos local (SQLite/MySQL).
