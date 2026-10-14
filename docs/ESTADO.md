# Estado del proyecto

> Resumen vivo. Se actualiza al cerrar cada fase. Léelo en lugar de releer el código de fases anteriores.
> Última actualización: 2026-10-14, cierre de la **Fase 6a** (cotización y apartado).

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
| Bloqueos | Una sola tabla `bloqueos` por equipo y periodo `[desde, hasta)` (`TSTZRANGE`). Tipos: `solicitud` (20 min), `apartado` (3 h), `renta`, `mantenimiento`, `manual`. **`EXCLUDE USING gist` sobre equipo + periodo donde `estado='activo'`**: dos bloqueos activos del mismo equipo no pueden traslaparse, ni con peticiones simultáneas (requiere la extensión `btree_gist`) | La garantía contra dobles reservas la da la base de datos, no el código |
| Vencimientos | Las reservas provisionales llevan `vence_en`. Las lecturas ignoran las vencidas con solo comparar la fecha; antes de insertar se marcan `expirado` las caducadas del equipo. **No hay proceso en segundo plano**; `python -m app.cli expire-holds` limpia el estado (apto para cron) | La corrección no depende de que un job corra a tiempo |
| Hora | La hora de referencia es la de PostgreSQL (`now()`), no la de cada instancia de la API | Varias instancias no se desfasan |
| Situación del equipo | `estado_actual` (`libre`, `bloqueado`, `rentado`, `mantenimiento`, `baja`) se **calcula** de los bloqueos vigentes; el estado administrativo (`status`) sigue aparte | Una sola fuente de verdad |
| Privacidad de la disponibilidad | Un cliente ve *cuándo* está ocupado un equipo, nunca por qué ni de quién | |
| Renta | Una sola entidad `Renta` con el ciclo completo (`solicitada → cotizada → apartada → confirmada → en_renta → devuelta → cerrada`, más `vencida`, `cancelada`, `rechazada`). La fase 5 solo crea `solicitada` y la lleva a `vencida` o `cancelada`; la fase 6 sigue desde ahí | No se rehace el modelo ni se altera el enum después |
| Solicitud | Reserva el equipo 20 min (`place_hold(commit=False)`) y guarda la renta **en la misma transacción**: o quedan las dos o ninguna | Sin reservas huérfanas |
| Folio | `CHR-{año local}-{n:05d}` desde una secuencia de PostgreSQL | No se salta ni repite con solicitudes simultáneas |
| Requisitos | Reglas puras en `services/requisitos.py` según equipo, operador (CHRISCO/cliente) y traslado (entrega/recoge). Se guardan en la renta **tal como se mostraron** (JSONB) | Cambiar las reglas no reescribe solicitudes viejas |
| WhatsApp | Sin API: enlace `wa.me` con el mensaje escrito; el número de ventas sale de `SALES_WHATSAPP_NUMBER` (solo dígitos con país). Si no está configurado se entrega el mensaje para copiarlo | Gratis y funciona desde el primer día |
| Anti-acaparamiento | Máx. 3 solicitudes abiertas por empresa (`max_active_requests_per_company`), con bloqueo de la fila de la empresa | Un cliente no puede apartar toda la flota con reservas de 20 min |
| Vencimiento de solicitudes | `rentas.expire_stale` vence las reservas caducadas y pasa a `vencida` las solicitudes que dependían de ellas; se ejecuta al consultar y desde `expire-holds` | Sin proceso en segundo plano |
| Acceso a rentas | El cliente ve y cancela solo las de su empresa (de otra empresa, «no existe» y no «prohibido»); admin y ventas ven y cancelan todas | No se revela qué folios existen |
| Cotización | `Cotizacion` + `CotizacionPartida` (concepto, descripción, cantidad, unidad, precio, importe). **Todo el dinero lo calcula el servidor** con `Decimal` y redondeo a centavos (mitad hacia arriba): IVA (`IVA_RATE`, 16 %) y anticipo (30 % por defecto, editable). `POST …/cotizacion/calcular` usa la misma función que guarda, así la vista previa de la interfaz nunca difiere | Sin aritmética de dinero duplicada en TypeScript |
| Versiones | Cada cotización nueva deja la anterior `reemplazada`; un índice único parcial garantiza **una sola cotización viva** (vigente o aceptada) por renta. Vigencia por defecto 24 h; pasada, `vencida` | Historial sin ambigüedad |
| Aceptar | El cliente acepta: si su reserva de 20 min sigue viva se promueve a **apartado de 3 h**; si ya venció, se intenta apartar de nuevo y falla con un mensaje claro si otra empresa se adelantó. Todo en una transacción; con aceptaciones simultáneas gana una sola (la restricción de exclusión) | Nadie aparta lo que otro ya apartó |
| Quién responde | Ventas debe cotizar **dentro de los 20 min** de la reserva (si no, la solicitud vence). Una solicitud cotizada puede aceptarse aunque haya pasado ese tiempo, si el equipo sigue libre | Equilibra urgencia comercial y no perder ventas |
| Cierres | Ventas puede rechazar una solicitud con motivo (le llega al cliente); el cliente puede rechazar la cotización (la solicitud queda `cancelada`). Siempre se libera el equipo y se guarda `motivo_cierre` | Trazabilidad |
| Python | **3.12 fijado** (`backend/.python-version`); `uv` elegía 3.14 por su cuenta y local/CI deben coincidir | Reproducibilidad |
| Especificaciones | Cada categoría define sus campos (`spec_fields`, JSONB: texto, número, sí/no, opciones, obligatoria, unidad); cada equipo guarda `specs` validados contra ellos | Tipos de maquinaria nuevos sin cambiar código. Cambiar los campos de una categoría **no reescribe** equipos ya guardados |
| Estado del equipo | `activo`, `mantenimiento`, `baja` (administrativo); si está rentado o bloqueado se calcula de los bloqueos | |
| Fotos | Pillow: se recodifican a JPEG en dos tamaños (1600 y 480 px), sin metadatos EXIF; máx. 10 por equipo y 40 MP. Se sirven **sin sesión** por UUID | Un `<img>` no puede enviar `Authorization`; son material de catálogo, no datos sensibles |
| Catálogo | Vista para clientes aprobados y personal: solo equipos `activo`, sin número de serie, horómetro ni notas | Lo interno no sale por la API de clientes |
| Importación CSV | Todo o nada, con vista previa (`dry_run=true` por defecto) y reporte por fila; acepta coma, punto y coma o tabulador, UTF-8 o ANSI de Excel | Los datos reales vienen de Excel |
| Salidas vs entradas | Los esquemas `*Out` no heredan las validaciones de los `*In` | Un registro viejo que no cumpla las reglas nuevas no debe tumbar un listado completo |
| Archivos | `PrivateStorage` en disco (`uploads/`), claves UUID (PDF `.pdf`, fotos `.jpg` y `-thumb.jpg`); las constancias se sirven solo por endpoints con permiso | Único punto a cambiar si algún día se pasa a S3/R2 |
| Correo | `Mailer` con 3 implementaciones: `console` (log), `file` (JSONL, para E2E), `smtp` | Se elige con `MAIL_BACKEND`; las pruebas lo sustituyen por un buzón en memoria |
| Frontend | Angular 22 standalone + signals + OnPush, Tailwind 4 compilado, Vitest | Dominio del usuario |
| Tipos de la API | Se **generan** del OpenAPI de FastAPI (`npm run api:gen`, `@hey-api/openapi-ts`) y CI falla si no están al día | Frente y backend no se desincronizan; sin tipos duplicados a mano |
| PWA | `@angular/service-worker` (solo build de producción); íconos `any` y `maskable` con el logo real | Reemplaza el `sw.js` manual del prototipo |
| Pruebas | Backend: Postgres real con migraciones reales. E2E: Playwright en navegador real con su propia BD (`chrisco_e2e`) y puertos (8011/4201) | Las reglas de BD y los flujos completos se prueban de verdad |
| Reutilizado de terceros | `slowapi`, `pwdlib[argon2]`, `PyJWT`, `python-multipart`, `Pillow` (fotos), `@angular/pwa`, `angular-eslint`, `@hey-api/openapi-ts`, `@playwright/test` | Se revisó GitHub/PyPI: no hay repo de renta de maquinaria reutilizable; [fastapi/full-stack-fastapi-template](https://github.com/fastapi/full-stack-fastapi-template) sirvió de referencia de auth |
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
| `models/bloqueo.py` | `BloqueoTipo`, `BloqueoEstado`, `HOLD_TYPES`, `Bloqueo` (`periodo` TSTZRANGE, `vence_en`, `motivo`; restricción de exclusión y CHECK de coherencia: solo las reservas provisionales vencen, mantenimiento/manual exigen motivo) |
| `models/cotizacion.py` | `CotizacionEstado` (vigente, aceptada, rechazada, reemplazada, vencida), `PartidaConcepto`, `PartidaUnidad`, `Cotizacion` (CHECK total = subtotal + IVA y anticipo ≤ total; índice parcial único), `CotizacionPartida` |
| `models/renta.py` | `RentaEstado` (ciclo completo), `OperadorModo`, `Transporte`, `Renta` (folio, empresa, solicitante, equipo, bloqueo, periodo, destino, `requisitos` JSONB, CHECK `hasta > desde`), `renta_folio_seq` |
| `models/categoria.py` | `Categoria` (nombre único, `spec_fields` JSONB) |
| `models/equipo.py` | `EquipoStatus`, `Equipo` (código y serie únicos; CHECK de tarifas, año y horómetro; `specs` JSONB; propiedad `categoria_nombre`), `EquipoFoto` |
| `models/empresa.py` | `EmpresaStatus`, `Empresa` (RFC único, estado, motivo de rechazo, constancia, revisor); propiedades `owner` y `active_users`. Todo modelo nuevo se importa en `models/__init__.py` |
| `schemas/auth.py` | `Password`, `LoginRequest`, `RefreshRequest`, `TokenRequest`, `EmailRequest`, `SetPasswordRequest`, `TokenPair`, `UserOut` |
| `schemas/empresa.py` | `CompanyData` (valida RFC y normaliza el sitio web), `RegistroEmpresaForm`, `InviteUserRequest`, `RejectRequest`, `CompanyUserOut`, `EmpresaOut`, `EmpresaDetailOut`, `EmpresaListItem`, `empresa_detail()` |
| `schemas/common.py` | `MessageOut`, `Page[T]` (`{items, total}`), `Money` y `Hours` (Decimal en BD, número en JSON) |
| `schemas/disponibilidad.py` | `EstadoActual`, `Periodo` (valida fin > inicio, máx. 366 días, fechas con zona), `BloqueoIn`, `BloqueoOut`, `Ocupacion`, `DisponibilidadOut` |
| `schemas/cotizacion.py` | `PartidaIn/Out`, `CotizacionIn`, `CotizacionOut`, `CotizacionCalculo`, `CotizacionSugerida`, `MotivoIn` |
| `schemas/renta.py` | `Requisito`, `SolicitudIn` (periodo futuro, mínimo 1 h), `PreviewOut`, `RentaOut`, `WhatsappOut`, `SolicitudCreada` |
| `schemas/equipo.py` | `SpecField`/`SpecFieldType`, `CategoriaIn/Out/AdminOut`, `EquipoIn` (validación común del alta, la edición y el CSV), `EquipoUpdate`, `EquipoOut`, `EquipoCatalogOut`, `FotoOut`, `ImportResult`, `RowError` |
| `services/accounts.py` | `user_from_token`, `get_by_email`, `unusable_password_hash`, `authenticate` (exige correo verificado), `verify_email`, `set_password_from_token` (invitación y recuperación) |
| `services/empresas.py` | `register_company`, `get_empresa`, `active_user_count`, `approve`, `reject`, `resubmit`, `invite_user` (con bloqueo y reactivación de bajas), `remove_user` |
| `services/disponibilidad.py` | Lectura: `overlapping`, `is_free`, `occupied_ids`, `free_between` (filtro SQL), `estado_actual` (en lote), `occupations`, `parse_window`, `upcoming`. Escritura: `block` (personal), `place_hold` (solicitud 20 min), `promote_to_apartado` (3 h), `confirm_rental`, `release`, `release_staff_block`, `expire_holds`. **`place_hold`, `promote_to_apartado` y `confirm_rental` los usará la fase 5**; hoy los ejerce la suite de pruebas |
| `services/cotizador.py` | Puras: `money`, `importe`, `totales`, `default_anticipo`, `billable_units`, `suggest` (renta con la tarifa más barata del periodo, flete y operador en cero para que ventas los llene) |
| `services/cotizaciones.py` | `calculate` (única aritmética), `create`, `accept`, `decline`, `reject_request`, `current`, `require_current`, `suggested`, `to_out` |
| `services/requisitos.py` | `compute(equipo, operador_modo, transporte)`: documentos, condiciones y cargos previstos (pura) |
| `services/whatsapp.py` | `build_message` (fechas en hora de México), `build_url` (`wa.me`, valida el número) |
| `services/rentas.py` | `preview`, `create_request`, `get_for_user`, `list_for`, `cancel`, `expire_stale` (reservas, cotizaciones y solicitudes que dependían de ellas), `to_out`, `whatsapp_for` |
| `services/storage.py` | `PrivateStorage` (`save`, `save_pdf`, `save_image`, `path`, `delete`), `get_storage`, `read_limited`, `read_pdf_upload` |
| `services/images.py` | `process_photo`: valida y recodifica una foto → (grande, miniatura) |
| `services/specs.py` | `parse_fields`, `validate_specs`, `display_specs` (puras, con pruebas propias) |
| `services/categorias.py` | `create`, `update`, `delete` (no si tiene equipos), `list_with_counts`, `get_categoria` |
| `services/equipos.py` | `create`, `update`, `search` (texto, categoría, estado, paginación), `apply_data`, `commit`, `add_photo`, `delete_photo`, `get_photo`, `get_active_equipo` (única definición del «equipo visible para clientes»), `catalog_out` |
| `services/equipos_import.py` | `import_csv` (todo o nada), `template_csv` (con columnas `spec_*` de una categoría) |
| `services/mailer.py` | `Mail`, `Mailer`, `ConsoleMailer`, `FileMailer`, `SmtpMailer`, `get_mailer` |
| `services/notifications.py` | Un correo por función: `verification_mail`, `invitation_mail`, `password_reset_mail`, `company_approved_mail`, `company_rejected_mail` |
| `api/deps.py` | `DbSession`, `MailerDep`, `StorageDep`, `CurrentUser`, `require_roles`, `company_of`, `ClientUser`, `ApprovedClientUser`, `CompanyOwner`, `AdminUser`, `StaffUser`, `CatalogUser` (personal o cliente aprobado) |
| `api/forms.py` | `CompanyForm`, `RegistroForm`: dependencias de formularios multipart (FastAPI no permite un modelo `Form()` junto a un archivo) |
| `api/routes/auth.py` | `POST /auth/login`, `/refresh`, `/logout-all`, `/verify-email`, `/resend-verification`, `/forgot-password`, `/reset-password`, `/accept-invite`; `GET /auth/me`. Los de correo responden 204 siempre (no revelan si el correo existe) |
| `api/routes/empresas.py` | `POST /empresa/registro` (público, 5/hora), `GET/PUT /empresa/me`, `POST /empresa/me/usuarios`, `DELETE /empresa/me/usuarios/{id}` |
| `api/routes/admin_empresas.py` | `GET /admin/empresas?status_filter=`, `GET /admin/empresas/{id}`, `GET …/constancia` (admin y ventas); `POST …/aprobar`, `…/rechazar` (solo admin) |
| `api/routes/categorias.py` | `GET /categorias` (catálogo); `GET/POST/PUT/DELETE /admin/categorias` (ver: admin y ventas; cambiar: admin) |
| `api/routes/admin_equipos.py` | `GET/POST /admin/equipos`, `GET/PUT /admin/equipos/{id}`, `POST/DELETE …/fotos`, `POST /admin/equipos/importar`, `GET …/importar/plantilla` (ver: admin y ventas; cambiar: admin) |
| `api/routes/catalogo.py` | `GET /equipos` (con `desde`/`hasta`/`solo_disponibles` indica `disponible`), `GET /equipos/{id}`, `GET /equipos/{id}/disponibilidad`, `GET /equipos/fotos/{id}/{thumb o full}` (público) |
| `api/routes/admin_bloqueos.py` | `GET/POST /admin/equipos/{id}/bloqueos` (ver: admin y ventas; crear: admin), `POST /admin/bloqueos/{id}/liberar` (solo los del personal; los de una renta se liberan desde la renta) |
| `api/routes/cotizaciones.py` | `GET …/cotizacion/sugerida`, `POST …/cotizacion/calcular`, `POST …/cotizacion`, `POST …/rechazar` (personal); `GET …/cotizacion` (empresa dueña o personal); `POST …/cotizacion/aceptar`, `…/rechazar` (cliente aprobado). Todas bajo `/rentas/{id}` |
| `api/routes/rentas.py` | `POST /rentas/solicitudes/preview`, `POST /rentas/solicitudes` (cliente aprobado); `GET /rentas`, `GET /rentas/{id}`, `GET /rentas/{id}/whatsapp`, `POST /rentas/{id}/cancelar` (cliente de la empresa dueña o personal) |
| `cli.py` | `python -m app.cli create-user` (personal: admin, ventas, operador) |
| `export_openapi.py` | Escribe el OpenAPI para generar los tipos del frontend |
| `alembic/` | Migraciones (`8469e6e1a421` users, `7156d33208d8` empresas y verificación, `2e41e63fc97a` categorías y equipos, `e7da6725fb24` bloqueos, `8c090348072c` rentas, `8137a8bea5dc` cotizaciones) |
| `tests/` | 338 pruebas: `test_auth`, `test_empresas`, `test_mailer`, `test_concurrencia`, `test_specs`, `test_categorias`, `test_equipos`, `test_catalogo`, `test_importacion`, `test_disponibilidad` (traslapes, contiguos, restricción en BD, 6 hilos simultáneos, vencimientos, ciclo solicitud→apartado→renta), `test_bloqueos_api`, `test_requisitos_whatsapp`, `test_cotizador`, `test_cotizaciones` (totales del servidor, versiones, aceptar/rechazar, apartado, vencimientos, 2 aceptaciones simultáneas —falla sin la restricción de la base de datos—), `rentas_helpers.py` (compartido), `test_rentas` (solicitud, reserva de 20 min, límite con hilos simultáneos —falla sin el bloqueo—, vencimiento, cancelación, aislamiento entre empresas); `conftest.py` (migra la BD de pruebas, buzón en memoria, Argon2 de bajo costo solo en pruebas, fixtures `register`, `approved_owner`, `admin_h`, `ventas_h`, `client_h`, `categoria`, `make_equipo`…), `probes.py` |

### Frontend (`frontend/src/app/`)

| Archivo | Qué hace |
|---|---|
| `core/api/generated/` | Tipos generados del OpenAPI (**no editar**; `npm run api:gen`) |
| `core/api/models.ts` | Nombres cortos de los tipos generados (`User`, `Role`, `EmpresaDetail`, `Equipo`, `Categoria`…) y `Page<T>` |
| `core/api/dates.ts` | `periodFromInputs` (dos `datetime-local` → periodo UTC válido o null), `toLocalInput` |
| `core/api/download.ts` | `saveBlob` (guarda un archivo en memoria) |
| `core/api/paged-list.ts` | `pagedList`: lista paginada con filtros cuyas peticiones se cancelan entre sí (una respuesta vieja no pisa a la nueva); la usan `CatalogoPage`, `EquiposPage` y `RentasPage` |
| `core/rentas/rentas.service.ts` | `RentasService` (`preview`, `create`, `list`, `get`, `whatsapp`, `cancel`, `cotizacion`, `sugerida`, `calcular`, `cotizar`, `aceptar`, `rechazarCotizacion`, `rechazarSolicitud`) |
| `core/catalogo/catalogo.service.ts` | `CatalogoService` (`list` con periodo, `get`, `disponibilidad`, `categorias`), `fotoUrl`, `toParams` |
| `core/api/errors.ts` | `apiErrorMessage`: errores de la API → mensaje en español |
| `core/api/form-data.ts` | `toFormData` (campos + PDF) |
| `core/auth/*` | `AuthService` (login, sesión, `refresh`, `verifyEmail`, `resendVerification`, `forgotPassword`, `setPassword`), interceptor con renovación, guards (`authGuard`, `guestGuard`, `homeRedirectGuard`, `roleGuard`), `HOME_BY_ROLE`, `ROLE_LABEL` |
| `core/empresa/empresa.service.ts` | `EmpresaService`: `register`, `mine`, `resubmit`, `inviteUser`, `removeUser` |
| `shared/` | `Logo`, `AuthCard` (contenedor de pantallas públicas), `StatusBadge` (estado de empresa, equipo, situación actual o renta), `Countdown` (cuenta regresiva que avisa al llegar a cero), `SpecFields` + `buildSpecGroup`/`specValues` (formulario dinámico de especificaciones) |
| `styles.css` | Utilidades de interfaz únicas: `card`, `label`, `input`, `btn`, `btn-primary`, `btn-secondary`, `btn-danger`, `alert-error`, `alert-ok`, `link` |
| `layout/shell.ts` | Marco autenticado: barra superior, rol, Salir y, para el personal, navegación Empresas / Equipos / Categorías |
| `features/login/` | Login (con reenvío de confirmación y enlaces a registro/recuperación) |
| `features/auth/` | `Register`, `VerifyEmail`, `SetPassword` (invitación y recuperación, según `data.mode`), `ForgotPassword` |
| `features/cliente/` | `ClienteHome` (estado de la empresa), `ResubmitForm` (tras rechazo), `CompanyTeam` (usuarios: invitar y dar de baja) |
| `features/admin/` | `AdminHome` (empresas con filtro por estado), `EmpresaReview` (detalle, constancia, aprobar/rechazar), `AdminEmpresasService` |
| `features/admin/equipos/` | `EquiposPage` (búsqueda, filtros, paginación), `EquipoForm` (alta y edición, especificaciones dinámicas, fotos, situación actual; solo lectura para ventas; no se muestra hasta cargar los datos), `EquipoBloqueos` (bloqueos vigentes y futuros, programar y liberar mantenimiento), `EquiposImport` (plantilla, validar, importar), `EquiposService` |
| `features/admin/categorias/` | `CategoriasPage` (la clave sugerida sale de la etiqueta; la clave de un campo ya guardado no se edita), `CategoriasService`, `slugify` |
| `features/cliente/catalogo/` | `CatalogoPage` (tarjetas, búsqueda, filtro, paginación, periodo «lo necesito desde/hasta» y «solo disponibles»), `CatalogoDetalle` (fotos, tarifas, requisitos, especificaciones, periodos ocupados en 90 días), `SolicitarRenta` (formulario → revisión de requisitos y disponibilidad → reserva → mensaje, enlace de WhatsApp y cuenta regresiva) |
| Listas con filtros | Paginadas con `pagedList`; `AdminHome` (sin paginar) aplica el mismo patrón a mano |
| `features/rentas/cotizacion-view.ts`, `cotizacion-editor.ts` | `CotizacionView` (renglones, totales, anticipo, vigencia) y `CotizacionEditor` (ventas: parte de lo sugerido, renglones editables, totales en vivo vía `calcular`) |
| `features/rentas/` | `RentasPage` (lista de «Mis rentas» o de todas, según el rol; búsqueda y estado) y `RentaDetalle` (datos, requisitos, cuenta regresiva de la reserva o del apartado, mensaje de WhatsApp, cotización con aceptar/rechazar para el cliente y cotizar/rechazar para ventas, cancelar); las usan `/cliente/rentas` y `/admin/rentas` |
| `features/operador/operador-home.ts` | Pantalla **provisional** (ancla de ruta) hasta la fase 8 |
| `app.routes.ts` | Públicas: `/login`, `/registro`, `/olvide-contrasena`, `/verificar-correo`, `/aceptar-invitacion`, `/recuperar-contrasena`. Con sesión: `/admin`, `/admin/empresas/:id`, `/admin/equipos` (`/nuevo`, `/importar`, `/:id`), `/admin/categorias`, `/operador`, `/cliente`, `/cliente/catalogo`, `/cliente/catalogo/:id`, `/cliente/rentas` (`/:id`), `/admin/rentas` (`/:id`); la navegación del personal incluye «Rentas» |

### E2E (`e2e/`)

Playwright: `playwright.config.ts` (levanta API en 8011 y Angular en 4201), `global-setup.ts` + `db.ts` + `scripts/prepare_db.py` (BD `chrisco_e2e` vacía y migrada, 2 usuarios del personal), `tests/empresas.spec.ts` (14 pasos: registro → confirmación → revisión → rechazo → reenvío → aprobación → invitación → máximo de 3 → recuperación), `tests/equipos.spec.ts` (11 pasos: categoría con especificaciones → equipo → fotos → CSV → búsqueda → ventas en solo lectura → catálogo del cliente → baja), `tests/disponibilidad.spec.ts` (10 pasos: equipos libres → mantenimiento en curso → no se puede duplicar → situación en la lista → ventas solo lectura → el cliente filtra por fechas y «solo disponibles» → ficha con periodos ocupados → liberar), `tests/rentas.spec.ts` (8 pasos: pedir un equipo → requisitos → reserva y mensaje de WhatsApp → otra empresa bloqueada → «Mis rentas» → el personal ve todo → aislamiento entre empresas → cancelar libera → límite de 3), `tests/cotizaciones.spec.ts` (8 pasos: sugerido → totales en vivo → enviar → el cliente acepta y queda apartado → otra empresa bloqueada → aviso al personal → el cliente rechaza → ventas rechaza con motivo → nueva versión), `tests/rentas-api.ts` (`equipoId`, `solicitarPorApi`, `tomorrowWorkday`), `tests/helpers.ts` (`login`, `signIn`, `logout`, `inHours`, `createApprovedClient`, `seedEquipos`, `userHeaders`, archivos de ejemplo), `tests/mail.ts` (lee los enlaces del buzón JSONL), `db.ts` (`resetDatabase`: **cada archivo de pruebas parte de un sistema limpio**). Local: `E2E_CHANNEL=msedge npx playwright test`.

## Fases

| # | Fase | Estado |
|---|---|---|
| 1 | Base: monorepo, API + BD, login con roles, Angular con guards y PWA, CI | ✅ |
| 2 | Registro y aprobación de empresas (RFC, constancia, máx. 3 usuarios, correo verificado), recuperación de contraseña, E2E | ✅ Cerrada |
| 3 | Equipos: alta/edición/baja, categorías, especificaciones flexibles, tarifas, fotos, carga masiva CSV, catálogo para clientes | ✅ Cerrada |
| 4 | Disponibilidad y bloqueos con vencimiento (20 min / 3 h), sin dobles reservas (restricción de exclusión en PostgreSQL); el catálogo muestra disponibilidad | ✅ Cerrada |
| 5 | Solicitud del cliente (reserva de 20 min), requisitos y transporte, mensaje `wa.me` al agente de ventas | ✅ Cerrada |
| 6a | Cotización por partidas, aceptación del cliente y apartado de 3 h, rechazos, vencimientos | ✅ Cerrada |
| 6b | Requisitos del apartado (documentos, condiciones), pagos por transferencia con comprobante, confirmación automática (`confirm_rental`), cobranza | ⏳ Siguiente |
| 7 | Licencias de operadores externos: foto, lectura de QR, verificación (SICT), revisión manual de respaldo | Pendiente (investigar la consulta oficial antes) |
| 8 | Check-in/out con horómetro y foto; mantenimiento y alertas por correo; luego WhatsApp con API | Pendiente |
| 9 | Gestión de personal desde la interfaz (hoy solo CLI), despliegue y endurecimiento | Pendiente |

## Deuda técnica

Ninguna que afecte a lo construido. Pendientes conocidos, sin impacto hoy:

1. **Límite de intentos en memoria** (slowapi): correcto con una sola instancia de la API; con varias hay que moverlo a Redis. Resolver al desplegar más de una instancia.
2. **Aviso de slowapi en Python 3.14** (`asyncio.iscoroutinefunction`, obsoleto para 3.16): no aparece con 3.12 (fijado). Revisar al subir de versión de Python.
3. **Despliegue** (Dockerfile del API, proxy inverso con `/api`, HTTPS, CSP, variables de producción, copias de seguridad de BD y de `uploads/`): sin construir; fase 9.
4. **Instalación de la PWA sin probar**: login, sesión, guards y todos los flujos de la fase 2 se verifican en Edge real; falta probar la instalación como app y el service worker, que solo se activan con el build de producción servido por HTTPS o `localhost`.
5. **Archivos en disco local**: suficiente para un servidor; con varias instancias o respaldo automático conviene objeto (S3/R2) cambiando solo `PrivateStorage`.
6. **Sin paginación** en la lista de empresas (equipos y catálogo sí la tienen): aceptable para decenas; revisar si crece.
7. **Limpieza de reservas vencidas** solo por `expire-holds` (cron) o al reservar: sin tarea programada hasta el despliegue (fase 9); no afecta a la corrección porque las lecturas ya ignoran las vencidas.
8. **E2E en CI sin ejecutar todavía en GitHub** (el trabajo `e2e` está escrito y la suite pasa en local; no hay remoto configurado). Confirmar en la primera ejecución real.

## Limitaciones conocidas (funcionalidad, no deuda)

- La primera foto es la portada; aún no hay forma de reordenarlas.
- La importación CSV solo **crea** equipos (no actualiza por código).
- El horómetro se captura a mano; lo alimentará el check-in/out de la fase 8.
- Una renta apartada todavía no avanza: cumplir requisitos, pagar el anticipo y confirmar llegan en la fase 6b (hoy el apartado vence a las 3 h). `confirm_rental` aún no lo usa ninguna ruta.
- La cotización no tiene PDF imprimible (se ve en pantalla y llega el aviso por correo).
- El número de WhatsApp de ventas se configura por variable de entorno (`SALES_WHATSAPP_NUMBER`); sin él el cliente copia el mensaje a mano.
- En producción, `CREATE EXTENSION btree_gist` necesita permisos (en PostgreSQL 13+ es una extensión «de confianza» para el dueño de la base; algunos servicios administrados la tienen disponible por defecto).
- Cambiar los campos de una categoría no migra los equipos ya guardados: sus valores antiguos quedan sin mostrarse.

## Notas de entorno

- Los puertos 5432 y 8000 de esta máquina los usan otras apps del usuario (Postgres y una app Apache/Debian en Docker). Este proyecto usa **5433** (BD), **8010** (API de desarrollo) y **8011/4201** (E2E); el proxy apunta a `127.0.0.1` explícito porque `localhost` resuelve primero a IPv6 y llegaría a la otra app.
- Si el volumen de Postgres ya existía antes de la Fase 2, las BD `chrisco_test` y `chrisco_e2e` se crean solas por `docker/init-databases.sql` solo en volúmenes nuevos; en uno viejo: `docker compose exec db psql -U chrisco -d postgres -c "CREATE DATABASE chrisco_e2e OWNER chrisco"` (el script de E2E también la crea si falta).
- El prototipo original está en `legacy/` (commit inicial `a054e2a`).
