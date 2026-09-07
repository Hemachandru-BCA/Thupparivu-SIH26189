"""
llm_providers.py
----------------
Optional LLM provider interface for dossier generation (Phase F).

Contract:

    class LLMProvider(Protocol):
        name: str
        def generate(self, prompt: str, context: list[dict]) -> str: ...

Implementations:

* :class:`MockLLMProvider`   - deterministic, fully offline; the default so
  the demo never needs API keys.
* :class:`OpenAICompatProvider` - optional adapter for any
  OpenAI-compatible chat endpoint, enabled only when
  ``SENTINELGRAPH_LLM_API_KEY`` is set.

Safety rules enforced by the dossier prompt (see dossier_generator):

* the LLM may not invent evidence, identities, timestamps or relationships;
* the LLM is never the source of truth - malformed output is discarded and
  replaced by a deterministic non-LLM dossier;
* hypotheses must stay hypotheses.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional, Protocol, Sequence

logger = logging.getLogger(__name__)


class LLMProvider(Protocol):
    """Minimal chat-style provider contract."""

    name: str

    def generate(self, prompt: str, context: Sequence[Dict[str, Any]]) -> str:
        ...


class MockLLMProvider:
    """Deterministic offline provider.

    Instead of free-form text generation it renders the bounded context back
    as a structured summary.  The point of the mock is to exercise the full
    dossier pipeline (context construction -> generation -> parse -> validate
    -> persist) without any external dependency, and to guarantee the demo is
    reproducible.
    """

    name = "mock"

    def generate(self, prompt: str, context: Sequence[Dict[str, Any]]) -> str:
        # The mock returns a JSON document describing the context it was
        # given; the dossier generator parses and validates it the same way
        # it would parse a real LLM response.
        payload = {
            "provider": self.name,
            "deterministic": True,
            "sections": [],
            "context_items": len(context),
        }
        for item in context:
            kind = str(item.get("kind", "note"))
            payload["sections"].append(
                {
                    "kind": kind,
                    "title": item.get("title") or kind.replace("_", " ").title(),
                    "items": item.get("items") or [],
                }
            )
        return json.dumps(payload)


class OpenAICompatProvider:
    """Optional adapter for OpenAI-compatible chat APIs.

    Enabled only when ``SENTINELGRAPH_LLM_API_KEY`` is present in the
    environment.  Never required for the demo.  Uses plain ``urllib`` so no
    SDK dependency is added.
    """

    name = "openai-compatible"

    def __init__(self,
                 api_key: Optional[str] = None,
                 base_url: Optional[str] = None,
                 model: Optional[str] = None,
                 timeout: float = 60.0) -> None:
        self.api_key = api_key or os.environ.get("SENTINELGRAPH_LLM_API_KEY", "")
        self.base_url = (base_url or os.environ.get(
            "SENTINELGRAPH_LLM_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self.model = model or os.environ.get("SENTINELGRAPH_LLM_MODEL", "gpt-4o-mini")
        self.timeout = timeout
        if not self.api_key:
            raise ValueError(
                "OpenAICompatProvider requires SENTINELGRAPH_LLM_API_KEY "
                "(or pass api_key= explicitly)"
            )

    def generate(self, prompt: str, context: Sequence[Dict[str, Any]]) -> str:
        from urllib.error import HTTPError, URLError
        from urllib.request import Request, urlopen

        body = json.dumps(
            {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are an intelligence-analysis writing assistant. "
                            "You must never invent evidence, identities, timestamps "
                            "or relationships; only use the provided context. "
                            "You must keep hypotheses labelled as hypotheses and "
                            "never assert guilt or certainty."
                        ),
                    },
                    {
                        "role": "user",
                        "content": prompt + "\n\nCONTEXT (JSON):\n"
                        + json.dumps(list(context), default=str),
                    },
                ],
                "temperature": 0.2,
            }
        ).encode("utf-8")
        req = Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )
        try:
            with urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError) as exc:
            raise RuntimeError(f"LLM provider call failed: {exc}") from exc
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Unexpected LLM response shape: {data!r}") from exc


class GoogleAICompatProvider:
    """Adapter for Google AI Gemini using the Google API key flow.

    This provider expects a Google AI Studio key and uses the Google-specific
    endpoint and header documented by Google's REST quickstart.
    """

    name = "google-ai-compatible"

    def __init__(self,
                 api_key: Optional[str] = None,
                 base_url: Optional[str] = None,
                 model: Optional[str] = None,
                 timeout: float = 60.0) -> None:
        primary_key = api_key or os.environ.get("SENTINELGRAPH_LLM_API_KEY", "")
        fallback_key = os.environ.get("SENTINELGRAPH_LLM_API_KEY_FALLBACK", "")
        self.api_keys = tuple(dict.fromkeys(key.strip() for key in (primary_key, fallback_key) if key.strip()))
        self.api_key = self.api_keys[0] if self.api_keys else ""
        self.base_url = (base_url or os.environ.get(
            "SENTINELGRAPH_LLM_BASE_URL",
            "https://generativelanguage.googleapis.com/v1beta"
        )).rstrip("/")
        self.model = model or os.environ.get("SENTINELGRAPH_LLM_MODEL", "gemini-2.0-flash")
        self.timeout = timeout
        if not self.api_key:
            raise ValueError(
                "GoogleAICompatProvider requires SENTINELGRAPH_LLM_API_KEY "
                "(or pass api_key= explicitly)"
            )

    @property
    def endpoint(self) -> str:
        if "/models/" in self.base_url:
            return self.base_url
        return f"{self.base_url}/models/{self.model}:generateContent"

    def generate(self, prompt: str, context: Sequence[Dict[str, Any]]) -> str:
        from urllib.error import HTTPError, URLError
        from urllib.request import Request, urlopen

        content = prompt + "\n\nCONTEXT (JSON):\n" + json.dumps(list(context), default=str)
        body = json.dumps({
            "contents": [{
                "role": "user",
                "parts": [{"text": content}],
            }]
        }).encode("utf-8")

        last_error = None
        for key_index, api_key in enumerate(self.api_keys):
            req = Request(
                self.endpoint,
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "X-goog-api-key": api_key,
                },
            )
            try:
                with urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                break
            except HTTPError as exc:
                response_body = exc.read().decode("utf-8", errors="replace")
                quota_exhausted = exc.code == 429 or (
                    exc.code == 403
                    and any(token in response_body.lower() for token in (
                        "quota", "resource_exhausted", "rate limit"
                    ))
                )
                last_error = exc
                if not quota_exhausted or key_index == len(self.api_keys) - 1:
                    raise RuntimeError(f"LLM provider call failed: {exc}") from exc
                logger.warning("Primary Google AI key is quota-limited; trying fallback key")
            except (URLError, TimeoutError) as exc:
                raise RuntimeError(f"LLM provider call failed: {exc}") from exc
        else:
            raise RuntimeError(f"LLM provider call failed: {last_error}") from last_error

        try:
            parts = data["candidates"][0]["content"]["parts"]
            return "".join(part.get("text", "") for part in parts)
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Unexpected LLM response shape: {data!r}") from exc


def provider_from_env() -> LLMProvider:
    """Return a real provider if configured, otherwise the offline mock."""
    if os.environ.get("SENTINELGRAPH_LLM_API_KEY"):
        base_url = os.environ.get("SENTINELGRAPH_LLM_BASE_URL", "")
        try:
            if "generativelanguage.googleapis.com" in base_url or "google" in base_url.lower():
                return GoogleAICompatProvider()
            return OpenAICompatProvider()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Falling back to MockLLMProvider: %s", exc)
    return MockLLMProvider()
