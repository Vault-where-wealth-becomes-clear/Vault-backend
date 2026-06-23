from functools import cache
from pathlib import Path

SKILLS_DIR = Path(__file__).parent.parent.parent / "app" / "skills" / "finanzas_personales"

MODULE_FILE_MAP = {
    "flujo_mensual": "01_flujo_mensual.md",
    "categorizacion_gasto": "02_categorizacion_gasto.md",
    "flujo_periodo": "03_flujo_periodo.md",
    "cuenta_comitente": "04_cuenta_comitente.md",
    "tablero_general": "05_tablero_general.md",
    "proyeccion_patrimonial": "06_proyeccion_patrimonial.md",
    "compromisos_futuros": "complementario_compromisos_futuros.md",
}


@cache
def _load_fragment(filename: str) -> str:
    return (SKILLS_DIR / filename).read_text(encoding="utf-8")


def build_skill_system_prompt(resolved_modules: list[str]) -> str:
    """
    Construye el system prompt SOLO con los módulos resueltos (pedidos + dependencias).
    Las reglas inviolables y el módulo 0 (registro de cuentas) SIEMPRE se incluyen —
    son la base estructural de cualquier análisis, sin excepción.
    """
    parts = [
        _load_fragment("reglas_inviolables.md"),
        _load_fragment("00_registro_cuentas.md"),
    ]
    for module in resolved_modules:
        filename = MODULE_FILE_MAP.get(module)
        if filename:
            parts.append(_load_fragment(filename))

    parts.append(_load_fragment("_output_contract.md"))
    return "\n\n---\n\n".join(parts)
