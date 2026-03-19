# Thunder/bot/plugins/topics.py

import datetime
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait

from Thunder.bot import StreamBot
from Thunder.utils.database import db
from Thunder.utils.logger import logger
from Thunder.vars import Var


def get_topic_name(msg: Message, topic_id: int, chat_id: int) -> str:
    """Get video title from message caption or file name.
    
    NOTE: Telegram bots cannot access forum topic names due to API limitations.
    The only way to set a custom title is to add a caption when sending the video.
    """
    try:
        # Method 1: Use caption as title (RECOMMENDED)
        if msg.caption:
            caption = msg.caption[:50] + "..." if len(msg.caption) > 50 else msg.caption
            logger.info(f"Using caption as title: {caption}")
            return caption
        
        # Method 2: Use video file name
        if msg.video and msg.video.file_name:
            logger.info(f"Using video file_name: {msg.video.file_name}")
            return msg.video.file_name
        
        # Method 3: Use document file name
        if msg.document and msg.document.file_name:
            logger.info(f"Using document file_name: {msg.document.file_name}")
            return msg.document.file_name
            
    except Exception as e:
        logger.debug(f"Could not get title from message: {e}")
    
    # Final fallback - use topic ID
    if topic_id == chat_id:
        return "General"
    return f"Topic {topic_id}"


@StreamBot.on_message(
    filters.chat(Var.GROUP_DATABASE_ID) &
    (filters.video | filters.document)
)
async def topic_video_handler(bot: Client, msg: Message):
    """Handle video/document messages in forum topics."""
    logger.info(f"VIDEO HANDLER TRIGGERED: msg_id={msg.id}, chat_id={msg.chat.id}, video={msg.video is not None}, document={msg.document is not None}")
    
    if not Var.GALLERY_ENABLED:
        logger.debug("Gallery is disabled, skipping")
        return
    if not Var.GROUP_DATABASE_ID:
        logger.debug("GROUP_DATABASE_ID not set, skipping")
        return
    
    try:
        # Extract topic information
        # Use reply_to_message_id if available (for topics), otherwise use chat ID
        topic_id = getattr(msg, 'reply_to_message_id', None) or getattr(msg, 'message_thread_id', None) or msg.chat.id
        logger.info(f"Processing video: topic_id={topic_id}, msg_id={msg.id}")
        if not topic_id:
            logger.debug("Message has no topic ID, skipping")
            return
        
        # Get video title from message (caption or file name)
        topic_name = get_topic_name(msg, topic_id, msg.chat.id)
        
        # Check if it's a video file
        is_video = False
        if msg.video:
            is_video = True
        elif msg.document and msg.document.mime_type:
            is_video = msg.document.mime_type.startswith("video/")
        
        if not is_video:
            logger.debug(f"Message {msg.id} is not a video, skipping")
            return
        
        # Check if a title was already set via text message
        existing_topic = await db.get_topic_video(topic_id)
        logger.info(f"Existing topic data: {existing_topic}")
        if existing_topic and existing_topic.get("topic_name"):
            # If existing title is not a generic one, keep it
            existing_name = existing_topic.get("topic_name")
            logger.info(f"Found existing name: {existing_name}")
            if not existing_name.startswith("Topic ") and existing_name != "General":
                topic_name = existing_name
                logger.info(f"Using existing topic title: {topic_name}")
            else:
                logger.info(f"Existing name is generic, using: {topic_name}")
        else:
            logger.info(f"No existing topic found, using: {topic_name}")
        
        # Forward video to BIN_CHANNEL for streaming
        try:
            forwarded = await msg.forward(Var.BIN_CHANNEL)
            if forwarded:
                logger.info(f"Forwarded video to BIN_CHANNEL: {forwarded.id}")
                # Store the BIN_CHANNEL message ID for streaming
                bin_message_id = forwarded.id
            else:
                bin_message_id = None
                logger.warning("Failed to forward video to BIN_CHANNEL")
        except Exception as e:
            logger.error(f"Error forwarding video: {e}")
            bin_message_id = None
        
        # Store in database with BIN_CHANNEL message ID
        await db.add_topic_video(
            topic_id=topic_id,
            topic_name=topic_name,
            group_id=msg.chat.id,
            video_message_id=msg.id,
            bin_message_id=bin_message_id,
            created_at=datetime.datetime.utcnow()
        )
        
        logger.info(f"Added video from topic '{topic_name}' (ID: {topic_id})")
        
    except FloodWait as e:
        logger.warning(f"FloodWait in topic_video_handler: {e.value}s")
    except Exception as e:
        logger.error(f"Error in topic_video_handler: {e}", exc_info=True)


