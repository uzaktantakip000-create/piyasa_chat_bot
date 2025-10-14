"""
Message Queue Module

Priority-based message queue for handling rate-limited Telegram messages.
Uses Redis for distributed queuing with fallback to in-memory queue.

Key Features:
- Priority-based message ordering (high/normal/low)
- Redis-backed persistence
- Retry mechanism for failed messages
- Dead letter queue for permanently failed messages
- Graceful degradation when Redis unavailable
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, List
from enum import IntEnum

import redis

logger = logging.getLogger("message_queue")


class MessagePriority(IntEnum):
    """Message priority levels"""
    LOW = 0
    NORMAL = 1
    HIGH = 2


@dataclass
class QueuedMessage:
    """Queued message with metadata"""
    bot_token: str
    chat_id: str | int
    text: str
    priority: MessagePriority = MessagePriority.NORMAL
    reply_to_message_id: Optional[int] = None
    disable_preview: bool = True
    parse_mode: Optional[str] = None

    # Metadata
    message_id: Optional[int] = None  # Database message ID
    bot_id: Optional[int] = None
    enqueued_at: float = 0.0
    retry_count: int = 0
    max_retries: int = 3
    last_error: Optional[str] = None

    def __post_init__(self):
        if self.enqueued_at == 0.0:
            self.enqueued_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization"""
        d = asdict(self)
        d['priority'] = int(self.priority)
        d['chat_id'] = str(self.chat_id)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> QueuedMessage:
        """Create from dict"""
        data['priority'] = MessagePriority(data['priority'])
        return cls(**data)


