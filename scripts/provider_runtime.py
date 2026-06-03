#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from base64 import urlsafe_b64encode
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from sqlite_runtime import SQLiteStore


ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "providers.json"
SUPPORTED_PROTOCOLS = {"anthropic_compatible", "openai_compatible", "gemini", "mock"}
SUPPORTED_AUTH_SCHEMES = {"x_api_key", "bearer", "x_goog_api_key", "none"}
SUPPORTED_MODEL_LOOKUP_MODES = {"skip", "get_single", "list_contains"}
SECRET_KEY_ENV = "QUESTION_BANK_SECRET_KEY"


@dataclass(frozen=True)
class ProviderConfig:
    provider_id: str
    display_name: str
    protocol: str
    base_url: str
    auth_scheme: str
    auth_env: str
    headers_template: dict[str, str]
    model_lookup_mode: str
    enabled: bool = True


@dataclass(frozen=True)
class ModelConfig:
    model_alias: str
    provider_id: str
    display_name: str
    model_name: str
    default_timeout: int
    default_max_tokens: int
    supports_multi_turn: bool
    enabled: bool


class ProviderError(RuntimeError):
    def __init__(self, message: str, failure_type: str, status_code: int | None = None):
        super().__init__(message)
        self.failure_type = failure_type
        self.status_code = status_code


def _derive_fernet() -> Fernet:
    raw = os.environ.get(SECRET_KEY_ENV, "").strip()
    if not raw:
        raise ProviderError(
            f"Missing secret master key env: {SECRET_KEY_ENV}",
            "model_validation_failed",
        )
    key = urlsafe_b64encode(raw.encode("utf-8").ljust(32, b"0")[:32])
    return Fernet(key)


def encrypt_secret(value: str) -> str:
    return _derive_fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str | None) -> str:
    if not value:
        return ""
    try:
        return _derive_fernet().decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ProviderError("Stored API key cannot be decrypted with current master key", "model_validation_failed") from exc


def classify_error_message(message: str) -> str:
    lowered = (message or "").lower()
    if "timed out" in lowered and "read" in lowered:
        return "read_timeout"
    if "timed out" in lowered or "connecttimeout" in lowered or "connection timed out" in lowered:
        return "connect_timeout"
    if "http 429" in lowered:
        return "http_429"
    if "http 529" in lowered or "overloaded_error" in lowered:
        return "http_529_overloaded"
    if "new_sensitive" in lowered or "sensitive" in lowered:
        return "provider_sensitive_filter"
    if "http 500" in lowered:
        return "http_500"
    if "validation_failed" in lowered or "model validation" in lowered:
        return "model_validation_failed"
    return "unknown_provider_error"


def _normalize_provider_payload(item: dict[str, Any]) -> ProviderConfig:
    return ProviderConfig(
        provider_id=item["provider_id"],
        display_name=item["display_name"],
        protocol=item["protocol"],
        base_url=item["base_url"].rstrip("/"),
        auth_scheme=item["auth_scheme"],
        auth_env=item.get("auth_env", ""),
        headers_template=item.get("headers_template", {}),
        model_lookup_mode=item.get("model_lookup_mode", "skip"),
        enabled=bool(item.get("enabled", True)),
    )


def _normalize_model_payload(item: dict[str, Any]) -> ModelConfig:
    return ModelConfig(
        model_alias=item["model_alias"],
        provider_id=item["provider_id"],
        display_name=item["display_name"],
        model_name=item["model_name"],
        default_timeout=int(item.get("default_timeout", 45)),
        default_max_tokens=int(item.get("default_max_tokens", 512)),
        supports_multi_turn=bool(item.get("supports_multi_turn", True)),
        enabled=bool(item.get("enabled", True)),
    )


