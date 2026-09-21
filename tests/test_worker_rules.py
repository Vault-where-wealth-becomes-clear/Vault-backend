"""Reglas deterministicas que corrigen la salida del LLM en `worker/processing.py`.

Cada una existe porque el LLM se equivoco de una forma concreta y repetible.
Son overrides duros: si estas reglas se rompen, el error vuelve en silencio.
"""

from decimal import Decimal

from worker.processing import (
    _apply_fiscal_rules,
    _apply_transfer_direction_rules,
    _dedup_transactions,
    _extract_opening_balance,
    _extract_tarjeta_remainder,
    _group_by_month,
    _is_cc_payment,
)

# ─────────────────────────── reglas fiscales ───────────────────────────


def test_db_lines_are_taxes_and_always_a_debit():
    txns = [{"description": "DB. IMPUESTO LEY 25413", "amount": 900.0, "category": "Otros"}]

    _apply_fiscal_rules(txns)

    assert txns[0]["category"] == "Impuestos"
    assert txns[0]["amount"] == -900.0


def test_cr_lines_are_taxes_and_always_a_credit():
    """Un CR.* es una devolucion del banco, no un gasto."""
    txns = [{"description": "CR. DEV. IMPUESTO", "amount": -450.0, "category": "Otros"}]

    _apply_fiscal_rules(txns)

    assert txns[0]["category"] == "Impuestos"
    assert txns[0]["amount"] == 450.0


def test_fiscal_rules_leave_ordinary_lines_alone():
    txns = [{"description": "SUPERMERCADO DIA", "amount": -45000.0, "category": "Supermercado"}]

    _apply_fiscal_rules(txns)

    assert txns[0]["category"] == "Supermercado"
    assert txns[0]["amount"] == -45000.0


# ─────────────────────── direccion de transferencias ───────────────────────


def test_a_received_transfer_is_always_a_credit():
    """Visto en extractos de Mercado Pago: 'recibida' y 'enviada' con el signo
    invertido entre si."""
    txns = [{"description": "Transferencia recibida de Juan", "amount": -50000.0}]

    _apply_transfer_direction_rules(txns)

    assert txns[0]["amount"] == 50000.0


def test_a_sent_transfer_is_always_a_debit():
    txns = [{"description": "Transferencia enviada a Ana", "amount": 50000.0}]

    _apply_transfer_direction_rules(txns)

    assert txns[0]["amount"] == -50000.0


def test_yields_are_always_a_credit():
    txns = [{"description": "Rendimientos de tu dinero", "amount": -1234.0}]

    _apply_transfer_direction_rules(txns)

    assert txns[0]["amount"] == 1234.0


def test_a_transfer_with_the_right_sign_is_not_flipped_twice():
    txns = [{"description": "Transferencia recibida de Juan", "amount": 50000.0}]

    _apply_transfer_direction_rules(txns)

    assert txns[0]["amount"] == 50000.0


# ─────────────────────────── agrupado por mes ───────────────────────────


def test_transactions_are_grouped_by_their_own_month():
    txns = [
        {"date": "2026-06-30", "description": "A"},
        {"date": "2026-07-01", "description": "B"},
        {"date": "2026-07-15", "description": "C"},
    ]

    grupos = _group_by_month(txns)

    assert sorted(grupos) == ["2026-06", "2026-07"]
    assert len(grupos["2026-07"]) == 2


def test_transactions_without_a_date_are_dropped_from_the_grouping():
    grupos = _group_by_month([{"description": "sin fecha"}, {"date": "", "description": "vacia"}])

    assert grupos == {}


# ─────────────────────── remanente de tarjeta ───────────────────────


def test_the_card_remainder_is_the_unpaid_part_of_the_previous_period():
    """Las tarjetas quedan fuera del libro_diario por diseño, asi que su saldo
    anterior solo llega por este campo. Sin esto, un saldo no cancelado
    desaparecia del total del periodo."""
    result = {"saldo_tarjeta": {"saldo_anterior_ars": 100000, "pago_ars": 30000}}

    assert _extract_tarjeta_remainder(result, is_usd=False) == Decimal("70000")


