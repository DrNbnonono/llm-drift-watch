from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from provider_runtime import (  # noqa: E402
    AnthropicCompatibleProvider,
    BaseProvider,
    ModelConfig,
    OpenAICompatibleProvider,
    ProviderConfig,
)


class ProviderTransportTests(unittest.TestCase):
    @staticmethod
    def _provider(provider_class):
        protocol = "anthropic_compatible" if provider_class is AnthropicCompatibleProvider else "openai_compatible"
        return provider_class(
            ProviderConfig("p", "P", protocol, "https://example.test/v1", "x_api_key", "KEY", {}, "skip"),
            ModelConfig("m", "p", "M", "model", 30, 512, True, True),
            "secret-value",
        )

    def test_curl_transport_decodes_utf8_independent_of_windows_locale(self):
        provider = BaseProvider(
            ProviderConfig("p", "P", "anthropic_compatible", "https://example.test/v1", "x_api_key", "KEY", {}, "skip"),
            ModelConfig("m", "p", "M", "MiniMax-M3", 30, 512, True, True),
            "secret-value",
        )
        completed = subprocess.CompletedProcess(["curl"], 0, stdout='{"content":[{"type":"text","text":"你好"}]}', stderr="")

        with patch("provider_runtime.subprocess.run", return_value=completed) as run:
            payload = provider._curl_request("POST", "https://example.test/v1/messages", {"prompt": "你好"})

        self.assertEqual(payload["content"][0]["text"], "你好")
        self.assertEqual(run.call_args.kwargs["encoding"], "utf-8")
        self.assertEqual(run.call_args.kwargs["errors"], "replace")

    def test_anthropic_response_preserves_safe_thinking_and_text_blocks(self):
        provider = self._provider(AnthropicCompatibleProvider)
        sanitized = provider.sanitize_response({
            "model": "MiniMax-M3",
            "content": [
                {"type": "thinking", "thinking": "first reason", "signature": "must-not-persist"},
                {"type": "text", "text": "final answer"},
            ],
        })

        self.assertEqual(sanitized["reasoning"], "first reason")
        self.assertTrue(sanitized["reasoning_available"])
        self.assertFalse(sanitized["reasoning_truncated"])
        self.assertEqual(sanitized["content_blocks"], [
            {"type": "thinking", "thinking": "first reason"},
            {"type": "text", "text": "final answer"},
        ])
        self.assertNotIn("signature", str(sanitized))

    def test_openai_response_normalizes_reasoning_content(self):
        provider = self._provider(OpenAICompatibleProvider)
        sanitized = provider.sanitize_response({
            "model": "model",
            "choices": [{"message": {"reasoning_content": "reason", "content": "answer"}, "finish_reason": "stop"}],
        })

        self.assertEqual(sanitized["reasoning"], "reason")
        self.assertEqual(sanitized["text"], "answer")
        self.assertEqual([block["type"] for block in sanitized["content_blocks"]], ["thinking", "text"])

    def test_reasoning_is_capped_and_reports_original_length(self):
        provider = self._provider(AnthropicCompatibleProvider)
        reasoning = "x" * (256 * 1024 + 7)
        sanitized = provider.sanitize_response({"content": [{"type": "thinking", "thinking": reasoning}]})

        self.assertEqual(len(sanitized["reasoning"]), 256 * 1024)
        self.assertTrue(sanitized["reasoning_truncated"])
        self.assertEqual(sanitized["reasoning_original_chars"], len(reasoning))

    def test_missing_reasoning_is_explicit(self):
        provider = self._provider(AnthropicCompatibleProvider)
        sanitized = provider.sanitize_response({"content": [{"type": "text", "text": "answer"}]})

        self.assertEqual(sanitized["reasoning"], "")
        self.assertFalse(sanitized["reasoning_available"])


if __name__ == "__main__":
    unittest.main()
