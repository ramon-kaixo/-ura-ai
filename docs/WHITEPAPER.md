# URA — Whitepaper Técnico

## Resumen
URA es un ecosistema de agentes de IA con autogestión, calidad de código automatizada y despliegue multi-nube.

## Arquitectura
- **Tuneladora**: Pipeline de 7 rodillos obligatorio para todo código nuevo
- **Enjambre**: 6 buzos que investigan tendencias, vulnerabilidades y modelos
- **Registry**: API REST para inventario vivo de agentes
- **Dashboard**: Panel unificado con salud en tiempo real
- **Cloud Portable**: Despliegue en AWS, Azure, GCP

## Seguridad
- OWASP ASI 10/10 (mapeo completo en docs/owasp_asi_mapping.json)
- MITRE ATLAS (8 tácticas cubiertas en docs/mitre_atlas_mapping.json)
- Aislamiento: read_only, cap_drop ALL, no-new-privileges
- Red: extra_hosts bloqueando redes sociales + proxy Squid

## Métricas
- 105.939 líneas de código
- 11 agentes registrados
- 10 timers launchd
- 544 dependencias auditadas

## Licencia
Propietario — CodeRefine Engineering 2026
