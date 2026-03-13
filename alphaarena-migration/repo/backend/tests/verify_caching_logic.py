import unittest
from unittest.mock import MagicMock, patch
import logging
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from backend.services.llm_provider import OpenAIProvider
from backend.services.ai_service import generate_analyst_report, generate_pm_decision

class TestCachingImplementation(unittest.TestCase):
    def setUp(self):
        # Mock environment variables
        os.environ["OPENAI_API_KEY"] = "fake-key"
        os.environ["GEMINI_API_KEY"] = "fake-key"

    @patch('backend.services.llm_provider.OpenAI')
    def test_provider_sends_caching_param(self, mock_openai_cls):
        """Verify that OpenAIProvider sends 'prompt_cache_retention': '24h'"""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        
        # Mock successful response
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Test Response"
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 10
        mock_response.usage.prompt_tokens_details.cached_tokens = 50
        mock_client.chat.completions.create.return_value = mock_response

        provider = OpenAIProvider("fake-key", "gpt-5-nano")
        provider.generate_text("Test Prompt")

        # Verify call arguments
        args, kwargs = mock_client.chat.completions.create.call_args
        self.assertIn("extra_body", kwargs, "extra_body parameter missing")
        self.assertEqual(kwargs["extra_body"], {"prompt_cache_retention": "24h"}, "Incorrect caching parameter")
        print("\n✅ Verification Passed: OpenAIProvider is sending 'prompt_cache_retention': '24h'")

    @patch('backend.services.ai_service.generate_text_with_provider')
    def test_analyst_prompt_structure(self, mock_gen):
        """Verify that Analyst Prompt starts with static content (ROLE/TASK)"""
        mock_gen.return_value = "Report"
        
        # Call with dummy data
        generate_analyst_report("AAPL", {"price": 100}, [], {}, {})
        
        # Get the prompt passed to the provider
        call_args = mock_gen.call_args
        prompt = call_args[0][0]
        
        # Check if static parts are at the beginning (simplified check)
        self.assertTrue(prompt.strip().startswith("ROLE:"), "Prompt should start with 'ROLE:' (Static)")
        self.assertIn("OUTPUT FORMAT", prompt[:2000], "OUTPUT FORMAT should be early in the prompt")
        self.assertIn("DATA INGESTION", prompt, "DATA INGESTION should be present")
        
        # Heuristic: Static content (ROLE) should precede Dynamic content (DATA INGESTION)
        role_idx = prompt.find("ROLE:")
        data_idx = prompt.find("DATA INGESTION:")
        
        self.assertTrue(role_idx < data_idx, "Static 'ROLE' must come before Dynamic 'DATA INGESTION'")
        print("\n✅ Verification Passed: Analyst Prompt is structured for prefix caching (Static before Dynamic).")

if __name__ == '__main__':
    unittest.main()