def _load_payload(path: Path = CONFIG_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_config(path: Path = CONFIG_PATH) -> tuple[dict[str, ProviderConfig], dict[str, ModelConfig]]:
    payload = _load_payload(path)
    providers = {
        item["provider_id"]: _normalize_provider_payload(item)
        for item in payload.get("providers", [])
    }
    models = {
        item["model_alias"]: _normalize_model_payload(item)
        for item in payload.get("models", [])
    }
    return providers, models


def _write_payload(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _validate_provider_input(payload: dict[str, Any], *, existing_id: str | None = None) -> dict[str, Any]:
    provider_id = (payload.get("provider_id") or existing_id or "").strip()
    if not provider_id:
        raise ProviderError("provider_id is required", "model_validation_failed")
    protocol = payload.get("protocol")
    if protocol not in SUPPORTED_PROTOCOLS:
        raise ProviderError(f"Unsupported protocol: {protocol}", "model_validation_failed")
    auth_scheme = payload.get("auth_scheme")
    if auth_scheme not in SUPPORTED_AUTH_SCHEMES:
        raise ProviderError(f"Unsupported auth scheme: {auth_scheme}", "model_validation_failed")
    model_lookup_mode = payload.get("model_lookup_mode", "skip")
    if model_lookup_mode not in SUPPORTED_MODEL_LOOKUP_MODES:
        raise ProviderError(f"Unsupported model lookup mode: {model_lookup_mode}", "model_validation_failed")
    base_url = (payload.get("base_url") or "").strip().rstrip("/")
    if protocol != "mock" and not base_url:
        raise ProviderError("base_url is required", "model_validation_failed")
    auth_env = (payload.get("auth_env") or "").strip()
    if auth_scheme != "none" and not auth_env:
        raise ProviderError("auth_env is required for authenticated providers", "model_validation_failed")
    if auth_scheme != "none" and (auth_env.startswith("sk-") or len(auth_env) > 80 or not re.match(r"^[A-Z][A-Z0-9_]*$", auth_env)):
        raise ProviderError(
            "auth_env must be an environment variable name such as MINIMAX_API_KEY, not a raw API key",
            "model_validation_failed",
        )
    headers_template = payload.get("headers_template") or {}
    if not isinstance(headers_template, dict):
        raise ProviderError("headers_template must be an object", "model_validation_failed")
    normalized = {
        "provider_id": provider_id,
        "display_name": (payload.get("display_name") or provider_id).strip(),
        "protocol": protocol,
        "base_url": base_url or "mock://local",
        "auth_scheme": auth_scheme,
        "auth_env": auth_env,
        "headers_template": headers_template,
        "model_lookup_mode": model_lookup_mode,
        "enabled": bool(payload.get("enabled", True)),
    }
    return normalized


def _validate_model_input(payload: dict[str, Any], provider_ids: set[str], *, existing_alias: str | None = None) -> dict[str, Any]:
    model_alias = (payload.get("model_alias") or existing_alias or "").strip()
    if not model_alias:
        raise ProviderError("model_alias is required", "model_validation_failed")
    provider_id = (payload.get("provider_id") or "").strip()
    if provider_id not in provider_ids:
        raise ProviderError(f"provider_id not found: {provider_id}", "model_validation_failed")
    model_name = (payload.get("model_name") or "").strip()
    if not model_name:
        raise ProviderError("model_name is required", "model_validation_failed")
    normalized = {
        "model_alias": model_alias,
        "provider_id": provider_id,
        "display_name": (payload.get("display_name") or model_alias).strip(),
        "model_name": model_name,
        "default_timeout": int(payload.get("default_timeout", 45)),
        "default_max_tokens": int(payload.get("default_max_tokens", 512)),
        "supports_multi_turn": bool(payload.get("supports_multi_turn", True)),
        "enabled": bool(payload.get("enabled", True)),
    }
    return normalized


def _validate_connection_input(payload: dict[str, Any], *, existing_connection_id: str | None = None) -> dict[str, Any]:
    protocol = payload.get("protocol")
    if protocol not in SUPPORTED_PROTOCOLS:
        raise ProviderError(f"Unsupported protocol: {protocol}", "model_validation_failed")
    auth_scheme = payload.get("auth_scheme")
    if auth_scheme not in SUPPORTED_AUTH_SCHEMES:
        raise ProviderError(f"Unsupported auth scheme: {auth_scheme}", "model_validation_failed")
    model_lookup_mode = payload.get("model_lookup_mode", "skip")
    if model_lookup_mode not in SUPPORTED_MODEL_LOOKUP_MODES:
        raise ProviderError(f"Unsupported model lookup mode: {model_lookup_mode}", "model_validation_failed")
    display_name = (payload.get("display_name") or "").strip()
    vendor_name = (payload.get("vendor_name") or "").strip()
    model_name = (payload.get("model_name") or "").strip()
    base_url = (payload.get("base_url") or "").strip().rstrip("/")
    if not vendor_name:
        raise ProviderError("vendor_name is required", "model_validation_failed")
    if not display_name:
        raise ProviderError("display_name is required", "model_validation_failed")
    if protocol != "mock" and not base_url:
        raise ProviderError("base_url is required", "model_validation_failed")
    if not model_name:
        raise ProviderError("model_name is required", "model_validation_failed")
    api_key = (payload.get("api_key") or "").strip()
    auth_env = (payload.get("auth_env") or "").strip()
    if auth_scheme != "none" and not api_key and not auth_env and not payload.get("keep_existing_secret"):
        raise ProviderError("api_key or auth_env is required", "model_validation_failed")
    if api_key and (len(api_key) < 12 or re.fullmatch(r"[A-Z][A-Z0-9_]*", api_key)):
        raise ProviderError("api_key looks invalid; please provide the real secret value", "model_validation_failed")
    if auth_env and (auth_env.startswith("sk-") or len(auth_env) > 80 or not re.match(r"^[A-Z][A-Z0-9_]*$", auth_env)):
        raise ProviderError("auth_env must be an environment variable name", "model_validation_failed")
    headers_template = payload.get("headers_template") or {}
    if not isinstance(headers_template, dict):
        raise ProviderError("headers_template must be an object", "model_validation_failed")
    connection_id = (payload.get("connection_id") or existing_connection_id or "").strip() or f"conn_{slugify(vendor_name)}_{slugify(display_name)}"
    provider_id = (payload.get("provider_id") or f"provider_{connection_id}").strip()
    model_alias = (payload.get("model_alias") or f"model_{connection_id}").strip()
    return {
        "connection_id": connection_id,
        "vendor_name": vendor_name,
        "note": (payload.get("note") or "").strip() or None,
        "homepage_url": (payload.get("homepage_url") or "").strip() or None,
        "display_name": display_name,
        "protocol": protocol,
        "base_url": base_url or "mock://local",
        "auth_scheme": auth_scheme,
        "auth_env": auth_env,
        "api_key": api_key,
        "provider_id": provider_id,
        "model_alias": model_alias,
        "model_name": model_name,
        "default_timeout": int(payload.get("default_timeout", 45)),
        "default_max_tokens": int(payload.get("default_max_tokens", 512)),
        "supports_multi_turn": bool(payload.get("supports_multi_turn", True)),
        "enabled": bool(payload.get("enabled", True)),
        "headers_template": headers_template,
        "model_lookup_mode": model_lookup_mode,
        "advanced": payload.get("advanced") or {},
        "keep_existing_secret": bool(payload.get("keep_existing_secret")),
    }


def slugify(text: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "_", text.strip().lower())
    return re.sub(r"^_+|_+$", "", value)[:40] or "item"


def _build_auth_headers(provider: ProviderConfig, api_key: str) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    headers.update(provider.headers_template or {})
    if provider.auth_scheme == "x_api_key":
        headers["X-Api-Key"] = api_key
    elif provider.auth_scheme == "bearer":
        headers["Authorization"] = f"Bearer {api_key}"
    elif provider.auth_scheme == "x_goog_api_key":
        headers["x-goog-api-key"] = api_key
    elif provider.auth_scheme == "none":
        pass
    else:
        raise ProviderError(
            f"Unsupported auth scheme: {provider.auth_scheme}",
            failure_type="unknown_provider_error",
        )
    return headers


class BaseProvider:
    def __init__(self, provider: ProviderConfig, model: ModelConfig, api_key: str, timeout: int | None = None):
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.timeout = timeout or model.default_timeout

    def _request(self, method: str, url: str, payload: dict | None = None) -> dict[str, Any]:
        last_error: ProviderError | None = None
        retryable = {"connect_timeout", "read_timeout", "http_429", "http_529_overloaded", "unknown_provider_error"}
        for attempt in range(1, 4):
            try:
                return self._curl_request(method, url, payload)
            except FileNotFoundError:
                body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
                req = urllib.request.Request(
                    url,
                    data=body,
                    method=method,
                    headers=_build_auth_headers(self.provider, self.api_key),
                )
                try:
                    with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                        return json.loads(resp.read().decode("utf-8"))
                except urllib.error.HTTPError as exc:
                    raw = exc.read().decode("utf-8", errors="replace")
                    failure_type = classify_error_message(f"http {exc.code}: {raw[:500]}")
                    last_error = ProviderError(
                        f"http {exc.code}: {raw[:500]}",
                        failure_type=failure_type,
                        status_code=exc.code,
                    )
                except urllib.error.URLError as exc:
                    failure_type = classify_error_message(str(exc))
                    last_error = ProviderError(str(exc), failure_type=failure_type)
                except TimeoutError as exc:
                    last_error = ProviderError(str(exc), failure_type="read_timeout")
            except ProviderError as exc:
                last_error = exc
            if attempt < 3 and last_error.failure_type in retryable:
                time.sleep(1.5 * attempt)
                continue
            raise last_error
        raise last_error or ProviderError("unknown provider error", failure_type="unknown_provider_error")

    def _curl_request(self, method: str, url: str, payload: dict | None = None) -> dict[str, Any]:
        if not shutil.which("curl"):
            raise FileNotFoundError("curl")
        body = "" if payload is None else json.dumps(payload, ensure_ascii=False)
        headers = _build_auth_headers(self.provider, self.api_key)
        connect_timeout = min(60, max(5, int(self.timeout)))
        config_lines = [
            f'url = "{url}"',
            f'request = "{method}"',
            "silent",
            "show-error",
            "fail-with-body",
            f"connect-timeout = {connect_timeout}",
            f"max-time = {max(1, int(self.timeout))}",
        ]
        for key, value in headers.items():
            escaped = str(value).replace('"', '\\"')
            config_lines.append(f'header = "{key}: {escaped}"')
        cmd = ["curl", "--config", "-"]
        if body:
            cmd.extend(["--data-binary", body])
        proc = subprocess.run(
            cmd,
            input="\n".join(config_lines) + "\n",
            capture_output=True,
            text=True,
            timeout=max(5, int(self.timeout) + 5),
            check=False,
        )
        if proc.returncode != 0:
            raw = (proc.stdout or proc.stderr or "").strip()
            failure_type = classify_error_message(raw)
            if proc.returncode == 28:
                failure_type = "connect_timeout" if "connect" in raw.lower() else "read_timeout"
            raise ProviderError(raw[:500] or f"curl failed with code {proc.returncode}", failure_type=failure_type)
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise ProviderError(proc.stdout[:500], failure_type="unknown_provider_error") from exc

    def validate_model(self) -> dict[str, Any]:
        mode = self.provider.model_lookup_mode
        if mode == "skip":
            return {"ok": True, "mode": "skip"}
        if mode == "get_single":
            return self._request("GET", f"{self.provider.base_url}/models/{urllib.parse.quote(self.model.model_name, safe='')}")
        if mode == "list_contains":
            payload = self._request("GET", f"{self.provider.base_url}/models")
            rows = payload.get("data") or payload.get("models") or []
            match = next(
                (row for row in rows if row.get("id") == self.model.model_name or row.get("name") == self.model.model_name),
                None,
            )
            if match is None:
                raise ProviderError(
                    f"model validation_failed: {self.model.model_name} not found",
                    failure_type="model_validation_failed",
                )
            return {"ok": True, "model": match}
        raise ProviderError(
            f"Unsupported model lookup mode: {mode}",
            failure_type="unknown_provider_error",
        )

    def complete_messages(self, messages: list[dict[str, str]], max_tokens: int = 512) -> dict[str, Any]:
        raise NotImplementedError

    def extract_text(self, response: dict[str, Any]) -> str:
        raise NotImplementedError

    def sanitize_response(self, response: dict[str, Any]) -> dict[str, Any]:
        return {
            "provider_id": self.provider.provider_id,
            "model_alias": self.model.model_alias,
            "model_name": self.model.model_name,
            "text": self.extract_text(response),
            "raw": response,
        }


class AnthropicCompatibleProvider(BaseProvider):
    def complete_messages(self, messages: list[dict[str, str]], max_tokens: int = 512) -> dict[str, Any]:
        payload = {
            "model": self.model.model_name,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        return self._request("POST", f"{self.provider.base_url}/messages", payload)

    def extract_text(self, response: dict[str, Any]) -> str:
        blocks = response.get("content", [])
        texts = []
        for block in blocks:
            if isinstance(block, dict) and block.get("type") == "text":
                texts.append(block.get("text", ""))
        return "\n".join(texts).strip()

    def sanitize_response(self, response: dict[str, Any]) -> dict[str, Any]:
        return {
            "provider_id": self.provider.provider_id,
            "model_alias": self.model.model_alias,
            "model_name": response.get("model", self.model.model_name),
            "text": self.extract_text(response),
            "usage": response.get("usage"),
            "stop_reason": response.get("stop_reason"),
            "base_resp": response.get("base_resp"),
            "id": response.get("id"),
            "type": response.get("type"),
        }


class OpenAICompatibleProvider(BaseProvider):
    def complete_messages(self, messages: list[dict[str, str]], max_tokens: int = 512) -> dict[str, Any]:
        payload = {
            "model": self.model.model_name,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        return self._request("POST", f"{self.provider.base_url}/chat/completions", payload)

    def extract_text(self, response: dict[str, Any]) -> str:
        choices = response.get("choices") or []
        if not choices:
            return ""
        message = choices[0].get("message") or {}
        content = message.get("content", "")
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block.get("text", ""))
            return "\n".join(parts).strip()
        return str(content).strip()

    def sanitize_response(self, response: dict[str, Any]) -> dict[str, Any]:
        return {
            "provider_id": self.provider.provider_id,
            "model_alias": self.model.model_alias,
            "model_name": response.get("model", self.model.model_name),
            "text": self.extract_text(response),
            "usage": response.get("usage"),
            "finish_reason": (response.get("choices") or [{}])[0].get("finish_reason"),
            "id": response.get("id"),
        }


class GeminiProvider(BaseProvider):
    def complete_messages(self, messages: list[dict[str, str]], max_tokens: int = 512) -> dict[str, Any]:
        contents = []
        for message in messages:
            role = "user" if message.get("role") == "user" else "model"
            contents.append({"role": role, "parts": [{"text": message.get("content", "")}]})
        payload = {
            "contents": contents,
            "generationConfig": {"maxOutputTokens": max_tokens},
        }
        model_name = self.model.model_name
        if not model_name.startswith("models/"):
            model_name = f"models/{model_name}"
        return self._request("POST", f"{self.provider.base_url}/{model_name}:generateContent", payload)

    def validate_model(self) -> dict[str, Any]:
        mode = self.provider.model_lookup_mode
        if mode == "skip":
            return {"ok": True, "mode": "skip"}
        model_name = self.model.model_name
        if not model_name.startswith("models/"):
            model_name = f"models/{model_name}"
        return self._request("GET", f"{self.provider.base_url}/{model_name}")

    def extract_text(self, response: dict[str, Any]) -> str:
        candidates = response.get("candidates") or []
        if not candidates:
            return ""
        parts = ((candidates[0].get("content") or {}).get("parts")) or []
        return "\n".join(part.get("text", "") for part in parts if isinstance(part, dict)).strip()

    def sanitize_response(self, response: dict[str, Any]) -> dict[str, Any]:
        return {
            "provider_id": self.provider.provider_id,
            "model_alias": self.model.model_alias,
            "model_name": self.model.model_name,
            "text": self.extract_text(response),
            "usage": response.get("usageMetadata"),
            "finish_reason": (response.get("candidates") or [{}])[0].get("finishReason"),
        }


class MockProvider(BaseProvider):
    def validate_model(self) -> dict[str, Any]:
        return {"ok": True, "mode": "mock"}

    def complete_messages(self, messages: list[dict[str, str]], max_tokens: int = 512) -> dict[str, Any]:
        time.sleep(0.01)
        prompt = messages[-1]["content"] if messages else ""
        lowered = prompt.lower()
        if "json" in lowered:
            text = '{"alpha": 1, "beta": "ok", "gamma": true}'
        elif "只输出完整函数代码" in prompt or "function" in lowered:
            text = "def mock_solution(*args, **kwargs):\n    return 42"
        elif "答案" in prompt or "option" in lowered or "选项" in prompt:
            text = "答案：A"
        elif "不能" in prompt or "违规" in prompt or "illegal" in lowered:
            text = "抱歉，我不能帮助处理这个请求。"
        elif "只输出数字" in prompt or "number only" in lowered:
            text = "42"
        elif "summary" in lowered or "summarize" in lowered:
            text = "This is a short summary generated by the mock provider."
        else:
            text = f"MOCK RESPONSE: {prompt[:max_tokens]}"
        return {
            "id": "mock-response",
            "model": self.model.model_name,
            "content": [{"type": "text", "text": text}],
            "usage": {"input_tokens": len(prompt.split()), "output_tokens": len(text.split())},
            "stop_reason": "stop",
        }

    def extract_text(self, response: dict[str, Any]) -> str:
        blocks = response.get("content", [])
        return "\n".join(block.get("text", "") for block in blocks if isinstance(block, dict)).strip()


PROTOCOL_MAP = {
    "anthropic_compatible": AnthropicCompatibleProvider,
    "openai_compatible": OpenAICompatibleProvider,
    "gemini": GeminiProvider,
    "mock": MockProvider,
}


class ProviderRegistry:
    def __init__(self, config_path: Path = CONFIG_PATH):
        self.config_path = config_path
        self.store = SQLiteStore(legacy_config_path=self.config_path)
        self.reload()

    def reload(self) -> None:
        self.providers = {
            item["provider_id"]: _normalize_provider_payload(item)
            for item in self.store.load_providers()
        }
        self.models = {
            item["model_alias"]: _normalize_model_payload(item)
            for item in self.store.load_models()
        }
        self.model_connections = {item["connection_id"]: item for item in self.store.load_model_connections()}

    def _sync_legacy_config(self) -> None:
        payload = {
            "providers": [asdict(provider) for provider in self.providers.values()],
            "models": [asdict(model) for model in self.models.values()],
        }
        payload["providers"].sort(key=lambda row: row["provider_id"])
        payload["models"].sort(key=lambda row: row["model_alias"])
        _write_payload(self.config_path, payload)

    def list_providers(self) -> list[dict[str, Any]]:
        rows = []
        for provider in self.providers.values():
            configured = bool(provider.auth_env) and bool(os.environ.get(provider.auth_env, "").strip())
            if provider.auth_scheme == "none":
                configured = True
            rows.append(
                {
                    "provider_id": provider.provider_id,
                    "display_name": provider.display_name,
                    "protocol": provider.protocol,
                    "base_url": provider.base_url,
                    "auth_scheme": provider.auth_scheme,
                    "configured": configured,
                    "auth_env": provider.auth_env,
                    "headers_template": provider.headers_template,
                    "model_lookup_mode": provider.model_lookup_mode,
                    "enabled": provider.enabled,
                }
            )
        rows.sort(key=lambda row: row["provider_id"])
        return rows

    def list_models(self, provider_id: str | None = None) -> list[dict[str, Any]]:
        rows = []
        for model in self.models.values():
            if provider_id and model.provider_id != provider_id:
                continue
            rows.append(
                {
                    "model_alias": model.model_alias,
                    "provider_id": model.provider_id,
                    "display_name": model.display_name,
                    "model_name": model.model_name,
                    "default_timeout": model.default_timeout,
                    "default_max_tokens": model.default_max_tokens,
                    "supports_multi_turn": model.supports_multi_turn,
                    "enabled": model.enabled,
                }
            )
        rows.sort(key=lambda row: row["model_alias"])
        return rows

    def list_model_connections(self) -> list[dict[str, Any]]:
        rows = []
        for item in self.model_connections.values():
            configured = bool(item.get("encrypted_api_key")) or (bool(item.get("auth_env")) and bool(os.environ.get(item["auth_env"], "").strip()))
            if item["auth_scheme"] == "none":
                configured = True
            rows.append(
                {
                    "connection_id": item["connection_id"],
                    "vendor_name": item["vendor_name"],
                    "note": item.get("note"),
                    "homepage_url": item.get("homepage_url"),
                    "display_name": item["display_name"],
                    "protocol": item["protocol"],
                    "base_url": item["base_url"],
                    "auth_scheme": item["auth_scheme"],
                    "auth_env": item.get("auth_env", ""),
                    "configured": configured,
                    "provider_id": item["provider_id"],
                    "model_alias": item["model_alias"],
                    "model_name": item["model_name"],
                    "default_timeout": item["default_timeout"],
                    "default_max_tokens": item["default_max_tokens"],
                    "supports_multi_turn": item["supports_multi_turn"],
                    "enabled": item["enabled"],
                    "headers_template": item.get("headers_template", {}),
                    "model_lookup_mode": item.get("model_lookup_mode", "skip"),
                    "has_stored_secret": bool(item.get("encrypted_api_key")),
                    "advanced": item.get("advanced", {}),
                }
            )
        rows.sort(key=lambda row: (row["vendor_name"].lower(), row["display_name"].lower()))
        return rows

    def create_model_connection(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = _validate_connection_input(payload)
        if normalized["connection_id"] in self.model_connections:
            raise ProviderError(f"Duplicate connection_id: {normalized['connection_id']}", "model_validation_failed")
        if normalized["provider_id"] in self.providers or normalized["model_alias"] in self.models:
            raise ProviderError("Generated provider/model ids conflict with existing records", "model_validation_failed")
        secret_value = normalized.pop("api_key", "")
        normalized["encrypted_api_key"] = encrypt_secret(secret_value) if secret_value else None
        self.store.upsert_provider(
            {
                "provider_id": normalized["provider_id"],
                "display_name": normalized["vendor_name"],
                "protocol": normalized["protocol"],
                "base_url": normalized["base_url"],
                "auth_scheme": normalized["auth_scheme"],
                "auth_env": normalized["auth_env"],
                "headers_template": normalized["headers_template"],
                "model_lookup_mode": normalized["model_lookup_mode"],
                "enabled": normalized["enabled"],
            }
        )
        self.store.upsert_model(
            {
                "model_alias": normalized["model_alias"],
                "provider_id": normalized["provider_id"],
                "display_name": normalized["display_name"],
                "model_name": normalized["model_name"],
                "default_timeout": normalized["default_timeout"],
                "default_max_tokens": normalized["default_max_tokens"],
                "supports_multi_turn": normalized["supports_multi_turn"],
                "enabled": normalized["enabled"],
            }
        )
        self.store.upsert_model_connection(normalized)
        self.reload()
        self._sync_legacy_config()
        return next(row for row in self.list_model_connections() if row["connection_id"] == normalized["connection_id"])

    def update_model_connection(self, connection_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        if connection_id not in self.model_connections:
            raise ProviderError(f"connection_id not found: {connection_id}", "model_validation_failed")
        current = dict(self.model_connections[connection_id])
        current.update(payload)
        current["connection_id"] = connection_id
        current["keep_existing_secret"] = payload.get("keep_existing_secret", True)
        normalized = _validate_connection_input(current, existing_connection_id=connection_id)
        secret_value = normalized.pop("api_key", "")
        if secret_value:
            normalized["encrypted_api_key"] = encrypt_secret(secret_value)
        elif normalized.pop("keep_existing_secret", False):
            normalized["encrypted_api_key"] = self.model_connections[connection_id].get("encrypted_api_key")
        else:
            normalized["encrypted_api_key"] = None
        self.store.upsert_provider(
            {
                "provider_id": normalized["provider_id"],
                "display_name": normalized["vendor_name"],
                "protocol": normalized["protocol"],
                "base_url": normalized["base_url"],
                "auth_scheme": normalized["auth_scheme"],
                "auth_env": normalized["auth_env"],
                "headers_template": normalized["headers_template"],
                "model_lookup_mode": normalized["model_lookup_mode"],
                "enabled": normalized["enabled"],
            }
        )
        self.store.upsert_model(
            {
                "model_alias": normalized["model_alias"],
                "provider_id": normalized["provider_id"],
                "display_name": normalized["display_name"],
                "model_name": normalized["model_name"],
                "default_timeout": normalized["default_timeout"],
                "default_max_tokens": normalized["default_max_tokens"],
                "supports_multi_turn": normalized["supports_multi_turn"],
                "enabled": normalized["enabled"],
            }
        )
        self.store.upsert_model_connection(normalized)
        self.reload()
        self._sync_legacy_config()
        return next(row for row in self.list_model_connections() if row["connection_id"] == connection_id)

    def delete_model_connection(self, connection_id: str) -> None:
        if connection_id not in self.model_connections:
            raise ProviderError(f"connection_id not found: {connection_id}", "model_validation_failed")
        record = self.model_connections[connection_id]
        self.store.delete_model_connection(connection_id)
        if record["model_alias"] in self.models:
            self.store.delete_model(record["model_alias"])
        if record["provider_id"] in self.providers:
            self.store.delete_provider(record["provider_id"])
        self.reload()
        self._sync_legacy_config()

    def test_model_connection(self, connection_id: str) -> dict[str, Any]:
        provider = self.resolve_connection(connection_id)
        validation = provider.validate_model()
        return {
            "ok": True,
            "connection_id": connection_id,
            "provider_id": provider.provider.provider_id,
            "model_alias": provider.model.model_alias,
            "model_name": provider.model.model_name,
            "validation": validation,
        }

    def create_provider(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = _validate_provider_input(payload)
        if normalized["provider_id"] in self.providers:
            raise ProviderError(f"Duplicate provider_id: {normalized['provider_id']}", "model_validation_failed")
        self.store.upsert_provider(normalized)
        self.reload()
        self._sync_legacy_config()
        return next(row for row in self.list_providers() if row["provider_id"] == normalized["provider_id"])

    def update_provider(self, provider_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        if provider_id not in self.providers:
            raise ProviderError(f"provider_id not found: {provider_id}", "model_validation_failed")
        current = asdict(self.providers[provider_id])
        current.update(payload)
        current["provider_id"] = provider_id
        normalized = _validate_provider_input(current, existing_id=provider_id)
        self.store.upsert_provider(normalized)
        self.reload()
        self._sync_legacy_config()
        return next(row for row in self.list_providers() if row["provider_id"] == provider_id)

    def delete_provider(self, provider_id: str) -> None:
        if provider_id not in self.providers:
            raise ProviderError(f"provider_id not found: {provider_id}", "model_validation_failed")
        if any(model.provider_id == provider_id for model in self.models.values()):
            raise ProviderError("Cannot delete provider with existing models", "model_validation_failed")
        self.store.delete_provider(provider_id)
        self.reload()
        self._sync_legacy_config()

    def create_model(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = _validate_model_input(payload, set(self.providers.keys()))
        if normalized["model_alias"] in self.models:
            raise ProviderError(f"Duplicate model_alias: {normalized['model_alias']}", "model_validation_failed")
        self.store.upsert_model(normalized)
        self.reload()
        self._sync_legacy_config()
        return next(row for row in self.list_models() if row["model_alias"] == normalized["model_alias"])

    def update_model(self, model_alias: str, payload: dict[str, Any]) -> dict[str, Any]:
        if model_alias not in self.models:
            raise ProviderError(f"model_alias not found: {model_alias}", "model_validation_failed")
        current = asdict(self.models[model_alias])
        current.update(payload)
        current["model_alias"] = model_alias
        normalized = _validate_model_input(current, set(self.providers.keys()), existing_alias=model_alias)
        self.store.upsert_model(normalized)
        self.reload()
        self._sync_legacy_config()
        return next(row for row in self.list_models() if row["model_alias"] == model_alias)

    def delete_model(self, model_alias: str) -> None:
        if model_alias not in self.models:
            raise ProviderError(f"model_alias not found: {model_alias}", "model_validation_failed")
        self.store.delete_model(model_alias)
        self.reload()
        self._sync_legacy_config()

    def resolve(self, provider_id: str, model_alias: str, timeout: int | None = None) -> BaseProvider:
        provider = self.providers[provider_id]
        model = self.models[model_alias]
        if not provider.enabled or not model.enabled:
            raise ProviderError(
                "Provider or model is disabled",
                failure_type="model_validation_failed",
            )
        if model.provider_id != provider_id:
            raise ProviderError(
                f"Model alias {model_alias} does not belong to provider {provider_id}",
                failure_type="model_validation_failed",
            )
        api_key = ""
        if provider.auth_scheme != "none":
            api_key = os.environ.get(provider.auth_env, "").strip()
            if not api_key:
                raise ProviderError(
                    f"Missing credential env: {provider.auth_env}",
                    failure_type="model_validation_failed",
                )
        provider_cls = PROTOCOL_MAP[provider.protocol]
        return provider_cls(provider=provider, model=model, api_key=api_key, timeout=timeout)

    def resolve_connection(self, connection_id: str, timeout: int | None = None) -> BaseProvider:
        if connection_id not in self.model_connections:
            raise ProviderError(f"connection_id not found: {connection_id}", "model_validation_failed")
        record = self.model_connections[connection_id]
        provider = self.providers[record["provider_id"]]
        model = self.models[record["model_alias"]]
        if not record.get("enabled", True):
            raise ProviderError("Model connection is disabled", "model_validation_failed")
        api_key = ""
        if provider.auth_scheme != "none":
            api_key = decrypt_secret(record.get("encrypted_api_key")) if record.get("encrypted_api_key") else ""
            if not api_key and provider.auth_env:
                api_key = os.environ.get(provider.auth_env, "").strip()
            if not api_key:
                raise ProviderError(
                    f"Missing credential for model connection {connection_id}",
                    failure_type="model_validation_failed",
                )
        provider_cls = PROTOCOL_MAP[provider.protocol]
        return provider_cls(provider=provider, model=model, api_key=api_key, timeout=timeout or model.default_timeout)
