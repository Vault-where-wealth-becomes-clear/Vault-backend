import json


def parse_llm_response(raw: str) -> list[dict]:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
    data = json.loads(cleaned)
    if not isinstance(data, list):
        raise ValueError("La respuesta de Claude no es un array JSON")
    return data
