# CHRISCO Go

Plataforma de renta y control de maquinaria pesada. Estado, decisiones y plan: [`docs/ESTADO.md`](docs/ESTADO.md). Reglas de trabajo: [`CLAUDE.md`](CLAUDE.md).

## Arranque en desarrollo

```bash
# 1. Base de datos (PostgreSQL en Docker, puerto 5433)
docker compose up -d db

# 2. Backend (puerto 8010)
cd backend
cp .env.example .env          # y rellena SECRET_KEY (ver el comentario del archivo)
                              # MAIL_BACKEND=console imprime los correos (enlaces de confirmación) en el log
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

# Extremo a extremo (navegador real; levanta su propia API, web y base de datos)
cd e2e && npm ci && E2E_CHANNEL=msedge npx playwright test    # en CI: npx playwright install chromium
```

Si cambias la API, regenera los tipos del frontend: `cd frontend && npm run api:gen`.

## Producción en Coolify

1. En Coolify: **New Resource → Docker Compose** y elige este repositorio. En *Docker Compose
   Location* pon `/docker-compose.coolify.yml`.
2. En el servicio **`web`** configura tu dominio (`https://go.tu-dominio.com`) con el puerto **80**.
   Coolify pone el HTTPS; no se publica ningún puerto desde el compose.
3. En *Environment Variables* llena las de `.env.coolify.example` (obligatorias: `POSTGRES_PASSWORD`,
   `SECRET_KEY`, `FRONTEND_URL` —el mismo dominio—, `MAIL_FROM` y `SMTP_HOST`).
4. **Deploy.** El API aplica las migraciones al arrancar. Crea el primer administrador desde la
   terminal del servicio `api` en Coolify:
   `python -m app.cli create-user --email tu@correo.com --name "Tu Nombre" --role admin`
5. Respaldos: en Coolify programa un *Scheduled Backup* del volumen de `db` (o `pg_dump`) y del
   volumen `uploads` (constancias, licencias, comprobantes y fotos: sin ellos se pierden).

## Producción (un servidor propio con Docker, sin Coolify)

```bash
cp .env.production.example .env.production      # llenar: DOMAIN, POSTGRES_PASSWORD, SECRET_KEY, SMTP...
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
docker compose -f docker-compose.prod.yml --env-file .env.production exec api \
    python -m app.cli create-user --email tu@correo.com --name "Tu Nombre" --role admin
```

- Solo el contenedor `web` (Caddy) publica los puertos 80/443; obtiene y renueva el certificado
  HTTPS solo. La API y la base de datos quedan en la red interna.
- El API **no arranca** en producción con valores de desarrollo (correo que no sea SMTP, URL sin
  https, CORS con http, límite de intentos apagado) y no publica `/docs`.
- El contenedor `tareas` vence las reservas cada minuto y manda las alertas de mantenimiento por
  correo cada día a las 8:00.
- Respaldo (base de datos + archivos privados): `./scripts/respaldo.sh ./respaldos`, programado a
  diario y copiado fuera del servidor.
- Actualizar: `git pull` y repetir el `up -d --build`; el API aplica las migraciones al arrancar.

El prototipo original (HTML estático) está en `legacy/` solo como referencia.
