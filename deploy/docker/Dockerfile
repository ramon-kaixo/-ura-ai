# URA - Dockerfile
FROM python:3.12-slim

# Establecer directorio de trabajo
WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    curl \
    libgl1 \
    libglib2.0-0 \
    x11-apps \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements.txt
COPY requirements.txt .

# Crear requirements sin PyAudio para Docker (PyQt5 sí se necesita para X11)
RUN grep -v PyAudio requirements.txt > requirements-docker.txt

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements-docker.txt

# Copiar código fuente
COPY . .

# Crear directorios necesarios
RUN mkdir -p /app/logs /app/core/data

# Exponer puerto si es necesario (para futura API web)
EXPOSE 5000

# Establecer variables de entorno por defecto
ENV PYTHONUNBUFFERED=1
ENV OLLAMA_HOST=host.docker.internal
ENV OLLAMA_PORT=11434
ENV REDIS_HOST=host.docker.internal
ENV REDIS_PORT=6379
ENV LOG_LEVEL=INFO
ENV SECURITY_MODE=APPLE

# Comando de arranque
CMD ["python", "main_final.py"]
