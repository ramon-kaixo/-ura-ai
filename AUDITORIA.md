# Auditoría Total — 10 herramientas deterministas

Catálogo cerrado. No añadir más herramientas después de estas.

---

## Sesión 0 — Ya consolidado

| Herramienta | Ángulo | Estado |
|-------------|--------|--------|
| ruff | Estilo, imports, errores lógicos | ✅ |
| radon | Complejidad ciclomática | ✅ Sin E/F |

---

## Sesión 1 — Seguridad

### bandit — credenciales, llamadas peligrosas
```bash
bandit -r . -ll
```
Si reporta "hardcoded password/secret" → hay una clave en el código.

### safety — dependencias vulnerables (CVEs)
```bash
safety check
```
Revisa si las librerías instaladas (requests, chromadb, etc.) tienen vulnerabilidades conocidas.

---

## Sesión 2 — Limpieza

### vulture — código muerto (funciones, variables no usadas)
```bash
vulture . --min-confidence 80
```
Puede dar falsos positivos. Ante la duda, no borrar.

### jscpd — código duplicado (copia/pega)
```bash
jscpd . --threshold 5
```
No unificar si rompe el aislamiento entre máquinas (Hetzner ↔ GX10).

---

## Sesión 3 — Tipado y Cobertura

### mypy — tipos estáticos
```bash
mypy --strict core/ cli/
```
Verifica que los type hints sean correctos. Previene bugs por tipos incorrectos.

### pytest-cov — cobertura de tests
```bash
pytest --cov=mochila_engine --cov=prompt_injector --cov-report=term -p no:testpaths
```
Saldrá baja al principio. Es el mapa de qué falta probar.

---

## Sesión 4 — Avanzado

### mutmut — calidad de tests (mutaciones)
```bash
mutmut run --paths-to-mutate=mochila_engine.py
mutmut results
```
Mete bugs falsos y mira si tus tests los cazan. SÓLO un módulo por vez (machaca CPU).

### hypothesis — casos extremos automáticos
```bash
# Requiere tests basados en propiedades (no los tests secuenciales actuales)
# Adaptar a la API real (MochilaEngine.nueva, no procesar_peso)
```
Genera cientos de casos de prueba extremos. Requiere reescribir tests.

---

## Resumen — 10 ángulos

| # | Ángulo | Herramienta | Sesión |
|---|--------|------------|--------|
| 1 | Estilo/sintaxis | ruff | 0 ✅ |
| 2 | Complejidad | radon | 0 ✅ |
| 3 | Seguridad (código) | bandit | 1 |
| 4 | Seguridad (deps) | safety | 1 |
| 5 | Código muerto | vulture | 2 |
| 6 | Duplicación | jscpd | 2 |
| 7 | Tipado estático | mypy | 3 |
| 8 | Cobertura | pytest-cov | 3 |
| 9 | Calidad de tests | mutmut | 4 |
| 10 | Casos extremos | hypothesis | 4 |

## Reglas

- Una sesión cada vez. NO todo el mismo día.
- Miran, no tocan. Anotar, no arreglar en caliente.
- git commit ANTES de cualquier cambio real.
- mutmut SÓLO módulo por módulo.
- chattr +i protege el núcleo de auto-fixes.
