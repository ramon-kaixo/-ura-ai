FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl git jq \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir requests pyyaml
WORKDIR /sandbox
COPY scripts/ /sandbox/scripts/
RUN chmod +x /sandbox/scripts/*.sh
CMD ["bash", "/sandbox/scripts/ejecutar_mantenimiento.sh"]
