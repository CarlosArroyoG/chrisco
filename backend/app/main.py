from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.routes import (
    admin_bloqueos,
    admin_dashboard,
    admin_empresas,
    admin_equipos,
    admin_gastos,
    admin_mantenimiento,
    admin_personal,
    auth,
    catalogo,
    categorias,
    cobranza,
    cotizaciones,
    cumplimiento,
    empresas,
    movimientos,
    rentas,
)
from app.core.config import get_settings
from app.core.errors import DomainError, domain_error_handler
from app.core.limiter import limiter

settings = get_settings()

app = FastAPI(
    title="CHRISCO API",
    version="0.9.0",
    # La documentación interactiva solo en desarrollo, no en producción.
    docs_url=None if settings.environment == "production" else "/docs",
    redoc_url=None,
    openapi_url=None if settings.environment == "production" else "/openapi.json",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
app.add_exception_handler(DomainError, domain_error_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(empresas.router)
app.include_router(admin_empresas.router)
app.include_router(categorias.router)
app.include_router(admin_equipos.router)
app.include_router(admin_bloqueos.router)
app.include_router(catalogo.router)
app.include_router(rentas.router)
app.include_router(cotizaciones.router)
app.include_router(cumplimiento.router)
app.include_router(cobranza.router)
app.include_router(movimientos.router)
app.include_router(admin_mantenimiento.router)
app.include_router(admin_personal.router)
app.include_router(admin_dashboard.router)
app.include_router(admin_gastos.router)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
