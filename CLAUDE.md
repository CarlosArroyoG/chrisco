# CHRISCO Go: reglas de trabajo

Plataforma de renta de maquinaria pesada para los dueños de CHRISCO (administración, cobro, mantenimiento, licencias, bloqueo de equipos). Stack: **FastAPI + PostgreSQL** (backend) y **Angular + Tailwind** (frontend PWA).

## Antes de tocar nada

1. **Lee `docs/ESTADO.md`.** Es el resumen vivo de lo construido, dónde está cada cosa, las decisiones y la deuda técnica. No releas fases anteriores: confía en ese archivo.
2. **Busca antes de escribir.** Antes de crear una función, servicio, componente, esquema o helper, búscalo en el código (Grep) y en el inventario de `ESTADO.md`. Si existe algo equivalente, reutilízalo o extiéndelo. No dupliques lógica.
3. **Busca antes de construir.** Para una capacidad nueva y no trivial, revisa primero si hay una librería o repo mantenido que la resuelva (GitHub, PyPI, npm). Comprueba licencia (evita AGPL) y mantenimiento antes de añadirla.

## Cómo se cierra una fase (cero deuda técnica)

Una fase solo está terminada si TODO esto se cumple:

- Backend: `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .` y `uv run mypy app` pasan.
- Frontend: `npx ng test --watch=false`, `npx ng lint` y `npx ng build` pasan.
- Hay migración de Alembic para cualquier cambio de modelo y las pruebas la aplican.
- Las reglas de negocio se validan **en el backend**; el frontend solo las refleja.
- `docs/ESTADO.md` está actualizado: inventario, decisiones, fase siguiente.
- Lo que no se pudo terminar queda escrito en la sección **Deuda técnica** de `ESTADO.md`, con motivo. Nunca se esconde. Idealmente esa sección está vacía.
- Commit en git con mensaje claro.

## Convenciones

- Código, comentarios y textos de interfaz en **español**; identificadores en inglés (excepto términos de dominio como `renta`, `equipo`).
- Backend: SQLAlchemy 2 síncrono, Pydantic v2, rutas en `app/api/routes/`, dependencias de acceso en `app/api/deps.py` (`require_roles`). Secretos solo por entorno (`.env`, ignorado por git).
- Frontend: Angular standalone + signals + `OnPush`, rutas con carga diferida por feature, API siempre bajo `/api` (constante `API_URL`). Tailwind compilado (tokens `chrisco-*` en `styles.css`).
- Archivos sensibles (licencias, constancias fiscales): almacenamiento privado, nunca públicos.
- No toques la carpeta `legacy/` (prototipo original, solo referencia visual).

## Entorno de esta máquina

- Python 3.12 (`uv run ...`), Node 24, Docker. `python` a secas apunta a un acceso directo de la Store; usa `uv run` o `py -3.12`.
- PostgreSQL de desarrollo: `docker compose up -d db` (puerto host **5433**; el 5432 y el 8000 los usan otras apps del usuario, no las toques).
- API local: puerto **8010** en `127.0.0.1`. Frontend: `ng serve` en 4200 con proxy `/api` → 8010.
- En PowerShell 5.1, `Set-Content -Encoding utf8` y `Get-Content` sin `-Encoding` corrompen tildes: edita archivos con las herramientas de edición, no con reemplazos de PowerShell.
