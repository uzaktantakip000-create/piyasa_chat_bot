from __future__ import annotations

import os
import sys
import json
from typing import Optional, Dict, Any

from dotenv import load_dotenv
import httpx

load_dotenv()

API_BASE = os.getenv("API_BASE", "http://localhost:8000")


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def _ok(msg: str):
    print(f"[OK] {msg}")


def _warn(msg: str):
    print(f"[Uyarı] {msg}")


def _fail(msg: str):
    eprint(f"[HATA] {msg}")


def api_get(path: str) -> Optional[Dict[str, Any]]:
    url = f"{API_BASE.rstrip('/')}{path}"
    with httpx.Client(timeout=15) as client:
        r = client.get(url)
        r.raise_for_status()
        return r.json()


def api_post(path: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    url = f"{API_BASE.rstrip('/')}{path}"
    with httpx.Client(timeout=20) as client:
        r = client.post(url, json=data)
        r.raise_for_status()
        try:
            return r.json()
        except Exception:
            return None


def check_api():
    try:
        resp = api_get("/healthz")
        if resp and resp.get("ok"):
            _ok(f"API erişilebilir: {API_BASE}")
            return True
    except Exception as exc:
        _fail(f"API erişilemiyor: {exc} (API’yi başlat: uvicorn main:app --port 8000)")
    return False


def check_db():
    try:
        settings = api_get("/settings") or []
        if settings:
            _ok(f"DB ayarları yüklü ({len(settings)} kayıt)")
            return True
        else:
            _warn("DB ayarları boş döndü (bu bir hata olmayabilir)")
            return True
    except Exception as exc:
        _fail(f"DB kontrolü başarısız: {exc}")
        return False


def check_llm():
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        _warn("OPENAI_API_KEY set değil (.env doldurun). LLM testi atlanıyor.")
        return True

    # API içinde değil doğrudan SDK ile çok basit bir deneme yapalım.
    try:
        from openai import OpenAI
        client = OpenAI(api_key=key, base_url=os.getenv("OPENAI_API_BASE"))
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        r = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": "ok: kısa yanıt ver"}, {"role": "user", "content": "ping"}],
            max_tokens=4,
        )
        text = r.choices[0].message.content.strip()
        _ok(f"LLM deneme başarılı (model={model}, çıktı='{text[:20]}...')")
        return True
    except Exception as exc:
        _fail(f"LLM denemesi başarısız: {exc}")
        return False


def first_bot_token() -> Optional[str]:
    try:
        bots = api_get("/bots") or []
        if not bots:
            _warn("Kayıtlı bot yok. /bots ile ekleyin veya bootstrap.py kullanın.")
            return None

        # Bot token’ı API’den güvenlik gereği dönmüyor; bu yüzden test için kullanıcıya soracağız.
        # İpucu: .env’de TST_BOT_TOKEN=... tanımlarsan buradan okuruz.
        tok = os.getenv("TST_BOT_TOKEN")
        if tok:
            return tok.strip()

        _warn("Bot token API’den güvenlik gereği görünmez. Test için TST_BOT_TOKEN ortam değişkeni set edebilirsiniz.")
        return None
    except Exception:
        return None


def check_telegram():
    base = os.getenv("TELEGRAM_API_BASE", "https://api.telegram.org")
    token = first_bot_token()
    if not token:
        _warn("Telegram testi atlandı (TST_BOT_TOKEN yok).")
        return True

    url = f"{base}/bot{token}/getMe"
    try:
        with httpx.Client(timeout=15) as client:
            r = client.get(url)
            data = r.json()
            if data.get("ok"):
                u = data.get("result", {})
                _ok(f"Telegram getMe başarılı: @{u.get('username')}")
                return True
            _fail(f"Telegram getMe başarısız: {data}")
            return False
    except Exception as exc:
        _fail(f"Telegram erişim hatası: {exc}")
        return False


def main():
    print(f"[i] API_BASE = {API_BASE}")
    api_ok = check_api()
    db_ok = check_db() if api_ok else False
    llm_ok = check_llm()
    tg_ok = check_telegram()

    print("\n--- Özet ---")
    print(f"API: {'OK' if api_ok else 'HATA'}")
    print(f"DB : {'OK' if db_ok else 'HATA'}")
    print(f"LLM: {'OK' if llm_ok else 'HATA'}")
    print(f"TG : {'OK' if tg_ok else 'HATA'}")

    if api_ok and db_ok and llm_ok and tg_ok:
        print("\nHepsi hazır görünüyor. Sıradaki adım:")
        print("1) /chats ve /bots ile kayıtları yapın (veya: python bootstrap.py --chat-id ... --tokens ... --start)")
        print("2) Worker açık olsun: python worker.py")
        print("3) Simülasyonu başlatın: curl -X POST http://localhost:8000/control/start")
    else:
        print("\nBazı kontroller başarısız. Yukarıdaki hata/uyarıları inceleyin.")


if __name__ == "__main__":
    main()
