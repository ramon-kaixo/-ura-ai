# Motor de Conocimiento — Proyecto Completo v3

## 1. Idea en una frase

Tú dices un tema → se parte en aspectos, busca, descarga en paralelo (con rate-limit por dominio), pasa antivirus, limpia, vectoriza con HashingVectorizer (memoria constante, sin IA), quita duplicados midiendo cuántas fuentes confirman cada idea, y guarda el mapa del tema en Qdrant Alemania. ASUS re-vectoriza con IA solo el 10% importante.

## 2. Reparto

```
TÚ (Mac) → pides un tema
    │
    ▼
OpenClaw (ASUS) → parte el tema en aspectos, reparte trabajo
    │
    ▼
╔═══════════════════════════════════════════════════════╗
║ ALEMANIA — 90% del trabajo, SIN IA                  ║
║  HashingVectorizer (memoria constante, 50MB)        ║
║  Colección Qdrant: knowledge_hash                   ║
║  Descarga paralela con rate-limit por dominio       ║
║  Límite duro de cuarentena                          ║
║  ClamAV daemon (RAM plana, sin picos)               ║
║  Checkpoint reanudable + systemd MemoryHigh         ║
╚═══════════════════════════════════════════════════════╝
    │  (solo 10% importante)
    ▼
╔═══════════════════════════════════════════════════════╗
║ ASUS — solo lo que necesita IA                       ║
║  Ollama nomic-embed-text → vectores semánticos      ║
║  Colección Qdrant: knowledge_semantic               ║
║  Whisper para vídeos                                 ║
╚═══════════════════════════════════════════════════════╝
```

## 3. Archivos

```
motor/
├── alemania/
│   ├── config.py
│   ├── instalar_alemania.sh
│   ├── monitor.py
│   ├── 1_buscar.py
│   ├── 2_prefiltro.py
│   ├── 3_descargar.py          ← aiohttp + Semaphore(2) por dominio
│   ├── 4_antivirus.py
│   ├── 5_limpiar.py
│   ├── 6_vectorizar.py         ← HashingVectorizer (n_features=2**18, norm=l2)
│   ├── 7_deduplicar.py
│   ├── 8_guardar.py            ← Qdrant knowledge_hash
│   └── motor.py                ← orquestador + systemd-run con MemoryHigh=12G
└── asus/
    ├── instalar_asus.sh
    ├── revectorizar_ia.py       ← Ollama re-embed → knowledge_semantic
    ├── procesar_video.py
    └── procesar_imagen.py
```

## 4. Pipeline con analizadores

### 4.1 monitor.py — daemon ligero

Corre en paralelo, solo inyecta JSON a journald. Zero Kill Scripts.

- Cada 10s: disco → si <15% libre → ALERTA
- Cada 10s: RAM → si <10% libre → ALERTA
- Cada 10s: cuarentena activa > MAX_MB → ALERTA
- Cada 30s: ¿motor.py colgado? → ALERTA

### 4.2 1_buscar.py — SearXNG → enlaces

- Máx 30 enlaces por tema
- Métricas: N_enlaces, tiempo
- Alerta si <3 → tema demasiado específico

### 4.3 2_prefiltro.py — Whitelist + dedup contra Qdrant

- Métrica: N_recibidos, N_filtrados
- Alerta si ratio filtrados >0.8 → whitelist muy restrictiva

### 4.4 3_descargar.py — aiohttp con rate-limit

- **asyncio.Semaphore(2) por netloc** → evita HTTP 429
- **Límite duro**: si cuarentena > MAX_CUARENTENA_MB → STOP + alerta
- Timeout 30s por request
- Métricas: N_exito, N_fallo, bytes, tiempo_por_url
- Alerta si tasa fallo >30% o tiempo_por_url >20s

### 4.5 4_antivirus.py — ClamAV daemon

- ClamAV en modo daemon (no freshclam por cada job)
- RAM plana ~1.2GB fijos, sin picos
- Métrica: N_escaneados, N_infectados
- Alerta si infección → fuente contaminada

### 4.6 5_limpiar.py — Trafilatura, pymupdf, Pillow, yt-dlp

