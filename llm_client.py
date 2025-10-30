# llm_client.py
from __future__ import annotations

from typing import Optional, List
from abc import ABC, abstractmethod
import os
import time
import random
import logging

# OpenAI SDK v1.x
try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore

# Google Gemini SDK
try:
    import google.generativeai as genai
except Exception:  # pragma: no cover
    genai = None  # type: ignore

# Groq SDK
try:
    from groq import Groq
except Exception:  # pragma: no cover
    Groq = None  # type: ignore

# -------------------------------------------------------------------
# system_prompt bağımlılıkları: geçmiş sürümle uyumlu olacak şekilde
# -------------------------------------------------------------------
# - Yeni sürümümüz: SYSTEM_STYLE, postprocess_output
# - Eski sürümler: SYSTEM_PROMPT, post_process_message, filter_content
SYSTEM_CONTENT_FALLBACK = (
    "Finans sohbetinde doğal, temkinli ve saygılı konuş. Garanti kazanç vaat etme."
)

try:
    from system_prompt import SYSTEM_STYLE as _SYSTEM_CONTENT  # type: ignore
except Exception:
    try:
        from system_prompt import SYSTEM_PROMPT as _SYSTEM_CONTENT  # type: ignore
    except Exception:
        _SYSTEM_CONTENT = SYSTEM_CONTENT_FALLBACK

# post-process
try:
    from system_prompt import postprocess_output as _postprocess  # type: ignore
except Exception:
    try:
        from system_prompt import post_process_message as _postprocess  # type: ignore
    except Exception:
        _postprocess = lambda s: (s or "").strip()

# içerik filtresi (opsiyonel)
_FILTER_MISSING = False
try:
    from system_prompt import filter_content as _filter_content  # type: ignore
except Exception:
    # Bazı sürümlerde yok; güvenli bir sahte filtre kullan
    _FILTER_MISSING = True
    def _filter_content(text: str) -> Optional[str]:
        # basit güvenli geçiş
        return (text or "").strip() or None

logger = logging.getLogger("llm")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())

REACTION_KEYWORDS = {
    "positive": {
        "artış",
        "yükseliş",
        "kazanç",
        "kâr",
        "kârı",
        "mutlu",
        "sevind",
        "teşekkür",
        "güçlü",
        "olumlu",
        "harika",
        "mükemmel",
    },
    "negative": {
        "düşüş",
        "düştü",
        "kayb",
        "kayıp",
        "olumsuz",
        "kötü",
        "berbat",
        "üzgün",
        "moral bozuk",
        "felaket",
        "sert sat",
    },
    "neutral": {
        "stabil",
        "dengede",
        "yatay",
        "nötr",
        "beklemede",
        "izlemede",
        "kararsız",
        "sideways",
    },
}

REACTION_EMOJIS = {
    "positive": "📈",
    "negative": "📉",
    "neutral": "💬",
}

# -------------------------------------------------------------------
# Abstract Base Provider
# -------------------------------------------------------------------
class BaseLLMProvider(ABC):
    """
    Abstract base class for LLM providers.
    Implements generate(), generate_reaction(), and pick_reaction_for_text().
    """

    @abstractmethod
    def generate(
        self,
        *,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 220,
    ) -> Optional[str]:
        """Generate a message using the LLM provider."""
        pass

    @staticmethod
    def generate_reaction() -> str:
        """Generate a random reaction emoji."""
        return random.choice(["👍", "🔥", "📈", "📉", "💡", "👌", "✅", "❤️"])

    @staticmethod
    def pick_reaction_for_text(text: Optional[str]) -> str:
        """Pick an appropriate reaction emoji based on text content."""
        content = (text or "").strip().lower()
        if not content:
            return BaseLLMProvider.generate_reaction()

        for category in ("positive", "negative", "neutral"):
            keywords = REACTION_KEYWORDS.get(category, set())
            if any(keyword in content for keyword in keywords):
                return REACTION_EMOJIS.get(category, BaseLLMProvider.generate_reaction())

        return BaseLLMProvider.generate_reaction()


