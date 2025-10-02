# news_client.py
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional
import httpx
import xml.etree.ElementTree as ET

# LLM özetleme (opsiyonel)
try:
    from llm_client import LLMClient
except Exception:
    LLMClient = None  # type: ignore

log = logging.getLogger("news")
UTC = timezone.utc

DEFAULT_FEEDS = [
    # İş/finans RSS (genel)
    "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
    "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",
]


@dataclass
class NewsItem:
    title: str
    published: Optional[datetime]
    link: Optional[str] = None


class NewsClient:
    """
    Hafif RSS tabanlı tetikleyici.
    - .env:
        NEWS_RSS_URLS           -> virgülle ayrılmış RSS adresleri (opsiyonel)
        NEWS_TTL_SECONDS        -> cache süresi (varsayılan 300 sn)
        NEWS_TIMEOUT            -> HTTP timeout (varsayılan 6 sn)
        NEWS_USE_LLM_SUMMARY    -> "true" ise başlığı LLM ile kısa/temkinli Türkçe özetler
    """

    def __init__(self, feeds: Optional[List[str]] = None) -> None:
        urls = os.getenv("NEWS_RSS_URLS", "").strip()
        env_feeds = [u.strip() for u in urls.split(",") if u.strip()]
        initial = env_feeds or (feeds or DEFAULT_FEEDS)
        self.feeds: List[str] = self._normalize_feeds(initial)
        self.ttl = int(os.getenv("NEWS_TTL_SECONDS", "300"))
        self.timeout = float(os.getenv("NEWS_TIMEOUT", "6"))
        self.use_llm = os.getenv("NEWS_USE_LLM_SUMMARY", "false").lower() in ("1", "true", "yes")

        self._cache_items: List[NewsItem] = []
        self._cache_at: Optional[datetime] = None

        # LLM (opsiyonel)
        self._llm = None
        if self.use_llm and LLMClient is not None:
            try:
                self._llm = LLMClient()
            except Exception:
                self._llm = None

    def set_feeds(self, feeds: List[str]) -> None:
        """Replace feed list and drop cache so next call pulls fresh data."""
        normalized = self._normalize_feeds(feeds)
        if normalized == self.feeds:
            return
        self.feeds = normalized
        self._cache_items = []
        self._cache_at = None

    # ------------- public -------------
    def get_brief(self, topic_hint: Optional[str]) -> Optional[str]:
        """
        Konu ipucuna göre yakın zamandan bir başlık seçer ve kısa tetik döndürür.
        Örn: "Gündem: Fed toplantısı yaklaşırken...", veya LLM ile temkinli kısa bir cümle.
        """
        items = self._get_recent_items()
        if not items:
            return None

        pick = self._pick_for_topic(items, topic_hint)
        if not pick:
            return None

        title = pick.title.strip()
        if not title:
            return None

        # LLM ile temkinli TR özet (opsiyonel)
        if self.use_llm and self._llm is not None:
            brief = self._summarize_title_tr(title)
            if brief:
                return brief

        # Basit varsayılan
        return f"Gündem: {title}"

    # ------------- fetch/cache -------------
    def _get_recent_items(self, window_minutes: int = 180) -> List[NewsItem]:
        """
        Cache tazeyse ondan; değilse RSS'leri çekip parse eder.
        Son 3 saat (varsayılan) içindeki maddeleri öne alır.
        """
        now = datetime.now(UTC)
        if self._cache_at and (now - self._cache_at).total_seconds() < self.ttl:
            items = self._cache_items
        else:
            items = []
            for url in self.feeds:
                try:
                    r = httpx.get(url, timeout=self.timeout)
                    r.raise_for_status()
                    items.extend(self._parse_rss(r.text))
                except Exception as e:
                    log.debug("RSS fetch failed: %s (%s)", url, e)
            # Yenile cache
            self._cache_items = items
            self._cache_at = now

        # Son X dakika öne
        cutoff = now - timedelta(minutes=window_minutes)
        recent = [it for it in items if (it.published and it.published >= cutoff)]
        # Eğer hiç yoksa en son 10 maddeyi dön
        return recent or sorted(items, key=lambda x: x.published or datetime.min.replace(tzinfo=UTC), reverse=True)[:10]

    def _parse_rss(self, xml_text: str) -> List[NewsItem]:
        out: List[NewsItem] = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return out

        # RSS 2.0: channel/item
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip() or None
            pub = self._parse_date((item.findtext("pubDate") or "").strip())
            if title:
                out.append(NewsItem(title=title, published=pub, link=link))

        # Atom: entry
        for entry in root.findall(".//{http://www.w3.org/2005/Atom}entry"):
            title = (entry.findtext("{http://www.w3.org/2005/Atom}title") or "").strip()
            link_el = entry.find("{http://www.w3.org/2005/Atom}link")
            link = (link_el.get("href") if link_el is not None else None) or None
            pub = self._parse_date((entry.findtext("{http://www.w3.org/2005/Atom}updated") or "").strip())
            if title:
                out.append(NewsItem(title=title, published=pub, link=link))

        return out

    def _normalize_feeds(self, feeds: List[str]) -> List[str]:
        seen: List[str] = []
        for url in feeds:
            url_str = str(url).strip()
            if not url_str:
                continue
            if url_str not in seen:
                seen.append(url_str)
        return seen or list(DEFAULT_FEEDS)

    def _parse_date(self, s: str) -> Optional[datetime]:
        # Çok basit yaklaşımlar (RFC 2822 / ISO)
        for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z"):
            try:
                return datetime.strptime(s, fmt).astimezone(UTC)
            except Exception:
                pass
        try:
            # ISO
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt.astimezone(UTC)
        except Exception:
            return None

    # ------------- selection -------------
    def _pick_for_topic(self, items: List[NewsItem], topic_hint: Optional[str]) -> Optional[NewsItem]:
        topic = (topic_hint or "").lower()
        if not items:
            return None

        # Basit anahtar kelime eşleşmesi
        KEYWORDS = {
            "bist": [r"bist", r"borsa istanbul", r"tcmb", r"turkey", r"türkiye", r"lira", r"try"],
            "fx": [r"forex", r"currency", r"dollar", r"euro", r"yen", r"usd", r"eur", r"jpy", r"lira", r"try"],
            "kripto": [r"bitcoin", r"\beth( |$)|\bethereum", r"crypto", r"btc", r"eth", r"stablecoin"],
            "makro": [r"inflation", r"enflasyon", r"gdp", r"growth", r"faiz", r"interest rate", r"central bank", r"fed", r"ecb", r"cpi", r"ppi", r"unemployment"],
        }

        pool = items
        if topic in KEYWORDS:
            pats = [re.compile(k, re.I) for k in KEYWORDS[topic]]
            scored = [it for it in items if any(p.search(it.title or "") for p in pats)]
            pool = scored or items

        # En günceli al
        pool = sorted(pool, key=lambda x: x.published or datetime.min.replace(tzinfo=UTC), reverse=True)
        return pool[0] if pool else None

    # ------------- llm summary -------------
    def _summarize_title_tr(self, title: str) -> Optional[str]:
        if self._llm is None:
            return None
        prompt = f"""Başlığı 1 kısa cümlede Türkçe ve temkinli şekilde özetle. Yatırım tavsiyesi verme, kesin hüküm kurma.

Başlık: {title}
"""
        try:
            out = self._llm.generate(user_prompt=prompt, temperature=0.3, max_tokens=80)
            if out:
                return out.strip()
        except Exception as e:
            log.debug("LLM summarize error: %s", e)
        return None
