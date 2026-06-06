FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl jq nmap openssh-client \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /sandbox
COPY scripts/ /sandbox/scripts/
RUN chmod +x /sandbox/scripts/*.sh
CMD ["bash", "/sandbox/scripts/ejecutar_seguridad.sh"]
