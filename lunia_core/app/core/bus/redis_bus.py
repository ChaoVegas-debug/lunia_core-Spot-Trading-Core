"""Redis-backed pub/sub event bus with graceful degradation."""
from __future__ import annotations

import json
import logging
import os
import threading
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable, DefaultDict, Dict, List, Optional

try:  # pragma: no cover - optional dependency
    import redis  # type: ignore
except Exception:  # pragma: no cover - redis optional
    redis = None  # type: ignore

logger = logging.getLogger(__name__)


MessageHandler = Callable[[Dict[str, Any]], None]


@dataclass
class RedisBusConfig:
    """Configuration for the Redis bus."""

    url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    enabled: bool = os.getenv("ENABLE_REDIS", "false").lower() == "true"


class RedisBus:
    """Simple Redis-backed bus with in-memory fallback."""

    def __init__(self, config: RedisBusConfig | None = None) -> None:
        self.config = config or RedisBusConfig()
        self._local_subscribers: DefaultDict[str, List[MessageHandler]] = defaultdict(list)
        self._redis: Optional["redis.Redis"] = None
        self._pubsubs: List["redis.client.PubSub"] = []  # type: ignore[attr-defined]
        self.enabled = False
        self._connect()

    # Connection management -------------------------------------------------
    def _connect(self) -> None:
        if not self.config.enabled:
            logger.info("Redis bus disabled via configuration; using in-memory mode")
            return
        if redis is None:
            logger.warning("redis-py not installed; falling back to in-memory bus")
            return
        try:
            self._redis = redis.from_url(self.config.url, decode_responses=True, socket_timeout=5)
            # simple ping to verify connectivity
            self._redis.ping()
            self.enabled = True
            logger.info("Redis bus connected to %s", self.config.url)
        except Exception as exc:  # pragma: no cover - network/redis errors
            logger.warning("Redis connection failed (%s); using in-memory mode", exc)
            self._redis = None
            self.enabled = False

    # API -------------------------------------------------------------------
    def publish(self, channel: str, message: Dict[str, Any]) -> None:
        """Publish message to channel. Falls back to in-memory dispatch."""
        logger.debug("Publishing to %s: %s", channel, message)
        if self.enabled and self._redis is not None:
            try:
                payload = json.dumps(message)
                self._redis.publish(channel, payload)
                logger.info("Published message to Redis channel %s", channel)
            except Exception as exc:  # pragma: no cover - runtime redis failures
                logger.warning("Redis publish failed (%s); using in-memory handlers", exc)
                self.enabled = False
                self._dispatch_local(channel, message)
        else:
            self._dispatch_local(channel, message)

    def _dispatch_local(self, channel: str, message: Dict[str, Any]) -> None:
        handlers = list(self._local_subscribers.get(channel, []))
        if not handlers:
            logger.debug("No local subscribers for channel %s", channel)
            return
        for handler in handlers:
            try:
                handler(message)
            except Exception as exc:  # pragma: no cover - handler errors
                logger.error("Local handler error on channel %s: %s", channel, exc)

    def subscribe(self, channel: str, handler: MessageHandler) -> None:
        """Subscribe handler to channel. Works offline."""
        self._local_subscribers[channel].append(handler)
        if not self.enabled or self._redis is None:
            logger.info("Registered in-memory handler for channel %s", channel)
            return

        try:
            pubsub = self._redis.pubsub(ignore_subscribe_messages=True)
            pubsub.subscribe(channel)

            def listener() -> None:
                logger.info("Redis subscriber started for channel %s", channel)
                for message in pubsub.listen():
                    if message.get("type") != "message":
                        continue
                    data = message.get("data")
                    if not isinstance(data, str):
                        continue
                    try:
                        payload = json.loads(data)
                    except json.JSONDecodeError:
                        logger.warning("Invalid JSON on channel %s: %s", channel, data)
                        continue
                    handler(payload)

            thread = threading.Thread(target=listener, name=f"redis-subscriber-{channel}", daemon=True)
            thread.start()
            self._pubsubs.append(pubsub)
        except Exception as exc:  # pragma: no cover - runtime redis failures
            logger.warning("Redis subscribe failed (%s); reverting to in-memory", exc)
            self.enabled = False


_bus: Optional[RedisBus] = None


def get_bus() -> RedisBus:
    global _bus
    if _bus is None:
        _bus = RedisBus()
    return _bus
