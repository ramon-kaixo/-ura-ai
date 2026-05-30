#!/usr/bin/env bash
# setup.sh - Instalación completa de URA en un comando
# Compatible con macOS (zsh/bash) y Linux (bash)

set -e  # Solo para errores críticos (pasos 1-2)

# Colores para mensajes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Función para mensajes de progreso
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Directorio del proyecto
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Archivo de log de errores
ERRORS_LOG="$PROJECT_DIR/setup_errors.log"
echo "" > "$ERRORS_LOG"

# ─────────────────────────────────────────────────────────────
# 1. Verificar requisitos previos
# ─────────────────────────────────────────────────────────────
log_info "Verificando requisitos previos..."

# Verificar Python 3.10+
if ! command -v python3 &> /dev/null; then
    log_error "python3 no encontrado. Instala Python 3.10+ desde python.org o con brew install python"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]); then
    log_error "Python versión $PYTHON_VERSION no es compatible. Se requiere Python 3.10+"
    exit 1
fi

log_info "✓ Python $PYTHON_VERSION encontrado"

# Verificar pip3
if ! command -v pip3 &> /dev/null; then
    log_error "pip3 no encontrado. Instala con: python3 -m ensurepip --upgrade"
    exit 1
fi

log_info "✓ pip3 encontrado"

# Verificar Docker
if ! command -v docker &> /dev/null; then
    log_error "Docker no encontrado. Instala desde docker.com"
    exit 1
fi

log_info "✓ Docker encontrado"

# Verificar Docker Compose v2
if ! docker compose version &> /dev/null; then
    log_error "Docker Compose v2 no encontrado. Instala desde docker.com"
    exit 1
fi

log_info "✓ Docker Compose v2 encontrado"

# Verificar curl
if ! command -v curl &> /dev/null; then
    log_error "curl no encontrado. Instala con brew install curl (macOS) o apt install curl (Linux)"
    exit 1
fi

log_info "✓ curl encontrado"

# ─────────────────────────────────────────────────────────────
# 2. Crear entorno virtual Python
# ─────────────────────────────────────────────────────────────
log_info "Creando entorno virtual Python..."

if [ ! -d "$PROJECT_DIR/.venv" ]; then
    python3 -m venv "$PROJECT_DIR/.venv"
    log_info "✓ Entorno virtual creado en .venv/"
else
    log_info "✓ Entorno virtual ya existe"
fi

# Activar entorno virtual
source "$PROJECT_DIR/.venv/bin/activate"

# Actualizar pip
pip install --upgrade pip setuptools wheel || {
    echo "Error actualizando pip" >> "$ERRORS_LOG"
}

# Instalar dependencias
log_info "Instalando dependencias desde requirements.txt..."
pip install -r "$PROJECT_DIR/requirements.txt" 2>> "$ERRORS_LOG" || {
    log_warn "Algunos paquetes fallaron (ver $ERRORS_LOG). Continuando..."
}

log_info "✓ Dependencias instaladas"

# A partir de aquí los errores son no críticos — no abortar
set +e

# ─────────────────────────────────────────────────────────────
# 3. Crear archivos de configuración
# ─────────────────────────────────────────────────────────────
log_info "Creando archivos de configuración..."

# Crear .env.example si no existe
if [ ! -f "$PROJECT_DIR/.env.example" ]; then
    cat > "$PROJECT_DIR/.env.example" << 'EOF'
TELEGRAM_TOKEN=
CHAT_ID=
N8N_API_KEY=
OLLAMA_BASE_URL=http://localhost:11434
MODEL_NAME=qwen2.5:3b-instruct
REDIS_URL=redis://localhost:6379
EOF
    log_info "✓ .env.example creado"
else
    log_info "✓ .env.example ya existe"
fi

# Copiar .env.example → .env si .env no existe
if [ ! -f "$PROJECT_DIR/.env" ]; then
    cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
    log_info "✓ .env creado desde .env.example"
    log_warn "⚠ Edita .env con tus credenciales antes de ejecutar URA"
else
    log_info "✓ .env ya existe (no sobrescribiendo)"
fi

# Crear directorios necesarios
mkdir -p "$PROJECT_DIR/logs"
mkdir -p "$PROJECT_DIR/data"
mkdir -p "$PROJECT_DIR/sandbox"
log_info "✓ Directorios creados: logs/, data/, sandbox/"

# ─────────────────────────────────────────────────────────────
# 4. Instalar y verificar Ollama
# ─────────────────────────────────────────────────────────────
log_info "Verificando Ollama..."

