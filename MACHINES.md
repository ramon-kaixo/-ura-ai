# URA Machine Architecture — 4+ Nodos (2026-06-06)

## Nodo 1: Hetzner Cloud (Nuremberg) — SCRAPING
  IP: 178.105.81.83 | 8 vCPU | 16 GB RAM | 40 GB SSD | 14.51€/mo
  Rol: Bulk web scraping 24/7
  Estado: ✅ ACTIVO (ura-scraper.service)
  Descarga: Pinterest, Google Images, FontsInUse
  Datos: /root/.nervioso/ura_search/cola/
  Conexión: ssh hetzner

## Nodo 2: GX10 (ASUS, local) — LLM + VISIÓN + CONTROL
  IP: 10.164.1.99 | 20 cores ARM | 128 GB RAM
  Rol: Análisis con IA, visión, OpenClaw, modelos
  Estado: ✅ ACTIVO
  Servicios: OpenClaw (:18789), llama-vision (:11436), Model Router (:11435)

## Nodo 3: open-webui (Docker GX10) — DASHBOARD
  Puerto: 3080
  Rol: Visualización de datos, chat con LLM
  Estado: ✅ ACTIVO

## Nodo 4: n8n (Docker GX10) — ORQUESTACIÓN
  Puerto: 5678
  Rol: Workflows cada 6h, notificaciones
  Estado: ✅ ACTIVO

## Objetivo: Barras de Calle San Gregorio
  - Bar Kaixo
  - Bar Museo
  - Bar Gregorio

## Flujo de datos
  Hetzner (scraping) → rsync → GX10 (análisis LLM) → open-webui (dashboard)
