# Rotar la API Key de Syncthing

## Cuándo usar esto
Si la API key de Syncthing se expone o se sospecha que puede estar en un repo.

## Método 1 — GUI (recomendado)
1. Abrir https://localhost:8384
2. Settings → GUI → API Key
3. Actions → Generate
4. Copiar la nueva key
5. Escribirla en `~/.syncthing_api_key`:
   ```bash
   echo "NUEVA_KEY" > ~/.syncthing_api_key
   chmod 600 ~/.syncthing_api_key
   ```

## Método 2 — API REST (automatizable)
Requiere la key actual como autenticación. Genera una nueva y aplica el PATCH:
```bash
OLD=$(cat ~/.syncthing_api_key)
NEW=$(python3 -c "import secrets,string; print(''.join(secrets.choice(string.ascii_letters+string.digits) for _ in range(32)))")
curl -sk -X PATCH https://localhost:8384/rest/config/gui \
  -H "X-API-Key: $OLD" -H "Content-Type: application/json" \
  -d "{\"apiKey\":\"$NEW\"}"
# Si verifica (200), persistir la nueva key:
curl -sk -o /dev/null -w "%{http_code}\n" -H "X-API-Key: $NEW" https://localhost:8384/rest/system/status
echo "$NEW" > ~/.syncthing_api_key && chmod 600 ~/.syncthing_api_key
```
Verificado con Syncthing v2.1.5 (macOS).

## Verificación
```bash
curl -sk -H "X-API-Key: $(cat ~/.syncthing_api_key)" https://localhost:8384/rest/system/status
```
Esperado: JSON con `"myID"`.

## Notas
- El hook `pre-push` de `.git/hooks/` lee la key desde `~/.syncthing_api_key`, no hardcodeada.
- Nunca hardcodear la key en scripts: usar `MAC_API_KEY="$(cat ~/.syncthing_api_key)"`.
