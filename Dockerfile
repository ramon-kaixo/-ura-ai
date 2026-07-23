FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install -e ".[dev]"
COPY motor/ motor/
COPY knowledge/ knowledge/
COPY scripts/ scripts/
EXPOSE 8000
CMD ["python", "-m", "motor.assistant.main"]
