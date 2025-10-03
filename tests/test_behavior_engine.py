import base64
import importlib
import sys
import asyncio
from pathlib import Path
from datetime import datetime
from types import SimpleNamespace
import pytest


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def setup_behavior_engine(tmp_path, monkeypatch):
    db_path = tmp_path / "behavior.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", base64.urlsafe_b64encode(b"0" * 32).decode())
    monkeypatch.setenv("API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai")

    import security
    import database
    import behavior_engine as behavior_engine_module

    importlib.reload(security)
    importlib.reload(database)
    from database import Base, engine as db_engine

    Base.metadata.drop_all(bind=db_engine)
    Base.metadata.create_all(bind=db_engine)

    importlib.reload(behavior_engine_module)
    Base.metadata.create_all(bind=db_engine)

    return behavior_engine_module, database


def test_pick_bot_respects_active_hours(tmp_path, monkeypatch):
    behavior_engine_module, database = setup_behavior_engine(tmp_path, monkeypatch)

    engine = behavior_engine_module.BehaviorEngine()
    SessionLocal = database.SessionLocal
    Bot = database.Bot

    session = SessionLocal()
    try:
        active_bot = Bot(
            name="Active",
            username="active_bot",
            is_enabled=True,
            active_hours=["00:00-23:59"],
        )
        active_bot.token = "12345:ACTIVE"

        now = datetime.now()
        inactive_hour = (now.hour + 2) % 24
        inactive_bot = Bot(
            name="Inactive",
            username="sleepy_bot",
            is_enabled=True,
            active_hours=[f"{inactive_hour:02d}:00-{inactive_hour:02d}:30"],
        )
        inactive_bot.token = "12345:INACTIVE"

        session.add_all([active_bot, inactive_bot])
        session.commit()

        selected = engine.pick_bot(session, {"max": 12})
        assert selected is not None
        assert selected.id == active_bot.id
    finally:
        session.close()


def test_pick_bot_avoids_last_bot_when_others_available(tmp_path, monkeypatch):
    behavior_engine_module, database = setup_behavior_engine(tmp_path, monkeypatch)

    engine = behavior_engine_module.BehaviorEngine()
    SessionLocal = database.SessionLocal
    Bot = database.Bot
    Chat = database.Chat
    Message = database.Message

    session = SessionLocal()
    try:
        chat = Chat(chat_id="-500", title="Rotation Chat", is_enabled=True)
        bot_a = Bot(name="Alpha", username="alpha_bot", is_enabled=True)
        bot_b = Bot(name="Beta", username="beta_bot", is_enabled=True)
        bot_a.token = "12345:ALPHA"
        bot_b.token = "12345:BETA"

        session.add_all([chat, bot_a, bot_b])
        session.commit()
        session.refresh(chat)
        session.refresh(bot_a)
        session.refresh(bot_b)

        session.add(
            Message(
                id=1,
                bot_id=bot_a.id,
                chat_db_id=chat.id,
                telegram_message_id=111,
                text="son mesaj alpha",
            )
        )
        session.commit()

        selected = engine.pick_bot(session, {"max": 12}, chat=chat)
        assert selected is not None
        assert selected.id == bot_b.id
    finally:
        session.close()


def test_speed_profile_scales_delays_and_typing(tmp_path, monkeypatch):
    behavior_engine_module, database = setup_behavior_engine(tmp_path, monkeypatch)

    engine = behavior_engine_module.BehaviorEngine()
    SessionLocal = database.SessionLocal
    Bot = database.Bot

    session = SessionLocal()
    try:
        speedy_bot = Bot(
            name="Speedy",
            username="speedy_bot",
            is_enabled=True,
            speed_profile={
                "delay": {
                    "base_delay_seconds": 20.0,
                    "delay_multiplier": 0.5,
                    "jitter_min": 1.0,
                    "jitter_max": 1.0,
                    "min_seconds": 1.0,
                    "max_seconds": 90.0,
                },
                "typing": {
                    "wpm_min": 50.0,
                    "wpm_max": 60.0,
                    "min_seconds": 0.2,
                    "max_seconds": 5.0,
                },
            },
        )
        speedy_bot.token = "12345:SPEED"

        session.add(speedy_bot)
        session.commit()

        monkeypatch.setattr(behavior_engine_module, "exp_delay", lambda mean: mean)
        monkeypatch.setattr(behavior_engine_module.random, "uniform", lambda a, b: 1.0)
        monkeypatch.setattr(behavior_engine_module, "is_prime_hours", lambda *_: False)

        delay = engine.next_delay_seconds(session, bot=speedy_bot)
        assert delay == pytest.approx(10.0)

        typing_duration = engine.typing_seconds(session, est_chars=20, bot=speedy_bot)
        expected_typing = 20 / ((55.0 * 5.0) / 60.0)
        assert typing_duration == pytest.approx(expected_typing)
    finally:
        session.close()


