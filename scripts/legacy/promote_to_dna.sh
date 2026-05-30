#!/bin/bash
# scripts/promote_to_dna.sh - Guarda versión estable en URA_DNA

URA_DNA="/Users/ramonesnaola/Desktop/URA_DNA"
VERSION=$1

if [ -z "$VERSION" ]; then
    VERSION=$(date +%Y%m%d_%H%M%S)
fi

echo "=== PROMOCIÓN A URA_DNA ==="
echo "Versión: $VERSION"

if [ ! -d "/Users/ramonesnaola/URA/ura_ia_1972" ]; then
    echo "❌ URA_App no encontrada"
    exit 1
fi

mkdir -p "$URA_DNA/versiones"

cp -r /Users/ramonesnaola/URA/ura_ia_1972 "$URA_DNA/versiones/ura_$VERSION"

rm -f "$URA_DNA/current"
ln -s "$URA_DNA/versiones/ura_$VERSION" "$URA_DNA/current"

cat > "$URA_DNA/versiones/ura_$VERSION/metadata.json" << JSON
{
    "version": "$VERSION",
    "fecha": "$(date '+%Y-%m-%d %H:%M:%S')",
    "git_hash": "$(git rev-parse HEAD 2>/dev/null || echo 'sin_git')",
    "tamaño_mb": "$(du -sm /Users/ramonesnaola/URA/ura_ia_1972 | cut -f1)"
}
JSON

echo "✅ Promoción completada"
echo "   Versión: $VERSION"
echo "   Ubicación: $URA_DNA/current"
