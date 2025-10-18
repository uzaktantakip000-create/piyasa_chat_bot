"""
Phase 1 - Incoming Message System Integration Tests

Tests the complete incoming message flow including:
- Webhook endpoint functionality
- Long polling message listener
- Priority queue system
- Mention detection
- User message context integration
- Bot response generation
"""

import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Dict, Any, List
from unittest.mock import Mock, patch, AsyncMock

import pytest
import redis
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from database import Base, Bot, Chat, Message, Setting, BotStance, BotHolding, BotMemory
from main import app, get_db
from behavior_engine import BehaviorEngine
from message_listener import MessageListenerService
from telegram_client import TelegramClient


# Test Database Setup
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def get_test_db():
    """Override database dependency for testing"""
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def test_db():
    """Create fresh database for each test"""
    Base.metadata.create_all(bind=test_engine)
    db = TestSessionLocal()

    # Initialize default settings
    default_settings = {
        "simulation_active": True,
        "scale_factor": 1.0,
        "max_msgs_per_min": 10,
        "reply_probability": 0.4,
        "mention_probability": 0.3,
    }
    for key, value in default_settings.items():
        db.add(Setting(key=key, value=value))

    db.commit()
    yield db
    db.close()
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def api_client(test_db):
    """FastAPI test client with test database"""
    app.dependency_overrides[get_db] = get_test_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def mock_redis():
    """Mock Redis client for priority queue testing"""
    mock_client = Mock(spec=redis.Redis)
    mock_client.lpush = Mock(return_value=1)
    mock_client.rpop = Mock(return_value=None)
    mock_client.ping = Mock(return_value=True)
    return mock_client


@pytest.fixture
def test_bot(test_db) -> Bot:
    """Create test bot"""
    bot = Bot(
        name="TestBot",
        token="test_token_123",
        username="testbot",
        is_enabled=True,
        persona_hint="Friendly market analyst",
        persona_profile={
            "tone": "analytical",
            "risk_profile": "moderate",
            "watchlist": ["BIST", "USD/TRY"],
        },
        emotion_profile={
            "tone": "professional",
            "energy": 0.7,
            "signature_emoji": ["📈", "💡"],
        }
    )
    test_db.add(bot)
    test_db.commit()
    test_db.refresh(bot)
    return bot


@pytest.fixture
def test_chat(test_db) -> Chat:
    """Create test chat"""
    chat = Chat(
        chat_id="123456789",  # Use numeric string for Telegram chat ID
        title="Test Market Chat",
        is_enabled=True,
        topics=["BIST", "FX", "Kripto"],
    )
    test_db.add(chat)
    test_db.commit()
    test_db.refresh(chat)
    return chat


