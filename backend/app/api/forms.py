"""Dependencias de formularios multipart.

FastAPI no permite combinar un modelo `Form()` con un archivo en la misma ruta, así que los campos
se declaran sueltos y se validan con el mismo esquema Pydantic que usa el resto de la API.
"""

from typing import Annotated, Any

from fastapi import Depends, Form
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ValidationError

from app.schemas.cumplimiento import PagoIn
from app.schemas.empresa import CompanyData, RegistroEmpresaForm


def _validate[M: BaseModel](model: type[M], **fields: Any) -> M:
    try:
        return model(**fields)
    except ValidationError as exc:
        # Sin `ctx`: contiene excepciones que no se pueden serializar a JSON.
        raise RequestValidationError(exc.errors(include_url=False, include_context=False)) from exc


def company_form(
    razon_social: Annotated[str, Form()],
    sitio_web: Annotated[str, Form()],
    rfc: Annotated[str, Form()],
) -> CompanyData:
    return _validate(CompanyData, razon_social=razon_social, sitio_web=sitio_web, rfc=rfc)


CompanyForm = Annotated[CompanyData, Depends(company_form)]


def registro_form(
    company: CompanyForm,
    full_name: Annotated[str, Form()],
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
) -> RegistroEmpresaForm:
    return _validate(
        RegistroEmpresaForm,
        **company.model_dump(),
        full_name=full_name,
        email=email,
        password=password,
    )


RegistroForm = Annotated[RegistroEmpresaForm, Depends(registro_form)]


def pago_form(
    monto: Annotated[str, Form()],
    fecha_pago: Annotated[str, Form()],
    referencia: Annotated[str | None, Form()] = None,
) -> PagoIn:
    return _validate(PagoIn, monto=monto, fecha_pago=fecha_pago, referencia=referencia or None)


PagoForm = Annotated[PagoIn, Depends(pago_form)]
