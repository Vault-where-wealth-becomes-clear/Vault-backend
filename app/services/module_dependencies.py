from app.models.enums import SkillModule

MODULE_DEPENDENCIES: dict[str, list[str]] = {
    SkillModule.categorizacion_gasto.value: [SkillModule.flujo_mensual.value],
    SkillModule.flujo_periodo.value: [SkillModule.flujo_mensual.value],
    SkillModule.tablero_general.value: [SkillModule.flujo_mensual.value],
    SkillModule.proyeccion_patrimonial.value: [SkillModule.tablero_general.value],
    SkillModule.compromisos_futuros.value: [],
}

# Mapeo módulo -> columna JSONB correspondiente en financial_snapshots
MODULE_SNAPSHOT_FIELD: dict[str, str] = {
    SkillModule.flujo_mensual.value: "flujo_mensual",
    SkillModule.categorizacion_gasto.value: "categorizacion",
    SkillModule.flujo_periodo.value: "flujo_periodo",
    SkillModule.cuenta_comitente.value: "cartera",
    SkillModule.tablero_general.value: "tablero_general",
    SkillModule.proyeccion_patrimonial.value: "proyeccion",
    SkillModule.compromisos_futuros.value: "compromisos",
}


def resolve_required_modules(requested: list[str], user_history: dict | None) -> list[str]:
    """
    Dado lo que el usuario pidió, devuelve el set completo de módulos a ejecutar,
    agregando dependencias no satisfechas por el histórico ya calculado.
    Si una dependencia ya está resuelta en financial_snapshots del mismo período
    (snapshot del mes corriente), NO se vuelve a ejecutar — se reusa el JSON guardado.
    """
    user_history = user_history or {}
    resolved: list[str] = []
    seen: set[str] = set()

    def _add(module: str) -> None:
        if module in seen:
            return
        for dependency in MODULE_DEPENDENCIES.get(module, []):
            field = MODULE_SNAPSHOT_FIELD.get(dependency)
            already_satisfied = field is not None and user_history.get(field) is not None
            if not already_satisfied:
                _add(dependency)
        seen.add(module)
        resolved.append(module)

    for module in requested:
        _add(module)

    return resolved
