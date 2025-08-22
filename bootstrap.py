from __future__ import annotations

import os
import json
import sys
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv
import httpx

load_dotenv()

API_BASE = os.getenv("API_BASE", "http://localhost:8000")


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def _get(client: httpx.Client, path: str) -> Optional[Any]:
    url = f"{API_BASE.rstrip('/')}{path}"
    r = client.get(url, timeout=20)
    r.raise_for_status()
    return r.json()


def _post(client: httpx.Client, path: str, data: Dict[str, Any]) -> Optional[Any]:
    url = f"{API_BASE.rstrip('/')}{path}"
    r = client.post(url, json=data, timeout=30)
    r.raise_for_status()
    return r.json()


def ensure_api_ready(client: httpx.Client) -> None:
    try:
        resp = _get(client, "/healthz")
        if not resp or not resp.get("ok"):
            raise RuntimeError("API /healthz ok dönmedi")
    except Exception as exc:
        eprint(f"[HATA] API erişilemiyor: {exc}")
        eprint(f"API için beklenen adres: {API_BASE} (değiştirmek için ortamda API_BASE ayarlayabilirsiniz)")
        sys.exit(1)


def ensure_chat(client: httpx.Client, chat_id: str, title: str, topics: List[str]) -> Dict[str, Any]:
    # zaten var mı?
    chats = _get(client, "/chats") or []
    for ch in chats:
        if ch.get("chat_id") == chat_id:
            print(f"[OK] Chat zaten kayıtlı: {chat_id} → id={ch.get('id')}, title={ch.get('title')}")
            return ch
    # yoksa ekle
    payload = {
        "chat_id": chat_id,
        "title": title or None,
        "is_enabled": True,
        "topics": topics or ["BIST", "FX", "Kripto", "Makro"],
    }
    ch = _post(client, "/chats", payload)
    print(f"[OK] Chat eklendi: {chat_id} → id={ch.get('id')}")
    return ch


def add_bots(client: httpx.Client, tokens: List[str], base_name: str = "Kullanıcı") -> List[Dict[str, Any]]:
    bots_added: List[Dict[str, Any]] = []
    for i, tok in enumerate(tokens, start=1):
        name = f"{base_name} {i:02d}"
        payload = {
            "name": name,
            "token": tok.strip(),
            "username": None,
            "is_enabled": True,
            "speed_profile": {},
            "active_hours": ["09:30-12:00", "14:00-18:00"],
            "persona_hint": "",
        }
        try:
            bot = _post(client, "/bots", payload)
            print(f"[OK] Bot eklendi: {name}")
            bots_added.append(bot)
        except httpx.HTTPStatusError as exc:
            # 4xx/5xx: kullanıcıyı bilgilendir
            eprint(f"[Uyarı] {name} eklenemedi: {exc.response.status_code} {exc.response.text}")
        except Exception as exc:
            eprint(f"[Uyarı] {name} eklenemedi: {exc}")
    return bots_added


def start_simulation(client: httpx.Client) -> None:
    try:
        _post(client, "/control/start", {})
        print("[OK] Simülasyon BAŞLATILDI.")
    except Exception as exc:
        eprint(f"[HATA] Simülasyon başlatılamadı: {exc}")


def parse_args() -> Dict[str, Any]:
    # Çok basit argüman ayrıştırıcı (standart kütüphane)
    import argparse

    p = argparse.ArgumentParser(description="Bootstrap: chat ve botları hızlıca ekle")
    p.add_argument("--api-base", default=API_BASE, help="API kök adresi (vars: http://localhost:8000)")
    p.add_argument("--chat-id", help="Telegram chat_id (örn: -1001234567890)")
    p.add_argument("--chat-title", default="Piyasa Sohbet", help="Chat başlığı")
    p.add_argument("--topics", default="BIST,FX,Kripto,Makro", help="Virgüllü konu listesi")
    p.add_argument("--tokens", help="Virgüllü bot token listesi")
    p.add_argument("--tokens-file", help="JSON dosyası (['111:AAA','222:BBB',...])")
    p.add_argument("--count", type=int, default=10, help="--tokens yoksa kaç adet bot bekleniyor (bilgi amaçlı)")
    p.add_argument("--start", action="store_true", help="Kurulumdan sonra simülasyonu başlat")
    args = p.parse_args()

    return {
        "api_base": args.api_base,
        "chat_id": args.chat_id,
        "chat_title": args.chat_title,
        "topics": [t.strip() for t in (args.topics or "").split(",") if t.strip()],
        "tokens_str": args.tokens,
        "tokens_file": args.tokens_file,
        "count_hint": int(args.count or 10),
        "start": bool(args.start),
    }


def read_tokens(tokens_str: Optional[str], tokens_file: Optional[str], count_hint: int) -> List[str]:
    tokens: List[str] = []
    if tokens_str:
        tokens = [t.strip() for t in tokens_str.split(",") if t.strip()]
    elif tokens_file:
        with open(tokens_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, list):
                raise ValueError("tokens-file JSON listesi olmalı: ['111:AAA','222:BBB',...]")
            tokens = [str(x).strip() for x in data if str(x).strip()]
    else:
        print(f"* Bot tokenları girmediniz. En az {count_hint} adet token bekleniyor.")
        print("  - Ya --tokens '111:AAA,222:BBB,...' şeklinde verin")
        print("  - Ya da --tokens-file tokens.json (JSON listesi) verin")
        sys.exit(2)

    if len(tokens) < 1:
        raise ValueError("Hiç token bulunamadı.")
    return tokens


def main():
    a = parse_args()

    global API_BASE
    API_BASE = a["api_base"]

    print(f"[i] API_BASE = {API_BASE}")

    with httpx.Client() as client:
        ensure_api_ready(client)

        # Chat ID yoksa sor
        chat_id = a["chat_id"]
        if not chat_id:
            chat_id = input("Telegram chat_id (-100...): ").strip()
            if not chat_id:
                eprint("chat_id zorunludur.")
                sys.exit(2)

        chat = ensure_chat(client, chat_id=chat_id, title=a["chat_title"], topics=a["topics"])

        tokens = read_tokens(a["tokens_str"], a["tokens_file"], a["count_hint"])
        added = add_bots(client, tokens)

        print(f"[OK] Toplam eklenen bot: {len(added)}")

        if a["start"]:
            start_simulation(client)
            print("[i] Not: Worker çalışıyor olmalı (python worker.py). Değilse başlatın ve /control/start sonrası akış görünür.")
        else:
            print("[i] Simülasyonu başlatmak için:")
            print("    curl -X POST http://localhost:8000/control/start")

        # Kısa özet
        try:
            m = _get(client, "/metrics")
            print(f"[METRICS] aktif_bot={m['active_bots']} chats={m['total_chats']} sim_active={m['simulation_active']}")
        except Exception:
            pass


if __name__ == "__main__":
    main()
