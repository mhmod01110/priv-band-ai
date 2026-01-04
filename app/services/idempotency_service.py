"""
Idempotency Service with MongoDB
Prevents duplicate requests and caches results
"""

import json
import hashlib
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from app.config import get_settings
from app.logger import app_logger
from app.services.mongodb_client import mongodb_client


class IdempotencyService:
    """
    Manages Idempotency Keys using MongoDB.
    Prevents duplicate requests and caches results for a TTL.
    """

    COLLECTION_NAME = "idempotency"

    def __init__(self) -> None:
        self.settings = get_settings()
        self.logger = app_logger
        self.mongodb = mongodb_client

        self.ttl: int = self.settings.idempotency_ttl
        self.enabled: bool = self.settings.idempotency_enable

    # ------------------------------------------------------------------
    # Connection Management
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Connect to MongoDB if idempotency is enabled."""
        if not self.enabled:
            self.logger.info("Idempotency is disabled")
            return

        try:
            await self.mongodb.connect()
            self.logger.info("✅ Idempotency service connected to MongoDB")
        except Exception as exc:
            self.logger.error(f"❌ Failed to connect idempotency service: {exc}")
            raise

    async def disconnect(self) -> None:
        """MongoDB client handles disconnection centrally."""
        return

    async def _is_ready(self) -> bool:
        """
        Safe check before any DB operation.
        Avoids MongoDB truth-value testing.
        """
        if not self.enabled:
            return False

        return await self.mongodb.is_connected()

    # ------------------------------------------------------------------
    # Key Utilities
    # ------------------------------------------------------------------

    def _normalize_key(self, key: str) -> str:
        """Ensure key has idempotency prefix."""
        if key.startswith("idempotency:"):
            return key
        return f"idempotency:{key}"

    def generate_key_from_request(self, request_data: Dict[str, Any]) -> str:
        """
        Generate a deterministic idempotency key from request payload.
        """

        key_data = {
            "shop_name": request_data.get("shop_name", ""),
            "shop_specialization": request_data.get("shop_specialization", ""),
            "policy_type": request_data.get("policy_type", ""),
            "policy_text_hash": hashlib.sha256(
                request_data.get("policy_text", "").encode()
            ).hexdigest(),
        }

        json_str = json.dumps(
            key_data, sort_keys=True, ensure_ascii=False
        )

        key_hash = hashlib.sha256(json_str.encode()).hexdigest()
        return f"idempotency:{key_hash}"

    # ------------------------------------------------------------------
    # Cache Operations
    # ------------------------------------------------------------------

    async def get_cached_result(
        self, idempotency_key: str
    ) -> Optional[Dict[str, Any]]:
        """Retrieve cached result if still valid."""

        if not await self._is_ready():
            return None

        try:
            key = self._normalize_key(idempotency_key)
            collection = self.mongodb.get_collection(self.COLLECTION_NAME)

            document = await collection.find_one(
                {
                    "key": key,
                    "expires_at": {"$gt": datetime.utcnow()},
                }
            )

            if document is None:
                self.logger.debug(f"Cache MISS for key: {key[:20]}...")
                return None

            self.logger.info(f"✅ Cache HIT for key: {key[:20]}...")

            result = document.get("value")

            if isinstance(result, dict):
                result["from_cache"] = True
                created_at = document.get("created_at")
                result["cache_timestamp"] = (
                    created_at.isoformat() if created_at else ""
                )

            return result

        except Exception as exc:
            self.logger.error(f"Error getting cached result: {exc}")
            return None

    async def store_result(
        self,
        idempotency_key: str,
        result: Dict[str, Any],
        ttl_override: Optional[int] = None,
    ) -> bool:
        """Store result with TTL."""

        if not self.enabled:
            self.logger.warning("⚠️ Idempotency is disabled")
            return False

        if not await self.mongodb.is_connected():
            self.logger.warning("⚠️ MongoDB not connected, reconnecting...")
            try:
                await self.mongodb.connect()
            except Exception as exc:
                self.logger.error(f"❌ MongoDB reconnect failed: {exc}")
                return False

        try:
            key = self._normalize_key(idempotency_key)
            ttl = ttl_override or self.ttl

            expires_at = datetime.utcnow() + timedelta(seconds=ttl)

            document = {
                "key": key,
                "value": result.copy(),
                "expires_at": expires_at,
                "created_at": datetime.utcnow(),
                "ttl": ttl,
            }

            collection = self.mongodb.get_collection(self.COLLECTION_NAME)

            await collection.update_one(
                {"key": key},
                {"$set": document},
                upsert=True,
            )

            self.logger.info(
                f"✅ Result cached: {key[:20]}... (TTL={ttl}s)"
            )
            return True

        except Exception as exc:
            self.logger.error(f"❌ Error storing cache: {exc}")
            return False

    # ------------------------------------------------------------------
    # Locking (In-Progress)
    # ------------------------------------------------------------------

    async def check_in_progress(self, idempotency_key: str) -> bool:
        """Check if a request with same key is in progress."""

        if not await self._is_ready():
            return False

        try:
            lock_key = f"{self._normalize_key(idempotency_key)}:lock"
            collection = self.mongodb.get_collection(self.COLLECTION_NAME)

            count = await collection.count_documents(
                {
                    "key": lock_key,
                    "expires_at": {"$gt": datetime.utcnow()},
                }
            )

            return count > 0

        except Exception as exc:
            self.logger.error(f"❌ Error checking lock: {exc}")
            return False

    async def mark_in_progress(
        self, idempotency_key: str, timeout: int = 300
    ) -> bool:
        """Create an in-progress lock."""

        if not await self._is_ready():
            return True

        try:
            lock_key = f"{self._normalize_key(idempotency_key)}:lock"
            collection = self.mongodb.get_collection(self.COLLECTION_NAME)

            existing = await collection.find_one(
                {
                    "key": lock_key,
                    "expires_at": {"$gt": datetime.utcnow()},
                }
            )

            if existing is not None:
                self.logger.warning(
                    f"⚠️ Lock already exists: {lock_key[:30]}..."
                )
                return False

            document = {
                "key": lock_key,
                "value": datetime.utcnow().isoformat(),
                "expires_at": datetime.utcnow()
                + timedelta(seconds=timeout),
                "created_at": datetime.utcnow(),
            }

            await collection.insert_one(document)
            self.logger.debug(f"🔒 Lock acquired: {lock_key[:30]}...")
            return True

        except Exception as exc:
            self.logger.error(f"❌ Error acquiring lock: {exc}")
            return False

    async def clear_in_progress(self, idempotency_key: str) -> None:
        """Remove in-progress lock."""

        if not await self._is_ready():
            return

        try:
            lock_key = f"{self._normalize_key(idempotency_key)}:lock"
            collection = self.mongodb.get_collection(self.COLLECTION_NAME)

            await collection.delete_one({"key": lock_key})
            self.logger.debug(f"🔓 Lock released: {lock_key[:30]}...")

        except Exception as exc:
            self.logger.error(f"❌ Error releasing lock: {exc}")

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    async def delete_cached_result(self, idempotency_key: str) -> bool:
        """Delete cached result manually."""

        if not await self._is_ready():
            return False

        try:
            key = self._normalize_key(idempotency_key)
            collection = self.mongodb.get_collection(self.COLLECTION_NAME)

            result = await collection.delete_one({"key": key})
            return result.deleted_count > 0

        except Exception as exc:
            self.logger.error(f"❌ Error deleting cache: {exc}")
            return False

    async def get_stats(self) -> Dict[str, Any]:
        """Return cache statistics."""

        if not await self._is_ready():
            return {"enabled": False}

        try:
            collection = self.mongodb.get_collection(self.COLLECTION_NAME)

            total = await collection.count_documents({})
            active = await collection.count_documents(
                {"expires_at": {"$gt": datetime.utcnow()}}
            )

            return {
                "enabled": True,
                "connected": True,
                "total_keys": total,
                "active_keys": active,
                "expired_keys": total - active,
            }

        except Exception as exc:
            self.logger.error(f"❌ Error getting stats: {exc}")
            return {
                "enabled": True,
                "connected": False,
                "error": str(exc),
            }


# Singleton instance
idempotency_service = IdempotencyService()
