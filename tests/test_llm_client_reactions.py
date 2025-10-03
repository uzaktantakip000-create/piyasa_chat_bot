import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import llm_client
from llm_client import LLMClient


def test_pick_reaction_positive():
    text = "Hisse bugün güzel bir yükseliş yakaladı ve yatırımcıları mutlu etti."
    assert LLMClient.pick_reaction_for_text(text) == "📈"


def test_pick_reaction_negative():
    text = "Beklenen haber gelmedi ve piyasa sert düşüş yaşadı, moraller bozuk."
    assert LLMClient.pick_reaction_for_text(text) == "📉"


def test_pick_reaction_neutral():
    text = "Piyasa bugün stabil seyretti, şimdilik beklemedeyiz."
    assert LLMClient.pick_reaction_for_text(text) == "💬"


def test_pick_reaction_random_fallback(monkeypatch):
    monkeypatch.setattr(llm_client.random, "choice", lambda seq: seq[0])
    assert LLMClient.pick_reaction_for_text("Bu metin ipucu içermiyor.") == "👍"
