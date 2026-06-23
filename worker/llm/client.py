import anthropic

from app.config import settings


def call_llm(prompt: str, system: str) -> str:
    """Llama al LLM configurado. El modelo se controla con LLM_MODEL en .env."""
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    message = client.messages.create(
        model=settings.llm_model,
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def call_llm_with_skill(prompt: str, system: str) -> str:
    """
    Llama al LLM con el system prompt de la skill (módulos dinámicos), activando
    cache_control sobre el bloque de system para no pagar precio completo en cada
    request — la combinación de módulos pedida se cachea dentro de la sesión.
    """
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    message = client.messages.create(
        model=settings.llm_model,
        max_tokens=8192,
        system=[
            {
                "type": "text",
                "text": system,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": prompt}],
    )
    usage = message.usage
    print(
        f"[worker] usage: input={usage.input_tokens} "
        f"cache_read={getattr(usage, 'cache_read_input_tokens', 0)} "
        f"cache_write={getattr(usage, 'cache_creation_input_tokens', 0)} "
        f"output={usage.output_tokens}"
    )
    return message.content[0].text
