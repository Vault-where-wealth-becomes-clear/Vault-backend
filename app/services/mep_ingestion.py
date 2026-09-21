"""Ingesta automática del TC MEP (compra/venta) desde fuentes públicas.

Mismo par de fuentes y misma lógica de fallback que ya usaba el frontend
para el fetch manual (src/api/mepQuote.api.ts) — se centraliza acá para
que el job diario del backend no dependa de que un usuario tenga la app
abierta.
"""

from dataclasses import dataclass
from datetime import date, datetime

import httpx

_DOLARAPI_URL = "https://dolarapi.com/v1/dolares/bolsa"
_ARGENTINADATOS_URL = "https://api.argentinadatos.com/v1/cotizaciones/dolares/bolsa"
_FETCH_TIMEOUT_SECONDS = 5.0


@dataclass
class MepQuote:
    buy_rate: float
    sell_rate: float
    fetched_at: datetime
    source: str


class MepFetchError(Exception):
    """Ninguna fuente pública devolvió una cotización válida."""


async def _fetch_from_dolarapi(client: httpx.AsyncClient) -> MepQuote:
    resp = await client.get(_DOLARAPI_URL, timeout=_FETCH_TIMEOUT_SECONDS)
    resp.raise_for_status()
    data = resp.json()
    return MepQuote(
        buy_rate=float(data["compra"]),
        sell_rate=float(data["venta"]),
        fetched_at=datetime.fromisoformat(data["fechaActualizacion"]),
        source="dolarapi",
    )


async def _fetch_from_argentinadatos(client: httpx.AsyncClient) -> MepQuote:
    resp = await client.get(_ARGENTINADATOS_URL, timeout=_FETCH_TIMEOUT_SECONDS)
    resp.raise_for_status()
    data = resp.json()
    if not data:
        raise MepFetchError("argentinadatos: respuesta vacía")
    latest = data[-1]
    return MepQuote(
        buy_rate=float(latest["compra"]),
        sell_rate=float(latest["venta"]),
        fetched_at=datetime.fromisoformat(latest["fecha"]),
        source="argentinadatos",
    )


async def fetch_mep_quote() -> MepQuote:
    """Trae la cotización MEP vigente. dolarapi primero, argentinadatos si falla."""
    async with httpx.AsyncClient() as client:
        try:
            return await _fetch_from_dolarapi(client)
        except (httpx.HTTPError, KeyError, ValueError, TypeError):
            pass
        try:
            return await _fetch_from_argentinadatos(client)
        except (httpx.HTTPError, KeyError, ValueError, TypeError, IndexError) as exc:
            raise MepFetchError("No se pudo obtener el TC MEP de ninguna fuente pública") from exc


def current_period_month(today: date | None = None) -> date:
    today = today or date.today()
    return today.replace(day=1)
