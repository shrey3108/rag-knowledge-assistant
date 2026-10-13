import hashlib
import json
import logging
import time
from typing import Optional, Dict, Any

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


class CacheManager:
    """Redis-backed cache with automatic graceful fallback to in-memory TTL caching."""

    _instance: Optional["CacheManager"] = None

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.client = None
        self._memory_cache: Dict[str, Dict[str, Any]] = {}
        self._redis_available = False

        if self.settings.redis_enabled:
            self._init_redis()

    @classmethod
    def get_instance(cls, settings: Optional[Settings] = None) -> "CacheManager":
        if cls._instance is None:
            cls._instance = cls(settings=settings)
        return cls._instance

    def _init_redis(self):
        try:
            import redis

            self.client = redis.Redis(
                host=self.settings.redis_host,
                port=self.settings.redis_port,
                db=self.settings.redis_db,
                password=self.settings.redis_password,
                decode_responses=True,
                socket_timeout=1.5,
                socket_connect_timeout=1.5,
            )
            # Test ping
            self.client.ping()
            self._redis_available = True
            logger.info(f"Connected to Redis at {self.settings.redis_host}:{self.settings.redis_port}")
        except Exception as e:
            self._redis_available = False
            self.client = None
            logger.info(
                f"Redis server not accessible ({e}). Falling back to internal in-memory cache."
            )

    def _hash_key(self, question: str) -> str:
        """Create a normalized deterministic cache key."""
        normalized = question.strip().lower().rstrip("?!.")
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
        return f"rag:query:{digest}"

    def get(self, question: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached query response."""
        key = self._hash_key(question)

        # 1. Try Redis
        if self._redis_available and self.client:
            try:
                raw = self.client.get(key)
                if raw:
                    logger.info(f"Cache HIT in Redis for query: '{question[:40]}...'")
                    data = json.loads(raw)
                    data["cached"] = True
                    return data
            except Exception as e:
                logger.warning(f"Redis get failed: {e}. Falling back to memory cache.")
                self._redis_available = False

        # 2. Try In-memory fallback
        item = self._memory_cache.get(key)
        if item:
            if time.time() < item["expires_at"]:
                logger.info(f"Cache HIT in memory for query: '{question[:40]}...'")
                data = json.loads(json.dumps(item["data"]))
                data["cached"] = True
                return data
            else:
                del self._memory_cache[key]

        return None

    def set(self, question: str, data: Dict[str, Any], ttl: Optional[int] = None):
        """Store query response in cache with TTL."""
        key = self._hash_key(question)
        expire_seconds = ttl if ttl is not None else self.settings.redis_ttl_seconds

        # Store in Redis
        if self._redis_available and self.client:
            try:
                payload = json.dumps(data)
                self.client.setex(key, expire_seconds, payload)
                return
            except Exception as e:
                logger.warning(f"Redis set failed: {e}. Storing in memory cache.")
                self._redis_available = False

        # Store in In-Memory fallback
        self._memory_cache[key] = {
            "data": data,
            "expires_at": time.time() + expire_seconds,
        }

    def invalidate_all(self):
        """Invalidate all cached answers (e.g. after uploading or deleting documents)."""
        logger.info("Invalidating query cache across Redis and in-memory stores.")
        if self._redis_available and self.client:
            try:
                keys = self.client.keys("rag:query:*")
                if keys:
                    self.client.delete(*keys)
            except Exception as e:
                logger.warning(f"Redis invalidate failed: {e}")

        self._memory_cache.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Return cache health and statistics."""
        return {
            "redis_enabled": self.settings.redis_enabled,
            "redis_connected": self._redis_available,
            "redis_host": self.settings.redis_host,
            "redis_port": self.settings.redis_port,
            "in_memory_keys": len(self._memory_cache),
        }
