# Añadir un nuevo usuario al sistema de voz

## Pasos

1. **Copiar plantilla:**
```bash
ssh ramon@gx10-ts "cp ~/URA/ura_ia_1972/data/voz/perfiles/_plantilla.json ~/URA/ura_ia_1972/data/voz/perfiles/NOMBRE/config.json"
ssh ramon@gx10-ts "mkdir -p ~/URA/ura_ia_1972/data/voz/perfiles/NOMBRE/sesiones"
```

2. **Editar config.json** con:
   - `nombre` — nombre del usuario
   - `velocidad_habla` — "rapida", "normal", "lenta"
   - `caracteristicas` — ["acento X", "voz aguda", ...]
   - `vocabulario_extra` — palabras propias de esta persona

3. **Para usar el perfil:**
```bash
export URA_USUARIO=NOMBRE
voz
```

## Cuándo añadir identificación automática

Solo si hay 3+ usuarios habituales.
Hasta entonces, selección manual con variable `URA_USUARIO`.

## Implementación pendiente (Fase 4)

- Modelo pyannote (~200 MB)
- Muestras de voz de 30s por usuario
- Modificar endpoint para detectar antes de transcribir
