# P1: ura-hetzner-tunnel — SSH Key + Config

**Fecha:** 2026-07-29
**Ejecutó:** OpenCode
**Duración:** ~15 min

## Diagnóstico

### Causa raíz
El servicio conectaba `root@178.105.81.83` (puerto 22, key por defecto)
pero la clave pública `id_rsa.pub` no está en `authorized_keys` del servidor.

### Hallazgos

| Aspecto | Antes | Después |
|---------|-------|---------|
| Puerto | 22 (por defecto) | 22 (sin cambios) |
| IdentityFile | ninguna (default probe) | `/home/ramon/.ssh/id_rsa` |
| ssh_config Host | `hetzner` con puerto 2222 | No usado (puerto 22 real) |
| Conectividad puerto 22 | ✅ Alcanzable | ✅ Alcanzable |
| Conectividad puerto 2222 | ❌ Connection refused | ❌ Connection refused |

### Corrección aplicada
Drop-in `/etc/systemd/system/ura-hetzner-tunnel.service.d/ssh-port-key.conf`:
```ini
[Service]
ExecStart=
ExecStart=/usr/bin/ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=30 \
    -o ServerAliveCountMax=3 -o ExitOnForwardFailure=yes -N \
    -L 8888:127.0.0.1:8888 \
    -L 3000:127.0.0.1:3000 \
    -D 1080 \
    -i /home/ramon/.ssh/id_rsa \
    root@178.105.81.83
```

## Acción manual requerida

Ejecutar el siguiente comando para copiar la clave pública al servidor Hetzner:

```bash
ssh-copy-id -i ~/.ssh/id_rsa.pub root@178.105.81.83
```

Luego:
```bash
sudo systemctl daemon-reload
sudo systemctl start ura-hetzner-tunnel
```

El servicio usa port 22 (SSH default). La key `id_rsa` ya está configurada en el unit file.

## Estado
- Drop-in creado: ✅
- Servicio detenido (evitar restart loop hasta que se copie la key): ✅
- Acción manual documentada: ✅
- Servicio activo: ❌ (pendiente ssh-copy-id)
