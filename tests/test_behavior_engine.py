import base64
import importlib
import sys
from pathlib import Path
from datetime import datetime

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
