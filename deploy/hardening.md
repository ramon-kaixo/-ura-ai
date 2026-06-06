# Hardening Guide — URA GX10

## D1: Blindar mejora-continua

El contenedor `ura-mejora-continua` monta el repo entero en RW. Cambio necesario:

```yaml
# Antes (riesgoso):
volumes:
  - /home/ramon/URA/ura_ia_1972:/workspace:rw

# Después (seguro):
volumes:
  - /home/ramon/URA/ura_ia_1972:/workspace:ro
  - /home/ramon/URA/workspace_rw:/workspace_rw:rw
```

**Ejecutar en GX10:**
```bash
mkdir -p /home/ramon/URA/workspace_rw/proposals
docker stop ura-mejora-continua
docker rm ura-mejora-continua
# Recrear con los binds corregidos
docker run -d --name ura-mejora-continua \
  --network sandbox-net \
  --read-only \
  -v /home/ramon/URA/ura_ia_1972:/workspace:ro \
  -v /home/ramon/URA/workspace_rw:/workspace_rw:rw \
  ura-mejora-continua:latest
```

**Resultado**: La IA solo puede escribir en `workspace_rw/proposals/`. Un validador humano o sandbox debe revisar antes de merge.

---

## D2: Redundancia de Red con Métricas

Configuración determinista de failover a nivel de kernel:

```bash
# Ejecutar en GX10 como root:
ip route replace 10.164.1.0/24 dev thunder0 metric 100   # Primaria (Thunderbolt)
ip route replace 10.164.1.0/24 dev tailscale0 metric 200  # Secundaria (VPN)
ip route replace 0.0.0.0/0 via 10.164.1.1 dev thunder0 metric 100

# Verificar:
ip route get 10.164.1.1   # Debe usar thunder0 (métrica 100)
ip route get 100.x.x.x     # Tailscale interna
```

**Persistencia tras reboot**: Añadir a `/etc/netplan/01-netcfg.yaml` o `/etc/network/interfaces`.

---

## D3: Quitar docker.sock del sandbox

El sandbox `ura-sandbox-mantenimiento` tiene acceso al socket Docker. Cambio:

```yaml
# En docker-compose.sandbox.yml, eliminar:
- /var/run/docker.sock:/var/run/docker.sock:ro

# Si necesita controlar Docker, usar API vía red interna:
# En vez de montar el socket, el contenedor llama a:
# curl -s --unix-socket /var/run/docker.sock http://localhost/containers/json
# → Cambiar por llamada HTTP al daemon Docker vía red interna.
```
