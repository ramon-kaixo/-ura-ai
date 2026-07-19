FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/base.txt requirements/
RUN pip install --no-cache-dir -r requirements/base.txt

COPY . .

ENV URA_DATA_DIR=/data
ENV URA_HOST=0.0.0.0
ENV URA_PORT=8000

EXPOSE 8000

VOLUME ["/data"]

CMD ["uvicorn", "motor.assistant.main:app", "--host", "0.0.0.0", "--port", "8000"]
