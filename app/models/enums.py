import enum


class PlanType(str, enum.Enum):
    free = "free"
    pro = "pro"
    family = "family"


class AccountType(str, enum.Enum):
    credit_card_ars = "credit_card_ars"
    credit_card_usd = "credit_card_usd"
    checking_ars = "checking_ars"
    checking_usd = "checking_usd"
    broker = "broker"
    crypto = "crypto"
    cash = "cash"
    savings_box = "savings_box"


class UploadStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    review = "review"
    done = "done"
    error = "error"


class CurrencyType(str, enum.Enum):
    ARS = "ARS"
    USD = "USD"


class RuleSource(str, enum.Enum):
    user = "user"
    ai = "ai"


class MepSource(str, enum.Enum):
    manual = "manual"
    api = "api"


class SkillModule(str, enum.Enum):
    flujo_mensual = "flujo_mensual"
    categorizacion_gasto = "categorizacion_gasto"
    flujo_periodo = "flujo_periodo"
    cuenta_comitente = "cuenta_comitente"
    tablero_general = "tablero_general"
    proyeccion_patrimonial = "proyeccion_patrimonial"
    compromisos_futuros = "compromisos_futuros"


class InstrumentoTipo(str, enum.Enum):
    accion_local = "accion_local"
    cedear = "cedear"
    bono_ars = "bono_ars"
    bono_usd = "bono_usd"
    fci_ars = "fci_ars"
    fci_usd = "fci_usd"
    lecap_boncap = "lecap_boncap"
    on_ars = "on_ars"
    on_usd = "on_usd"
    efectivo_comitente = "efectivo_comitente"
    otro = "otro"


# Taxonomía exacta de `Transaction.category` según
# app/skills/finanzas_personales/_output_contract.md, separada en los mismos tres grupos
# que usa la skill — ningún consumidor debe inventar su propia lista de "qué es gasto":
# GASTO_CATEGORIES es la única fuente de verdad para "esto es plata que salió como
# consumo", la usan tanto la validación de categoría como el desglose de gasto del
# tablero (ver worker/processing.py::_normalize_category y
# dashboard_service.py::get_month_summary).
GASTO_CATEGORIES = {
    "Supermercado",
    "Restaurantes",
    "Transporte",
    "Salud",
    "Indumentaria",
    "Tecnología",
    "Entretenimiento",
    "Servicios",
    "Educación",
    "Viajes",
    "Suscripciones",
    "Impuestos",
    "Varios",
}

INGRESO_MOVIMIENTO_CATEGORIES = {
    "Ingreso operativo",
    "Rendimiento",
    "Cambio de moneda",
    "Pago deuda",
    "Transferencia interna",
}

TRANSITORIO_CATEGORIES = {
    "Reintegro",
    "Sin categoría",
}

# El LLM no siempre respeta el string exacto (sinónimos, mayúsculas/tildes distintas),
# así que el backend nunca debe confiar en el valor crudo: todo lo que no matchee uno de
# estos strings se coerciona a "Varios" antes de guardar.
TRANSACTION_CATEGORIES = GASTO_CATEGORIES | INGRESO_MOVIMIENTO_CATEGORIES | TRANSITORIO_CATEGORIES
