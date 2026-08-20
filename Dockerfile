# Build stage: instala deps de build y prepara el paquete
FROM python:3.12-slim AS builder
WORKDIR /build
COPY pyproject.toml .
RUN pip install --no-cache-dir build
RUN python -m build --wheel

# Runtime stage: solo runtime deps, sin herramientas de build
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
COPY --from=builder /build/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl
COPY motor/ motor/
COPY knowledge/ knowledge/
COPY scripts/ scripts/
EXPOSE 8000
CMD ["python", "-m", "motor.assistant.main"]