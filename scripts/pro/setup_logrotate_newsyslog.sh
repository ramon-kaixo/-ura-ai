#!/bin/bash
# setup_logrotate_newsyslog.sh – Configura rotación nativa de logs en macOS via newsyslog
# Ejecutar con: sudo bash scripts/pro/setup_logrotate_newsyslog.sh

set -e

cat > /etc/newsyslog.d/ura.conf << 'EOF'
# logfilename                        [owner:group]  mode  count  size  when  flags  [/pid_file]  [sig_num]
/opt/ura/logs/*.log                                  644   7      1000  *     Z
/var/log/ura_*.log                                   644   7      1000  *     Z
/Users/ramonesnaola/ura_backup_inmortal/*.log         644   7      1000  *     Z
EOF

echo "newsyslog config installed at /etc/newsyslog.d/ura.conf"
echo "Logs rotate when they reach 1 MB; 7 rotations kept; compressed with gzip."