def test_a_fully_paid_card_leaves_no_remainder():
    result = {"saldo_tarjeta": {"saldo_anterior_ars": 100000, "pago_ars": 120000}}

    assert _extract_tarjeta_remainder(result, is_usd=False) == Decimal("0"), "nunca negativo"


def test_the_card_remainder_reads_the_currency_it_was_asked_for():
    result = {
        "saldo_tarjeta": {
            "saldo_anterior_ars": 100000,
            "pago_ars": 30000,
            "saldo_anterior_usd": 500,
            "pago_usd": 200,
        }
    }

    assert _extract_tarjeta_remainder(result, is_usd=True) == Decimal("300")


def test_no_card_balance_block_means_no_remainder():
    assert _extract_tarjeta_remainder({}, is_usd=False) == Decimal("0")


# ─────────────────────────── saldo inicial ───────────────────────────


def test_the_opening_balance_comes_from_the_first_account_with_a_real_value():
    result = {
        "flujo_mensual": {
            "libro_diario": {
                "Cuenta vacia": {"saldo_inicial": 0},
                "Caja de ahorro": {"saldo_inicial": 150000},
            }
        }
    }

    assert _extract_opening_balance(result) == (Decimal("150000"), Decimal("0"))
    assert _extract_opening_balance(result, is_usd=True) == (Decimal("0"), Decimal("150000"))


def test_a_missing_opening_balance_is_zero_not_an_error():
    assert _extract_opening_balance({}) == (Decimal("0"), Decimal("0"))


# ─────────────────────────── dedup y pagos de tarjeta ───────────────────────────


def test_the_llm_double_emitting_a_row_in_both_currencies_is_collapsed():
    txns = [
        {"description": "NETFLIX", "date": "2026-07-05", "currency": "ARS", "amount": -13000.0},
        {"description": "NETFLIX", "date": "2026-07-05", "currency": "USD", "amount": -10.0},
    ]

    resultado = _dedup_transactions(txns, "credit_card_usd")

    assert len(resultado) == 1
    assert resultado[0]["currency"] == "USD"


def test_an_ars_card_keeps_the_ars_side_of_the_duplicate():
    txns = [
        {"description": "NETFLIX", "date": "2026-07-05", "currency": "ARS", "amount": -13000.0},
        {"description": "NETFLIX", "date": "2026-07-05", "currency": "USD", "amount": -10.0},
    ]

    resultado = _dedup_transactions(txns, "credit_card_ars")

    assert len(resultado) == 1
    assert resultado[0]["currency"] == "ARS"


def test_two_real_purchases_sharing_description_and_date_are_both_kept():
    """El mismo comercio cobrando dos veces el mismo dia no es un duplicado:
    difieren en monto y en cupon, y las dos tienen que quedar."""
    txns = [
        {"description": "CAFE", "date": "2026-07-05", "currency": "ARS", "amount": -3500.0},
        {"description": "CAFE", "date": "2026-07-05", "currency": "ARS", "amount": -4200.0},
    ]

    assert len(_dedup_transactions(txns, "credit_card_ars")) == 2


def test_statement_order_survives_deduplication():
    txns = [
        {"description": "A", "date": "2026-07-01", "currency": "ARS", "amount": -1.0},
        {"description": "B", "date": "2026-07-02", "currency": "ARS", "amount": -2.0},
        {"description": "B", "date": "2026-07-02", "currency": "USD", "amount": -0.02},
        {"description": "C", "date": "2026-07-03", "currency": "ARS", "amount": -3.0},
    ]

    resultado = _dedup_transactions(txns, "credit_card_ars")

    assert [t["description"] for t in resultado] == ["A", "B", "C"]


def test_card_payment_lines_are_recognised():
    assert _is_cc_payment("SU PAGO EN PESOS")
    assert _is_cc_payment("su pago anterior")
    assert _is_cc_payment("PAGO MINIMO")
    assert not _is_cc_payment("SUPERMERCADO DIA")
