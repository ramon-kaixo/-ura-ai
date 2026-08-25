#!/usr/bin/env bash
# audit_semanal.sh — Auditoría semanal de seguridad/infra URA (2026-08-25)
# Uso: bash scripts/pro/audit_semanal.sh  (NO programado en cron aún)
REPO="$HOME/URA/ura_ia_1972"
FECHA=$(date "+%Y-%m-%d %H:%M")
echo "=== AUDIT SEMANAL URA — $FECHA ==="

echo "--- 1. Secretos hardcodeados en scripts/ ---"
if [ -x "$REPO/scripts/pro/audit_secrets.py" ]; then
  python3 "$REPO/scripts/pro/audit_secrets.py" 2>&1 | tail -5 || true
else
  grep -rnE "(password|passwd|secret|token)[\"']?\s*[:=]\s*[\"'][^\"'$]{8,}" "$REPO/scripts/" --include="*.py" --include="*.sh" --exclude-dir=.git 2>/dev/null | grep -v "\${" | head -5 || echo "LIMPIO"
fi

echo "--- 2. IPs muertas conocidas ---"
SUJOS=$(grep -rn -E "10\.164\.1\.99|192\.168\.1\.135|100\.127\.206\.86" "$REPO" --exclude-dir=.git --exclude="*.backup.*" --exclude="audit_semanal.sh" 2>/dev/null | head -5)
[ -z "$SUJOS" ] && echo "LIMPIO" || echo "$SUJOS"

echo "--- 3. Proteccion chattr +i esperada ---"
for f in config/system_config.json deploy/lildax_config.json deploy/sync_to_asus.sh core/debate/committee_config.json; do
  FLAG=$(lsattr "$REPO/$f" 2>/dev/null | cut -d" " -f1)
  echo "$FLAG" | grep -q -- "-i-" && echo "OK   $f" || echo "FALTA+I $f"
done

echo "--- 4. Servicios ---"
for s in opencode ollama tailscaled; do
  printf "%-12s %s\n" "$s:" "$(systemctl is-active $s.service 2>/dev/null)"
done

echo "--- 5. Deriva unidades systemd (deploy/timers vs /etc) ---"
# Petición TASK-20260825-002: detectar corrupción tipo cleanup-auto
# (OnCalendar válido en repo, inválido desplegado) antes de que mute.
DERIVA=0
for f in "$REPO"/deploy/timers/*; do
  n=$(basename "$f")
  etc="/etc/systemd/system/$n"
  if [ -f "$etc" ]; then
    if ! cmp -s "$f" "$etc"; then
      echo "DRIFT: $n difiere repo<->/etc:"
      diff "$f" "$etc" 2>/dev/null | head -4
      DERIVA=1
    fi
  else
    echo "SOLO REPO (sin desplegar): $n"
  fi
done
[ "$DERIVA" -eq 0 ] && echo "OK: sin derivas en unidades versionadas"
N_ETC=$(ls /etc/systemd/system/ura-*.service /etc/systemd/system/ura-*.timer 2>/dev/null | wc -l | tr -d " ")
echo "(info) unidades ura-* instaladas en /etc: $N_ETC (flota no versionada en repo)"

echo "--- FIN ---"
