# CHRISCO Go

Plataforma de renta y control de maquinaria pesada. Estado, decisiones y plan: [`docs/ESTADO.md`](docs/ESTADO.md). Reglas de trabajo: [`CLAUDE.md`](CLAUDE.md).

## Arranque en desarrollo

```bash
# 1. Base de datos (PostgreSQL en Docker, puerto 5433)
docker compose up -d db

# 2. Backend (puerto 8010)
cd backend
cp .env.example .env          # y rellena SECRET_KEY (ver el comentario del archivo)
uv sync
uv run alembic upgrade head
uv run python -m app.cli create-user --email tu@correo.com --name "Tu Nombre" --role admin
uv run uvicorn app.main:app --host 127.0.0.1 --port 8010 --reload

# 3. Frontend (puerto 4200, proxy /api -> 8010)
cd frontend
npm install
npx ng serve
```

Documentación interactiva de la API: http://127.0.0.1:8010/docs

## Pruebas

```bash
cd backend  && uv run pytest && uv run ruff check . && uv run mypy app
cd frontend && npx ng test --watch=false && npx ng lint && npx ng build
```

El prototipo original (HTML estático) está en `legacy/` solo como referencia.
