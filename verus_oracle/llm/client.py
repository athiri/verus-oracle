from __future__ import annotations

from dataclasses import dataclass

import anthropic

DEFAULT_MODEL = "claude-opus-4-7"


@dataclass(frozen=True)
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int
    cache_creation_input_tokens: int


class LLMClient:
    """Thin wrapper around `anthropic.Anthropic` with automatic prefix caching.

    The router and per-pattern prompts are stable across requests, so they go
    in `system` and are auto-cached via top-level `cache_control`. The varying
    snippet goes in `messages` so it doesn't invalidate the cache.
    """

    def __init__(self, model: str = DEFAULT_MODEL, api_key: str | None = None):
        self.model = model
        self._client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    def call(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int = 1024,
        output_schema: dict | None = None,
    ) -> LLMResponse:
        kwargs: dict = {
            "model": self.model,
            "max_tokens": max_tokens,
            "cache_control": {"type": "ephemeral"},
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        if output_schema is not None:
            kwargs["output_config"] = {
                "format": {
                    "type": "json_schema",
                    "schema": output_schema,
                }
            }

        response = self._client.messages.create(**kwargs)
        text = next((b.text for b in response.content if b.type == "text"), "")
        usage = response.usage
        return LLMResponse(
            text=text,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_read_input_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
            cache_creation_input_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
        )
