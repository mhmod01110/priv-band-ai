"""
MongoDB Client
Manages MongoDB connections and provides helper methods
"""

from motor.motor_asyncio import (
    AsyncIOMotorClient,
    AsyncIOMotorDatabase,
    AsyncIOMotorCollection,
)
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

from app.config import get_settings
from app.logger import app_logger

settings = get_settings()


class MongoDBClient:
    """
    MongoDB client for managing connections and operations
    """

    def __init__(self) -> None:
        self.settings = settings
        self.logger = app_logger

        self.client: Optional[AsyncIOMotorClient] = None
        self.db: Optional[AsyncIOMotorDatabase] = None
        self._connected: bool = False

    # --------------------------------------------------
    # Connection management
    # --------------------------------------------------

    async def connect(self) -> None:
        """Create MongoDB connection"""
        if self._connected:
            return

        try:
            if self.settings.mongodb_username and self.settings.mongodb_password:
                connection_string = (
                    f"mongodb://{self.settings.mongodb_username}:"
                    f"{self.settings.mongodb_password}@"
                    f"{self.settings.mongodb_url.replace('mongodb://', '')}"
                    f"?authSource={self.settings.mongodb_auth_source}"
                )
            else:
                connection_string = self.settings.mongodb_url

            self.client = AsyncIOMotorClient(
                connection_string,
                minPoolSize=self.settings.mongodb_min_pool_size,
                maxPoolSize=self.settings.mongodb_max_pool_size,
                serverSelectionTimeoutMS=self.settings.mongodb_timeout,
                connectTimeoutMS=self.settings.mongodb_timeout,
            )

            self.db = self.client[self.settings.mongodb_database]

            # Hard connectivity test
            await self.client.admin.command("ping")

            self._connected = True
            self.logger.info(
                f"✅ MongoDB connected successfully - Database: {self.settings.mongodb_database}"
            )

            await self._create_indexes()

        except Exception as exc:
            self.logger.error(f"❌ Failed to connect to MongoDB: {exc}")
            self.client = None
            self.db = None
            self._connected = False
            raise

    async def disconnect(self) -> None:
        """Close MongoDB connection"""
        if self.client is not None:
            self.client.close()

        self.client = None
        self.db = None
        self._connected = False
        self.logger.info("MongoDB connection closed")

    async def is_connected(self) -> bool:
        """
        SAFE connection check.
        NEVER boolean-test Motor objects.
        """
        if not self._connected:
            return False

        if self.client is None or self.db is None:
            self._connected = False
            return False

        try:
            await self.client.admin.command("ping")
            return True
        except Exception:
            self._connected = False
            return False

    # --------------------------------------------------
    # Internal helpers
    # --------------------------------------------------

    async def _create_indexes(self) -> None:
        """Create necessary indexes"""
        try:
            if self.db is None:
                return

            idempotency = self.db["idempotency"]
            await idempotency.create_index("key", unique=True)
            await idempotency.create_index("expires_at", expireAfterSeconds=0)

            fallback = self.db["graceful_fallback"]
            await fallback.create_index(
                [("policy_type", 1), ("content_hash", 1)], unique=True
            )
            await fallback.create_index("expires_at", expireAfterSeconds=0)

            quota = self.db["quota"]
            await quota.create_index(
                [("provider", 1), ("period_type", 1), ("period_key", 1)],
                unique=True,
            )
            await quota.create_index("expires_at", expireAfterSeconds=0)

            self.logger.info("✅ MongoDB indexes created successfully")

        except Exception as exc:
            self.logger.warning(f"⚠️ Failed to create indexes: {exc}")

    # --------------------------------------------------
    # Public helpers
    # --------------------------------------------------

    def get_collection(self, name: str) -> AsyncIOMotorCollection:
        """Get collection safely"""
        if self.db is None:
            raise RuntimeError("MongoDB not connected")
        return self.db[name]

    async def set_with_ttl(
        self,
        collection_name: str,
        key: str,
        value: Any,
        ttl_seconds: int,
        **extra_fields,
    ) -> bool:
        try:
            collection = self.get_collection(collection_name)
            expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)

            document = {
                "key": key,
                "value": value,
                "expires_at": expires_at,
                "created_at": datetime.utcnow(),
                **extra_fields,
            }

            await collection.update_one(
                {"key": key},
                {"$set": document},
                upsert=True,
            )
            return True

        except Exception as exc:
            self.logger.error(f"Error setting value in MongoDB: {exc}")
            return False

    async def get(self, collection_name: str, key: str) -> Optional[Any]:
        try:
            collection = self.get_collection(collection_name)
            document = await collection.find_one(
                {"key": key, "expires_at": {"$gt": datetime.utcnow()}}
            )
            return document.get("value") if document else None

        except Exception as exc:
            self.logger.error(f"Error getting value from MongoDB: {exc}")
            return None

    async def delete(self, collection_name: str, key: str) -> bool:
        try:
            collection = self.get_collection(collection_name)
            result = await collection.delete_one({"key": key})
            return result.deleted_count > 0

        except Exception as exc:
            self.logger.error(f"Error deleting value from MongoDB: {exc}")
            return False

    async def exists(self, collection_name: str, key: str) -> bool:
        try:
            collection = self.get_collection(collection_name)
            count = await collection.count_documents(
                {"key": key, "expires_at": {"$gt": datetime.utcnow()}}
            )
            return count > 0

        except Exception as exc:
            self.logger.error(f"Error checking existence in MongoDB: {exc}")
            return False

    async def count_documents(
        self, collection_name: str, filter_dict: Optional[Dict] = None
    ) -> int:
        try:
            collection = self.get_collection(collection_name)
            return await collection.count_documents(filter_dict or {})
        except Exception as exc:
            self.logger.error(f"Error counting documents in MongoDB: {exc}")
            return 0

    async def find_many(
        self,
        collection_name: str,
        filter_dict: Optional[Dict] = None,
        limit: int = 100,
    ) -> List[Dict]:
        try:
            collection = self.get_collection(collection_name)
            cursor = collection.find(filter_dict or {}).limit(limit)
            return await cursor.to_list(length=limit)

        except Exception as exc:
            self.logger.error(f"Error finding documents in MongoDB: {exc}")
            return []

    async def get_stats(self) -> Dict[str, Any]:
        try:
            if not await self.is_connected():
                return {"connected": False}

            if self.db is None:
                return {"connected": False}

            stats = await self.db.command("dbStats")

            collections = {}
            for name in ["idempotency", "graceful_fallback", "quota"]:
                collections[name] = await self.count_documents(name)

            return {
                "connected": True,
                "database": self.settings.mongodb_database,
                "collections": collections,
                "data_size": stats.get("dataSize", 0),
                "index_size": stats.get("indexSize", 0),
                "total_size": stats.get("storageSize", 0),
            }

        except Exception as exc:
            self.logger.error(f"Error getting MongoDB stats: {exc}")
            return {"connected": False, "error": str(exc)}


# Singleton
mongodb_client = MongoDBClient()