class MessageQueue:
    """
    Priority-based message queue with Redis backend.

    Architecture:
    - Three priority levels: high, normal, low
    - Each priority has its own Redis list
    - Messages are JSON-encoded
    - Failed messages go to retry queue
    - Permanently failed messages go to dead letter queue

    Example:
        queue = MessageQueue(redis_client)

        # Enqueue message
        msg = QueuedMessage(
            bot_token="token",
            chat_id=123456,
            text="Hello",
            priority=MessagePriority.HIGH
        )
        queue.enqueue(msg)

        # Dequeue message
        msg = queue.dequeue()
        if msg:
            try:
                send_telegram_message(msg)
                queue.ack(msg)
            except Exception as e:
                queue.nack(msg, str(e))
    """

    def __init__(
        self,
        redis_client: Optional[redis.Redis],
        key_prefix: str = "msg_queue",
    ):
        """
        Initialize message queue.

        Args:
            redis_client: Redis client for distributed queue
            key_prefix: Redis key prefix for queue lists
        """
        self.redis_client = redis_client
        self.key_prefix = key_prefix
        self._fallback_mode = redis_client is None

        if self._fallback_mode:
            logger.warning("MessageQueue initialized without Redis - using in-memory fallback")
            self._local_queues: Dict[str, List[QueuedMessage]] = {
                "high": [],
                "normal": [],
                "low": [],
            }
            self._retry_queue: List[QueuedMessage] = []
            self._dlq: List[QueuedMessage] = []

    def _get_queue_key(self, priority: MessagePriority) -> str:
        """Get Redis key for priority queue"""
        priority_name = {
            MessagePriority.HIGH: "high",
            MessagePriority.NORMAL: "normal",
            MessagePriority.LOW: "low",
        }[priority]
        return f"{self.key_prefix}:{priority_name}"

    def _get_retry_key(self) -> str:
        """Get Redis key for retry queue"""
        return f"{self.key_prefix}:retry"

    def _get_dlq_key(self) -> str:
        """Get Redis key for dead letter queue"""
        return f"{self.key_prefix}:dlq"

    def enqueue(self, message: QueuedMessage) -> bool:
        """
        Add message to queue.

        Args:
            message: Message to enqueue

        Returns:
            True if successful, False otherwise
        """
        if self._fallback_mode:
            return self._enqueue_local(message)
        return self._enqueue_redis(message)

    def _enqueue_redis(self, message: QueuedMessage) -> bool:
        """Enqueue message to Redis"""
        try:
            key = self._get_queue_key(message.priority)
            data = json.dumps(message.to_dict())
            self.redis_client.rpush(key, data)

            logger.debug(
                "Message enqueued: priority=%s, chat=%s, text_len=%d",
                message.priority.name, message.chat_id, len(message.text)
            )
            return True
        except redis.RedisError as e:
            logger.warning("Redis error enqueuing message: %s - falling back to local", e)
            return self._enqueue_local(message)
        except Exception as e:
            logger.exception("Error enqueuing message: %s", e)
            return False

    def _enqueue_local(self, message: QueuedMessage) -> bool:
        """Enqueue message to local memory"""
        try:
            priority_name = {
                MessagePriority.HIGH: "high",
                MessagePriority.NORMAL: "normal",
                MessagePriority.LOW: "low",
            }[message.priority]
            self._local_queues[priority_name].append(message)

            logger.debug(
                "Message enqueued (local): priority=%s, chat=%s",
                message.priority.name, message.chat_id
            )
            return True
        except Exception as e:
            logger.exception("Error enqueuing message (local): %s", e)
            return False

    def dequeue(self, block: bool = False, timeout: float = 1.0) -> Optional[QueuedMessage]:
        """
        Get next message from queue.

        Priority order: high > normal > low > retry

        Args:
            block: If True, block until message available
            timeout: Block timeout in seconds

        Returns:
            Next message or None if queue empty
        """
        if self._fallback_mode:
            return self._dequeue_local(block, timeout)
        return self._dequeue_redis(block, timeout)

    def _dequeue_redis(self, block: bool, timeout: float) -> Optional[QueuedMessage]:
        """Dequeue message from Redis"""
        try:
            # Check retry queue first
            retry_key = self._get_retry_key()

            # Then check priority queues in order
            keys = [
                self._get_queue_key(MessagePriority.HIGH),
                self._get_queue_key(MessagePriority.NORMAL),
                self._get_queue_key(MessagePriority.LOW),
                retry_key,
            ]

            if block:
                # BLPOP with timeout
                result = self.redis_client.blpop(keys, timeout=timeout)
                if not result:
                    return None
                key, data = result
            else:
                # Try each queue in order
                for key in keys:
                    data = self.redis_client.lpop(key)
                    if data:
                        break
                else:
                    return None

            # Decode and parse message
            message_dict = json.loads(data)
            message = QueuedMessage.from_dict(message_dict)

            logger.debug(
                "Message dequeued: priority=%s, chat=%s, retry=%d",
                message.priority.name, message.chat_id, message.retry_count
            )
            return message

        except redis.RedisError as e:
            logger.warning("Redis error dequeuing message: %s - falling back to local", e)
            return self._dequeue_local(block, timeout)
        except Exception as e:
            logger.exception("Error dequeuing message: %s", e)
            return None

    def _dequeue_local(self, block: bool, timeout: float) -> Optional[QueuedMessage]:
        """Dequeue message from local memory"""
        start_time = time.time()

        while True:
            # Check retry queue first
            if self._retry_queue:
                message = self._retry_queue.pop(0)
                logger.debug(
                    "Message dequeued (local): priority=RETRY, chat=%s",
                    message.chat_id
                )
                return message

            # Check priority queues in order
            for priority_name in ["high", "normal", "low"]:
                queue = self._local_queues[priority_name]
                if queue:
                    message = queue.pop(0)
                    logger.debug(
                        "Message dequeued (local): priority=%s, chat=%s",
                        priority_name.upper(), message.chat_id
                    )
                    return message

            # No messages available
            if not block:
                return None

            # Check timeout
            if time.time() - start_time >= timeout:
                return None

            # Sleep briefly before retry
            time.sleep(0.1)

    def ack(self, message: QueuedMessage) -> None:
        """
        Acknowledge successful message delivery.

        Args:
            message: Successfully delivered message
        """
        logger.debug(
            "Message acknowledged: chat=%s, retry=%d",
            message.chat_id, message.retry_count
        )

    def nack(self, message: QueuedMessage, error: str) -> None:
        """
        Negative acknowledge - message delivery failed.

        If retries remain, re-enqueue to retry queue.
        Otherwise, move to dead letter queue.

        Args:
            message: Failed message
            error: Error description
        """
        message.retry_count += 1
        message.last_error = error

        if message.retry_count <= message.max_retries:
            # Re-enqueue to retry queue
            logger.warning(
                "Message delivery failed (retry %d/%d): chat=%s, error=%s",
                message.retry_count, message.max_retries, message.chat_id, error
            )

            if self._fallback_mode:
                self._retry_queue.append(message)
            else:
                try:
                    key = self._get_retry_key()
                    data = json.dumps(message.to_dict())
                    self.redis_client.rpush(key, data)
                except Exception as e:
                    logger.exception("Error re-enqueuing to retry queue: %s", e)
        else:
            # Move to dead letter queue
            logger.error(
                "Message permanently failed (max retries exceeded): chat=%s, error=%s",
                message.chat_id, error
            )

            if self._fallback_mode:
                self._dlq.append(message)
            else:
                try:
                    key = self._get_dlq_key()
                    data = json.dumps(message.to_dict())
                    self.redis_client.rpush(key, data)
                except Exception as e:
                    logger.exception("Error moving to DLQ: %s", e)

    def get_stats(self) -> Dict[str, int]:
        """
        Get queue statistics.

        Returns:
            Dict with queue lengths
        """
        if self._fallback_mode:
            return {
                "high": len(self._local_queues["high"]),
                "normal": len(self._local_queues["normal"]),
                "low": len(self._local_queues["low"]),
                "retry": len(self._retry_queue),
                "dlq": len(self._dlq),
            }

        try:
            return {
                "high": self.redis_client.llen(self._get_queue_key(MessagePriority.HIGH)),
                "normal": self.redis_client.llen(self._get_queue_key(MessagePriority.NORMAL)),
                "low": self.redis_client.llen(self._get_queue_key(MessagePriority.LOW)),
                "retry": self.redis_client.llen(self._get_retry_key()),
                "dlq": self.redis_client.llen(self._get_dlq_key()),
            }
        except redis.RedisError as e:
            logger.warning("Redis error getting stats: %s", e)
            return {
                "high": 0,
                "normal": 0,
                "low": 0,
                "retry": 0,
                "dlq": 0,
            }

    def clear_queue(self, priority: Optional[MessagePriority] = None) -> None:
        """
        Clear queue(s).

        Args:
            priority: Priority queue to clear, or None to clear all
        """
        if self._fallback_mode:
            if priority is None:
                self._local_queues = {"high": [], "normal": [], "low": []}
                self._retry_queue = []
                logger.info("All queues cleared (local)")
            else:
                priority_name = {
                    MessagePriority.HIGH: "high",
                    MessagePriority.NORMAL: "normal",
                    MessagePriority.LOW: "low",
                }[priority]
                self._local_queues[priority_name] = []
                logger.info("Queue cleared (local): priority=%s", priority.name)
        else:
            try:
                if priority is None:
                    keys = [
                        self._get_queue_key(MessagePriority.HIGH),
                        self._get_queue_key(MessagePriority.NORMAL),
                        self._get_queue_key(MessagePriority.LOW),
                        self._get_retry_key(),
                    ]
                    for key in keys:
                        self.redis_client.delete(key)
                    logger.info("All queues cleared")
                else:
                    key = self._get_queue_key(priority)
                    self.redis_client.delete(key)
                    logger.info("Queue cleared: priority=%s", priority.name)
            except redis.RedisError as e:
                logger.warning("Redis error clearing queue: %s", e)

    def get_dlq_messages(self, limit: int = 100) -> List[QueuedMessage]:
        """
        Get messages from dead letter queue.

        Args:
            limit: Maximum number of messages to retrieve

        Returns:
            List of failed messages
        """
        if self._fallback_mode:
            return self._dlq[:limit]

        try:
            key = self._get_dlq_key()
            messages = []

            # Get messages without removing them
            items = self.redis_client.lrange(key, 0, limit - 1)
            for item in items:
                try:
                    message_dict = json.loads(item)
                    message = QueuedMessage.from_dict(message_dict)
                    messages.append(message)
                except Exception as e:
                    logger.warning("Error parsing DLQ message: %s", e)

            return messages
        except redis.RedisError as e:
            logger.warning("Redis error getting DLQ messages: %s", e)
            return []