@StreamBot.on_message(
    filters.chat(Var.GROUP_DATABASE_ID) &
    filters.group &
    filters.photo
)
async def topic_image_handler(bot: Client, msg: Message):
    """Handle image messages in forum topics for thumbnails."""
    if not Var.GALLERY_ENABLED or not Var.GROUP_DATABASE_ID:
        return
    
    try:
        # Extract topic information
        # Use reply_to_message_id if available (for topics), otherwise use chat ID
        topic_id = getattr(msg, 'reply_to_message_id', None) or getattr(msg, 'message_thread_id', None) or msg.chat.id
        if not topic_id:
            logger.debug("Message has no topic ID, skipping")
            return
        
        # Store image as potential thumbnail
        await db.add_topic_image(
            topic_id=topic_id,
            group_id=msg.chat.id,
            image_message_id=msg.id
        )
        
        logger.debug(f"Added image from topic ID: {topic_id}")
        
    except FloodWait as e:
        logger.warning(f"FloodWait in topic_image_handler: {e.value}s")
    except Exception as e:
        logger.error(f"Error in topic_image_handler: {e}", exc_info=True)


@StreamBot.on_message(
    filters.chat(Var.GROUP_DATABASE_ID) &
    filters.group &
    filters.text &
    ~filters.command(["updatetopic"])
)
async def topic_text_handler(bot: Client, msg: Message):
    """Handle text messages in forum topics to use as video titles."""
    if not Var.GALLERY_ENABLED or not Var.GROUP_DATABASE_ID:
        return
    
    try:
        # Extract topic information
        topic_id = getattr(msg, 'reply_to_message_id', None) or getattr(msg, 'message_thread_id', None) or msg.chat.id
        if not topic_id:
            logger.debug("Message has no topic ID, skipping")
            return
        
        # Store the text as the topic title
        if msg.text and len(msg.text.strip()) > 0:
            title = msg.text.strip()[:100]  # Limit to 100 chars
            await db.update_topic_title(topic_id, title, msg.chat.id)
            logger.info(f"Updated topic {topic_id} title to: {title}")
            
    except FloodWait as e:
        logger.warning(f"FloodWait in topic_text_handler: {e.value}s")
    except Exception as e:
        logger.error(f"Error in topic_text_handler: {e}", exc_info=True)


@StreamBot.on_message(
    filters.chat(Var.GROUP_DATABASE_ID) &
    filters.group &
    filters.command("updatetopic")
)
async def update_topic_handler(bot: Client, msg: Message):
    """Admin command to manually update topic information."""
    if not Var.GALLERY_ENABLED or not Var.GROUP_DATABASE_ID:
        return
    
    try:
        # Check if user is admin
        user = await bot.get_chat_member(msg.chat.id, msg.from_user.id)
        if not user or user.status not in ["administrator", "creator"]:
            await msg.reply_text("Only admins can use this command.")
            return
        
        topic_id = getattr(msg, 'reply_to_message_id', None) or getattr(msg, 'message_thread_id', None) or msg.chat.id
        if not topic_id:
            await msg.reply_text("This command must be used in a topic.")
            return
        
        # Get current topic info
        topic_name = f"Topic {topic_id}"
        
        # Update topic name in database
        existing = await db.get_topic_video(topic_id)
        if existing:
            await db.add_topic_video(
                topic_id=topic_id,
                topic_name=topic_name,
                group_id=msg.chat.id,
                video_message_id=existing.get("video_message_id"),
                created_at=existing.get("created_at", datetime.datetime.utcnow())
            )
            await msg.reply_text(f"Updated topic name to: {topic_name}")
        else:
            await msg.reply_text("No video found for this topic. Send a video first.")
            
    except FloodWait as e:
        logger.warning(f"FloodWait in update_topic_handler: {e.value}s")
    except Exception as e:
        logger.error(f"Error in update_topic_handler: {e}", exc_info=True)


@StreamBot.on_message(
    filters.chat(Var.GROUP_DATABASE_ID) &
    filters.group &
    filters.command("deletetopic")
)
async def delete_topic_handler(bot: Client, msg: Message):
    """Admin command to remove a topic from the gallery."""
    if not Var.GALLERY_ENABLED or not Var.GROUP_DATABASE_ID:
        return
    
    try:
        # Check if user is admin
        user = await bot.get_chat_member(msg.chat.id, msg.from_user.id)
        if not user or user.status not in ["administrator", "creator"]:
            await msg.reply_text("Only admins can use this command.")
            return
        
        topic_id = getattr(msg, 'reply_to_message_id', None) or getattr(msg, 'message_thread_id', None) or msg.chat.id
        if not topic_id:
            await msg.reply_text("This command must be used in a topic.")
            return
        
        # Delete from database
        deleted = await db.delete_topic_video(topic_id)
        if deleted:
            await msg.reply_text("Topic removed from gallery.")
        else:
            await msg.reply_text("Topic not found in gallery.")
            
    except FloodWait as e:
        logger.warning(f"FloodWait in delete_topic_handler: {e.value}s")
    except Exception as e:
        logger.error(f"Error in delete_topic_handler: {e}", exc_info=True)
