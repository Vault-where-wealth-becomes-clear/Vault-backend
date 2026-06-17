_KNOWN_BANKS = [
    "Galicia",
    "BBVA",
    "Santander",
    "Brubank",
    "Macro",
    "ICBC",
    "HSBC",
    "Naranja",
    "Mercado Pago",
    "Ualá",
    "IOL",
    "INVIU",
    "Binance",
    "Belo",
]


def detect_bank(text: str) -> str | None:
    upper = text.upper()
    for bank in _KNOWN_BANKS:
        if bank.upper() in upper:
            return bank
    return None
