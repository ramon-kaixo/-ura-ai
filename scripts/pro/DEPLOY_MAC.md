# Mac mini M4 — Deployment Checklist

## 1. Instalar dependencias

```bash
pip install torch torchvision torchaudio --index-url https://pytorch.org --break-system-packages
pip install openai-whisper sounddevice soundfile piper-tts --break-system-packages
```

## 2. Sembrar DB de correcciones

```bash
python3 /Users/ramonesnaola/URA/ura_ia_1972/scripts/pro/seed_correcciones_voz.py
```

## 3. Configurar LaunchDaemon

```bash
cp /Users/ramonesnaola/URA/ura_ia_1972/scripts/pro/com.ura.voice.plist \
   /Users/ramonesnaola/Library/LaunchAgents/com.ura.voice.plist

mkdir -p /Users/ramonesnaola/URA/ura_ia_1972/logs

launchctl bootstrap gui/$(id -u) /Users/ramonesnaola/Library/LaunchAgents/com.ura.voice.plist
launchctl kickstart -k gui/$(id -u)/com.ura.voice

tail -f /Users/ramonesnaola/URA/ura_ia_1972/logs/mac_voice_err.log
```

## 4. Test de latencia (con Anker S500 conectado)

```bash
python3 /Users/ramonesnaola/URA/ura_ia_1972/scripts/pro/test_latencia_mac.py
```

## 5. Configurar claves SSH (sync con ASUS/GB10)

```bash
ssh-keygen -t rsa -b 4000 -f ~/.ssh/id_rsa -N ""
ssh-copy-id -i ~/.ssh/id_rsa.pub ramon@10.164.1.99
ssh ramon@10.164.1.99 "echo '✅ OK'"
```

## 6. Programar cron de sincronización

```bash
(crontab -l 2>/dev/null; echo "*/5 * * * * /usr/bin/python3 /Users/ramonesnaola/URA/ura_ia_1972/scripts/pro/sincronizar_vocabulario.py >> /Users/ramonesnaola/URA/ura_ia_1972/logs/sync.log 2>&1") | crontab -
```

## Parar/Reiniciar el daemon

```bash
# Detener
launchctl bootout gui/$(id -u) /Users/ramonesnaola/Library/LaunchAgents/com.ura.voice.plist

# Recargar tras cambios
launchctl kickstart -k gui/$(id -u)/com.ura.voice

# Ver logs
tail -f /Users/ramonesnaola/URA/ura_ia_1972/logs/mac_voice_{out,err}.log
```
