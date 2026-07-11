from typing import Literal

from pydantic import BaseModel

InstrumentoTipo = Literal[
    "accion_local",
    "cedear",
    "bono_ars",
    "bono_usd",
    "fci_ars",
    "fci_usd",
    "lecap_boncap",
    "on_ars",
    "on_usd",
    "efectivo_comitente",
    "otro",
]


class CarteraPosicion(BaseModel):
    instrumento: str
    ticker: str | None = None
    tipo: InstrumentoTipo
    moneda: Literal["ARS", "USD"]
    cantidad: float
    precio_cierre: float
    valor_moneda: float
    valor_base_ars: float
    pct_cartera: float
    cpp: float | None = None
    resultado_realizado_ars: float | None = None
    rendimiento_pct: float | None = None


class DeltaCarteraMes(BaseModel):
    revaluacion_mercado_ars: float
    compras_netas_ars: float
    ventas_netas_ars: float
    rentas_cobradas_ars: float


class CarteraEvolucionPoint(BaseModel):
    month: str
    nivel_detectado: int
    valor_base_ars: float
    delta_ars: float | None
    delta_pct: float | None
    composicion_por_tipo: dict[str, float]


class AccountCarteraResponse(BaseModel):
    month: str
    nivel_detectado: int
    posiciones: list[CarteraPosicion]
    rendimientos_netos_ars: float | None
    retenciones_ars: float | None
    delta_cartera_mes: DeltaCarteraMes | None
    evolucion: list[CarteraEvolucionPoint]
    composicion_por_tipo: dict[str, float]
    alertas: list[str]
    insights: list[str]
