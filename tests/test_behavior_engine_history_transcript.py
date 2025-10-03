from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from behavior_engine import build_history_transcript


class DummyBot(SimpleNamespace):
    pass


class DummyChat(SimpleNamespace):
    pass


def _make_message(*, minutes: int, text: str, bot=None, sender_name: str | None = None, chat=None):
    msg = SimpleNamespace(
        text=text,
        bot=bot,
        chat=chat,
        bot_id=getattr(bot, "id", None),
        created_at=datetime.utcnow() + timedelta(minutes=minutes),
    )
    if sender_name is not None:
        msg.sender_name = sender_name
    return msg


def test_build_history_transcript_labels_and_orders_messages():
    chat = DummyChat(title="Genel Sohbet")
    bot_ali = DummyBot(id=1, username="@AliBot", name="Ali Bot")
    bot_ayse = DummyBot(id=2, name="Ayşe Bot")

    raw_messages = [
        _make_message(minutes=idx, text=f"Mesaj {idx}", sender_name=f"Kullanıcı{idx}", chat=chat)
        for idx in range(1, 4)
    ]
    raw_messages.extend(
        [
            _make_message(minutes=4, text="Selamlar", bot=bot_ali, chat=chat),
            _make_message(minutes=5, text="Nasılsınız?", sender_name="Zeynep", chat=chat),
            _make_message(minutes=6, text="İyi gidiyor", bot=bot_ayse, chat=chat),
            _make_message(minutes=7, text="Harika", sender_name="Murat", chat=chat),
        ]
    )

    # Behavior engine son 6 mesajı kullanır; bu nedenle en güncel 6 mesajı alıyoruz.
    last_six = raw_messages[-6:]

    transcript = build_history_transcript(last_six)

    expected_lines = [
        "[Kullanıcı2]: Mesaj 2",
        "[Kullanıcı3]: Mesaj 3",
        "[AliBot]: Selamlar",
        "[Zeynep]: Nasılsınız?",
        "[Ayşe Bot]: İyi gidiyor",
        "[Murat]: Harika",
    ]

    assert transcript.splitlines() == expected_lines