if ! command -v ollama &> /dev/null; then
    log_info "Ollama no instalado. Instalando..."
    curl -fsSL https://ollama.com/install.sh | sh || {
        log_error "Error instalando Ollama"
        echo "Error instalando Ollama" >> "$ERRORS_LOG"
    }
    log_info "✓ Ollama instalado"
else
    log_info "✓ Ollama ya instalado"
fi

# Verificar si Ollama responde
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    log_info "✓ Ollama respondiendo en localhost:11434"
else
    log_warn "Ollama no responde. Intentando arrancarlo..."
    ollama serve > /dev/null 2>&1 &
    sleep 5
    
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        log_info "✓ Ollama arrancado correctamente"
    else
        log_warn "Ollama no responde después del arranque. Ejecuta manualmente: ollama serve"
        echo "Ollama no responde" >> "$ERRORS_LOG"
    fi
fi

# Descargar modelo mínimo si no hay ninguno
log_info "Verificando modelos de Ollama..."
MODELS=$(ollama list 2>/dev/null | tail -n +2 | grep -v "^$" || echo "")
if [ -z "$MODELS" ]; then
    log_info "No hay modelos. Descargando qwen2.5:3b-instruct..."
    ollama pull qwen2.5:3b-instruct || {
        log_warn "Error descargando modelo. Ejecuta manualmente: ollama pull qwen2.5:3b-instruct"
        echo "Error descargando modelo Ollama" >> "$ERRORS_LOG"
    }
    log_info "✓ Modelo descargado"
else
    log_info "✓ Modelos ya instalados"
fi

# ─────────────────────────────────────────────────────────────
# 5. Levantar servicios Docker
# ─────────────────────────────────────────────────────────────
log_info "Levantando servicios Docker (redis, postgres)..."

# Verificar si existe docker-compose.yml
if [ -f "$PROJECT_DIR/docker-compose.yml" ]; then
    docker compose up -d redis postgres || {
        log_warn "Error levantando servicios Docker. Ejecuta manualmente: docker compose up -d redis postgres"
        echo "Error levantando servicios Docker" >> "$ERRORS_LOG"
    }
    
    # Esperar a que Redis responda
    log_info "Esperando a que Redis responda..."
    REDIS_OK=0
    for i in {1..30}; do
        if docker compose exec -T redis redis-cli ping > /dev/null 2>&1; then
            log_info "✓ Redis respondiendo"
            REDIS_OK=1
            break
        fi
        sleep 1
    done

    if [ $REDIS_OK -eq 0 ]; then
        log_warn "Redis no respondió después de 30 segundos"
        echo "Redis no respondió" >> "$ERRORS_LOG"
    fi
    
    log_info "✓ Servicios Docker levantados"
else
    log_warn "docker-compose.yml no encontrado. Saltando servicios Docker"
    echo "docker-compose.yml no encontrado" >> "$ERRORS_LOG"
fi

# ─────────────────────────────────────────────────────────────
# 6. Verificar n8n (opcional)
# ─────────────────────────────────────────────────────────────
log_info "Verificando n8n (opcional)..."

if curl -s http://localhost:5678 > /dev/null 2>&1; then
    log_info "✓ n8n detectado en localhost:5678"
else
    log_warn "n8n no detectado. Puedes instalarlo con: npx n8n (opcional)"
fi

# ─────────────────────────────────────────────────────────────
# 7. Ejecutar tests de humo rápidos
# ─────────────────────────────────────────────────────────────
log_info "Ejecutando tests de humo rápidos..."

python3 -m pytest tests/ -k "test_imports or test_estructura" --tb=no -q || {
    log_warn "Tests de humo fallaron (no crítico)"
    echo "Tests de humo fallaron" >> "$ERRORS_LOG"
}

log_info "✓ Tests de humo completados"

# ─────────────────────────────────────────────────────────────
# 8. Mensaje final
# ─────────────────────────────────────────────────────────────
# Verificar si hubo errores no críticos
if [ -s "$ERRORS_LOG" ]; then
    log_warn "⚠ URA instalado con advertencias. Revisa $ERRORS_LOG"
    echo ""
    echo "Advertencias encontradas:"
    cat "$ERRORS_LOG"
else
    log_info "✓ URA instalado correctamente"
fi

echo ""
echo "Para ejecutar URA:"
echo "  cd $PROJECT_DIR"
echo "  source .venv/bin/activate"
echo "  python3 main_final.py"
echo ""

# Hacer el script ejecutable
chmod +x "$PROJECT_DIR/setup.sh"

log_info "✓ setup.sh es ahora ejecutable"