def test_generate_user_prompt_includes_persona_hint():
    from system_prompt import generate_user_prompt

    prompt = generate_user_prompt(
        topic_name="BIST",
        history_excerpt="",
        reply_context="",
        market_trigger="",
        mode="new",
        persona_profile=None,
        stances=None,
        holdings=None,
        length_hint="kısa",
        persona_hint="iyimser ve temkinli",
    )

    assert "iyimser ve temkinli" in prompt


def _first_choice(seq):
    if not seq:
        raise IndexError("Cannot choose from an empty sequence")
    return seq[0]


def test_pick_reply_target_ignores_self_messages(tmp_path, monkeypatch):
    behavior_engine_module, database = setup_behavior_engine(tmp_path, monkeypatch)

    engine = behavior_engine_module.BehaviorEngine()
    SessionLocal = database.SessionLocal
    Bot = database.Bot
    Chat = database.Chat
    Message = database.Message

    session = SessionLocal()
    try:
        bot = Bot(
            name="Responder",
            username="responder_bot",
            is_enabled=True,
        )
        bot.token = "12345:RESP"
        chat = Chat(chat_id="-1001", title="Test Chat", is_enabled=True)
        session.add_all([bot, chat])
        session.commit()
        session.refresh(bot)
        session.refresh(chat)

        # Bot'un kendi mesajı (filtrelenmeli)
        session.add(
            Message(
                id=1,
                bot_id=bot.id,
                chat_db_id=chat.id,
                telegram_message_id=101,
                text="kendi mesajı",
            )
        )
        # Kullanıcı mesajı (yanıt hedefi olmalı)
        session.add(
            Message(
                id=2,
                bot_id=None,
                chat_db_id=chat.id,
                telegram_message_id=102,
                text="merhaba bot",
            )
        )
        session.commit()

        monkeypatch.setattr(behavior_engine_module.random, "random", lambda: 0.0)
        monkeypatch.setattr(behavior_engine_module.random, "choice", _first_choice)
        monkeypatch.setattr(engine, "settings", lambda _db: {"mention_probability": 0.0})

        target, mention = engine.pick_reply_target(
            session,
            chat,
            reply_p=1.0,
            active_bot_id=bot.id,
            active_bot_username=bot.username,
        )

        assert target is not None
        assert target.text == "merhaba bot"
        assert mention is None
    finally:
        session.close()


def test_pick_reply_target_returns_none_for_only_self_messages(tmp_path, monkeypatch):
    behavior_engine_module, database = setup_behavior_engine(tmp_path, monkeypatch)

    engine = behavior_engine_module.BehaviorEngine()
    SessionLocal = database.SessionLocal
    Bot = database.Bot
    Chat = database.Chat
    Message = database.Message

    session = SessionLocal()
    try:
        bot = Bot(
            name="Solo",
            username="solo_bot",
            is_enabled=True,
        )
        bot.token = "12345:SOLO"
        chat = Chat(chat_id="-1002", title="Solo Chat", is_enabled=True)
        session.add_all([bot, chat])
        session.commit()
        session.refresh(bot)
        session.refresh(chat)

        session.add(
            Message(
                id=1,
                bot_id=bot.id,
                chat_db_id=chat.id,
                telegram_message_id=201,
                text="bot botla konuşmaz",
            )
        )
        session.commit()

        monkeypatch.setattr(behavior_engine_module.random, "random", lambda: 0.0)
        monkeypatch.setattr(behavior_engine_module.random, "choice", _first_choice)
        monkeypatch.setattr(engine, "settings", lambda _db: {"mention_probability": 0.0})

        target, mention = engine.pick_reply_target(
            session,
            chat,
            reply_p=1.0,
            active_bot_id=bot.id,
            active_bot_username=bot.username,
        )

        assert target is None
        assert mention is None
    finally:
        session.close()


