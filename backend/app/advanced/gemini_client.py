"""Production Gemini API Client (v1beta REST) with model discovery & tool calling.

Never logs or exposes GEMINI_API_KEY.
"""
from __future__ import annotations

import http.client
import json
import os
import urllib.error
import urllib.request
from typing import Any

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
PREFERRED_FLASH_MODELS = (
    "gemini-3.1-flash-lite-preview",
    "gemini-3-flash-preview",
    "gemini-3.5-flash",
)


class GeminiClient:
    """Thin, safe REST client for Google Gemini API v1beta."""

    def __init__(self, api_key: str | None = None, model: str | None = None, timeout_seconds: float = 25.0):
        self._api_key = (api_key or os.getenv("GEMINI_API_KEY") or "").strip()
        env_model = (os.getenv("SAR2ACTION_GEMINI_MODEL") or "").strip()
        self.model = (model or env_model or "gemini-3.1-flash-lite-preview").removeprefix("models/")
        self.timeout_seconds = timeout_seconds

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    def list_generate_models(self) -> list[str]:
        if not self._api_key:
            return []
        url = f"{GEMINI_API_BASE}/models?key={self._api_key}"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return [
            str(m["name"]).removeprefix("models/")
            for m in data.get("models", [])
            if "generateContent" in m.get("supportedGenerationMethods", [])
        ]

    def resolve_working_flash_model(self) -> str | None:
        available = set(self.list_generate_models())
        for candidate in (self.model, *PREFERRED_FLASH_MODELS):
            if candidate in available:
                return candidate
        for name in sorted(available):
            if "flash" in name.lower():
                return name
        return None

    def generate_content(
        self,
        contents: list[dict[str, Any]],
        *,
        system_instruction: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.2,
        max_output_tokens: int = 512,
        model_override: str | None = None,
    ) -> dict[str, Any]:
        if not self._api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")
        target_model = (model_override or self.model).removeprefix("models/")
        url = f"{GEMINI_API_BASE}/models/{target_model}:generateContent?key={self._api_key}"

        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_output_tokens,
                "thinkingConfig": {"thinkingBudget": 0},
            },
        }
        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}
        if tools:
            payload["tools"] = [{"functionDeclarations": tools}]

        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        candidates_to_try = [target_model]
        if model_override is None:
            for alt in PREFERRED_FLASH_MODELS:
                if alt not in candidates_to_try:
                    candidates_to_try.append(alt)

        last_err: Exception | None = None
        for idx, cand_model in enumerate(candidates_to_try):
            cand_url = f"{GEMINI_API_BASE}/models/{cand_model}:generateContent?key={self._api_key}"
            req = urllib.request.Request(cand_url, data=body, headers={"Content-Type": "application/json"}, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                err_body = exc.read().decode("utf-8", errors="replace")
                last_err = RuntimeError(f"Gemini HTTP {exc.code} on model '{cand_model}': {err_body}")
                if exc.code in (404, 429, 503) and idx + 1 < len(candidates_to_try):
                    continue
                raise last_err from None
            except (TimeoutError, urllib.error.URLError, http.client.HTTPException) as exc:
                last_err = RuntimeError(f"Gemini transport/timeout error on model '{cand_model}': {exc}")
                if idx + 1 < len(candidates_to_try):
                    continue
                raise last_err from None
        raise last_err or RuntimeError("Gemini request failed")
