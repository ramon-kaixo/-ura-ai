# PLAN MAESTRO: PROYECTO IA 1972 (FLUJO DISTRIBUIDO)

## 1. Objetivo del Sistema
Busqueda, extraccion y analisis de informacion continuo al 10% de capacidad constante,
sin picos de consumo ni saturacion del internet domestico.

## 2. Reparto de Tareas

| Maquina | Rol | RAM | Que hace |
|---------|-----|-----|----------|
| **ASUS GX10** (España) | Cerebro Consumidor | 128 GB + Blackwell | Envia ordenes en texto. Recibe datos limpios. Procesa con GPU. |
| **Hetzner** (Alemania) | Obrero Extractor | 16 GB | Recibe orden. Busca en internet. Filtra y limpia HTML. Envia resultados. |

## 3. Motor de Doble Flujo (en Alemania)

```
                          ┌─────────────────────────────┐
  Orden desde España ───→ │   Hetzner procesa y filtra   │
                          └─────────────┬───────────────┘
                                        │
                          ┌─────────────┴───────────────┐
                          ▼                             ▼
                  ┌──────────────┐           ┌──────────────────┐
                  │ VIA 1: TEXTO │           │ VIA 2: CRUDO     │
                  │ (prioritario)│           │ (segundo plano)  │
                  │ 80% del tiempo│           │ 20% del tiempo   │
                  │              │           │                  │
                  │ Texto puro   │           │ PDFs, imagenes,  │
                  │ filtrado     │           │ estructuras      │
                  │ → tubo 200Mbps│           │ → mochila_cloud/ │
                  └──────┬───────┘           └──────┬───────────┘
                         │                         │
                         ▼                         ▼
                  ┌──────────────┐           ┌──────────────────┐
                  │ ASUS GX10    │           │ Disco Hetzner    │
                  │ RAM + GPU    │           │ (40 GB)          │
                  └──────────────┘           └──────────────────┘
```

## 4. Tres Escudos Antibugs

### 🛡️ Escudo 1: Hash Dedup (SHA256)
- Cada pieza de datos se hashea antes de procesar
- Si ya se vio antes → se destruye sin enviar
- Cola de 100,000 hashes con rotacion automatica

### 🛡️ Escudo 2: Anti-OOM (Proteccion de RAM)
- Maximo 1 GB de datos en cola en RAM de Hetzner
- Si se supera → desvio automatico a disco (mochila_cloud/)
- Si internet de España se cae → todo a disco
- Cuando vuelve la conexion → se vacia el disco a 200 Mbps

### 🛡️ Escudo 3: Purga de n8n
- n8n detenido en Hetzner (estaba en bucle de reinicio)
- Los scrapers trabajan en modo silencioso: sin historial, sin logs acumulados

## 5. Preguntas para OpenClaw

1. ¿El limite estatico de 200 Mbps en software es suficiente para evitar
   congestion en routers domesticos con trafico UDP/TCP masivo?
   
2. ¿Que herramienta de mercado (ZeroMQ, WebSockets, gRPC) recomiendas
   para streaming de texto estructurado RAM a RAM con minimo CPU en 16 GB?

3. ¿Hay riesgo de cuello de botella en el borrado de archivos del disco
   de Hetzner cuando la mochila empiece a vaciarse hacia España?

4. ¿El hash SHA256 para dedup tiene overhead aceptable en 16 GB?

## 6. Estado de Implementacion

| Componente | Estado | Archivo |
|-----------|--------|---------|
| Doble via (texto + crudo) | ✅ Implementado | `app/flujo_constante.py` |
| Hash dedup | ✅ Implementado | `app/flujo_constante.py` |
| Anti-OOM (1 GB max) | ✅ Implementado | `app/flujo_constante.py` |
| Tubo capado 200 Mbps | ✅ Implementado | `app/flujo_constante.py` |
| Mochila cloud en disco | ✅ Creada | `storage/mochila_cloud/` |
| Log rotatorio | ✅ Implementado | `app/flujo_constante.py` |
| Purga n8n | ✅ Ejecutado | `docker stop n8n` en Hetzner |
