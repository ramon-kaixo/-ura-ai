FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl jq rsync \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir requests pandas numpy scikit-learn
WORKDIR /sandbox
COPY Enjambre/ /sandbox/Enjambre/
COPY scripts/ /sandbox/scripts/
RUN chmod +x /sandbox/scripts/*.sh /sandbox/Enjambre/*.sh /sandbox/Enjambre/buzos/*.sh
CMD ["bash", "/sandbox/scripts/ejecutar_aprendizaje.sh"]
