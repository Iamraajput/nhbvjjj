# Thunder/utils/database.py

import datetime
from typing import Optional, Dict, Any
from pymongo import AsyncMongoClient
from pymongo.asynchronous.collection import AsyncCollection
from Thunder.vars import Var
from Thunder.utils.logger import logger

class Database:
    def __init__(self, uri: str, database_name: str, *args, **kwargs):
        self._client = AsyncMongoClient(uri, *args, **kwargs)
        self.db = self._client[database_name]
        self.col: AsyncCollection = self.db.users
        self.banned_users_col: AsyncCollection = self.db.banned_users
        self.banned_channels_col: AsyncCollection = self.db.banned_channels
        self.token_col: AsyncCollection = self.db.tokens
        self.authorized_users_col: AsyncCollection = self.db.authorized_users
        self.restart_message_col: AsyncCollection = self.db.restart_message
        self.topics_col: AsyncCollection = self.db.topics
        self.topic_images_col: AsyncCollection = self.db.topic_images

    async def ensure_indexes(self):
        try:
            await self.banned_users_col.create_index("user_id", unique=True)
            await self.banned_channels_col.create_index("channel_id", unique=True)
            await self.token_col.create_index("token", unique=True)
            await self.authorized_users_col.create_index("user_id", unique=True)
            await self.col.create_index("id", unique=True)
            await self.token_col.create_index("expires_at", expireAfterSeconds=0)
            await self.token_col.create_index("activated")
            await self.restart_message_col.create_index("message_id", unique=True)
            await self.restart_message_col.create_index("timestamp", expireAfterSeconds=3600)
            await self.topics_col.create_index("topic_id", unique=True)
            await self.topics_col.create_index("group_id")
            await self.topics_col.create_index("created_at")
            await self.topic_images_col.create_index("topic_id")
            await self.topic_images_col.create_index("group_id")

            logger.debug("Database indexes ensured.")
        except Exception as e:
            logger.error(f"Error in ensure_indexes: {e}", exc_info=True)
            raise

    def new_user(self, user_id: int) -> dict:
        try:
            return {
                'id': user_id,
                'join_date': datetime.datetime.utcnow()
            }
        except Exception as e:
            logger.error(f"Error in new_user for user {user_id}: {e}", exc_info=True)
            raise

    async def add_user(self, user_id: int):
        try:
            if not await self.is_user_exist(user_id):
                await self.col.insert_one(self.new_user(user_id))
                logger.debug(f"Added new user {user_id} to database.")
        except Exception as e:
            logger.error(f"Error in add_user for user {user_id}: {e}", exc_info=True)
            raise


    async def is_user_exist(self, user_id: int) -> bool:
        try:
            user = await self.col.find_one({'id': user_id}, {'_id': 1})
            return bool(user)
        except Exception as e:
            logger.error(f"Error in is_user_exist for user {user_id}: {e}", exc_info=True)
            raise

    async def total_users_count(self) -> int:
        try:
            return await self.col.count_documents({})
        except Exception as e:
            logger.error(f"Error in total_users_count: {e}", exc_info=True)
            return 0

    async def get_authorized_users_count(self) -> int:
        try:
            return await self.authorized_users_col.count_documents({})
        except Exception as e:
            logger.error(f"Error in get_authorized_users_count: {e}", exc_info=True)
            return 0

    async def get_regular_users_count(self) -> int:
        try:
            auth_ids = await self.authorized_users_col.distinct("user_id")
            return await self.col.count_documents({"id": {"$nin": auth_ids}})
        except Exception as e:
            logger.error(f"Error in get_regular_users_count: {e}", exc_info=True)
            return 0

    async def get_all_users(self):
        try:
            return self.col.find({})
        except Exception as e:
            logger.error(f"Error in get_all_users: {e}", exc_info=True)
            return self.col.find({"_id": {"$exists": False}})

    async def get_authorized_users_cursor(self):
        try:
            return self.authorized_users_col.find({})
        except Exception as e:
            logger.error(f"Error in get_authorized_users_cursor: {e}", exc_info=True)
            return self.authorized_users_col.find({"_id": {"$exists": False}})

    async def get_regular_users_cursor(self):
        try:
            auth_ids = await self.authorized_users_col.distinct("user_id")
            return self.col.find({"id": {"$nin": auth_ids}})
        except Exception as e:
            logger.error(f"Error in get_regular_users_cursor: {e}", exc_info=True)
            return self.col.find({"_id": {"$exists": False}})

    async def delete_user(self, user_id: int):
        try:
            await self.col.delete_one({'id': user_id})
            logger.debug(f"Deleted user {user_id}.")
        except Exception as e:
            logger.error(f"Error in delete_user for user {user_id}: {e}", exc_info=True)
            raise


    async def add_banned_user(
        self, user_id: int, banned_by: Optional[int] = None,
        reason: Optional[str] = None
    ):
        try:
            ban_data = {
                "user_id": user_id,
                "banned_at": datetime.datetime.utcnow(),
                "banned_by": banned_by,
                "reason": reason
            }
            await self.banned_users_col.update_one(
                {"user_id": user_id},
                {"$set": ban_data},
                upsert=True
            )
            logger.debug(f"Added/Updated banned user {user_id}. Reason: {reason}")
        except Exception as e:
            logger.error(f"Error in add_banned_user for user {user_id}: {e}", exc_info=True)
            raise

    async def remove_banned_user(self, user_id: int) -> bool:
        try:
            result = await self.banned_users_col.delete_one({"user_id": user_id})
            if result.deleted_count > 0:
                logger.debug(f"Removed banned user {user_id}.")
                return True
            return False
        except Exception as e:
            logger.error(f"Error in remove_banned_user for user {user_id}: {e}", exc_info=True)
            return False

    async def is_user_banned(self, user_id: int) -> Optional[Dict[str, Any]]:
        try:
            return await self.banned_users_col.find_one({"user_id": user_id})
        except Exception as e:
            logger.error(f"Error in is_user_banned for user {user_id}: {e}", exc_info=True)
            return None

    async def add_banned_channel(
        self, channel_id: int, banned_by: Optional[int] = None,
        reason: Optional[str] = None
    ):
        try:
            ban_data = {
                "channel_id": channel_id,
                "banned_at": datetime.datetime.utcnow(),
                "banned_by": banned_by,
                "reason": reason
            }
            await self.banned_channels_col.update_one(
                {"channel_id": channel_id},
                {"$set": ban_data},
                upsert=True
            )
            logger.debug(f"Added/Updated banned channel {channel_id}. Reason: {reason}")
        except Exception as e:
            logger.error(f"Error in add_banned_channel for channel {channel_id}: {e}", exc_info=True)
            raise

    async def remove_banned_channel(self, channel_id: int) -> bool:
        try:
            result = await self.banned_channels_col.delete_one({"channel_id": channel_id})
            if result.deleted_count > 0:
                logger.debug(f"Removed banned channel {channel_id}.")
                return True
            return False
        except Exception as e:
            logger.error(f"Error in remove_banned_channel for channel {channel_id}: {e}", exc_info=True)
            return False

    async def is_channel_banned(self, channel_id: int) -> Optional[Dict[str, Any]]:
        try:
            return await self.banned_channels_col.find_one({"channel_id": channel_id})
        except Exception as e:
            logger.error(f"Error in is_channel_banned for channel {channel_id}: {e}", exc_info=True)
            return None

    async def save_main_token(self, user_id: int, token_value: str, expires_at: datetime.datetime, created_at: datetime.datetime, activated: bool) -> None:
        try:
            await self.token_col.update_one(
                {"user_id": user_id, "token": token_value},
                {"$set": {
                    "expires_at": expires_at,
                    "created_at": created_at,
                    "activated": activated
                    }
                },
                upsert=True
            )
            logger.debug(f"Saved main token {token_value} for user {user_id} with activated status {activated}.")
        except Exception as e:
            logger.error(f"Error saving main token for user {user_id}: {e}", exc_info=True)
            raise


    async def add_restart_message(self, message_id: int, chat_id: int) -> None:
        try:
            await self.restart_message_col.insert_one({
                "message_id": message_id,
                "chat_id": chat_id,
                "timestamp": datetime.datetime.utcnow()
            })
            logger.debug(f"Added restart message {message_id} for chat {chat_id}.")
        except Exception as e:
            logger.error(f"Error adding restart message {message_id}: {e}", exc_info=True)

    async def get_restart_message(self) -> Optional[Dict[str, Any]]:
        try:
            return await self.restart_message_col.find_one(sort=[("timestamp", -1)])
        except Exception as e:
            logger.error(f"Error getting restart message: {e}", exc_info=True)
            return None

    async def delete_restart_message(self, message_id: int) -> None:
        try:
            await self.restart_message_col.delete_one({"message_id": message_id})
            logger.debug(f"Deleted restart message {message_id}.")
        except Exception as e:
            logger.error(f"Error deleting restart message {message_id}: {e}", exc_info=True)

    async def is_user_authorized(self, user_id: int) -> bool:
        try:
            user = await self.authorized_users_col.find_one({'user_id': user_id}, {'_id': 1})
            return bool(user)
        except Exception as e:
            logger.error(f"Error in is_user_authorized for user {user_id}: {e}", exc_info=True)
            return False

    async def add_topic_video(self, topic_id: int, topic_name: str, group_id: int,
                              video_message_id: int, created_at: datetime.datetime,
                              bin_message_id: int = None) -> None:
        try:
            update_data = {
                "topic_name": topic_name,
                "group_id": group_id,
                "video_message_id": video_message_id,
                "updated_at": datetime.datetime.utcnow()
            }
            if bin_message_id:
                update_data["bin_message_id"] = bin_message_id
            
            await self.topics_col.update_one(
                {"topic_id": topic_id},
                {"$set": update_data,
                 "$setOnInsert": {"created_at": created_at}},
                upsert=True
            )
            logger.debug(f"Added/Updated topic video: topic_id={topic_id}, name={topic_name}, bin_msg={bin_message_id}")
        except Exception as e:
            logger.error(f"Error in add_topic_video for topic {topic_id}: {e}", exc_info=True)
            raise

    async def add_topic_image(self, topic_id: int, group_id: int, image_message_id: int) -> None:
        try:
            await self.topic_images_col.update_one(
                {"topic_id": topic_id, "image_message_id": image_message_id},
                {"$set": {
                    "group_id": group_id,
                    "added_at": datetime.datetime.utcnow()
                }},
                upsert=True
            )
            logger.debug(f"Added topic image: topic_id={topic_id}, msg_id={image_message_id}")
        except Exception as e:
            logger.error(f"Error in add_topic_image for topic {topic_id}: {e}", exc_info=True)
            raise

    async def update_topic_title(self, topic_id: int, title: str, group_id: int = None) -> None:
        """Update the title/name of a topic. Creates document if not exists."""
        try:
            await self.topics_col.update_one(
                {"topic_id": topic_id},
                {"$set": {
                    "topic_name": title,
                    "updated_at": datetime.datetime.utcnow()
                },
                "$setOnInsert": {
                    "topic_id": topic_id,
                    "group_id": group_id,
                    "created_at": datetime.datetime.utcnow()
                }},
                upsert=True
            )
            logger.debug(f"Updated topic title: topic_id={topic_id}, title={title}")
        except Exception as e:
            logger.error(f"Error in update_topic_title for topic {topic_id}: {e}", exc_info=True)
            raise

    async def get_topic_video(self, topic_id: int) -> Optional[dict]:
        """Get topic video information by topic_id."""
        try:
            result = await self.topics_col.find_one({"topic_id": topic_id})
            return result
        except Exception as e:
            logger.error(f"Error in get_topic_video for topic {topic_id}: {e}", exc_info=True)
            return None

    async def update_topic_bin_message_id(self, topic_id: int, bin_message_id: int) -> None:
        """Update the BIN_CHANNEL message ID for a topic."""
        try:
            await self.topics_col.update_one(
                {"topic_id": topic_id},
                {"$set": {
                    "bin_message_id": bin_message_id,
                    "updated_at": datetime.datetime.utcnow()
                }}
            )
            logger.info(f"Updated topic {topic_id} with bin_message_id: {bin_message_id}")
        except Exception as e:
            logger.error(f"Error updating bin_message_id for topic {topic_id}: {e}", exc_info=True)
            raise

    async def get_random_topic_thumbnail(self, topic_id: int) -> Optional[int]:
        try:
            # Use find() with sample instead of aggregate for better compatibility
            cursor = self.topic_images_col.find({"topic_id": topic_id})
            results = await cursor.to_list(length=None)
            if results:
                import random
                return random.choice(results).get("image_message_id")
            return None
        except Exception as e:
            logger.error(f"Error in get_random_topic_thumbnail for topic {topic_id}: {e}", exc_info=True)
            return None

    async def get_all_topic_videos(self, group_id: Optional[int] = None) -> list:
        try:
            match_stage = {"group_id": group_id} if group_id else {}
            cursor = self.topics_col.find(match_stage).sort("created_at", -1)
            return await cursor.to_list(length=None)
        except Exception as e:
            logger.error(f"Error in get_all_topic_videos: {e}", exc_info=True)
            return []

    async def get_topic_video(self, topic_id: int) -> Optional[Dict[str, Any]]:
        try:
            return await self.topics_col.find_one({"topic_id": topic_id})
        except Exception as e:
            logger.error(f"Error in get_topic_video for topic {topic_id}: {e}", exc_info=True)
            return None

    async def delete_topic_video(self, topic_id: int) -> bool:
        try:
            result = await self.topics_col.delete_one({"topic_id": topic_id})
            await self.topic_images_col.delete_many({"topic_id": topic_id})
            if result.deleted_count > 0:
                logger.debug(f"Deleted topic video: topic_id={topic_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error in delete_topic_video for topic {topic_id}: {e}", exc_info=True)
            return False

    async def close(self):
        if self._client:
            await self._client.close()

db = Database(Var.DATABASE_URL, Var.NAME)
