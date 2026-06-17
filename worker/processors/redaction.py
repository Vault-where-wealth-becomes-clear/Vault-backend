import re

_CARD_PATTERN = re.compile(r"(?<!\d)(?:\d{4}[ -]){3}\d{4}(?!\d)")
_LONG_DIGIT_RUN = re.compile(r"(?<!\d)\d{10,}(?!\d)")


def _mask_keep_last4(digits: str) -> str:
    return "•" * max(len(digits) - 4, 0) + digits[-4:]


def redact_sensitive_numbers(text: str) -> str:
    """Enmascara numeros de tarjeta, CBU/CVU y cuentas largas antes de mandar el texto a Claude.

    Deja fechas y montos intactos (no son corridas de 10+ digitos sin separadores
    ni bloques de 4x4 separados por espacio/guion).
    """

    def _mask_card(match: re.Match) -> str:
        digits = re.sub(r"[ \-]", "", match.group(0))
        return _mask_keep_last4(digits)

    text = _CARD_PATTERN.sub(_mask_card, text)
    text = _LONG_DIGIT_RUN.sub(lambda m: _mask_keep_last4(m.group(0)), text)
    return text
