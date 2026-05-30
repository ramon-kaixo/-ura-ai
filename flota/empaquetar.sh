#!/bin/bash
set -euo pipefail
# empaquetar.sh — Prepara paquetes de instalacion por tipo de dispositivo
PAQUETES_DIR="${HOME}/URA/ura_ia_1972/paquetes"
TIPO="${1:-todos}"
mkdir -p "$PAQUETES_DIR"
echo "   📦 $TIPO..."

empaquetar_caja() {
    local d="/tmp/pkg_caja"; mkdir -p "$d"
    [ -d /opt/floreant ] && cp -r /opt/floreant "$d/" 2>/dev/null
    cat > "$d/instalar.sh" << 'EOF'
#!/bin/bash
cd /opt/floreant && java -jar floreant.jar 2>/dev/null &
echo "OK caja en :8080"
EOF
    chmod +x "$d/instalar.sh"
    tar czf "${PAQUETES_DIR}/paquete_caja.tar.gz" -C "$d" . 2>/dev/null
    rm -rf "$d"; echo "   ✅ caja.tar.gz"
}

empaquetar_musica() {
    local d="/tmp/pkg_musica"; mkdir -p "$d"
    cat > "$d/instalar.sh" << 'EOF'
#!/bin/bash
pip install maloja 2>/dev/null && maloja start --port 42010 &
echo "OK musica en :42010"
EOF
    chmod +x "$d/instalar.sh"
    tar czf "${PAQUETES_DIR}/paquete_musica.tar.gz" -C "$d" . 2>/dev/null
    rm -rf "$d"; echo "   ✅ musica.tar.gz"
}

empaquetar_general() {
    local d="/tmp/pkg_general"; mkdir -p "$d"
    cat > "$d/instalar.sh" << 'EOF'
#!/bin/bash
curl -fsSL https://raw.githubusercontent.com/fleetdm/fleet/main/tools/install-osquery.sh | bash 2>/dev/null
echo "OK agente instalado"
EOF
    chmod +x "$d/instalar.sh"
    tar czf "${PAQUETES_DIR}/paquete_general.tar.gz" -C "$d" . 2>/dev/null
    rm -rf "$d"; echo "   ✅ general.tar.gz"
}

case "$TIPO" in caja) empaquetar_caja ;; musica) empaquetar_musica ;; general) empaquetar_general ;; todos) empaquetar_caja; empaquetar_musica; empaquetar_general ;; *) echo "Tipos: caja, musica, general, todos" ;; esac
echo "   ✅ Paquetes en $PAQUETES_DIR"
