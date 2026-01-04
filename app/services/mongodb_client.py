"""
MongoDB Client
Manages MongoDB connections and provides helper methods
"""
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from app.config import get_settings
from app.logger import app_logger

settings = get_settings()


class MongoDBClient:
    """
    MongoDB client for managing connections and operations
    """
    
    def __init__(self):
        self.settings = settings
        self.logger = app_logger
        self.client: Optional[AsyncIOMotorClient] = None
        self.db: Optional[AsyncIOMotorDatabase] = None
        self._connected = False
    
    async def connect(self):
        """Create MongoDB connection"""
        if self._connected:
            return
        
        try:
            # Build connection string
            if self.settings.mongodb_username and self.settings.mongodb_password:
                connection_string = (
                    f"mongodb://{self.settings.mongodb_username}:"
                    f"{self.settings.mongodb_password}@"
                    f"{self.settings.mongodb_url.replace('mongodb://', '')}"
                    f"?authSource={self.settings.mongodb_auth_source}"
                )
            else:
                connection_string = self.settings.mongodb_url
            
            # Create client
            self.client = AsyncIOMotorClient(
                connection_string,
                minPoolSize=self.settings.mongodb_min_pool_size,
                maxPoolSize=self.settings.mongodb_max_pool_size,
                serverSelectionTimeoutMS=self.settings.mongodb_timeout,
                connectTimeoutMS=self.settings.mongodb_timeout,
            )
            
            # Get database
            self.db = self.client[self.settings.mongodb_database]
            
            # Test connection
            await self.client.admin.command('ping')
            
            self._connected = True
            self.logger.info(f"✅ MongoDB connected successfully - Database: {self.settings.mongodb_database}")
            
            # Create indexes
            await self._create_indexes()
            
        except Exception as e:
            self.logger.error(f"❌ Failed to connect to MongoDB: {str(e)}")
            self.client = None
            self.db = None
            self._connected = False
            raise
    
    async def disconnect(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            self._connected = False
            self.logger.info("MongoDB connection closed")
    
    async def _create_indexes(self):
        """Create necessary indexes for collections"""
        try:
            # Idempotency collection indexes
            idempotency_collection = self.db['idempotency']
            await idempotency_collection.create_index("key", unique=True)
            await idempotency_collection.create_index("expires_at", expireAfterSeconds=0)
            
            # Graceful degradation collection indexes
            fallback_collection = self.db['graceful_fallback']
            await fallback_collection.create_index([("policy_type", 1), ("content_hash", 1)], unique=True)
            await fallback_collection.create_index("expires_at", expireAfterSeconds=0)
            
            # Quota collection indexes
            quota_collection = self.db['quota']
            await quota_collection.create_index([("provider", 1), ("period_type", 1), ("period_key", 1)], unique=True)
            await quota_collection.create_index("expires_at", expireAfterSeconds=0)
            
            self.logger.info("✅ MongoDB indexes created successfully")
            
        except Exception as e:
            self.logger.warning(f"⚠️ Failed to create indexes: {str(e)}")
    
    def get_collection(self, name: str) -> AsyncIOMotorCollection:
        """Get a collection by name"""
        if not self.db:
            raise Exception("MongoDB not connected")
        return self.db[name]
    
    async def is_connected(self) -> bool:
        """Check if MongoDB is connected"""
        if not self._connected or not self.client:
            return False
        
        try:
            await self.client.admin.command('ping')
            return True
        except:
            self._connected = False
            return False
    
    async def set_with_ttl(
        self,
        collection_name: str,
        key: str,
        value: Any,
        ttl_seconds: int,
        **extra_fields
    ) -> bool:
        """
        Set a value with TTL (Time To Live)
        
        Args:
            collection_name: Collection name
            key: Document key
            value: Value to store
            ttl_seconds: TTL in seconds
            **extra_fields: Additional fields to store
        """
        try:
            collection = self.get_collection(collection_name)
            
            expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
            
            document = {
                "key": key,
                "value": value,
                "expires_at": expires_at,
                "created_at": datetime.utcnow(),
                **extra_fields
            }
            
            await collection.update_one(
                {"key": key},
                {"$set": document},
                upsert=True
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error setting value in MongoDB: {str(e)}")
            return False
    
    async def get(self, collection_name: str, key: str) -> Optional[Any]:
        """
        Get a value by key
        
        Args:
            collection_name: Collection name
            key: Document key
        
        Returns:
            Value or None if not found or expired
        """
        try:
            collection = self.get_collection(collection_name)
            
            document = await collection.find_one({
                "key": key,
                "expires_at": {"$gt": datetime.utcnow()}
            })
            
            if document:
                return document.get("value")
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting value from MongoDB: {str(e)}")
            return None
    
    async def delete(self, collection_name: str, key: str) -> bool:
        """
        Delete a document by key
        
        Args:
            collection_name: Collection name
            key: Document key
        """
        try:
            collection = self.get_collection(collection_name)
            result = await collection.delete_one({"key": key})
            return result.deleted_count > 0
            
        except Exception as e:
            self.logger.error(f"Error deleting value from MongoDB: {str(e)}")
            return False
    
    async def exists(self, collection_name: str, key: str) -> bool:
        """
        Check if a key exists and is not expired
        
        Args:
            collection_name: Collection name
            key: Document key
        """
        try:
            collection = self.get_collection(collection_name)
            
            count = await collection.count_documents({
                "key": key,
                "expires_at": {"$gt": datetime.utcnow()}
            })
            
            return count > 0
            
        except Exception as e:
            self.logger.error(f"Error checking existence in MongoDB: {str(e)}")
            return False
    
    async def count_documents(self, collection_name: str, filter_dict: Dict = None) -> int:
        """
        Count documents in a collection
        
        Args:
            collection_name: Collection name
            filter_dict: Filter dictionary
        """
        try:
            collection = self.get_collection(collection_name)
            filter_dict = filter_dict or {}
            return await collection.count_documents(filter_dict)
            
        except Exception as e:
            self.logger.error(f"Error counting documents in MongoDB: {str(e)}")
            return 0
    
    async def find_many(
        self,
        collection_name: str,
        filter_dict: Dict = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        Find multiple documents
        
        Args:
            collection_name: Collection name
            filter_dict: Filter dictionary
            limit: Maximum number of documents to return
        """
        try:
            collection = self.get_collection(collection_name)
            filter_dict = filter_dict or {}
            
            cursor = collection.find(filter_dict).limit(limit)
            documents = await cursor.to_list(length=limit)
            
            return documents
            
        except Exception as e:
            self.logger.error(f"Error finding documents in MongoDB: {str(e)}")
            return []
    
    async def get_stats(self) -> Dict[str, Any]:
        """
        Get MongoDB statistics
        """
        try:
            if not self.is_connected():
                return {"connected": False}
            
            # Get database stats
            stats = await self.db.command("dbStats")
            
            # Get collection counts
            collections = {}
            for collection_name in ['idempotency', 'graceful_fallback', 'quota']:
                count = await self.count_documents(collection_name)
                collections[collection_name] = count
            
            return {
                "connected": True,
                "database": self.settings.mongodb_database,
                "collections": collections,
                "data_size": stats.get("dataSize", 0),
                "index_size": stats.get("indexSize", 0),
                "total_size": stats.get("storageSize", 0)
            }
            
        except Exception as e:
            self.logger.error(f"Error getting MongoDB stats: {str(e)}")
            return {"connected": False, "error": str(e)}


# Singleton instance
mongodb_client = MongoDBClient()