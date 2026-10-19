"""Minimal client for a Qwen model served behind an OpenAI-compatible ``/chat/completions`` endpoint.

Works with vLLM, SGLang, Ollama, DashScope compatible mode, OpenRouter, Hugging Face router and similar.
Configuration comes from the environment (or .env): QWEN_BASE_URL (ending in /v1), QWEN_API_KEY
(optional for local servers) and QWEN_MODEL (default Qwen/Qwen3.5-4B).
"""
from __future__ import annotations

import os
import random
import time
from typing import Any

import requests

DEFAULT_MODEL = "Qwen/Qwen3.5-4B"
RETRYABLE_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}


class QwenError(RuntimeError):
    pass


class QwenClient:
    def __init__(self, base_url: str | None = None, api_key: str | None = None, model: str | None = None,
                 timeout: float = 300.0, max_retries: int = 6, response_format: str = "none",
                 thinking: bool | None = False, temperature: float = 0.3, max_tokens: int = 4000) -> None:
        self.base_url = (base_url or os.environ.get("QWEN_BASE_URL", "")).rstrip("/")
        if not self.base_url:
            raise QwenError("Set QWEN_BASE_URL (for example http://localhost:8000/v1) in the environment or .env")
        self.model = model or os.environ.get("QWEN_MODEL") or DEFAULT_MODEL
        self.timeout = timeout
        self.max_retries = max_retries
        self.response_format = response_format
        self.thinking = thinking
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.session = requests.Session()
        api_key = api_key or os.environ.get("QWEN_API_KEY")
        if api_key:
            self.session.headers["Authorization"] = f"Bearer {api_key}"

    def _body(self, messages: list[dict[str, str]], schema: dict[str, Any]) -> dict[str, Any]:
        body: dict[str, Any] = {"model": self.model, "messages": messages, "temperature": self.temperature,
                                "max_tokens": self.max_tokens}
        if self.response_format == "json_schema":
            body["response_format"] = {"type": "json_schema",
                                       "json_schema": {"name": "variants", "schema": schema, "strict": True}}
        elif self.response_format == "json_object":
            body["response_format"] = {"type": "json_object"}
        if self.thinking is not None:
            # Qwen3-family chat template switch; honoured by vLLM/SGLang, ignored by servers that don't know it.
            body["chat_template_kwargs"] = {"enable_thinking": self.thinking}
        return body

    def complete(self, messages: list[dict[str, str]], schema: dict[str, Any]) -> tuple[str, dict[str, int]]:
        """Return (assistant text, usage). Retries rate limits, server errors and network failures."""
        url = f"{self.base_url}/chat/completions"
        body = self._body(messages, schema)
        for attempt in range(self.max_retries + 1):
            try:
                response = self.session.post(url, json=body, timeout=self.timeout)
            except requests.RequestException as error:
                failure: str | None = f"network error: {error}"
            else:
                if response.status_code == 200:
                    payload = response.json()
                    choice = payload["choices"][0]
                    if choice.get("finish_reason") == "length":
                        raise QwenError(f"reply cut off at max_tokens={self.max_tokens}")
                    text = choice["message"].get("content") or ""
                    return text, payload.get("usage") or {}
                if response.status_code not in RETRYABLE_STATUS:
                    raise QwenError(f"HTTP {response.status_code}: {response.text[:500]}")
                failure = f"HTTP {response.status_code}"
                retry_after = response.headers.get("retry-after")
                if retry_after and retry_after.isdigit() and attempt < self.max_retries:
                    time.sleep(int(retry_after))
                    continue
            if attempt == self.max_retries:
                raise QwenError(f"giving up after {self.max_retries} retries: {failure}")
            time.sleep(min(2 ** attempt, 60) + random.uniform(0, 1))
        raise AssertionError("unreachable")
