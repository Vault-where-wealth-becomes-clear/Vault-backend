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
