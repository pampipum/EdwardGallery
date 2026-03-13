import os
import json
import time
import shutil
import subprocess
from abc import ABC, abstractmethod
import google.generativeai as genai
from openai import OpenAI
from backend.utils.logger import logger
from backend.utils.llm_monitor import llm_monitor

# Retry configuration
MAX_RETRIES = 5
INITIAL_BACKOFF_SECONDS = 5  # Will be multiplied exponentially: 5, 10, 20, 40, 80


class LLMProvider(ABC):
    @abstractmethod
    def generate_text(self, prompt: str, purpose: str = "Unknown", pm_id: str = "N/A") -> str:
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        pass


class OpenClawProvider(LLMProvider):
    def __init__(self, agent_id: str = "main", thinking: str = "minimal", timeout_seconds: int = 600):
        if not shutil.which("openclaw"):
            raise ValueError("OpenClaw CLI is not available in PATH")
        self.agent_id = agent_id or "main"
        self.thinking = thinking
        self.timeout_seconds = timeout_seconds

    def get_provider_name(self) -> str:
        return "OpenClaw"

    def generate_text(self, prompt: str, purpose: str = "Unknown", pm_id: str = "N/A") -> str:
        started = time.time()
        result = subprocess.run(
            [
                "openclaw",
                "agent",
                "--agent",
                self.agent_id,
                "--json",
                "--thinking",
                self.thinking,
                "--timeout",
                str(self.timeout_seconds),
                "--message",
                prompt,
            ],
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds + 30,
            check=False,
        )
        if result.returncode != 0:
            error_text = (result.stderr or result.stdout).strip()
            raise RuntimeError(f"OpenClaw agent call failed: {error_text}")

        payload = json.loads(result.stdout)
        texts = payload.get("result", {}).get("payloads", [])
        if not texts:
            raise RuntimeError("OpenClaw agent returned no payload text")

        text = texts[0].get("text", "").strip()
        duration = time.time() - started
        llm_monitor.log_request(
            provider="OpenClaw",
            model=self.agent_id,
            prompt=prompt,
            response=text,
            purpose=purpose,
            pm_id=pm_id,
            duration=duration
        )
        return text


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str, model_name: str):
        if not api_key:
            raise ValueError("Gemini API Key is missing")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)
        self.model_name = model_name

    def get_provider_name(self) -> str:
        return "Gemini"

    def generate_text(self, prompt: str, purpose: str = "Unknown", pm_id: str = "N/A") -> str:
        last_error = None
        start_time = time.time()
        
        for attempt in range(MAX_RETRIES):
            try:
                response = self.model.generate_content(prompt)
                text = response.text.strip()
                
                # Log usage
                duration = time.time() - start_time
                # Gemini doesn't always expose token usage in this SDK version easily
                llm_monitor.log_request(
                    provider="Gemini",
                    model=self.model_name,
                    prompt=prompt,
                    response=text,
                    purpose=purpose,
                    pm_id=pm_id,
                    duration=duration
                )
                return text
            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                if "limit: 0" in error_str or "free_tier" in error_str:
                    logger.error(f"Gemini quota unavailable for model {self.model_name}: {e}")
                    raise e
                
                # Check for retryable errors (rate limits and transient connection issues)
                is_rate_limit = any(x in error_str for x in ['429', 'quota', 'rate limit', 'resource exhausted'])
                is_transient = any(x in error_str for x in [
                    'connection error', 'connection reset', 'connection refused',
                    'timeout', 'timed out', 'temporarily unavailable', 
                    'service unavailable', '503', '502', 'bad gateway',
                    'network', 'ssl', 'eof', 'broken pipe'
                ])
                
                if (is_rate_limit or is_transient) and attempt < MAX_RETRIES - 1:
                    backoff = INITIAL_BACKOFF_SECONDS * (2 ** attempt)
                    error_type = "Rate limit" if is_rate_limit else "Transient error"
                    logger.warning(f"[Gemini] {error_type} (attempt {attempt + 1}/{MAX_RETRIES}). Retrying in {backoff}s... Error: {e}")
                    time.sleep(backoff)
                elif not is_rate_limit and not is_transient:
                    # Non-retryable error, don't retry
                    logger.error(f"Gemini Error: {e}")
                    raise e
        
        # All retries exhausted
        logger.error(f"Gemini Error after {MAX_RETRIES} retries: {last_error}")
        raise last_error


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, model_name: str):
        if not api_key:
            raise ValueError("OpenAI API Key is missing")

        # Supports OpenAI-compatible providers (e.g. DashScope/Alibaba)
        # via OPENAI_BASE_URL, while defaulting to OpenAI's official endpoint.
        base_url = (os.getenv("OPENAI_BASE_URL") or os.getenv("ALIBABA_BASE_URL") or "").strip() or None
        if base_url:
            self.client = OpenAI(api_key=api_key.strip(), base_url=base_url)
            logger.info(f"[OpenAIProvider] Using custom OPENAI_BASE_URL: {base_url}")
        else:
            self.client = OpenAI(api_key=api_key.strip())

        self.model_name = model_name
        self.cache_key = f"llm-provider-{model_name}-v1"

    def get_provider_name(self) -> str:
        return "OpenAI"

    def generate_text(self, prompt: str, purpose: str = "Unknown", pm_id: str = "N/A") -> str:
        last_error = None
        start_time = time.time()
        
        for attempt in range(MAX_RETRIES):
            try:
                use_extended_cache = 'gpt-5.1' in self.model_name.lower()
                
                if use_extended_cache:
                    response = self.client.chat.completions.create(
                        model=self.model_name,
                        messages=[{"role": "user", "content": prompt}],
                        timeout=180.0,
                        extra_body={"prompt_cache_retention": "24h"},
                        prompt_cache_key=self.cache_key
                    )
                else:
                    response = self.client.chat.completions.create(
                        model=self.model_name,
                        messages=[{"role": "user", "content": prompt}],
                        timeout=180.0,
                        prompt_cache_key=self.cache_key
                    )
                
                text = response.choices[0].message.content.strip()
                duration = time.time() - start_time

                # Log tokens and usage
                tokens_in, tokens_out = 0, 0
                if hasattr(response, 'usage') and response.usage:
                    usage = response.usage
                    tokens_in = usage.prompt_tokens
                    tokens_out = usage.completion_tokens
                    
                    cached = 0
                    if hasattr(usage, 'prompt_tokens_details') and hasattr(usage.prompt_tokens_details, 'cached_tokens'):
                        cached = usage.prompt_tokens_details.cached_tokens or 0
                    
                    if cached > 0:
                        savings = cached / usage.prompt_tokens if usage.prompt_tokens > 0 else 0
                        logger.info(f"   [OpenAI] ✅ CACHE HIT! Input: {usage.prompt_tokens} | Cached: {cached} ({savings:.0%} savings) | Output: {usage.completion_tokens}")
                    else:
                        logger.debug(f"   [OpenAI] Input: {usage.prompt_tokens} | Output: {usage.completion_tokens} (no cache hit)")

                llm_monitor.log_request(
                    provider="OpenAI",
                    model=self.model_name,
                    prompt=prompt,
                    response=text,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    purpose=purpose,
                    pm_id=pm_id,
                    duration=duration
                )

                return text
                
            except Exception as e:
                last_error = e
                error_str = str(e).lower()
                
                # Check for retryable errors (rate limits and transient connection issues)
                is_rate_limit = any(x in error_str for x in ['429', 'quota', 'rate limit', 'rate_limit'])
                is_transient = any(x in error_str for x in [
                    'connection error', 'connection reset', 'connection refused',
                    'timeout', 'timed out', 'temporarily unavailable', 
                    'service unavailable', '503', '502', 'bad gateway',
                    'network', 'ssl', 'eof', 'broken pipe'
                ])
                
                if (is_rate_limit or is_transient) and attempt < MAX_RETRIES - 1:
                    backoff = INITIAL_BACKOFF_SECONDS * (2 ** attempt)
                    error_type = "Rate limit" if is_rate_limit else "Transient error"
                    logger.warning(f"[OpenAI] {error_type} (attempt {attempt + 1}/{MAX_RETRIES}). Retrying in {backoff}s... Error: {e}")
                    time.sleep(backoff)
                elif not is_rate_limit and not is_transient:
                    # Non-retryable error, don't retry
                    logger.error(f"OpenAI Error: {e}")
                    raise e
        
        # All retries exhausted
        logger.error(f"OpenAI Error after {MAX_RETRIES} retries: {last_error}")
        raise last_error


