import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.gasto import GastoCategoria
from app.models.renta import RentaEstado
from app.schemas.common import Money, SignedMoney


class Comparativo(BaseModel):
    """Una cifra del mes contra la del mes anterior."""

    actual: SignedMoney
    anterior: SignedMoney
    # Variación en %; None si el mes anterior fue cero (no hay contra qué comparar).
    cambio_pct: float | None


class PuntoMensual(BaseModel):
    mes: str  # AAAA-MM
    etiqueta: str  # «oct»
    ingresos: Money
    gastos: Money
    ganancia: SignedMoney


class Flota(BaseModel):
    total: int
    rentados: int
    bloqueados: int
    libres: int
    utilizacion_pct: float


class Mantenimiento(BaseModel):
    vencidos: int
    proximos: int


class RentasEstadoTotal(BaseModel):
    estado: RentaEstado
    total: int


class GastoCategoriaTotal(BaseModel):
    categoria: GastoCategoria
    total: Money


class EquipoIngreso(BaseModel):
    equipo_id: uuid.UUID
    codigo: str
    nombre: str
    ingresos: Money


class ProximaSalida(BaseModel):
    renta_id: uuid.UUID
    folio: str
    equipo: str
    empresa: str
    desde: datetime


class DashboardOut(BaseModel):
    mes: str
    mes_nombre: str
    ingresos: Comparativo  # pagos confirmados con fecha del mes
    gastos: Comparativo
    ganancia: Comparativo  # ingresos − gastos
    vendido: Comparativo  # total de las cotizaciones aceptadas en el mes
    por_cobrar: Money
    pagos_por_confirmar: int
    empresas_pendientes: int
    mantenimiento: Mantenimiento
    flota: Flota
    serie_mensual: list[PuntoMensual]
    rentas_por_estado: list[RentasEstadoTotal]
    gastos_por_categoria: list[GastoCategoriaTotal]
    top_equipos: list[EquipoIngreso]
    proximas_salidas: list[ProximaSalida]
