import anthropic

from app.config import settings


def _extract_text(message: anthropic.types.Message) -> str:
    """
    Concatena todos los bloques de tipo texto de la respuesta. Asumir que la
    respuesta está siempre en content[0] es frágil: se vio a Sonnet devolver
    un bloque inicial vacío (text=None) seguido del contenido real en el
    segundo bloque — content[0].text solo devolvía None.
    """
    parts = [block.text for block in message.content if getattr(block, "text", None)]
    if not parts:
        raise ValueError(
            f"La respuesta del LLM no tiene ningún bloque de texto con contenido "
            f"(stop_reason={message.stop_reason!r}, bloques={len(message.content)})"
        )
    return "".join(parts)


def call_llm(prompt: str, system: str) -> str:
    """Llama al LLM configurado. El modelo se controla con LLM_MODEL en .env."""
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    message = client.messages.create(
        model=settings.llm_model,
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return _extract_text(message)


def call_llm_with_skill(prompt: str, system: str, model: str | None = None) -> tuple[str, dict]:
    """
    Llama al LLM con el system prompt de la skill (módulos dinámicos), activando
    cache_control sobre el bloque de system para no pagar precio completo en cada
    request — la combinación de módulos pedida se cachea dentro de la sesión.

    `model`: por defecto settings.llm_model (el chico/económico). Pasar
    settings.llm_model_large para extractos grandes — ver
    worker/llm/model_selector.py, que decide esto automáticamente según la
    cantidad de movimientos detectados en el texto, sin gastar tokens.

    Devuelve (texto, uso) — `uso` es un dict con el detalle de tokens para que
    el caller lo persista (ver Upload.llm_*), en vez de que quede solo en el
    log de la terminal.
    """
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    resolved_model = model or settings.llm_model

    extra_body: dict = {}
    if resolved_model == settings.llm_model_large:
        # Sonnet 5 corre con adaptive thinking + effort "high" por defecto
        # cuando no se especifica nada — para una tarea de extracción
        # estructurada (no razonamiento abierto) eso generó 15k+ tokens de
        # thinking por PDF sin necesidad. "medium" da un nivel de
        # inteligencia comparable al "high" de Sonnet 4.6 con mucho menos
        # gasto y latencia.
        # extra_body (no kwargs directos): el SDK instalado (anthropic==0.28.0)
        # es anterior a que "thinking"/"output_config" existieran como
        # parámetros tipados — pasarlos como kwargs tira TypeError.
        extra_body["thinking"] = {"type": "adaptive"}
        extra_body["output_config"] = {"effort": "medium"}

    message = client.messages.create(
        model=resolved_model,
        # 64k, no 16k/32k: con extended thinking, los tokens de razonamiento
        # cuentan contra max_tokens, y varían de una corrida a otra — en
        # pruebas con CA ABR.pdf (49 movimientos, 4 meses) se vieron 15k+
        # tokens solo de thinking, y con cuentas que además piden varios
        # módulos del dashboard (flujo_mensual + categorizacion_gasto +
        # tablero_general) la respuesta completa superó los 32k y se cortó a
        # la mitad. 64k deja margen real. Igual queda el chequeo de
        # stop_reason abajo: si algún día no alcanza, falla explícito en vez
        # de confiar en un JSON parcial.
        max_tokens=64000,
        system=[
            {
                "type": "text",
                "text": system,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": prompt}],
        extra_body=extra_body or None,
    )
    usage = message.usage
    # output_tokens_details llega como dict crudo, no como submodelo, porque
    # el SDK instalado (0.28.0) es anterior a que este campo existiera —
    # Usage lo guarda vía extra="allow" pero sin parsearlo a un objeto, así
    # que getattr() sobre él siempre fallaba en silencio y reportaba 0.
    thinking_details = getattr(usage, "output_tokens_details", None)
    if isinstance(thinking_details, dict):
        thinking_tokens = thinking_details.get("thinking_tokens", 0)
    else:
        thinking_tokens = getattr(thinking_details, "thinking_tokens", 0) if thinking_details else 0
    cache_read = getattr(usage, "cache_read_input_tokens", 0)
    cache_creation = getattr(usage, "cache_creation_input_tokens", 0)
    print(
        f"[worker] usage: input={usage.input_tokens} "
        f"cache_read={cache_read} cache_write={cache_creation} "
        f"output={usage.output_tokens} thinking={thinking_tokens} "
        f"stop_reason={message.stop_reason}"
    )
    if message.stop_reason == "max_tokens":
        raise ValueError(
            "La respuesta del LLM se cortó por límite de tokens (max_tokens) "
            "antes de terminar — no se puede confiar en el JSON parcial."
        )
    usage_dict = {
        "model": resolved_model,
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "thinking_tokens": thinking_tokens,
        "cache_read_tokens": cache_read,
        "cache_creation_tokens": cache_creation,
    }
    return _extract_text(message), usage_dict
