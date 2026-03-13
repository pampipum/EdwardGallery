import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.llm_provider import get_llm_provider, GeminiProvider, OpenAIProvider, OpenRouterProvider

class TestLLMProvider(unittest.TestCase):
    def test_get_gemini_provider(self):
        provider = get_llm_provider("gemini", "fake_key", "gemini-pro")
        self.assertIsInstance(provider, GeminiProvider)
        self.assertEqual(provider.model.model_name, "models/gemini-pro")

    def test_get_openai_provider(self):
        with patch("services.llm_provider.OpenAI") as mock_openai:
            provider = get_llm_provider("openai", "fake_key", "gpt-5")
            self.assertIsInstance(provider, OpenAIProvider)
            self.assertEqual(provider.model_name, "gpt-5")
            mock_openai.assert_called_with(api_key="fake_key")

    def test_get_openrouter_provider(self):
        with patch("services.llm_provider.OpenAI") as mock_openai:
            provider = get_llm_provider("openrouter", "fake_or_key", "minimax/minimax-m2.5")
            self.assertIsInstance(provider, OpenRouterProvider)
            self.assertEqual(provider.model_name, "minimax/minimax-m2.5")
            mock_openai.assert_called_with(
                api_key="fake_or_key",
                base_url="https://openrouter.ai/api/v1",
            )

    def test_invalid_provider(self):
        with self.assertRaises(ValueError):
            get_llm_provider("unknown", "key", "model")

if __name__ == "__main__":
    unittest.main()

