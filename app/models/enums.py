import enum


class PlanType(enum.StrEnum):
    free = "free"
    pro = "pro"
    family = "family"


class AccountType(enum.StrEnum):
    credit_card_ars = "credit_card_ars"
    credit_card_usd = "credit_card_usd"
    checking_ars = "checking_ars"
    checking_usd = "checking_usd"
    broker = "broker"
    crypto = "crypto"
    cash = "cash"
    savings_box = "savings_box"


class UploadStatus(enum.StrEnum):
    pending = "pending"
    processing = "processing"
    review = "review"
    done = "done"
    error = "error"


class CurrencyType(enum.StrEnum):
    ARS = "ARS"
    USD = "USD"


class RuleSource(enum.StrEnum):
    user = "user"
    ai = "ai"


class MepSource(enum.StrEnum):
    manual = "manual"
    api = "api"


class SkillModule(enum.StrEnum):
    flujo_mensual = "flujo_mensual"
    categorizacion_gasto = "categorizacion_gasto"
    flujo_periodo = "flujo_periodo"
    cuenta_comitente = "cuenta_comitente"
    tablero_general = "tablero_general"
    proyeccion_patrimonial = "proyeccion_patrimonial"
    compromisos_futuros = "compromisos_futuros"
