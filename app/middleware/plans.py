PLAN_FEATURES = {
    "free": {
        "max_accounts": 1,
        "ai_processing": False,
        "broker_support": False,
        "export_xlsx": False,
        "history_days": 30,
    },
    "pro": {
        "max_accounts": None,
        "ai_processing": True,
        "broker_support": True,
        "export_xlsx": True,
        "history_days": None,
    },
    "family": {
        "max_accounts": None,
        "ai_processing": True,
        "broker_support": True,
        "export_xlsx": True,
        "history_days": None,
        "max_family_members": 4,
        "shared_dashboard": True,
    },
}


PLAN_MODULE_ACCESS = {
    "free": ["flujo_mensual", "categorizacion_gasto"],
    "pro": [
        "flujo_mensual",
        "categorizacion_gasto",
        "flujo_periodo",
        "cuenta_comitente",
        "tablero_general",
        "proyeccion_patrimonial",
        "compromisos_futuros",
    ],
    "family": [
        "flujo_mensual",
        "categorizacion_gasto",
        "flujo_periodo",
        "cuenta_comitente",
        "tablero_general",
        "proyeccion_patrimonial",
        "compromisos_futuros",
    ],
}


def filter_modules_by_plan(requested: list[str], user_plan: str) -> list[str]:
    """Si el usuario Free pide un módulo Pro, se filtra silenciosamente y se avisa en la respuesta."""
    allowed = PLAN_MODULE_ACCESS.get(user_plan, [])
    return [m for m in requested if m in allowed]


def require_plan(*plans: str):
    """Dependency factory: valida que el usuario actual tenga uno de los planes dados."""
    from fastapi import Depends, HTTPException

    from app.middleware.auth import get_current_user
    from app.models.user import User

    async def _checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.plan.value not in plans:
            raise HTTPException(
                status_code=403,
                detail=f"Esta funcion requiere plan {' o '.join(plans)}",
            )
        return current_user

    return _checker
