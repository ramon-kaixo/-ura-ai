# Arena de Mejora Continua - Herramientas QA PINNED
# Base: python:3.12-slim (ARM64 compatible)

FROM python:3.12-slim

# Instalar dependencias del sistema para herramientas
RUN apt-get update && apt-get install -y \
    # shellcheck (auditoría de scripts bash)
    shellcheck \
    # hadolint (linter de Dockerfiles) - instalado vía descarga directa
    wget \
    # yamllint (validación YAML)
    yamllint \
    # trivy (vulnerabilidades + secretos + configs)
    wget gnupg lsb-release \
    # Memray (profiler de memoria)
    build-essential \
    # py-spy (profiler runtime)
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Instalar hadolint (versión fija)
RUN wget -O /usr/local/bin/hadolint https://github.com/hadolint/hadolint/releases/download/v2.12.0/hadolint-Linux-arm64 \
    && chmod +x /usr/local/bin/hadolint

# Instalar trivy (versión fija)
RUN wget -qO - https://aquasecurity.github.io/trivy-repo/deb/public.key | gpg --dearmor -o /usr/share/keyrings/trivy.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/trivy.gpg] https://aquasecurity.github.io/trivy-repo/deb $(lsb_release -sc) main" | tee -a /etc/apt/sources.list.d/trivy.list \
    && apt-get update && apt-get install -y trivy \
    && rm -rf /var/lib/apt/lists/*

# Instalar uv (gestor de paquetes rápido, versiones fijadas)
RUN pip install --no-cache-dir uv==0.1.40

# Copiar requirements PINNED
COPY requirements-arena.txt /tmp/

# Copiar test script
COPY test_arena.sh /test_arena.sh

# Instalar dependencias Python con uv (reproducible)
RUN uv pip install --system -r /tmp/requirements-arena.txt

# Directorio de trabajo
WORKDIR /workspace

# Configuración de seguridad
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Comando por defecto (se sobrescribe en docker-compose)
CMD ["sh", "-c", "exec tail -f /dev/null"]
