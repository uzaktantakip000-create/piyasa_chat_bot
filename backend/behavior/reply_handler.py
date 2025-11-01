"""
Reply target selection and message analysis utilities for the behavior engine.

This module provides helper functions for smart reply target selection:
- Topic detection (BIST, FX, Kripto, Makro)
- Sentiment analysis
- Symbol/ticker extraction
"""

import re
from typing import List


def detect_topics(text: str) -> List[str]:
    """
    Detect market topics in a message.

    Scans text for keywords related to Turkish financial markets:
    - BIST (Turkish stock exchange)
    - FX (foreign exchange)
    - Kripto (cryptocurrency)
    - Makro (macroeconomics)

    Args:
        text: Message text to analyze

    Returns:
        List of detected topic names (e.g., ["BIST", "FX"])
    """
    topics = []
    text_lower = text.lower()

    # BIST (Turkish stock market)
    if any(w in text_lower for w in ["bist", "borsa", "hisse", "imkb", "endeks"]):
        topics.append("BIST")

    # FX (Foreign exchange)
    if any(w in text_lower for w in ["dolar", "euro", "tl", "kur", "forex", "usd", "eur"]):
        topics.append("FX")

    # Kripto
    if any(w in text_lower for w in ["btc", "eth", "kripto", "bitcoin", "ethereum", "coin", "altcoin"]):
        topics.append("Kripto")

    # Makro
    if any(w in text_lower for w in ["enflasyon", "faiz", "tcmb", "merkez", "fed", "piyasa", "ekonomi"]):
        topics.append("Makro")

    return topics


def detect_sentiment(text: str) -> float:
    """
    Simple sentiment analysis of Turkish market message.

    Counts positive and negative financial keywords to estimate sentiment.

    Positive keywords: yükseldi, arttı, güçlü, kazanç, rally, boğa, alım, etc.
    Negative keywords: düştü, azaldı, zayıf, zarar, satış, ayı, risk, etc.

    Args:
        text: Message text to analyze

    Returns:
        Sentiment score from -1.0 (very negative) to +1.0 (very positive)
        Returns 0.0 if no sentiment keywords found
    """
    positive_words = [
        "yükseldi", "arttı", "güçlü", "olumlu", "iyi", "kazanç", "başarılı",
        "pozitif", "yükseliş", "artış", "rally", "boğa", "al", "alım"
    ]
    negative_words = [
        "düştü", "azaldı", "zayıf", "olumsuz", "kötü", "zarar", "başarısız",
        "negatif", "düşüş", "azalış", "satış", "ayı", "sat", "risk"
    ]

    text_lower = text.lower()

    pos_count = sum(1 for w in positive_words if w in text_lower)
    neg_count = sum(1 for w in negative_words if w in text_lower)

    total = pos_count + neg_count
    if total == 0:
        return 0.0

    return (pos_count - neg_count) / total


def extract_symbols(text: str) -> List[str]:
    """
    Extract stock symbols and crypto tickers from message text.

    Detects:
    - Turkish stock codes (4-6 uppercase letters, e.g., AKBNK, GARAN, THYAO)
    - Major crypto symbols (BTC, ETH, USDT, BNB, XRP, ADA, SOL, etc.)

    Args:
        text: Message text to scan

    Returns:
        List of unique symbols found (deduplicated)
    """
    symbols = []
    text_upper = text.upper()

    # Türk hisse kodları (4-6 harf, tüm büyük)
    turkish_stocks = re.findall(r'\b[A-Z]{4,6}\b', text_upper)
    symbols.extend(turkish_stocks)

    # Kripto sembolleri (BTC, ETH, USDT, etc.)
    crypto_pattern = r'\b(BTC|ETH|USDT|BNB|XRP|ADA|SOL|DOGE|AVAX|MATIC|DOT)\b'
    cryptos = re.findall(crypto_pattern, text_upper)
    symbols.extend(cryptos)

    # Duplicate'leri temizle
    return list(set(symbols))
