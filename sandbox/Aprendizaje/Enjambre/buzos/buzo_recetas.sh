#!/bin/bash
set -euo pipefail
MALETA="$1"; OUTPUT="$2"
SEARXNG_URL="${SEARXNG_URL:-http://178.105.81.83:8888}"
THEMEALDB="https://www.themealdb.com/api/json/v1/1"
TMPFILE=$(mktemp); trap 'rm -f "$TMPFILE"' EXIT
jq -r '.cocina.areas[]' "$MALETA" 2>/dev/null | while IFS= read -r area; do
    [ -z "$area" ] && continue
    echo "   🔍 $area"
    curl -s --max-time 15 "${THEMEALDB}/filter.php?a=${area}" 2>/dev/null | jq -c '.meals[]?' 2>/dev/null | while read meal; do
        ID=$(echo "$meal" | jq -r '.idMeal'); NAME=$(echo "$meal" | jq -r '.strMeal')
        THUMB=$(echo "$meal" | jq -r '.strMealThumb')
        DETAIL=$(curl -s --max-time 10 "${THEMEALDB}/lookup.php?i=${ID}" 2>/dev/null)
        INGREDIENTS=$(echo "$DETAIL" | jq '[.meals[0] | to_entries[] | select(.key | test("strIngredient[0-9]+")) | select(.value != "" and .value != null) | .value]' 2>/dev/null)
        MEASURES=$(echo "$DETAIL" | jq '[.meals[0] | to_entries[] | select(.key | test("strMeasure[0-9]+")) | select(.value != "" and .value != null) | .value]' 2>/dev/null)
        INSTRUCTIONS=$(echo "$DETAIL" | jq -r '.meals[0].strInstructions' 2>/dev/null)
        YOUTUBE=$(echo "$DETAIL" | jq -r '.meals[0].strYoutube' 2>/dev/null)
        jq -c -n --arg area "$area" --arg id "$ID" --arg nombre "$NAME" --argjson ingredientes "$INGREDIENTS" --argjson medidas "$MEASURES" --arg instrucciones "$INSTRUCTIONS" --arg youtube "$YOUTUBE" --arg imagen "$THUMB" '{buzo: "recetas", area: $area, id: $id, nombre: $nombre, ingredientes: $ingredientes, medidas: $medidas, instrucciones: $instrucciones, youtube: $youtube, imagen: $imagen, fuente: "TheMealDB"}' 2>/dev/null >> "$TMPFILE"
    done
done
python3 -c "import json; items=[json.loads(l) for l in open('$TMPFILE') if l.strip()]; json.dump(items, open('$OUTPUT','w'), ensure_ascii=False, indent=2); print(len(items))" > /tmp/_recetas_count 2>/dev/null || echo 0 > /tmp/_recetas_count
echo "   ✅ $(cat /tmp/_recetas_count) recetas"
