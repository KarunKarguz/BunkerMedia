FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN addgroup --system bunker && adduser --system --ingroup bunker --home /app bunker

COPY . /app
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir . && \
    mkdir -p /app/media /app/logs /app/backups && \
    chown -R bunker:bunker /app

USER bunker

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=5)"

CMD ["bunker", "serve", "--host", "0.0.0.0", "--port", "8080"]
