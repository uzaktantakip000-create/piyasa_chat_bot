# llm_client.py
from __future__ import annotations

from typing import Optional, List
import os
import time
import random
import logging

# OpenAI SDK v1.x
try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore

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

# -------------------------------------------------------------------
# LLM Client
# -------------------------------------------------------------------
class LLMClient:
    """
    OpenAI Chat Completions için yalın istemci.
    - Timeout
    - Exponential backoff + jitter (basit)
    - (Opsiyonel) model fallback
    - Çıktı filtresi + post-process
    """

    def __init__(self) -> None:
        if OpenAI is None:
            raise RuntimeError("OpenAI SDK yüklü değil.")

        self.model: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
        self.fallback_model: Optional[str] = os.getenv("LLM_FALLBACK_MODEL") or None
        # SDK genel timeout (saniye)
        self.timeout: float = float(os.getenv("OPENAI_TIMEOUT", "30"))
        # Toplam deneme sayısı (aynı model için)
        self.max_retries: int = int(os.getenv("LLM_MAX_RETRIES", "3"))

        # OpenAI istemcisi: base_url/env anahtarı ile
        base_url = os.getenv("OPENAI_BASE_URL") or None
        # Not: SDK v1'de timeout parametresi desteklenir
        self.client = OpenAI(base_url=base_url, timeout=self.timeout)

    # --------------------------
    # Ana üretim fonksiyonu
    # --------------------------
    def generate(
        self,
        *,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 220,
    ) -> Optional[str]:
        """
        System + user prompt ile bir mesaj üretir.
        İçerik filtresi ve post-process uygular.
        Basit exponential backoff ile yeniden dener.
        """
        messages = [
            {"role": "system", "content": _SYSTEM_CONTENT},
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
                        presence_penalty=0.4,
                        frequency_penalty=0.2,
                    )
                    text = (resp.choices[0].message.content or "").strip()
                    if not text:
                        raise RuntimeError("Empty LLM response")

                    # İçerik filtresi (varsa)
                    filtered = _filter_content(text)
                    if filtered is None:
                        # Filtre çok katıysa bir sonraki denemeye bırak
                        raise RuntimeError("Filtered by content rules")

                    # Son işlem (AI izleri törpüleme vb.)
                    processed = _postprocess(filtered)
                    return processed

                except Exception as e:
                    # backoff: 0.6, 1.2, 2.4, ... + jitter
                    base = 0.6 * (2 ** (attempt - 1))
                    sleep_s = min(base + random.uniform(0, 0.3), 6.0)
                    logger.warning(
                        "LLM generate error (model=%s, attempt=%d/%d): %s; sleep=%.2fs",
                        model, attempt, self.max_retries, e, sleep_s
                    )
                    if attempt == self.max_retries:
                        break
                    time.sleep(sleep_s)
            # bir sonraki modele (fallback) geç
            logger.info("Switching to fallback model: %s", model if model != self.model else (self.fallback_model or "-"))

        return None

    # Basit tepki emojisi üretir (engine için yardımcı)
    @staticmethod
    def generate_reaction() -> str:
        return random.choice(["👍", "🔥", "📈", "📉", "💡", "👌", "✅", "❤️"])
