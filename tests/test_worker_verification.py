"""Cobertura de la capa de verificacion deterministica del worker.

Es el codigo que decide si los numeros de un usuario estan bien, y el que mas
seguido se toca cuando aparece un formato de banco nuevo. Varios de estos
casos corresponden a fallas reales ya documentadas en los comentarios del
codigo: estos tests existen para que no vuelvan.
"""

from decimal import Decimal

from worker.processors.amount_verifier import verify_and_correct_amounts
from worker.processors.ledger_verifier import (
    last_printed_saldo,
    parse_ledger_lines,
    reconciliation_gap,
    verify_and_correct_ledger,
)
from worker.processors.mep_converter import apply_mep_conversion

# ─────────────────────────── amount_verifier ───────────────────────────

_RESUMEN_TARJETA = """
RESUMEN DE CUENTA - TARJETA VISA
19-May-25  SUPERMERCADO DIA           123456        45.000,00
20-May-25  HELADERA 12 CUOTAS         234567       120.000,00
21-May-25  CAFE                       345678         3.500,50
"""


def test_the_printed_amount_wins_over_the_llm_amount():
    """El caso original: el LLM dividio el monto por la cantidad de cuotas en
    vez de tomarlo tal cual. El texto del PDF no tiene ese problema."""
    txns = [{"description": "HELADERA 12 CUOTAS", "cupon": "234567", "amount": -10000.0}]

    verify_and_correct_amounts(txns, _RESUMEN_TARJETA)

    assert txns[0]["amount"] == -120000.0, "gana el impreso"
    assert txns[0]["confidence"] == 0.5, "queda marcada para revision"


def test_correcting_an_amount_also_fixes_the_per_installment_value():
    txns = [
        {
            "description": "HELADERA 12 CUOTAS",
            "cupon": "234567",
            "amount": -10000.0,
            "installments": {"amount_per": 833.33},
        }
    ]

    verify_and_correct_amounts(txns, _RESUMEN_TARJETA)

    assert txns[0]["installments"]["amount_per"] == 120000.0


def test_a_matching_amount_is_left_alone():
    txns = [{"description": "CAFE", "cupon": "345678", "amount": -3500.50, "confidence": 0.9}]

    verify_and_correct_amounts(txns, _RESUMEN_TARJETA)

    assert txns[0]["amount"] == -3500.50
    assert txns[0]["confidence"] == 0.9, "no se marca para revision lo que ya coincidia"


def test_a_positive_amount_keeps_its_sign_when_corrected():
    """El impreso se lee en valor absoluto: el signo lo pone la transaccion."""
    txns = [{"description": "SUPERMERCADO DIA", "cupon": "123456", "amount": 1.0}]

    verify_and_correct_amounts(txns, _RESUMEN_TARJETA)

    assert txns[0]["amount"] == 45000.0


def test_transactions_without_a_cupon_are_untouched():
    txns = [{"description": "ALGO SIN CUPON", "amount": -999.0, "confidence": 0.8}]

    verify_and_correct_amounts(txns, _RESUMEN_TARJETA)

    assert txns[0] == {"description": "ALGO SIN CUPON", "amount": -999.0, "confidence": 0.8}


def test_text_without_printed_amounts_short_circuits():
    txns = [{"description": "X", "cupon": "123456", "amount": -1.0}]

    verify_and_correct_amounts(txns, "un PDF del que no se pudo leer ninguna linea")

    assert txns[0]["amount"] == -1.0


# ─────────────────────────── ledger_verifier ───────────────────────────

_EXTRACTO_CUENTA = """
MOVIMIENTOS
05/07  TRANSFERENCIA RECIBIDA        150.000,00     150.000,00
12/07  DB. IMPUESTO LEY 25413           -900,00     149.100,00
20/07  COMPRA VENTA MON.EXTRANJERA    50.000,00     199.100,00
"""


def test_ledger_lines_are_parsed_as_amount_and_running_balance_in_order():
    lines = parse_ledger_lines(_EXTRACTO_CUENTA)

    assert lines == [
        (Decimal("150000.00"), Decimal("150000.00")),
        (Decimal("-900.00"), Decimal("149100.00")),
        (Decimal("50000.00"), Decimal("199100.00")),
    ]