class OpenRouterProvider(LLMProvider):
    """
    OpenRouter provider — uses the OpenAI-compatible API at openrouter.ai.
    Supports any model available on OpenRouter (e.g. minimax/minimax-m2.5).
    """
    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(self, api_key: str, model_name: str):
        if not api_key:
            raise ValueError("OpenRouter API Key is missing")
        self.client = OpenAI(
            api_key=api_key,
            base_url=self.OPENROUTER_BASE_URL,
        )
        self.model_name = model_name

    def get_provider_name(self) -> str:
        return "OpenRouter"

    def generate_text(self, prompt: str, purpose: str = "Unknown", pm_id: str = "N/A") -> str:
        last_error = None
        start_time = time.time()

        for attempt in range(MAX_RETRIES):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    timeout=180.0,
                )

                text = response.choices[0].message.content.strip()
                duration = time.time() - start_time

                # Log usage
                tokens_in, tokens_out = 0, 0
                if hasattr(response, 'usage') and response.usage:
                    usage = response.usage
                    tokens_in = usage.prompt_tokens
                    tokens_out = usage.completion_tokens
                    logger.debug(
                        f"   [OpenRouter/{self.model_name}] "
                        f"Input: {usage.prompt_tokens} | Output: {usage.completion_tokens}"
                    )

                llm_monitor.log_request(
                    provider="OpenRouter",
                    model=self.model_name,
                    prompt=prompt,
                    response=text,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    purpose=purpose,
                    pm_id=pm_id,
                    duration=duration
                )

                return text

            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                is_rate_limit = any(x in error_str for x in ['429', 'quota', 'rate limit', 'rate_limit'])
                is_transient = any(x in error_str for x in [
                    'connection error', 'connection reset', 'connection refused',
                    'timeout', 'timed out', 'temporarily unavailable',
                    'service unavailable', '503', '502', 'bad gateway',
                    'network', 'ssl', 'eof', 'broken pipe'
                ])

                if (is_rate_limit or is_transient) and attempt < MAX_RETRIES - 1:
                    backoff = INITIAL_BACKOFF_SECONDS * (2 ** attempt)
                    error_type = "Rate limit" if is_rate_limit else "Transient error"
                    logger.warning(
                        f"[OpenRouter] {error_type} (attempt {attempt + 1}/{MAX_RETRIES}). "
                        f"Retrying in {backoff}s... Error: {e}"
                    )
                    time.sleep(backoff)
                elif not is_rate_limit and not is_transient:
                    logger.error(f"OpenRouter Error: {e}")
                    raise e

        logger.error(f"OpenRouter Error after {MAX_RETRIES} retries: {last_error}")
        raise last_error


def get_llm_provider(provider_name: str, api_key: str, model_name: str) -> LLMProvider:
    provider_name = provider_name.lower()
    if provider_name == "openclaw":
        thinking = os.getenv("ALPHAARENA_OPENCLAW_THINKING", "minimal")
        timeout_seconds = int(os.getenv("ALPHAARENA_OPENCLAW_TIMEOUT_SECONDS", "600"))
        return OpenClawProvider(model_name or "main", thinking, timeout_seconds)
    if provider_name == "gemini":
        return GeminiProvider(api_key, model_name)
    elif provider_name == "openai":
        return OpenAIProvider(api_key, model_name)
    elif provider_name == "openrouter":
        return OpenRouterProvider(api_key, model_name)
    else:
        raise ValueError(f"Unknown provider: {provider_name}")
