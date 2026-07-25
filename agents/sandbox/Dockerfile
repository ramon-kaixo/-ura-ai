FROM python:3.12-slim

WORKDIR /agent
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    rm -rf /root/.cache/pip

COPY *.py /agent/
RUN chmod +x /agent/*.py

ENTRYPOINT ["python3", "/agent/agent_runner.py"]
