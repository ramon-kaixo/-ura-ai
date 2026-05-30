FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl git pandoc texlive-latex-base \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir mkdocs pdoc
WORKDIR /sandbox
COPY scripts/ /sandbox/scripts/
RUN chmod +x /sandbox/scripts/*.sh
CMD ["bash", "/sandbox/scripts/ejecutar_documentacion.sh"]
