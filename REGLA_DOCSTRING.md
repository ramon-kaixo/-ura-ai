# REGLA OBLIGATORIA — Docstring en todo archivo .py

**Vigencia:** inmediata. **Alcance:** todo el proyecto URA.

## Formato mínimo obligatorio

```python
"""
Módulo: ruta/del/archivo.py
Propósito: [Una frase clara de qué hace este archivo]
Dependencias principales: [lista de imports críticos]
Reglas especiales: [seguridad, tiempos, restricciones]
"""
```

## Ejemplo

```python
"""
Módulo: core/security/agente_policia_v2.py
Propósito: Valida comandos contra inyección shell, path traversal y comandos peligrosos.
Dependencias: re, subprocess (sin shell=True)
Reglas especiales: Rechazar '|', '&', ';', 'rm -rf', '../'. Loguear cada intento.
"""
```

## Consecuencias

- **Sin docstring → código incompleto.** No se despliega a producción sin revisión humana.
- **Si el propósito cambia → actualizar el docstring.**
- **Las auditorías automáticas usarán el docstring como contexto.** Sin él, la IA no sabe qué revisa.

## Archivos existentes

Los 28 archivos CRITICAL y cualquier archivo modificado deben recibir docstring en el próximo commit.
