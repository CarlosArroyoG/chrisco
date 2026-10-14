# Estado del proyecto

> Resumen vivo. Se actualiza al cerrar cada fase. Léelo en lugar de releer el código de fases anteriores.
> Última actualización: 2026-10-13, cierre de la **Fase 1**.

## Qué es

Plataforma para que los dueños de CHRISCO administren la renta de maquinaria pesada: qué equipos están rentados, cuánto cobrar, alertas de mantenimiento, licencias de operadores externos y bloqueo de equipos no disponibles. Los clientes (empresas verificadas, máx. 3 usuarios cada una) consultan el catálogo y solicitan equipo; la solicitud se envía por WhatsApp al agente de ventas.

**Flujo de renta (objetivo):** `solicitada` (equipo bloqueado 20 min) → `cotizada` → `apartada` (bloqueo 3 h hasta cumplir requisitos: contrato, licencia verificada, póliza, anticipo) → `confirmada` → `en renta` → `devuelta` → `cerrada/cobrada`. Si vence un bloqueo, el equipo vuelve a `libre`. Pagos por transferencia manual (el admin valida comprobante).

## Stack y decisiones

| Tema | Decisión | Motivo |
|---|---|---|
| Backend | FastAPI, SQLAlchemy 2 **síncrono**, Pydantic v2, Alembic | Dominio del usuario; escala sobra para decenas de equipos y ~100 usuarios |
| BD | PostgreSQL 17 (Docker, puerto host 5433) | Habrá restricciones de exclusión para evitar dobles reservas |
| Auth | JWT access (15 min) + refresh (7 días), Argon2, `token_version` para cerrar todas las sesiones | Sesión corta sin obligar a loguearse seguido en campo |
| Roles | `admin`, `ventas`, `operador`, `cliente` (enum `Role`) | Reglas en backend con `require_roles` |
| Frontend | Angular 22 standalone + signals, Tailwind 4 compilado, Vitest | Dominio del usuario |
| PWA | `@angular/service-worker` (solo en build de producción) | Reemplaza el `sw.js` manual del prototipo |
| API desde el front | Siempre bajo `/api`; el proxy de dev lo reescribe a `127.0.0.1:8010` | Sin CORS en producción con proxy inverso |
| Pruebas backend | Postgres real (`chrisco_test`) con migraciones reales | Las restricciones de BD se prueban de verdad |
| Reutilizado de terceros | `slowapi` (límite de intentos), `pwdlib[argon2]`, `PyJWT`, `@angular/pwa`, `angular-eslint` | Se revisó GitHub: no hay repo de renta de maquinaria reutilizable; la base de [fastapi/full-stack-fastapi-template](https://github.com/fastapi/full-stack-fastapi-template) sirvió de referencia de auth |

Aceptado: el refresh token vive en `localStorage` (el access token solo en memoria). Es el compromiso habitual de una PWA; se mitiga con vida corta, `token_version` y, más adelante, una CSP estricta en el despliegue.

## Cómo correrlo

Ver [`README.md`](../README.md). Usuario de desarrollo creado en la BD local: `admin@chrisco-pruebas.com` / `dev-admin-12345` (solo desarrollo).

## Inventario de lo construido (consultar antes de crear algo nuevo)

### Backend (`backend/`)

| Archivo | Qué hace |
|---|---|
| `app/core/config.py` | `Settings` / `get_settings()` desde entorno y `.env` (`database_url`, `secret_key`, duración de tokens, CORS, `rate_limit_enabled`) |
| `app/core/security.py` | `hash_password`, `verify_password` (tiempo constante aunque no exista el usuario), `create_token`, `decode_token` (valida tipo `access`/`refresh`) |
| `app/core/limiter.py` | Instancia `limiter` de slowapi |
| `app/db/base.py` | `Base` (convención de nombres de restricciones), `IdMixin` (UUID), `TimestampMixin` |
| `app/db/session.py` | `engine`, `SessionLocal`, `get_db` |
| `app/models/user.py` | `Role`, `User` (email único, `password_hash`, `is_active`, `token_version`). Todo modelo nuevo se importa en `app/models/__init__.py` |
| `app/schemas/auth.py` | `LoginRequest`, `RefreshRequest`, `TokenPair`, `UserOut` |
| `app/api/deps.py` | `DbSession`, `CurrentUser`, `get_current_user`, `load_user_from_token`, `require_roles(*roles)` |
| `app/api/routes/auth.py` | `POST /auth/login` (10/min), `POST /auth/refresh` (30/min), `GET /auth/me`, `POST /auth/logout-all` |
| `app/main.py` | App FastAPI, CORS, límite de intentos, `GET /health` |
| `app/cli.py` | `python -m app.cli create-user` (único camino para crear el primer admin) |
| `alembic/` | Migraciones; `env.py` toma la URL de `Settings` y los modelos de `app.models` |
| `tests/` | `conftest.py` (migra la BD de pruebas, limpia tablas, fixtures `client`, `db`, `make_user`, `login`) y `test_auth.py` (14 pruebas) |

### Frontend (`frontend/src/app/`)

| Archivo | Qué hace |
|---|---|
| `core/auth/auth.models.ts` | Tipos `Role`, `User`, `TokenPair`; `HOME_BY_ROLE` y `ROLE_LABEL` (fuente única de redirecciones y etiquetas) |
| `core/auth/auth.service.ts` | `AuthService`: `login`, `restoreSession` (al arrancar), `refresh` (peticiones simultáneas comparten una), `logout`; señales `user`, `isAuthenticated`; constante `API_URL` |
| `core/auth/auth.interceptor.ts` | Añade el bearer; ante 401 renueva y repite una vez; si falla, cierra sesión y va a `/login` |
| `core/auth/auth.guards.ts` | `authGuard`, `guestGuard`, `homeRedirectGuard`, `roleGuard(...roles)` |
| `shared/logo/logo.ts` | Componente `app-logo` (único lugar con el SVG del logo; `onDark`) |
| `layout/shell.ts` | Marco autenticado: barra superior, rol, botón Salir |
| `features/login/login.ts` | Pantalla de login (formulario reactivo, mensajes de error en español) |
| `features/{admin,operador,cliente}/*-home.ts` | Pantallas de inicio **provisionales** (anclas de ruta); se reemplazan en las fases 3 a 8 |
| `app.routes.ts` | `/login`, y bajo el shell: `/admin` (admin, ventas), `/operador`, `/cliente`; `''` redirige según rol |
| `public/` | Manifest (iconos `any` y `maskable` con el logo real) e iconos PNG |

## Fases

| # | Fase | Estado |
|---|---|---|
| 1 | Base: monorepo, API + BD, login con roles, Angular con guards y PWA, CI | ✅ Cerrada |
| 2 | Registro y aprobación de empresas (RFC, constancia fiscal, máx. 3 usuarios por empresa, correo verificado) | ⏳ Siguiente |
| 3 | Equipos: alta/edición/baja, categorías, especificaciones flexibles, tarifas, carga masiva CSV | Pendiente |
| 4 | Disponibilidad y bloqueos con vencimiento (20 min / 3 h), sin dobles reservas | Pendiente |
| 5 | Solicitud del cliente, requisitos y transporte, mensaje `wa.me` al agente de ventas | Pendiente |
| 6 | Cotización por partidas, apartado, pagos manuales y cobranza | Pendiente |
| 7 | Licencias de operadores externos: foto, lectura de QR, verificación (SICT), revisión manual de respaldo | Pendiente (investigar la consulta oficial antes) |
| 8 | Check-in/out con horómetro y foto; mantenimiento y alertas por correo; luego WhatsApp con API | Pendiente |

Para validar RFC/constancia (fase 2) evaluar la librería [satcfdi](https://pypi.org/project/satcfdi) (revisar licencia y código); el endpoint exacto del QR de la constancia **no está confirmado**: la revisión manual del admin es el respaldo obligatorio.

## Deuda técnica

Ninguna que afecte a lo construido. Pendientes conocidos, sin impacto hoy:

1. **Límite de intentos en memoria** (slowapi): correcto con una sola instancia de la API; con varias hay que moverlo a Redis. Resolver al desplegar más de una instancia.
2. **Aviso de slowapi** (`asyncio.iscoroutinefunction` obsoleto para Python 3.16): viene de la librería, no afecta a 3.12. Revisar al actualizar Python o cuando salga nueva versión.
3. **Despliegue** (Dockerfile del API, proxy inverso con `/api`, HTTPS, CSP, variables de producción): sin construir; se aborda antes del primer uso real.
4. **Instalación de la PWA sin probar**: el login, la sesión tras recargar, los guards de rol y el cierre de sesión se verificaron en Edge real (Playwright) en viewport móvil. Falta probar la instalación como app y el service worker, que solo se activan con el build de producción servido por HTTPS o `localhost`.

## Notas de entorno

- Los puertos 5432 y 8000 de esta máquina los usan otras apps del usuario (Postgres y una app Apache/Debian en Docker). Este proyecto usa **5433** (BD) y **8010** (API); el proxy apunta a `127.0.0.1` explícito porque `localhost` resuelve primero a IPv6 y llegaría a la otra app.
- El prototipo original está en `legacy/` (commit inicial `a054e2a`).