# -------------------------------------------------------------------
# OpenAI Provider
# -------------------------------------------------------------------
class OpenAIProvider(BaseLLMProvider):
    """
    OpenAI Chat Completions provider.
    - Timeout
    - Exponential backoff + jitter
    - Model fallback support
    - Content filtering + post-processing
    """

    def __init__(self) -> None:
        if OpenAI is None:
            raise RuntimeError("OpenAI SDK yüklü değil.")

        self.model: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
        self.fallback_model: Optional[str] = os.getenv("LLM_FALLBACK_MODEL") or None
        self.timeout: float = float(os.getenv("OPENAI_TIMEOUT", "30"))
        self.max_retries: int = int(os.getenv("LLM_MAX_RETRIES", "3"))

        base_url = os.getenv("OPENAI_BASE_URL") or None
        self.client = OpenAI(base_url=base_url, timeout=self.timeout)

        logger.info("OpenAIProvider initialized (model=%s)", self.model)

    def generate(
        self,
        *,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 220,
        system_prompt: Optional[str] = None,
        top_p: float = 0.95,
        frequency_penalty: float = 0.4,
    ) -> Optional[str]:
        """
        System + user prompt ile bir mesaj üretir.
        İçerik filtresi ve post-process uygular.
        Basit exponential backoff ile yeniden dener.

        Args:
            user_prompt: User mesajı
            temperature: LLM temperature (default 0.7)
            max_tokens: Max token sayısı (default 220)
            system_prompt: Custom system prompt (None ise default kullanılır)
            top_p: Nucleus sampling (default 0.95)
            frequency_penalty: Frequency penalty (default 0.4)
        """
        # System prompt: custom varsa onu kullan, yoksa default
        system_content = system_prompt if system_prompt is not None else _SYSTEM_CONTENT

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_prompt},
        ]

        models: List[str] = [self.model]
        if self.fallback_model and self.fallback_model != self.model:
            models.append(self.fallback_model)

        for model in models:
            for attempt in range(1, self.max_retries + 1):
                try:
                    resp = self.client.chat.completions.create(
                        model=model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        top_p=top_p,
                        presence_penalty=0.4,
                        frequency_penalty=frequency_penalty,
                    )
                    text = (resp.choices[0].message.content or "").strip()
                    if not text:
                        raise RuntimeError("Empty LLM response")

                    # İçerik filtresi (varsa)
                    filtered = _filter_content(text)
                    if filtered is None:
                        raise RuntimeError("Filtered by content rules")

                    # Son işlem (AI izleri törpüleme vb.)
                    processed = _postprocess(filtered)
                    return processed

                except Exception as e:
                    base = 0.6 * (2 ** (attempt - 1))
                    sleep_s = min(base + random.uniform(0, 0.3), 6.0)
                    logger.warning(
                        "OpenAI generate error (model=%s, attempt=%d/%d): %s; sleep=%.2fs",
                        model, attempt, self.max_retries, e, sleep_s
                    )
                    if attempt == self.max_retries:
                        break
                    time.sleep(sleep_s)
            logger.info("Switching to fallback model: %s", model if model != self.model else (self.fallback_model or "-"))

        return None


# -------------------------------------------------------------------
# Google Gemini Provider
# -------------------------------------------------------------------
class GeminiProvider(BaseLLMProvider):
    """
    Google Gemini API provider.
    - Türkçe desteği mükemmel
    - Exponential backoff
    - Content filtering + post-processing
    """

    def __init__(self) -> None:
        if genai is None:
            raise RuntimeError("google-generativeai SDK yüklü değil.")

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY environment variable gerekli.")

        genai.configure(api_key=api_key)

        # Model selection: gemini-1.5-flash (hızlı) veya gemini-1.5-pro (güçlü)
        # Not: SDK kendi başına model adını kullanır, "models/" prefix gerekmez
        self.model_name: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        self.max_retries: int = int(os.getenv("LLM_MAX_RETRIES", "3"))

        # Safety settings: BLOCK_NONE for all categories (finans tartışması için gerekli)
        self.safety_settings = [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_NONE",
            },
            {
                "category": "HARM_CATEGORY_HATE_SPEECH",
                "threshold": "BLOCK_NONE",
            },
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_NONE",
            },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_NONE",
            },
        ]

        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            safety_settings=self.safety_settings,
        )

        logger.info("GeminiProvider initialized (model=%s)", self.model_name)

    def generate(
        self,
        *,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 220,
        system_prompt: Optional[str] = None,
        top_p: float = 0.95,
        frequency_penalty: float = 0.4,
    ) -> Optional[str]:
        """
        Gemini API ile mesaj üretir.
        System prompt'u user prompt'a prepend eder (Gemini'de system role yoktur).
        """
        # System prompt: custom varsa onu kullan, yoksa default
        system_content = system_prompt if system_prompt is not None else _SYSTEM_CONTENT

        # Gemini'de system role yok, user prompt'a ekliyoruz
        combined_prompt = f"{system_content}\n\n{user_prompt}"

        generation_config = genai.types.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            top_p=0.95,
            top_k=40,
        )

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.model.generate_content(
                    combined_prompt,
                    generation_config=generation_config,
                    safety_settings=self.safety_settings,
                )

                # Gemini response structure check
                if not response.candidates:
                    raise RuntimeError("No candidates in Gemini response")

                candidate = response.candidates[0]

                # Check if blocked by safety filters
                if candidate.finish_reason.name in ["SAFETY", "RECITATION", "OTHER"]:
                    raise RuntimeError(f"Gemini blocked response: {candidate.finish_reason.name}")

                text = candidate.content.parts[0].text.strip()
                if not text:
                    raise RuntimeError("Empty Gemini response")

                # İçerik filtresi (varsa)
                filtered = _filter_content(text)
                if filtered is None:
                    raise RuntimeError("Filtered by content rules")

                # Son işlem
                processed = _postprocess(filtered)
                return processed

            except Exception as e:
                base = 0.6 * (2 ** (attempt - 1))
                sleep_s = min(base + random.uniform(0, 0.3), 6.0)
                logger.warning(
                    "Gemini generate error (model=%s, attempt=%d/%d): %s; sleep=%.2fs",
                    self.model_name, attempt, self.max_retries, e, sleep_s
                )
                if attempt == self.max_retries:
                    break
                time.sleep(sleep_s)

        return None


