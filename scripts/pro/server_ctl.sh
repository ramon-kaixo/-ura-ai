#!/bin/bash
# Control del metrics_server.py de URA

PROJECT_ROOT=$(cd "$(dirname "$0")/../.." && pwd)
PYTHON="$PROJECT_ROOT/.venv/bin/python3"
[ -x "$PYTHON" ] || PYTHON="python3"
PIDFILE="/tmp/ura_metrics_server.pid"

case "$1" in
  start)
    if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
      echo "Metrics server ya corriendo (PID $(cat "$PIDFILE"))"
      exit 0
    fi
    nohup "$PYTHON" "$PROJECT_ROOT/scripts/pro/metrics_server.py" > /tmp/ura_metrics.log 2>&1 &
    echo $! > "$PIDFILE"
    echo "Metrics server iniciado en http://localhost:9091 (PID $!)"
    ;;
  stop)
    if [ -f "$PIDFILE" ]; then
      kill "$(cat "$PIDFILE")" 2>/dev/null && echo "Metrics server detenido" || echo "Proceso ya muerto"
      rm -f "$PIDFILE"
    else
      echo "No hay PID file"
    fi
    ;;
  status)
    if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
      echo "Metrics server corriendo (PID $(cat "$PIDFILE"))"
      curl -s http://localhost:9091/health | head -1 || echo "  Health check no responde"
    else
      echo "Metrics server NO corriendo"
    fi
    ;;
  *)
    echo "Uso: $0 {start|stop|status}"
    exit 1
    ;;
esac
