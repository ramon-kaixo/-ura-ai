FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl jq \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir requests
WORKDIR /sandbox
COPY scripts/ /sandbox/scripts/
COPY proyecto_prueba/ /sandbox/proyecto_prueba/
RUN chmod +x /sandbox/scripts/*.sh
CMD ["bash"]