# -------------------------------------------------------------------
# Groq Provider
# -------------------------------------------------------------------
class GroqProvider(BaseLLMProvider):
    """
    Groq API provider - Ücretsiz ve ÇOK HIZLI!
    - OpenAI-compatible API
    - Llama, Mistral, Mixtral modelleri
    - Saniyede 300+ token hız
    - Exponential backoff
    """

    def __init__(self) -> None:
        if Groq is None:
            raise RuntimeError("Groq SDK yüklü değil.")

        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY environment variable gerekli.")

        self.client = Groq(api_key=api_key)

        # Model selection: llama-3.3-70b-versatile (en iyi), mixtral-8x7b-32768 (hızlı)
        self.model: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.max_retries: int = int(os.getenv("LLM_MAX_RETRIES", "3"))

        logger.info("GroqProvider initialized (model=%s)", self.model)

    def generate(
        self,
        *,
        user_prompt: str,
        temperature: float = 1.7,
        max_tokens: int = 220,
        system_prompt: Optional[str] = None,
        top_p: float = 0.95,
        frequency_penalty: float = 0.4,
    ) -> Optional[str]:
        """
        Groq API ile mesaj üretir.
        OpenAI-compatible API kullanır.
        """
        # System prompt: custom varsa onu kullan, yoksa default
        system_content = system_prompt if system_prompt is not None else _SYSTEM_CONTENT

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_prompt},
        ]

        for attempt in range(1, self.max_retries + 1):
            try:
                completion = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=top_p,
                    frequency_penalty=frequency_penalty,
                    presence_penalty=0.7,
                )

                text = (completion.choices[0].message.content or "").strip()
                if not text:
                    raise RuntimeError("Empty Groq response")

                # İçerik filtresi (varsa)
                filtered = _filter_content(text)
                if filtered is None:
                    raise RuntimeError("Filtered by content rules")

                # Son işlem
                processed = _postprocess(filtered)
                return processed

            except Exception as e:
                base = 0.6 * (2 ** (attempt - 1))
                sleep_s = min(base + random.uniform(0, 0.3), 6.0)
                logger.warning(
                    "Groq generate error (model=%s, attempt=%d/%d): %s; sleep=%.2fs",
                    self.model, attempt, self.max_retries, e, sleep_s
                )
                if attempt == self.max_retries:
                    break
                time.sleep(sleep_s)

        return None


# -------------------------------------------------------------------
# LLMClient Factory
# -------------------------------------------------------------------
class LLMClient:
    """
    Factory class that returns the appropriate LLM provider based on LLM_PROVIDER env variable.
    Maintains backward compatibility with existing code.
    """

    _instance: Optional[BaseLLMProvider] = None

    def __init__(self) -> None:
        """Initialize the appropriate provider based on LLM_PROVIDER env variable."""
        if LLMClient._instance is None:
            provider = os.getenv("LLM_PROVIDER", "openai").lower()

            if provider == "gemini":
                LLMClient._instance = GeminiProvider()
            elif provider == "groq":
                LLMClient._instance = GroqProvider()
            elif provider == "openai":
                LLMClient._instance = OpenAIProvider()
            else:
                logger.error("Unknown LLM_PROVIDER: %s, falling back to OpenAI", provider)
                LLMClient._instance = OpenAIProvider()

    def generate(
        self,
        *,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 220,
        system_prompt: Optional[str] = None,
        top_p: float = 0.95,
        frequency_penalty: float = 0.4,
    ) -> Optional[str]:
        """Delegate to the active provider."""
        return LLMClient._instance.generate(
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            system_prompt=system_prompt,
            top_p=top_p,
            frequency_penalty=frequency_penalty,
        )

    @staticmethod
    def generate_reaction() -> str:
        """Generate a random reaction emoji."""
        return BaseLLMProvider.generate_reaction()

    @staticmethod
    def pick_reaction_for_text(text: Optional[str]) -> str:
        """Pick an appropriate reaction emoji based on text content."""
        return BaseLLMProvider.pick_reaction_for_text(text)