def test_pick_reply_target_prioritizes_user_questions_over_bot_messages(tmp_path, monkeypatch):
    behavior_engine_module, database = setup_behavior_engine(tmp_path, monkeypatch)

    engine = behavior_engine_module.BehaviorEngine()
    SessionLocal = database.SessionLocal
    Bot = database.Bot
    Chat = database.Chat
    Message = database.Message

    session = SessionLocal()
    try:
        responder = Bot(
            name="Responder",
            username="responder_bot",
            is_enabled=True,
        )
        responder.token = "12345:RESP"
        other_bot = Bot(
            name="Announcer",
            username="announcer_bot",
            is_enabled=True,
        )
        other_bot.token = "12345:ANN"
        chat = Chat(chat_id="-2001", title="Test Chat", is_enabled=True)
        session.add_all([responder, other_bot, chat])
        session.commit()
        session.refresh(responder)
        session.refresh(other_bot)
        session.refresh(chat)

        session.add(
            Message(
                id=1,
                bot=other_bot,
                chat_db_id=chat.id,
                telegram_message_id=501,
                text="borsa hakkında düşüncelerim",
            )
        )
        session.add(
            Message(
                id=2,
                bot_id=None,
                chat_db_id=chat.id,
                telegram_message_id=502,
                text="borsa düşer mi?",
            )
        )
        session.commit()

        monkeypatch.setattr(behavior_engine_module.random, "random", lambda: 0.0)
        monkeypatch.setattr(engine, "settings", lambda _db: {"mention_probability": 0.0})

        target, _ = engine.pick_reply_target(
            session,
            chat,
            reply_p=1.0,
            active_bot_id=responder.id,
            active_bot_username=responder.username,
        )

        assert target is not None
        assert target.text == "borsa düşer mi?"
    finally:
        session.close()


def test_pick_reply_target_respects_active_bot_mentions(tmp_path, monkeypatch):
    behavior_engine_module, database = setup_behavior_engine(tmp_path, monkeypatch)

    engine = behavior_engine_module.BehaviorEngine()
    SessionLocal = database.SessionLocal
    Bot = database.Bot
    Chat = database.Chat
    Message = database.Message

    session = SessionLocal()
    try:
        responder = Bot(
            name="Responder",
            username="responder_bot",
            is_enabled=True,
        )
        responder.token = "12345:RESP"
        other_bot = Bot(
            name="Announcer",
            username="announcer_bot",
            is_enabled=True,
        )
        other_bot.token = "12345:ANN"
        chat = Chat(chat_id="-2002", title="Test Chat", is_enabled=True)
        session.add_all([responder, other_bot, chat])
        session.commit()
        session.refresh(responder)
        session.refresh(other_bot)
        session.refresh(chat)

        session.add(
            Message(
                id=1,
                bot=other_bot,
                chat_db_id=chat.id,
                telegram_message_id=601,
                text="@responder_bot görüşlerin neler?",
            )
        )
        session.commit()

        def fake_settings(_db):
            return {"mention_probability": 1.0}

        monkeypatch.setattr(behavior_engine_module.random, "random", lambda: 0.0)
        monkeypatch.setattr(engine, "settings", fake_settings)

        target, mention = engine.pick_reply_target(
            session,
            chat,
            reply_p=1.0,
            active_bot_id=responder.id,
            active_bot_username=responder.username,
        )

        assert target is not None
        assert target.text == "@responder_bot görüşlerin neler?"
        assert mention == "announcer_bot"
    finally:
        session.close()


