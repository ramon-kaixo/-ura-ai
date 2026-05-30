# Instructivo: Entrenamiento N3 con OpenClaw VM

## Pasos para configurar y ejecutar el entrenamiento

### 1. Conectar disco Toshiba
Conecta el disco externo Toshiba al Mac.
Verifica que está montado:
```bash
ls -la /Volumes/TOSHIBA_NUEVO/
```

### 2. Ejecutar script de configuración
```bash
cd /Users/ramonesnaola/URA/ura_ia_1972
bash scripts/setup_openclaw_vm.sh
```

Este script:
- Verifica Toshiba conectado
- Crea directorio URA_entrenamiento
- Genera archivo .env
- Crea cloud-init.yaml para VM
- Crea servidor API para VM

### 3. Crear VM en UTM (manual)

Abre UTM y sigue estos pasos:
1. Click en "Create VM"
2. Selecciona "Ubuntu Server 24.04 LTS"
3. Configura:
   - RAM: 8 GB
   - CPUs: 4
   - Storage: 20 GB
4. Red: "Host-Only"
   - IP fija: 192.168.64.100
5. Importa cloud-init.yaml:
   - En VM settings -> Cloud Init
   - Importa el archivo generado

### 4. Iniciar VM y copiar servidor API
```bash
# Copiar servidor a VM
scp vm_files/server.py root@192.168.64.100:/opt/openclaw_api/

# Verificar VM responde
curl http://192.168.64.100:5000/health
```

### 5. Ejecutar entrenamiento
```bash
bash scripts/start_training.sh
```

Este script:
- Verifica Toshiba
- Verifica VM
- Instala dependencias
- Carga semillas manuales
- Ejecuta entrenamiento

### 6. Ver resultados por la mañana

En Toshiba:
```bash
# Ver respuestas generadas
ls /Volumes/TOSHIBA_NUEVO/URA_entrenamiento/respuestas/ | wc -l

# Ver informe
cat /Volumes/TOSHIBA_NUEVO/URA_entrenamiento/reports/*.json
```

## Solución de problemas

### Toshiba no aparece
- Desconecta y reconecta el disco
- Verifica en Finder: /Volumes/
- Si no aparece, abre Disk Utility

### VM no responde
- Verifica VM está iniciada en UTM
- Verifica IP: 192.168.64.100
- Verifica puerto: 5000

### Entrenamiento falla
- Verifica logs en terminal
- Verifica informe en Toshiba
- Revisa conexión VM

## Después del entrenamiento

1. Analizar resultados en Toshiba
2. Revisar informes generados
3. Pausar o borrar VM si ya no necesitas
4. Los datos permanecen en Toshiba
