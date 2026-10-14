# Estado del proyecto

> Resumen vivo. Se actualiza al cerrar cada fase. Léelo en lugar de releer el código de fases anteriores.
> Última actualización: 2026-10-13, cierre de la **Fase 2**.

## Qué es

Plataforma para que los dueños de CHRISCO administren la renta de maquinaria pesada: qué equipos están rentados, cuánto cobrar, alertas de mantenimiento, licencias de operadores externos y bloqueo de equipos no disponibles. Los clientes (empresas verificadas, máx. 3 usuarios cada una) consultan el catálogo y solicitan equipo; la solicitud se envía por WhatsApp al agente de ventas.

**Flujo de renta (objetivo):** `solicitada` (equipo bloqueado 20 min) → `cotizada` → `apartada` (bloqueo 3 h hasta cumplir requisitos: contrato, licencia verificada, póliza, anticipo) → `confirmada` → `en renta` → `devuelta` → `cerrada/cobrada`. Si vence un bloqueo, el equipo vuelve a `libre`. Pagos por transferencia manual (el admin valida comprobante). Se cobra por hora, por día, flete de lowboy, trailer, combustible y operador (partidas configurables).

## Stack y decisiones

| Tema | Decisión | Motivo |
|---|---|---|
| Backend | FastAPI, SQLAlchemy 2 **síncrono**, Pydantic v2, Alembic | Dominio del usuario; la escala (decenas de equipos, ~100 usuarios) no exige async |
| BD | PostgreSQL 17 (Docker, puerto host 5433) | Restricciones y bloqueos de fila; habrá restricciones de exclusión para evitar dobles reservas |
| Auth | JWT access (15 min) + refresh (7 días), Argon2, `token_version` para invalidar sesiones | Sesión corta sin obligar a loguearse seguido en campo |
| Enlaces por correo | Mismos JWT con `type` propio: `verify_email` (48 h), `invite` (7 d), `reset_password` (60 min); un solo uso gracias a `token_version` | Sin tablas extra |
| Roles | `admin`, `ventas`, `operador`, `cliente`. El personal se crea por CLI; los clientes solo por registro | Reglas en backend (`require_roles`, `ApprovedClientUser`, `CompanyOwner`) |
| Cliente ⇔ empresa | Restricción CHECK en BD: `role='cliente'` si y solo si `empresa_id` no es nulo | Integridad garantizada aunque falle el código |
| Límite de usuarios | 3 activos por empresa (`max_users_per_company`), con `SELECT … FOR UPDATE` sobre la empresa | Probado con concurrencia real (la prueba falla sin el bloqueo) |
| Errores de negocio | Servicios lanzan `DomainError` (`Conflict`, `Forbidden`, `InvalidInput`, `NotFound`, `Unauthorized`); `main.py` los convierte a HTTP | Las rutas quedan delgadas y los servicios no conocen HTTP |
| Archivos | `PrivateStorage` en disco (`uploads/`), claves UUID, solo PDF validado por contenido (`%PDF-`) y tamaño; se sirven solo por endpoints con permiso | Único punto a cambiar si algún día se pasa a S3/R2 |
| Correo | `Mailer` con 3 implementaciones: `console` (log), `file` (JSONL, para E2E), `smtp` | Se elige con `MAIL_BACKEND`; las pruebas lo sustituyen por un buzón en memoria |
| Frontend | Angular 22 standalone + signals + OnPush, Tailwind 4 compilado, Vitest | Dominio del usuario |
| Tipos de la API | Se **generan** del OpenAPI de FastAPI (`npm run api:gen`, `@hey-api/openapi-ts`) y CI falla si no están al día | Frente y backend no se desincronizan; sin tipos duplicados a mano |
| PWA | `@angular/service-worker` (solo build de producción); íconos `any` y `maskable` con el logo real | Reemplaza el `sw.js` manual del prototipo |
| Pruebas | Backend: Postgres real con migraciones reales. E2E: Playwright en navegador real con su propia BD (`chrisco_e2e`) y puertos (8011/4201) | Las reglas de BD y los flujos completos se prueban de verdad |
| Reutilizado de terceros | `slowapi`, `pwdlib[argon2]`, `PyJWT`, `python-multipart`, `@angular/pwa`, `angular-eslint`, `@hey-api/openapi-ts`, `@playwright/test` | Se revisó GitHub/PyPI: no hay repo de renta de maquinaria reutilizable; [fastapi/full-stack-fastapi-template](https://github.com/fastapi/full-stack-fastapi-template) sirvió de referencia de auth |
| Verificación fiscal | **Manual** por el admin (RFC con formato válido + constancia PDF). No se automatiza contra el SAT | El endpoint del QR de la constancia no está documentado oficialmente; no se promete lo que no se confirmó |

Aceptado: el refresh token vive en `localStorage` (el access token solo en memoria). Es el compromiso habitual de una PWA; se mitiga con vida corta, `token_version` y, más adelante, una CSP estricta en el despliegue.

## Cómo correrlo

Ver [`README.md`](../README.md). Usuario de desarrollo en la BD local: `admin@chrisco-pruebas.com` / `dev-admin-12345` (solo desarrollo).

## Inventario de lo construido (consultar antes de crear algo nuevo)

### Backend (`backend/app/`)

| Archivo | Qué hace |
|---|---|
| `core/config.py` | `Settings` / `get_settings()`: BD, secreto, duración de tokens, CORS, `frontend_url`, `uploads_dir`, `max_upload_mb`, correo (`mail_*`, `smtp_*`), `max_users_per_company`, `rate_limit_enabled` |
| `core/security.py` | `hash_password`, `verify_password` (tiempo constante aunque no exista el usuario), `create_token` / `decode_token` (tipos `access`, `refresh`, `verify_email`, `invite`, `reset_password`), `MIN_PASSWORD_LENGTH` |
| `core/errors.py` | `DomainError` y subclases; `domain_error_handler` |
| `core/rfc.py` | `normalize_rfc` (formato de persona moral/física, fecha válida, rechaza RFC genéricos del SAT) |
| `core/limiter.py` | Instancia `limiter` de slowapi |
| `db/base.py`, `db/session.py` | `Base` (nombres de restricciones), `IdMixin` (UUID), `TimestampMixin`; `engine`, `SessionLocal`, `get_db` |
| `models/user.py` | `Role`, `User` (+ `email_verified_at`, `empresa_id`, `is_company_owner`, CHECK cliente⇔empresa) |
| `models/empresa.py` | `EmpresaStatus`, `Empresa` (RFC único, estado, motivo de rechazo, constancia, revisor); propiedades `owner` y `active_users`. Todo modelo nuevo se importa en `models/__init__.py` |
| `schemas/auth.py` | `Password`, `LoginRequest`, `RefreshRequest`, `TokenRequest`, `EmailRequest`, `SetPasswordRequest`, `TokenPair`, `UserOut` |
| `schemas/empresa.py` | `CompanyData` (valida RFC y normaliza el sitio web), `RegistroEmpresaForm`, `InviteUserRequest`, `RejectRequest`, `CompanyUserOut`, `EmpresaOut`, `EmpresaDetailOut`, `EmpresaListItem`, `empresa_detail()` |
| `schemas/common.py` | `MessageOut` |
| `services/accounts.py` | `user_from_token`, `get_by_email`, `unusable_password_hash`, `authenticate` (exige correo verificado), `verify_email`, `set_password_from_token` (invitación y recuperación) |
| `services/empresas.py` | `register_company`, `get_empresa`, `active_user_count`, `approve`, `reject`, `resubmit`, `invite_user` (con bloqueo y reactivación de bajas), `remove_user` |
| `services/storage.py` | `PrivateStorage` (`save_pdf`, `path`, `delete`), `get_storage`, `read_pdf_upload` |
| `services/mailer.py` | `Mail`, `Mailer`, `ConsoleMailer`, `FileMailer`, `SmtpMailer`, `get_mailer` |
| `services/notifications.py` | Un correo por función: `verification_mail`, `invitation_mail`, `password_reset_mail`, `company_approved_mail`, `company_rejected_mail` |
| `api/deps.py` | `DbSession`, `MailerDep`, `StorageDep`, `CurrentUser`, `require_roles`, `company_of`, `ClientUser`, `ApprovedClientUser`, `CompanyOwner`, `AdminUser`, `StaffUser` |
| `api/forms.py` | `CompanyForm`, `RegistroForm`: dependencias de formularios multipart (FastAPI no permite un modelo `Form()` junto a un archivo) |
| `api/routes/auth.py` | `POST /auth/login`, `/refresh`, `/logout-all`, `/verify-email`, `/resend-verification`, `/forgot-password`, `/reset-password`, `/accept-invite`; `GET /auth/me`. Los de correo responden 204 siempre (no revelan si el correo existe) |
| `api/routes/empresas.py` | `POST /empresa/registro` (público, 5/hora), `GET/PUT /empresa/me`, `POST /empresa/me/usuarios`, `DELETE /empresa/me/usuarios/{id}` |
| `api/routes/admin_empresas.py` | `GET /admin/empresas?status_filter=`, `GET /admin/empresas/{id}`, `GET …/constancia` (admin y ventas); `POST …/aprobar`, `…/rechazar` (solo admin) |
| `cli.py` | `python -m app.cli create-user` (personal: admin, ventas, operador) |
| `export_openapi.py` | Escribe el OpenAPI para generar los tipos del frontend |
| `alembic/` | Migraciones (`8469e6e1a421` users, `7156d33208d8` empresas y verificación) |
| `tests/` | 69 pruebas: `test_auth`, `test_empresas`, `test_mailer`, `test_concurrencia`; `conftest.py` (migra la BD de pruebas, buzón en memoria, fixtures `register`, `approved_owner`, `make_user`, `login`…), `probes.py` (rutas solo de prueba) |

### Frontend (`frontend/src/app/`)

| Archivo | Qué hace |
|---|---|
| `core/api/generated/` | Tipos generados del OpenAPI (**no editar**; `npm run api:gen`) |
| `core/api/models.ts` | Nombres cortos de los tipos generados (`User`, `Role`, `EmpresaDetail`…) |
| `core/api/errors.ts` | `apiErrorMessage`: errores de la API → mensaje en español |
| `core/api/form-data.ts` | `toFormData` (campos + PDF) |
| `core/auth/*` | `AuthService` (login, sesión, `refresh`, `verifyEmail`, `resendVerification`, `forgotPassword`, `setPassword`), interceptor con renovación, guards (`authGuard`, `guestGuard`, `homeRedirectGuard`, `roleGuard`), `HOME_BY_ROLE`, `ROLE_LABEL` |
| `core/empresa/empresa.service.ts` | `EmpresaService`: `register`, `mine`, `resubmit`, `inviteUser`, `removeUser` |
| `shared/` | `Logo`, `AuthCard` (contenedor de pantallas públicas), `StatusBadge` |
| `styles.css` | Utilidades de interfaz únicas: `card`, `label`, `input`, `btn`, `btn-primary`, `btn-secondary`, `btn-danger`, `alert-error`, `alert-ok`, `link` |
| `layout/shell.ts` | Marco autenticado (barra superior, rol, Salir) |
| `features/login/` | Login (con reenvío de confirmación y enlaces a registro/recuperación) |
| `features/auth/` | `Register`, `VerifyEmail`, `SetPassword` (invitación y recuperación, según `data.mode`), `ForgotPassword` |
| `features/cliente/` | `ClienteHome` (estado de la empresa), `ResubmitForm` (tras rechazo), `CompanyTeam` (usuarios: invitar y dar de baja) |
| `features/admin/` | `AdminHome` (empresas con filtro por estado), `EmpresaReview` (detalle, constancia, aprobar/rechazar), `AdminEmpresasService` |
| `features/operador/operador-home.ts` | Pantalla **provisional** (ancla de ruta) hasta la fase 8 |
| `app.routes.ts` | Públicas: `/login`, `/registro`, `/olvide-contrasena`, `/verificar-correo`, `/aceptar-invitacion`, `/recuperar-contrasena`. Con sesión: `/admin`, `/admin/empresas/:id`, `/operador`, `/cliente` |

### E2E (`e2e/`)

Playwright: `playwright.config.ts` (levanta API en 8011 y Angular en 4201), `global-setup.ts` + `scripts/prepare_db.py` (BD `chrisco_e2e` vacía y migrada, 2 usuarios del personal), `tests/empresas.spec.ts` (14 pasos: registro → confirmación → revisión → rechazo → reenvío → aprobación → invitación → máximo de 3 → recuperación de contraseña), `tests/mail.ts` (lee los enlaces del buzón JSONL). Local: `E2E_CHANNEL=msedge npx playwright test`.

## Fases

| # | Fase | Estado |
|---|---|---|
| 1 | Base: monorepo, API + BD, login con roles, Angular con guards y PWA, CI | ✅ |
| 2 | Registro y aprobación de empresas (RFC, constancia, máx. 3 usuarios, correo verificado), recuperación de contraseña, E2E | ✅ Cerrada |
| 3 | Equipos: alta/edición/baja, categorías, especificaciones flexibles, tarifas, carga masiva CSV, fotos | ⏳ Siguiente |
| 4 | Disponibilidad y bloqueos con vencimiento (20 min / 3 h), sin dobles reservas (restricción de exclusión en PostgreSQL) | Pendiente |
| 5 | Solicitud del cliente, requisitos y transporte, mensaje `wa.me` al agente de ventas | Pendiente |
| 6 | Cotización por partidas, apartado, pagos manuales y cobranza | Pendiente |
| 7 | Licencias de operadores externos: foto, lectura de QR, verificación (SICT), revisión manual de respaldo | Pendiente (investigar la consulta oficial antes) |
| 8 | Check-in/out con horómetro y foto; mantenimiento y alertas por correo; luego WhatsApp con API | Pendiente |
| 9 | Gestión de personal desde la interfaz (hoy solo CLI), despliegue y endurecimiento | Pendiente |

## Deuda técnica

Ninguna que afecte a lo construido. Pendientes conocidos, sin impacto hoy:

1. **Límite de intentos en memoria** (slowapi): correcto con una sola instancia de la API; con varias hay que moverlo a Redis. Resolver al desplegar más de una instancia.
2. **Aviso de slowapi** (`asyncio.iscoroutinefunction` obsoleto para Python 3.16): viene de la librería, no afecta a 3.12. Revisar al actualizar Python o cuando salga nueva versión.
3. **Despliegue** (Dockerfile del API, proxy inverso con `/api`, HTTPS, CSP, variables de producción, copias de seguridad de BD y de `uploads/`): sin construir; fase 9.
4. **Instalación de la PWA sin probar**: login, sesión, guards y todos los flujos de la fase 2 se verifican en Edge real; falta probar la instalación como app y el service worker, que solo se activan con el build de producción servido por HTTPS o `localhost`.
5. **Archivos en disco local**: suficiente para un servidor; con varias instancias o respaldo automático conviene objeto (S3/R2) cambiando solo `PrivateStorage`.
6. **Sin paginación** en la lista de empresas: aceptable para decenas; revisar si crece.
7. **E2E en CI sin ejecutar todavía en GitHub** (el trabajo `e2e` está escrito y la suite pasa en local; no hay remoto configurado). Confirmar en la primera ejecución real.

## Notas de entorno

- Los puertos 5432 y 8000 de esta máquina los usan otras apps del usuario (Postgres y una app Apache/Debian en Docker). Este proyecto usa **5433** (BD), **8010** (API de desarrollo) y **8011/4201** (E2E); el proxy apunta a `127.0.0.1` explícito porque `localhost` resuelve primero a IPv6 y llegaría a la otra app.
- Si el volumen de Postgres ya existía antes de la Fase 2, las BD `chrisco_test` y `chrisco_e2e` se crean solas por `docker/init-databases.sql` solo en volúmenes nuevos; en uno viejo: `docker compose exec db psql -U chrisco -d postgres -c "CREATE DATABASE chrisco_e2e OWNER chrisco"` (el script de E2E también la crea si falta).
- El prototipo original está en `legacy/` (commit inicial `a054e2a`).
