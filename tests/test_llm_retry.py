"""Un 529/5xx pasajero de la API no tiene que costar un ciclo entero de
redelivery de SQS. El SDK ya sabe reintentar; lo que se verifica aca es que
el cliente se construya con presupuesto de reintentos suficiente y que el
reintento efectivamente ocurra de punta a punta."""

import anthropic
import httpx

from worker.llm import client as llm_client


def _message_payload(text: str = "hola") -> dict:
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "model": "claude-test",
        "content": [{"type": "text", "text": text}],
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }


def _overloaded() -> httpx.Response:
    return httpx.Response(
        529,
        json={"type": "error", "error": {"type": "overloaded_error", "message": "Overloaded"}},
    )


def test_client_carries_an_explicit_retry_budget():
    assert llm_client._client().max_retries == llm_client._MAX_RETRIES
    assert llm_client._MAX_RETRIES > 2, "tiene que superar el default del SDK para valer la pena"


def test_transient_overload_is_retried_instead_of_failing_the_upload(monkeypatch):
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        return _overloaded() if len(attempts) < 3 else httpx.Response(200, json=_message_payload())

    monkeypatch.setattr(
        llm_client,
        "_client",
        lambda: anthropic.Anthropic(
            api_key="test",
            max_retries=llm_client._MAX_RETRIES,
            http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        ),
    )

    text, usage = llm_client.call_llm_with_skill("prompt", "system")

    assert text == "hola"
    assert len(attempts) == 3, "dos 529 seguidos se reintentan, no rompen el upload"
    assert usage["input_tokens"] == 10
