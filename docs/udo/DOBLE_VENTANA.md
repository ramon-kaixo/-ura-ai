# Doble Ventana — OpenCode Web (dorada) + OpenCode Sistema (oscura)

**Fecha**: 2026-08-09 · **Objetivo**: dos interfaces del MISMO OpenCode sobre la MISMA carpeta de ASUS, con comunicación bidireccional instantánea.

## Arquitectura

```
        TU MAC
        /     \
   Safari      Terminal
 (web DORADA)  (TUI OSCURA)
      \         /
       \       /
   ASUS: opencode web :8081
   ├── binario: ~/.opencode/bin/opencode (1.17.7)
   ├── config: ~/.config/opencode/opencode.json
   ├── datos compartidos: ~/.local/share/opencode/opencode.db (SESIONES ÚNICAS)
   └── repo: /home/ramon/URA/ura_ia_1972 (código ÚNICO)
```

**Por qué funciona**: ambos (web y terminal) son clientes del MISMO servidor en ASUS. Comparten:
- El mismo `opencode.db` → **las mismas sesiones** (lo que ves en uno lo ve el otro)
- El mismo repo git → **el mismo código** (un cambio se ve al instante en ambos)

## Cómo distinguirlas

| Ventana | Tema | Uso |
|---------|------|-----|
| **Web (Safari)** | **Dorado** (`ura-dorado`) | Conversar y programar con la interfaz gráfica |
| **Sistema (Terminal/TUI)** | Oscuro (default) | Control de ingeniería, revisiones, UDO |

## Tema dorado (Web)

- Archivo: `.opencode/themes/ura-dorado.json` (en el repo — versión de control)
- Paleta: dorados (#FFD700/#DAA520/#B8860B) sobre crema/dorado oscuro
- **Activación**: reiniciar `opencode.service` (para que cargue el tema) + seleccionar "ura-dorado" en el selector de temas de la web

## Conexión de la terminal al servidor (opcional)

Si quieres la TUI conectada al MISMO servidor web (en vez de una TUI local):

```bash
opencode attach http://10.164.1.99:8081
```

## Pendiente (requiere sudo Ramón — rootfs RO)

```bash
sudo systemctl restart opencode.service   # carga el tema ura-dorado
```

## Reversibilidad

- Tema: borrar `.opencode/themes/ura-dorado.json` + seleccionar otro tema en la web
- No hay cambios de servicio ni de config global
