import json


def _strip_markdown_fence(raw: str) -> str:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
    return cleaned


def parse_llm_response(raw: str) -> list[dict]:
    data = json.loads(_strip_markdown_fence(raw))
    if not isinstance(data, list):
        raise ValueError("La respuesta de Claude no es un array JSON")
    return data


def parse_skill_response(raw: str) -> dict:
    """
    Valida la respuesta completa de la skill: un objeto JSON con la clave
    "transacciones" obligatoria y, opcionalmente, una clave por cada módulo
    efectivamente procesado.
    """
    data = json.loads(_strip_markdown_fence(raw))
    if not isinstance(data, dict):
        raise ValueError("La respuesta de la skill no es un objeto JSON")
    if "transacciones" not in data or not isinstance(data["transacciones"], list):
        raise ValueError("La respuesta de la skill no incluye la clave 'transacciones'")
    return data
