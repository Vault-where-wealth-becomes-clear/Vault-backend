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