- Extrae texto de HTML, PDF, imágenes
- Métrica: N_textos, chars, tipos
- Alerta si <100 chars → página sin contenido

### 4.7 6_vectorizar.py — HashingVectorizer

```
MEMORIA CONSTANTE: 50MB, no crece con datos
TAMAÑO FIJO: 2^18 features (262144), norm=l2
RÁPIDO: 0.5ms por texto
SIN PYTHON: solo scikit-learn, no PyTorch (0 dependencia extra)

Colección destino: knowledge_hash
Limitación: no entiende sinónimos.
  → El dedup semántico real se hace después en ASUS.
```

- Métrica: N_textos, tiempo_por_texto_ms
- Alerta si >10ms → CPU saturada

### 4.8 7_deduplicar.py — Cosine + confianza

- Cosine entre vectores hash (O(n²), n<50 asumible)
- Threshold 0.85
- Nota de confianza = N fuentes que confirman el cluster
- Métrica: N_brutos, N_clusters, N_unicos, confianza_media
- Alerta si ratio unicos/brutos <0.2

### 4.9 8_guardar.py — Qdrant knowledge_hash

- Payload: {tema, aspecto, texto, fuente, confianza, timestamp, N_fuentes}
- Borra job_dir al completar
- Métrica: N_puntos, tiempo_escritura

### 4.10 motor.py — Orquestador

```
- job_id = uuid4
- systemd-run --unit=motor-{uuid} --property=MemoryHigh=12G --property=MemoryMax=14G
- Checkpoint .done por paso → reanudable
- Timeout total configurable (defecto: 30 min)
- Logs JSON a stdout (journald)
- Zero Kill Scripts: systemctl stop motor-{uuid} si timeout
```

## 5. ASUS (10% IA)

```python
# revectorizar_ia.py
# 1. SCP unicos.json desde Alemania
# 2. Ollama nomic-embed-text → vectores semánticos (768 dims)
# 3. Qdrant knowledge_semantic
```

```python
# procesar_video.py
# 1. yt-dlp baja audio
# 2. faster-whisper transcribe
# 3. HashingVectorizer (rápido) → knowledge_hash como "guion"
```

```python
# procesar_imagen.py
# 1. exiftool metadatos
# 2. Pillow dimensiones/colores
# 3. Descripción + guardar
```

## 6. Dos colecciones Qdrant

| Colección | Dónde | Vectorizador | Dimensión | Uso |
|-----------|-------|-------------|-----------|-----|
| knowledge_hash | Alemania | HashingVectorizer | 262144 (2^18) sparsa | Búsqueda amplia, todo lo scrapeado |
| knowledge_semantic | ASUS | nomic-embed-text (Ollama) | 768 | Precisión semántica, solo lo importante |

## 7. Cuellos de botella resueltos

| Problema | Solución | Archivo |
|----------|----------|---------|
| HTTP 429 por rate-limit | Semaphore(2) por netloc | 3_descargar.py |
| OOM por crecer datos | HashingVectorizer (memoria constante) | 6_vectorizar.py |
| RAM insuficiente | MemoryHigh=12G en systemd-run | motor.py |
| Colisión de jobs | job_id = uuid4 | motor.py |
| Disco lleno en descarga | Límite duro MAX_CUARENTENA_MB | config.py |
| Fallo a mitad sin reanudar | Checkpoint .done | motor.py |
| Vectorización sin sentido | ASUS re-vectoriza el 10% con IA | revectorizar_ia.py |

## 8. Instalación

```bash
# Alemania
scp -r motor/alemania/ ramon_admin@178.105.81.83:/opt/motor/
ssh ramon_admin@178.105.81.83 "bash /opt/motor/instalar_alemania.sh"
# pip: aiohttp, trafilatura, yt-dlp, pymupdf, scikit-learn, exiftool, psutil
# ClamAV daemon + freshclam inicial
# colección Qdrant: knowledge_hash

# ASUS
scp -r motor/asus/ ramon@10.164.1.99:/opt/motor/
ssh ramon@10.164.1.99 "bash /opt/motor/instalar_asus.sh"
# pip: faster-whisper
# modelo whisper small
# colección Qdrant: knowledge_semantic
```