def test_short_reaction_skips_self_messages(tmp_path, monkeypatch):
    behavior_engine_module, database = setup_behavior_engine(tmp_path, monkeypatch)

    engine = behavior_engine_module.BehaviorEngine()
    SessionLocal = database.SessionLocal
    Bot = database.Bot
    Chat = database.Chat
    Message = database.Message

    session = SessionLocal()
    try:
        bot = Bot(
            name="Reactor",
            username="reactor_bot",
            is_enabled=True,
        )
        bot.token = "12345:REACT"
        chat = Chat(chat_id="-1003", title="Reaction Chat", is_enabled=True, topics=["BIST"])
        session.add_all([bot, chat])
        session.commit()
        session.refresh(bot)
        session.refresh(chat)

        session.add(
            Message(
                id=1,
                bot_id=bot.id,
                chat_db_id=chat.id,
                telegram_message_id=301,
                text="bot kendi mesajı",
            )
        )
        session.commit()

        bot_stub = SimpleNamespace(
            id=bot.id,
            token=bot.token,
            username=bot.username,
            name=bot.name,
        )
        chat_stub = SimpleNamespace(
            id=chat.id,
            chat_id=chat.chat_id,
            topics=list(chat.topics or []),
            title=chat.title,
        )
        session.expunge(bot)
        session.expunge(chat)
    finally:
        session.close()

    monkeypatch.setattr(behavior_engine_module.random, "random", lambda: 0.0)
    monkeypatch.setattr(behavior_engine_module.random, "choice", _first_choice)

    settings_payload = {
        "simulation_active": True,
        "bot_hourly_msg_limit": {"max": 12},
        "short_reaction_probability": 1.0,
        "reply_probability": 1.0,
        "mention_probability": 0.0,
        "cooldown_filter_enabled": False,
        "news_trigger_enabled": False,
        "message_length_profile": None,
        "consistency_guard_enabled": False,
        "dedup_enabled": False,
        "typing_enabled": False,
    }

    monkeypatch.setattr(engine, "settings", lambda _db: settings_payload)
    monkeypatch.setattr(engine, "global_rate_ok", lambda _db: True)
    monkeypatch.setattr(engine, "pick_chat", lambda _db: chat_stub)
    monkeypatch.setattr(
        engine, "pick_bot", lambda _db, hourly_limit=None, chat=None: bot_stub
    )
    monkeypatch.setattr(engine, "fetch_psh", lambda _db, _bot, topic_hint: (None, [], [], None))
    monkeypatch.setattr(engine, "next_delay_seconds", lambda _db, bot=None: 0.0)
    monkeypatch.setattr(engine, "apply_consistency_guard", lambda **_: None)
    monkeypatch.setattr(engine, "is_duplicate_recent", lambda *_, **__: False)

    calls = {
        "reaction": False,
        "sent": False,
    }

    async def fake_try_set_reaction(*args, **kwargs):
        calls["reaction"] = True
        return True

    async def fake_send_message(*args, **kwargs):
        calls["sent"] = True
        return 999

    async def fake_send_typing(*args, **kwargs):
        return None

    monkeypatch.setattr(engine.tg, "try_set_reaction", fake_try_set_reaction)
    monkeypatch.setattr(engine.tg, "send_message", fake_send_message)
    monkeypatch.setattr(engine.tg, "send_typing", fake_send_typing)
    monkeypatch.setattr(engine.llm, "generate", lambda **_: "selam")

    asyncio.run(engine.tick_once())

    assert calls["reaction"] is False, "bot kendi mesajına reaksiyon vermemeli"
    assert calls["sent"] is True, "reaksiyon atlanınca normal gönderim akışı devam etmeli"


def test_choose_topic_prefers_context():
    from behavior_engine import choose_topic_from_messages

    messages = [
        SimpleNamespace(text="BTC fiyatı bugün çok oynak"),
        SimpleNamespace(text="Kripto piyasası sert düştü"),
    ]

    topic = choose_topic_from_messages(messages, ["BIST", "Kripto", "Makro"])

    assert topic == "Kripto"


def test_choose_topic_fallback_preserves_random_choice():
    from behavior_engine import choose_topic_from_messages

    class DummyRng:
        def __init__(self):
            self.last_choices = None

        def choice(self, seq):
            self.last_choices = list(seq)
            return seq[0]

    rng = DummyRng()
    messages = [SimpleNamespace(text="Merhaba nasılsın"), SimpleNamespace(text="Bugün hava güzel")]  # no keywords
    topics = ["BIST", "FX"]

    topic = choose_topic_from_messages(messages, topics, rng=rng)

    assert topic == "BIST"
    assert rng.last_choices == topics
