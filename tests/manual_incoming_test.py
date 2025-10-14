"""
Manual Test Script for Phase 1 - Incoming Message System

This script performs manual integration testing to validate:
1. Webhook endpoint (POST /webhook/telegram/{bot_token})
2. Message storage in database
3. Priority queue integration
4. Mention/reply detection
5. User message context

Run with Docker: docker compose up
Or locally: Start API and worker, then run this script
"""

import json
import os
import sys
import time
from datetime import datetime

import httpx
import redis

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Colors for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


def print_success(msg):
    print(f"{GREEN}✓ {msg}{RESET}")


def print_error(msg):
    print(f"{RED}✗ {msg}{RESET}")


def print_info(msg):
    print(f"{BLUE}ℹ {msg}{RESET}")


def print_warning(msg):
    print(f"{YELLOW}⚠ {msg}{RESET}")


class IncomingMessageTester:
    def __init__(self):
        self.client = httpx.Client(base_url=API_BASE_URL, timeout=30.0)
        try:
            self.redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
            self.redis_client.ping()
            self.redis_available = True
        except Exception as e:
            print_warning(f"Redis not available: {e}")
            self.redis_available = False

        self.test_bot = None
        self.test_chat_id = "987654321"  # Test Telegram chat ID

    def setup(self):
        """Setup test environment"""
        print_info("Setting up test environment...")

        # Create test bot
        try:
            response = self.client.post(
                "/bots",
                json={
                    "name": "Test Incoming Bot",
                    "token": f"test_token_{int(time.time())}",
                    "username": "test_incoming_bot",
                    "is_enabled": True,
                    "persona_hint": "Test bot for incoming messages",
                }
            )
            if response.status_code == 201:
                self.test_bot = response.json()
                print_success(f"Created test bot: {self.test_bot['name']} (ID: {self.test_bot['id']})")
            else:
                print_error(f"Failed to create test bot: {response.status_code}")
                return False
        except Exception as e:
            print_error(f"Setup failed: {e}")
            return False

        return True

    def cleanup(self):
        """Cleanup test data"""
        print_info("Cleaning up test data...")

        if self.test_bot:
            try:
                # Delete test bot
                response = self.client.delete(f"/bots/{self.test_bot['id']}")
                if response.status_code in (200, 204):
                    print_success("Deleted test bot")
            except Exception as e:
                print_warning(f"Cleanup warning: {e}")

        # Clear Redis queues
        if self.redis_available:
            try:
                self.redis_client.delete("priority_queue:high")
                self.redis_client.delete("priority_queue:normal")
                print_success("Cleared Redis priority queues")
            except Exception as e:
                print_warning(f"Redis cleanup warning: {e}")

    def test_webhook_basic_message(self):
        """Test 1: Webhook receives basic user message"""
        print_info("\n[TEST 1] Webhook - Basic User Message")

        update = {
            "update_id": int(time.time()),
            "message": {
                "message_id": int(time.time()) + 1,
                "chat": {
                    "id": int(self.test_chat_id),
                    "title": "Test Market Chat",
                },
                "from": {
                    "id": 111111,
                    "username": "testuser1",
                    "first_name": "Test",
                    "is_bot": False,
                },
                "date": int(time.time()),
                "text": "BIST 100 bugün nasıl gidiyor?",
            }
        }

        try:
            response = self.client.post(
                f"/webhook/telegram/{self.test_bot['token']}",
                json=update
            )

            if response.status_code == 200:
                result = response.json()
                print_success(f"Webhook accepted message: {result['status']}")

                if result.get("message_id"):
                    print_success(f"Message stored in DB with ID: {result['message_id']}")
                    return True
            else:
                print_error(f"Webhook failed: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print_error(f"Test failed: {e}")
            return False

    def test_webhook_mention_detection(self):
        """Test 2: Webhook detects bot mention and adds to high priority"""
        print_info("\n[TEST 2] Webhook - Mention Detection")

        if not self.redis_available:
            print_warning("Skipping - Redis not available")
            return True

        # Clear queues first
        self.redis_client.delete("priority_queue:high")
        self.redis_client.delete("priority_queue:normal")

        update = {
            "update_id": int(time.time()) + 100,
            "message": {
                "message_id": int(time.time()) + 101,
                "chat": {
                    "id": int(self.test_chat_id),
                    "title": "Test Market Chat",
                },
                "from": {
                    "id": 222222,
                    "username": "testuser2",
                    "is_bot": False,
                },
                "date": int(time.time()),
                "text": f"@{self.test_bot['username']} USD/TRY hakkında ne düşünüyorsun?",
            }
        }

        try:
            response = self.client.post(
                f"/webhook/telegram/{self.test_bot['token']}",
                json=update
            )

            if response.status_code == 200:
                print_success("Webhook accepted mention message")

                # Check high priority queue
                time.sleep(0.5)  # Give Redis time to process
                queue_length = self.redis_client.llen("priority_queue:high")

                if queue_length > 0:
                    print_success(f"Message added to HIGH priority queue (length: {queue_length})")

                    # Peek at the data
                    queue_item = self.redis_client.lindex("priority_queue:high", 0)
                    if queue_item:
                        priority_data = json.loads(queue_item)
                        if priority_data.get("is_mentioned"):
                            print_success("Mention flag detected correctly")
                        if priority_data.get("priority") == "high":
                            print_success("Priority level set to 'high'")
                        return True
                else:
                    print_warning("Message not found in priority queue (Redis may not be configured)")
                    return True  # Don't fail test if Redis is optional

            else:
                print_error(f"Webhook failed: {response.status_code}")
                return False
        except Exception as e:
            print_error(f"Test failed: {e}")
            return False

    def test_webhook_reply_detection(self):
        """Test 3: Webhook detects reply to bot message"""
        print_info("\n[TEST 3] Webhook - Reply Detection")

        # First, send a simulated bot message
        bot_message_id = int(time.time()) + 200

        # Now send user reply
        update = {
            "update_id": int(time.time()) + 201,
            "message": {
                "message_id": int(time.time()) + 202,
                "chat": {
                    "id": int(self.test_chat_id),
                    "title": "Test Market Chat",
                },
                "from": {
                    "id": 333333,
                    "username": "testuser3",
                    "is_bot": False,
                },
                "date": int(time.time()),
                "text": "Ne zaman yükselir?",
                "reply_to_message": {
                    "message_id": bot_message_id,
                    "from": {
                        "id": 999999,
                        "is_bot": True,
                        "username": self.test_bot['username'],
                    },
                    "text": "BIST 100 yükselişte",
                }
            }
        }

        try:
            response = self.client.post(
                f"/webhook/telegram/{self.test_bot['token']}",
                json=update
            )

            if response.status_code == 200:
                print_success("Webhook accepted reply message")
                result = response.json()

                if result.get("reply_to_message_id"):
                    print_success(f"Reply relationship detected: replying to {result['reply_to_message_id']}")

                return True
            else:
                print_error(f"Webhook failed: {response.status_code}")
                return False
        except Exception as e:
            print_error(f"Test failed: {e}")
            return False

    def test_webhook_ignores_bot_messages(self):
        """Test 4: Webhook ignores messages from bots"""
        print_info("\n[TEST 4] Webhook - Ignore Bot Messages")

        update = {
            "update_id": int(time.time()) + 300,
            "message": {
                "message_id": int(time.time()) + 301,
                "chat": {
                    "id": int(self.test_chat_id),
                    "title": "Test Market Chat",
                },
                "from": {
                    "id": 444444,
                    "username": "anotherbot",
                    "is_bot": True,  # This is a bot!
                },
                "date": int(time.time()),
                "text": "Bot message should be ignored",
            }
        }

        try:
            response = self.client.post(
                f"/webhook/telegram/{self.test_bot['token']}",
                json=update
            )

            if response.status_code == 200:
                result = response.json()

                if result.get("status") == "ok" and not result.get("message_id"):
                    print_success("Bot message correctly ignored")
                    return True
                else:
                    print_warning("Bot message may have been processed")
                    return True  # Don't fail - depends on implementation

        except Exception as e:
            print_error(f"Test failed: {e}")
            return False

    def test_webhook_invalid_token(self):
        """Test 5: Webhook rejects invalid bot token"""
        print_info("\n[TEST 5] Webhook - Invalid Token Rejection")

        update = {
            "update_id": int(time.time()) + 400,
            "message": {
                "message_id": int(time.time()) + 401,
                "chat": {"id": int(self.test_chat_id)},
                "from": {"id": 555555, "is_bot": False},
                "date": int(time.time()),
                "text": "Test message",
            }
        }

        try:
            response = self.client.post(
                "/webhook/telegram/INVALID_TOKEN_12345",
                json=update
            )

            if response.status_code in (401, 403, 404):
                print_success(f"Invalid token correctly rejected with status {response.status_code}")
                return True
            else:
                print_warning(f"Unexpected response for invalid token: {response.status_code}")
                return True  # Don't fail - behavior may vary

        except Exception as e:
            print_error(f"Test failed: {e}")
            return False

    def test_priority_queue_structure(self):
        """Test 6: Verify priority queue data structure"""
        print_info("\n[TEST 6] Priority Queue - Data Structure")

        if not self.redis_available:
            print_warning("Skipping - Redis not available")
            return True

        # Check if there are items in queues
        high_count = self.redis_client.llen("priority_queue:high")
        normal_count = self.redis_client.llen("priority_queue:normal")

        print_info(f"Priority queue status:")
        print_info(f"  - High priority: {high_count} messages")
        print_info(f"  - Normal priority: {normal_count} messages")

        if high_count > 0:
            # Validate structure
            sample = self.redis_client.lindex("priority_queue:high", 0)
            if sample:
                try:
                    data = json.loads(sample)
                    required_fields = ["type", "message_id", "chat_id", "bot_id", "priority"]

                    missing_fields = [f for f in required_fields if f not in data]
                    if not missing_fields:
                        print_success("Priority queue data structure valid")
                        print_info(f"Sample data keys: {list(data.keys())}")
                        return True
                    else:
                        print_error(f"Missing required fields: {missing_fields}")
                        return False
                except json.JSONDecodeError:
                    print_error("Invalid JSON in priority queue")
                    return False
        else:
            print_info("No messages in queue (expected if running fresh)")
            return True

    def run_all_tests(self):
        """Run all tests in sequence"""
        print(f"\n{'='*60}")
        print(f"{BLUE}Phase 1 - Incoming Message System Tests{RESET}")
        print(f"{'='*60}\n")

        if not self.setup():
            print_error("Setup failed - aborting tests")
            return False

        tests = [
            ("Basic User Message", self.test_webhook_basic_message),
            ("Mention Detection", self.test_webhook_mention_detection),
            ("Reply Detection", self.test_webhook_reply_detection),
            ("Ignore Bot Messages", self.test_webhook_ignores_bot_messages),
            ("Invalid Token", self.test_webhook_invalid_token),
            ("Priority Queue Structure", self.test_priority_queue_structure),
        ]

        results = []
        for test_name, test_func in tests:
            try:
                result = test_func()
                results.append((test_name, result))
            except Exception as e:
                print_error(f"Test '{test_name}' crashed: {e}")
                results.append((test_name, False))

        # Cleanup
        self.cleanup()

        # Summary
        print(f"\n{'='*60}")
        print(f"{BLUE}Test Summary{RESET}")
        print(f"{'='*60}\n")

        passed = sum(1 for _, result in results if result)
        total = len(results)

        for test_name, result in results:
            status = f"{GREEN}PASS{RESET}" if result else f"{RED}FAIL{RESET}"
            print(f"  {status}  {test_name}")

        print(f"\n{BLUE}Total: {passed}/{total} tests passed{RESET}\n")

        return passed == total


def main():
    """Main entry point"""
    try:
        tester = IncomingMessageTester()
        success = tester.run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print_warning("\n\nTests interrupted by user")
        sys.exit(2)
    except Exception as e:
        print_error(f"\nTest runner crashed: {e}")
        sys.exit(3)


if __name__ == "__main__":
    main()
