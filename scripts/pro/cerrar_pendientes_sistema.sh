#!/usr/bin/env bash
# cerrar_pendientes_sistema.sh — Cierra pendientes del sistema detectados en revisión 2026-08-11.
# IDEMPOTENTE. Hace backup de todo lo que modifica. Requiere sudo (Ramón).
# Uso: sudo bash scripts/pro/cerrar_pendientes_sistema.sh
set -uo pipefail

FECHA=$(date +%Y%m%d_%H%M%S)
REPO=/home/ramon/URA/ura_ia_1972
BK=/home/ramon/URA/backups/pendientes_sistema_$FECHA
mkdir -p "$BK"
echo "== Backups en: $BK"

# ---------- 1. model-router.service: unit correcta + drop-ins rotos retirados ----------
echo "== [1/5] model-router.service"
if [ -f /etc/systemd/system/model-router.service ]; then
  cp -a /etc/systemd/system/model-router.service "$BK/" 2>/dev/null
fi
mkdir -p /etc/systemd/system/model-router.service.d
for dropin in execstart-fix.conf workingdir-fix.conf workingdir.conf; do
  if [ -f "/etc/systemd/system/model-router.service.d/$dropin" ]; then
    cp -a "/etc/systemd/system/model-router.service.d/$dropin" "$BK/dropin-$dropin"
    rm -f "/etc/systemd/system/model-router.service.d/$dropin"
    echo "  retirado drop-in roto: $dropin (backup OK)"
  fi
done
cp -a "$REPO/deploy/model-router.service" /etc/systemd/system/model-router.service
echo "  unit instalada desde deploy/model-router.service"

# ---------- 2. Token OPENCLAW_GATEWAY_TOKEN (solo si falta) ----------
echo "== [2/5] token OPENCLAW_GATEWAY_TOKEN"
if ! grep -q "OPENCLAW_GATEWAY_TOKEN" /etc/ura/secrets.env 2>/dev/null; then
  cp -a /etc/ura/secrets.env "$BK/secrets.env"
  TOKEN=$(openssl rand -hex 24)
  printf '\nOPENCLAW_GATEWAY_TOKEN=%s\n' "$TOKEN" >> /etc/ura/secrets.env
  chmod 600 /etc/ura/secrets.env
  echo "  token generado y anadido a /etc/ura/secrets.env (backup OK)"
else
  echo "  token ya presente; sin cambios"
fi

# ---------- 3. Retirar ura-capturador (unit huerfana, app/ retirado en F3) ----------
echo "== [3/5] ura-capturador"
systemctl stop ura-capturador.service 2>/dev/null && echo "  servicio detenido"
systemctl disable ura-capturador.service 2>/dev/null && echo "  disabled"
if [ -f /etc/systemd/system/ura-capturador.service ]; then
  cp -a /etc/systemd/system/ura-capturador.service "$BK/"
  rm -f /etc/systemd/system/ura-capturador.service
  echo "  unit retirada (backup OK)"
fi

# ---------- 4. Retirar ura-historiador (unit huerfana, script inexistente) ----------
echo "== [4/5] ura-historiador"
systemctl stop ura-historiador.service 2>/dev/null && echo "  servicio detenido"
if [ -f /etc/systemd/system/ura-historiador.service ]; then
  cp -a /etc/systemd/system/ura-historiador.service "$BK/"
  rm -f /etc/systemd/system/ura-historiador.service
  echo "  unit retirada (backup OK)"
fi

# ---------- 5. Wrapper OpenClaw retirado + reload + arranque router ----------
echo "== [5/5] wrapper + daemon-reload + router"
if [ -e /usr/local/bin/opencode ]; then
  cp -a /usr/local/bin/opencode "$BK/opencode-wrapper" 2>/dev/null
  rm -f /usr/local/bin/opencode
  echo "  /usr/local/bin/opencode eliminado (backup OK)"
else
  echo "  /usr/local/bin/opencode no existe; sin cambios"
fi

systemctl daemon-reload
systemctl enable model-router.service 2>/dev/null
systemctl restart model-router.service

echo
echo "== VERIFICACION =="
sleep 6
systemctl is-active model-router.service
ss -tlnp 2>/dev/null | grep 11435 && echo "  puerto 11435 ESCUCHANDO" || echo "  ERROR: 11435 no escucha"
for s in ura-capturador.service ura-historiador.service; do
  systemctl is-active "$s" 2>/dev/null || true
done
systemctl is-enabled ura-capturador.service 2>/dev/null || true
systemctl is-enabled ura-historiador.service 2>/dev/null || true
echo "== FIN (backups en $BK) =="
