# API de CHRISCO Go. Construir desde la carpeta backend/:  docker build -t chrisco-api .
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

COPY --from=ghcr.io/astral-sh/uv:0.12.15 /uv /usr/local/bin/uv

WORKDIR /app

# Dependencias primero: la capa se reutiliza mientras no cambien pyproject.toml / uv.lock.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY scripts ./scripts

# Sin privilegios: el proceso solo escribe en /data (archivos privados subidos).
RUN useradd --system --create-home chrisco \
    && mkdir -p /data/uploads \
    && chown -R chrisco /data
USER chrisco
ENV UPLOADS_DIR=/data/uploads

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"

# Migra la base y arranca. `--proxy-headers` toma la IP real del cliente del proxy (para el límite
# de intentos); el puerto no se publica fuera de la red de Docker, solo lo alcanza el proxy.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]
