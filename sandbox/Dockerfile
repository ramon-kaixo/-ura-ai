FROM python:3.11-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    jq \
    && rm -rf /var/lib/apt/lists/*
COPY sandbox_client.py /app/sandbox_client.py
ENTRYPOINT ["python3", "/app/sandbox_client.py"]