def test_a_sign_flipped_by_the_llm_is_corrected_against_the_printed_amount():
    """El caso documentado: 'COMPRA VENTA MON.EXTRANJERA' leido como gasto
    cuando el banco lo acredito."""
    txns = [
        {"description": "TRANSFERENCIA RECIBIDA", "amount": 150000.0},
        {"description": "DB. IMPUESTO LEY 25413", "amount": -900.0},
        {"description": "COMPRA VENTA MON.EXTRANJERA", "amount": -50000.0},
    ]

    verify_and_correct_ledger(txns, _EXTRACTO_CUENTA)

    assert txns[2]["amount"] == 50000.0
    assert txns[2]["confidence"] == 0.5
    assert txns[0]["amount"] == 150000.0, "las que ya coincidian no se tocan"


def test_nothing_is_corrected_when_the_line_count_does_not_line_up():
    """La propiedad de seguridad mas importante del modulo: la correccion es
    posicional, asi que si el LLM agrego, partio o se comio una linea, alinear
    igual corregiria cada monto contra el de otro movimiento."""
    txns = [
        {"description": "TRANSFERENCIA RECIBIDA", "amount": 999.0},
        {"description": "DB. IMPUESTO LEY 25413", "amount": -900.0},
    ]

    verify_and_correct_ledger(txns, _EXTRACTO_CUENTA)

    assert txns[0]["amount"] == 999.0, "no se toca nada ante desalineacion"
    assert "_printed_saldo" not in txns[0]


def test_the_printed_running_balance_is_recorded_for_reconciliation():
    txns = [
        {"description": "A", "amount": 150000.0},
        {"description": "B", "amount": -900.0},
        {"description": "C", "amount": 50000.0},
    ]

    verify_and_correct_ledger(txns, _EXTRACTO_CUENTA)

    assert [t["_printed_saldo"] for t in txns] == [150000.0, 149100.0, 199100.0]


def test_last_printed_saldo_uses_statement_order_not_date_order():
    txns = [
        {"date": "2026-07-20", "_printed_saldo": 199100.0},
        {"date": "2026-07-05", "_printed_saldo": 150000.0},
    ]

    assert last_printed_saldo(txns) == Decimal(
        "150000.0"
    ), "el ultimo del extracto, no el mas nuevo"


def test_reconciliation_gap_is_none_without_any_printed_balance():
    """Sin alineacion posicional no hay contra que comparar, y devolver 0
    haria pasar por conciliado algo que nadie verifico."""
    assert reconciliation_gap([{"amount": 100.0}], Decimal("0")) is None


def test_reconciliation_gap_reports_the_difference_against_the_printed_balance():
    txns = [
        {"amount": 150000.0, "_printed_saldo": 150000.0},
        {"amount": -900.0, "_printed_saldo": 149100.0},
    ]

    assert reconciliation_gap(txns, Decimal("0")) == Decimal("0")
    assert reconciliation_gap(txns, Decimal("500")) == Decimal("500")


# ─────────────────────────── mep_converter ───────────────────────────


def test_an_ars_transaction_gets_its_usd_side_derived():
    txns = [{"amount": -130000.00, "currency": "ARS"}]

    apply_mep_conversion(txns, Decimal("1300"))

    assert txns[0]["amount_ars"] == Decimal("-130000.00")
    assert txns[0]["amount_usd"] == Decimal("-100.0000")


def test_a_usd_transaction_keeps_its_native_amount_and_derives_the_ars_side():
    """La moneda nativa es el dato real del extracto y no se sobreescribe."""
    txns = [{"amount": 250.00, "currency": "USD"}]

    apply_mep_conversion(txns, Decimal("1300"))

    assert txns[0]["amount_usd"] == Decimal("250.00")
    assert txns[0]["amount_ars"] == Decimal("325000.00")


def test_a_transaction_without_an_explicit_currency_is_treated_as_ars():
    txns = [{"amount": 1300.00}]

    apply_mep_conversion(txns, Decimal("1300"))

    assert txns[0]["amount_usd"] == Decimal("1.0000")