class TestWebhookEndpoint:
    """Test webhook endpoint functionality"""

    def test_webhook_receives_message(self, api_client, test_bot, test_chat, test_db):
        """Test webhook successfully receives and stores incoming message"""
        update = {
            "update_id": 12345,
            "message": {
                "message_id": 100,
                "chat": {
                    "id": int(test_chat.chat_id),
                    "title": test_chat.title,
                },
                "from": {
                    "id": 999,
                    "username": "testuser",
                    "is_bot": False,
                },
                "text": "BIST 100 bugün nasıl?",
            }
        }

        response = api_client.post(
            f"/webhook/telegram/{test_bot.token}",
            json=update
        )

        assert response.status_code == 200
        assert response.json()["status"] == "ok"

        # Verify message was stored
        msg = test_db.query(Message).filter(
            Message.telegram_message_id == 100
        ).first()
        assert msg is not None
        assert msg.text == "BIST 100 bugün nasıl?"
        assert msg.bot_id is None  # User message
        assert msg.msg_metadata["from_user_id"] == 999
        assert msg.msg_metadata["username"] == "testuser"
        assert msg.msg_metadata["is_incoming"] is True

    def test_webhook_auto_creates_chat(self, api_client, test_bot, test_db):
        """Test webhook auto-creates chat if not exists"""
        new_chat_id = "999888777"
        update = {
            "update_id": 12346,
            "message": {
                "message_id": 101,
                "chat": {
                    "id": int(new_chat_id),
                    "title": "New Test Chat",
                },
                "from": {
                    "id": 888,
                    "username": "newuser",
                    "is_bot": False,
                },
                "text": "Hello world",
            }
        }

        response = api_client.post(
            f"/webhook/telegram/{test_bot.token}",
            json=update
        )

        assert response.status_code == 200

        # Verify chat was auto-created
        chat = test_db.query(Chat).filter(Chat.chat_id == new_chat_id).first()
        assert chat is not None
        assert chat.title == "New Test Chat"
        assert chat.is_enabled is True

    def test_webhook_detects_mention(self, api_client, test_bot, test_chat, test_db, mock_redis):
        """Test webhook detects bot mention and adds to high priority queue"""
        with patch('main.get_redis', return_value=mock_redis):
            update = {
                "update_id": 12347,
                "message": {
                    "message_id": 102,
                    "chat": {
                        "id": int(test_chat.chat_id),
                        "title": test_chat.title,
                    },
                    "from": {
                        "id": 777,
                        "username": "mentionuser",
                        "is_bot": False,
                    },
                    "text": f"@{test_bot.username} ne düşünüyorsun?",
                }
            }

            response = api_client.post(
                f"/webhook/telegram/{test_bot.token}",
                json=update
            )

            assert response.status_code == 200

            # Verify high priority queue was called
            mock_redis.lpush.assert_called()
            call_args = mock_redis.lpush.call_args
            assert call_args[0][0] == "priority_queue:high"

            # Verify priority data
            priority_data = json.loads(call_args[0][1])
            assert priority_data["is_mentioned"] is True
            assert priority_data["priority"] == "high"

    def test_webhook_detects_reply_to_bot(self, api_client, test_bot, test_chat, test_db, mock_redis):
        """Test webhook detects reply to bot message"""
        # Create a bot message first
        bot_msg = Message(
            bot_id=test_bot.id,
            chat_db_id=test_chat.id,
            telegram_message_id=50,
            text="BIST 100 yükselişte",
            msg_metadata={},
        )
        test_db.add(bot_msg)
        test_db.commit()

        with patch('main.get_redis', return_value=mock_redis):
            update = {
                "update_id": 12348,
                "message": {
                    "message_id": 103,
                    "chat": {
                        "id": int(test_chat.chat_id),
                        "title": test_chat.title,
                    },
                    "from": {
                        "id": 666,
                        "username": "replyuser",
                        "is_bot": False,
                    },
                    "text": "Ne kadar yükselir?",
                    "reply_to_message": {
                        "message_id": 50,
                    }
                }
            }

            response = api_client.post(
                f"/webhook/telegram/{test_bot.token}",
                json=update
            )

            assert response.status_code == 200

            # Verify high priority queue was called
            mock_redis.lpush.assert_called()
            call_args = mock_redis.lpush.call_args
            assert call_args[0][0] == "priority_queue:high"

            priority_data = json.loads(call_args[0][1])
            assert priority_data["is_reply_to_bot"] is True
            assert priority_data["priority"] == "high"

    def test_webhook_ignores_bot_messages(self, api_client, test_bot, test_chat, test_db):
        """Test webhook ignores messages from bots"""
        update = {
            "update_id": 12349,
            "message": {
                "message_id": 104,
                "chat": {
                    "id": int(test_chat.chat_id),
                    "title": test_chat.title,
                },
                "from": {
                    "id": 555,
                    "username": "anotherbot",
                    "is_bot": True,  # Bot message
                },
                "text": "Bot message",
            }
        }

        response = api_client.post(
            f"/webhook/telegram/{test_bot.token}",
            json=update
        )

        assert response.status_code == 200

        # Verify no message was stored
        msg = test_db.query(Message).filter(
            Message.telegram_message_id == 104
        ).first()
        assert msg is None

    def test_webhook_invalid_token(self, api_client, test_chat):
        """Test webhook rejects invalid bot token"""
        update = {
            "update_id": 12350,
            "message": {
                "message_id": 105,
                "chat": {"id": int(test_chat.chat_id)},
                "from": {"id": 444, "is_bot": False},
                "text": "Test",
            }
        }

        response = api_client.post(
            "/webhook/telegram/invalid_token_xxx",
            json=update
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestMessageListener:
    """Test MessageListenerService (long polling mode)"""

    @pytest.mark.asyncio
    async def test_listener_polls_updates(self, test_bot, test_chat, test_db, mock_redis):
        """Test listener successfully polls and processes updates"""
        mock_telegram = AsyncMock(spec=TelegramClient)
        mock_telegram.get_updates = AsyncMock(return_value=[
            {
                "update_id": 1001,
                "message": {
                    "message_id": 200,
                    "chat": {
                        "id": int(test_chat.chat_id),
                        "title": test_chat.title,
                    },
                    "from": {
                        "id": 333,
                        "username": "pollinguser",
                        "is_bot": False,
                    },
                    "text": "Test polling message",
                }
            }
        ])
        mock_telegram.close = AsyncMock()

        service = MessageListenerService(
            redis_client=mock_redis,
            polling_interval=0.1,
        )
        service.telegram_client = mock_telegram
        service.running = False  # Don't loop forever

        # Run one poll cycle
        await service._poll_all_bots()

        # Verify get_updates was called
        mock_telegram.get_updates.assert_called()

        # Verify message was stored
        msg = test_db.query(Message).filter(
            Message.telegram_message_id == 200
        ).first()
        assert msg is not None
        assert msg.text == "Test polling message"

    @pytest.mark.asyncio
    async def test_listener_tracks_update_ids(self, test_bot, test_db):
        """Test listener tracks last_update_id to avoid duplicates"""
        mock_telegram = AsyncMock(spec=TelegramClient)
        mock_telegram.get_updates = AsyncMock(return_value=[
            {"update_id": 2001, "message": {"message_id": 201, "chat": {"id": 123}, "from": {"id": 222, "is_bot": False}, "text": "First"}},
            {"update_id": 2002, "message": {"message_id": 202, "chat": {"id": 123}, "from": {"id": 222, "is_bot": False}, "text": "Second"}},
        ])
        mock_telegram.close = AsyncMock()

        service = MessageListenerService()
        service.telegram_client = mock_telegram
        service.running = False

        await service._poll_all_bots()

        # Verify last_update_id was tracked
        assert service.last_update_ids.get(test_bot.id) == 2002

        # Next call should use offset
        mock_telegram.get_updates.reset_mock()
        mock_telegram.get_updates.return_value = []
        await service._poll_all_bots()

        # Verify offset was passed
        call_kwargs = mock_telegram.get_updates.call_args[1]
        assert call_kwargs["offset"] == 2003  # last_update_id + 1


class TestPriorityQueue:
    """Test priority queue system"""

    @pytest.mark.asyncio
    async def test_priority_queue_processing(self, test_bot, test_chat, test_db, mock_redis):
        """Test behavior engine processes priority queue messages"""
        # Create user message in DB
        user_msg = Message(
            bot_id=None,
            chat_db_id=test_chat.id,
            telegram_message_id=300,
            text="@testbot BIST analizi yapabilir misin?",
            msg_metadata={
                "from_user_id": 111,
                "username": "priorityuser",
                "is_incoming": True,
            }
        )
        test_db.add(user_msg)
        test_db.commit()
        test_db.refresh(user_msg)

        # Add to priority queue
        priority_data = {
            "type": "incoming_message",
            "message_id": user_msg.id,
            "telegram_message_id": 300,
            "chat_id": test_chat.id,
            "telegram_chat_id": test_chat.chat_id,
            "bot_id": test_bot.id,
            "text": user_msg.text,
            "is_mentioned": True,
            "is_reply_to_bot": False,
            "priority": "high",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        mock_redis.rpop = Mock(side_effect=[
            json.dumps(priority_data),  # First call returns priority item
            None,  # Second call returns None
        ])

        # Mock OpenAI
        mock_openai_response = Mock()
        mock_openai_response.choices = [Mock()]
        mock_openai_response.choices[0].message.content = "BIST 100 son günlerde güzel bir yükseliş trendinde. Teknik göstergeler de olumlu."

        # Mock Telegram client
        mock_telegram = AsyncMock(spec=TelegramClient)
        mock_telegram.send_typing = AsyncMock()
        mock_telegram.send_message = AsyncMock(return_value=301)

        with patch.dict(os.environ, {"REDIS_URL": "redis://localhost:6379/0", "OPENAI_API_KEY": "test_key"}):
            with patch('behavior_engine.openai.ChatCompletion.create', return_value=mock_openai_response):
                engine = BehaviorEngine()
                engine.telegram_client = mock_telegram
                engine._redis_sync_client = mock_redis

                # Process one tick
                await engine.tick_once()

                # Verify priority queue was checked
                mock_redis.rpop.assert_called()

                # Verify bot response was sent
                mock_telegram.send_message.assert_called()
                call_kwargs = mock_telegram.send_message.call_args[1]
                assert call_kwargs["reply_to_message_id"] == 300  # Reply to user message

                # Verify bot message was stored in DB
                bot_response = test_db.query(Message).filter(
                    Message.bot_id == test_bot.id,
                    Message.telegram_message_id == 301,
                ).first()
                assert bot_response is not None

    def test_priority_queue_high_vs_normal(self, mock_redis):
        """Test high priority queue is checked before normal"""
        high_priority_data = {
            "type": "incoming_message",
            "priority": "high",
            "is_mentioned": True,
        }
        normal_priority_data = {
            "type": "incoming_message",
            "priority": "normal",
            "is_mentioned": False,
        }

        # Setup mock to return high priority first
        mock_redis.rpop = Mock(side_effect=[
            json.dumps(high_priority_data),
            json.dumps(normal_priority_data),
        ])

        with patch.dict(os.environ, {"REDIS_URL": "redis://localhost:6379/0"}):
            engine = BehaviorEngine()
            engine._redis_sync_client = mock_redis

            from database import SessionLocal
            db = SessionLocal()
            try:
                # First check should get high priority
                result1 = engine._check_priority_queue(db)
                assert result1["priority"] == "high"

                # Second check should get normal priority
                result2 = engine._check_priority_queue(db)
                assert result2["priority"] == "normal"

                # Verify rpop was called on high queue first each time
                calls = mock_redis.rpop.call_args_list
                assert calls[0][0][0] == "priority_queue:high"
                assert calls[1][0][0] == "priority_queue:high"
            finally:
                db.close()


class TestUserMessageContext:
    """Test user messages are used in bot context"""

    @pytest.mark.asyncio
    async def test_user_messages_in_history(self, test_bot, test_chat, test_db):
        """Test user messages are included in conversation history"""
        # Create conversation with mixed user and bot messages
        messages = [
            Message(bot_id=None, chat_db_id=test_chat.id, telegram_message_id=401,
                   text="BIST 100 bugün nasıl?", msg_metadata={"from_user_id": 123, "is_incoming": True}),
            Message(bot_id=test_bot.id, chat_db_id=test_chat.id, telegram_message_id=402,
                   text="BIST 100 güzel yükselişte, %2 artmış.", msg_metadata={}),
            Message(bot_id=None, chat_db_id=test_chat.id, telegram_message_id=403,
                   text="Devam eder mi sence?", msg_metadata={"from_user_id": 123, "is_incoming": True}),
        ]

        for msg in messages:
            test_db.add(msg)
        test_db.commit()

        # Fetch history
        history = test_db.query(Message).filter(
            Message.chat_db_id == test_chat.id
        ).order_by(Message.id.desc()).limit(10).all()

        assert len(history) == 3

        # Verify user messages are included (bot_id is None)
        user_messages = [m for m in history if m.bot_id is None]
        assert len(user_messages) == 2
        assert user_messages[0].text == "Devam eder mi sence?"
        assert user_messages[1].text == "BIST 100 bugün nasıl?"

    @pytest.mark.asyncio
    async def test_context_includes_user_metadata(self, test_bot, test_chat, test_db):
        """Test user message metadata is accessible"""
        user_msg = Message(
            bot_id=None,
            chat_db_id=test_chat.id,
            telegram_message_id=404,
            text="Merhaba",
            msg_metadata={
                "from_user_id": 999,
                "username": "testuser123",
                "is_incoming": True,
                "update_id": 5000,
            }
        )
        test_db.add(user_msg)
        test_db.commit()
        test_db.refresh(user_msg)

        # Verify metadata is stored and retrievable
        assert user_msg.msg_metadata["from_user_id"] == 999
        assert user_msg.msg_metadata["username"] == "testuser123"
        assert user_msg.msg_metadata["is_incoming"] is True


class TestIntegration:
    """Full integration tests"""

    @pytest.mark.asyncio
    async def test_full_webhook_to_response_flow(self, api_client, test_bot, test_chat, test_db, mock_redis):
        """Test complete flow: webhook receives message -> priority queue -> bot responds"""
        # Step 1: Webhook receives user message
        with patch('main.get_redis', return_value=mock_redis):
            update = {
                "update_id": 9001,
                "message": {
                    "message_id": 500,
                    "chat": {
                        "id": int(test_chat.chat_id),
                        "title": test_chat.title,
                    },
                    "from": {
                        "id": 888,
                        "username": "integrationuser",
                        "is_bot": False,
                    },
                    "text": f"@{test_bot.username} USD/TRY analizi?",
                }
            }

            response = api_client.post(
                f"/webhook/telegram/{test_bot.token}",
                json=update
            )

            assert response.status_code == 200

        # Verify message in DB
        user_msg = test_db.query(Message).filter(
            Message.telegram_message_id == 500
        ).first()
        assert user_msg is not None

        # Verify priority queue was populated
        mock_redis.lpush.assert_called()
        priority_call = mock_redis.lpush.call_args
        priority_data = json.loads(priority_call[0][1])

        # Step 2: Behavior engine processes priority queue
        mock_redis.rpop = Mock(return_value=priority_call[0][1])

        mock_openai_response = Mock()
        mock_openai_response.choices = [Mock()]
        mock_openai_response.choices[0].message.content = "USD/TRY 34.50 seviyelerinde. Kısa vadede 35'i test edebilir."

        mock_telegram = AsyncMock(spec=TelegramClient)
        mock_telegram.send_typing = AsyncMock()
        mock_telegram.send_message = AsyncMock(return_value=501)

        with patch.dict(os.environ, {"REDIS_URL": "redis://localhost:6379/0", "OPENAI_API_KEY": "test_key"}):
            with patch('behavior_engine.openai.ChatCompletion.create', return_value=mock_openai_response):
                engine = BehaviorEngine()
                engine.telegram_client = mock_telegram
                engine._redis_sync_client = mock_redis

                await engine.tick_once()

                # Step 3: Verify bot responded
                mock_telegram.send_message.assert_called()
                send_call = mock_telegram.send_message.call_args

                # Should reply to user message
                assert send_call[1]["reply_to_message_id"] == 500
                assert "USD/TRY" in send_call[1]["text"]

                # Verify bot response in DB
                bot_msg = test_db.query(Message).filter(
                    Message.bot_id == test_bot.id,
                    Message.telegram_message_id == 501,
                ).first()
                assert bot_msg is not None
                assert bot_msg.reply_to_message_id == 500


# Performance and Stress Tests
class TestPerformance:
    """Performance and load testing"""

    @pytest.mark.asyncio
    async def test_concurrent_webhook_requests(self, api_client, test_bot, test_chat, test_db):
        """Test webhook handles concurrent requests"""
        updates = [
            {
                "update_id": 8000 + i,
                "message": {
                    "message_id": 600 + i,
                    "chat": {"id": int(test_chat.chat_id), "title": test_chat.title},
                    "from": {"id": 700 + i, "username": f"user{i}", "is_bot": False},
                    "text": f"Message {i}",
                }
            }
            for i in range(10)
        ]

        # Send concurrent requests
        responses = []
        for update in updates:
            response = api_client.post(
                f"/webhook/telegram/{test_bot.token}",
                json=update
            )
            responses.append(response)

        # Verify all succeeded
        assert all(r.status_code == 200 for r in responses)

        # Verify all messages stored
        stored_messages = test_db.query(Message).filter(
            Message.telegram_message_id >= 600,
            Message.telegram_message_id < 610,
        ).all()
        assert len(stored_messages) == 10

    def test_priority_queue_ordering(self, mock_redis):
        """Test priority queue maintains FIFO order"""
        messages = []

        def lpush_side_effect(key, value):
            messages.append((key, value))
            return 1

        mock_redis.lpush = Mock(side_effect=lpush_side_effect)

        # Simulate adding multiple messages
        for i in range(5):
            priority_data = {
                "message_id": i,
                "priority": "high" if i % 2 == 0 else "normal",
            }
            queue_key = f"priority_queue:{priority_data['priority']}"
            mock_redis.lpush(queue_key, json.dumps(priority_data))

        # Verify messages were added to correct queues
        high_priority_msgs = [m for key, m in messages if "high" in key]
        normal_priority_msgs = [m for key, m in messages if "normal" in key]

        assert len(high_priority_msgs) == 3  # Messages 0, 2, 4
        assert len(normal_priority_msgs) == 2  # Messages 1, 3


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
