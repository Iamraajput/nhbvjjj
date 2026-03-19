# Thunder/server/gallery_routes.py

import secrets
import json
from aiohttp import web

from Thunder.bot import StreamBot, multi_clients, work_loads
from Thunder.utils.database import db
from Thunder.utils.logger import logger
from Thunder.utils.render_template import render_page
from Thunder.vars import Var

routes = web.RouteTableDef()

# CORS headers for frontend access
CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
}


@routes.get("/api/gallery", allow_head=True)
async def api_gallery(request: web.Request):
    """API endpoint for gallery data (used by external frontend)."""
    if not Var.GALLERY_ENABLED:
        return web.json_response(
            {"error": "Gallery is disabled"},
            status=404,
            headers=CORS_HEADERS
        )
    
    try:
        # Get all topic videos
        topics = await db.get_all_topic_videos(Var.GROUP_DATABASE_ID)
        
        # Build response data
        videos = []
        for topic in topics:
            topic_id = topic.get("topic_id")
            topic_name = topic.get("topic_name", f"Topic {topic_id}")
            video_msg_id = topic.get("video_message_id")
            bin_message_id = topic.get("bin_message_id")
            group_id = topic.get("group_id")
            
            # Get thumbnail
            thumbnail_msg_id = await db.get_random_topic_thumbnail(topic_id)
            
            # Build stream URL
            safe_name = topic_name.replace(' ', '_').replace('/', '_')[:50]
            if bin_message_id:
                from Thunder.bot import StreamBot
                from Thunder.utils.file_properties import get_hash
                try:
                    msg = await StreamBot.get_messages(Var.BIN_CHANNEL, bin_message_id)
                    secure_hash = get_hash(msg)
                    if secure_hash:
                        stream_url = f"{Var.URL.rstrip('/')}/{secure_hash}{bin_message_id}/{safe_name}.mp4"
                    else:
                        stream_url = f"{Var.URL.rstrip('/')}/watch/{bin_message_id}"
                except:
                    stream_url = f"{Var.URL.rstrip('/')}/watch/{bin_message_id}"
            else:
                stream_url = f"{Var.URL.rstrip('/')}/group/{group_id}/{video_msg_id}/{safe_name}.mp4"
            
            # Thumbnail URL
            thumbnail_url = None
            if thumbnail_msg_id:
                thumbnail_url = f"{Var.URL.rstrip('/')}/gallery/thumbnail/{topic_id}"
            
            videos.append({
                "id": topic_id,
                "title": topic_name,
                "stream_url": stream_url,
                "thumbnail_url": thumbnail_url,
                "created_at": topic.get("created_at", "").isoformat() if topic.get("created_at") else ""
            })
        
        response_data = {
            "gallery_title": Var.GALLERY_TITLE,
            "base_url": Var.URL,
            "videos": videos
        }
        
        return web.json_response(
            response_data,
            headers=CORS_HEADERS
        )
        
    except Exception as e:
        error_id = secrets.token_hex(6)
        logger.error(f"API Gallery error {error_id}: {e}", exc_info=True)
        return web.json_response(
            {"error": f"Server error: {error_id}"},
            status=500,
            headers=CORS_HEADERS
        )


@routes.options("/api/gallery")
async def api_gallery_options(request: web.Request):
    """Handle CORS preflight requests."""
    return web.Response(status=200, headers=CORS_HEADERS)


@routes.get("/gallery", allow_head=True)
async def gallery_page(request: web.Request):
    """Main gallery page listing all topic videos."""
    if not Var.GALLERY_ENABLED:
        raise web.HTTPNotFound(text="Gallery is disabled")
    
    try:
        # Get all topic videos
        topics = await db.get_all_topic_videos(Var.GROUP_DATABASE_ID)
        
        if not topics:
            return web.Response(
                text="""
                <!DOCTYPE html>
                <html>
                <head><title>""" + Var.GALLERY_TITLE + """</title></head>
                <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                    <h1>""" + Var.GALLERY_TITLE + """</h1>
                    <p>No videos found in the gallery.</p>
                    <p>Add videos to topics in the database group to see them here.</p>
                </body>
                </html>
                """,
                content_type='text/html'
            )
        
        # Build gallery HTML
        gallery_items = []
        for topic in topics:
            topic_id = topic.get("topic_id")
            topic_name = topic.get("topic_name", f"Topic {topic_id}")
            video_msg_id = topic.get("video_message_id")
            bin_message_id = topic.get("bin_message_id")
            group_id = topic.get("group_id")
            
            # Get random thumbnail
            thumbnail_msg_id = await db.get_random_topic_thumbnail(topic_id)
            
            # Build stream URL - use BIN_CHANNEL if available, otherwise forward to BIN_CHANNEL
            safe_name = topic_name.replace(' ', '_').replace('/', '_')[:50]
            if bin_message_id:
                # Use the main streaming route with BIN_CHANNEL
                # Need to get the secure hash from the BIN_CHANNEL message
                from Thunder.bot import StreamBot
                from Thunder.utils.file_properties import get_hash
                try:
                    msg = await StreamBot.get_messages(Var.BIN_CHANNEL, bin_message_id)
                    secure_hash = get_hash(msg)
                    if secure_hash:
                        stream_url = f"{Var.URL.rstrip('/')}/{secure_hash}{bin_message_id}/{safe_name}.mp4"
                        logger.info(f"Gallery stream URL (BIN_CHANNEL): {stream_url}")
                    else:
                        # Fallback to watch route
                        stream_url = f"{Var.URL.rstrip('/')}/watch/{bin_message_id}"
                        logger.info(f"Gallery stream URL (watch): {stream_url}")
                except Exception as e:
                    logger.error(f"Error getting hash for bin_message {bin_message_id}: {e}")
                    stream_url = f"{Var.URL.rstrip('/')}/watch/{bin_message_id}"
            else:
                # No BIN_CHANNEL message - forward the video now
                logger.info(f"No BIN_CHANNEL message for topic {topic_id}, forwarding...")
                try:
                    from Thunder.bot import StreamBot
                    from Thunder.utils.file_properties import get_hash
                    
                    # Get the original message from group
                    original_msg = await StreamBot.get_messages(group_id, video_msg_id)
                    if original_msg and (original_msg.video or original_msg.document):
                        # Forward to BIN_CHANNEL
                        forwarded = await original_msg.forward(Var.BIN_CHANNEL)
                        if forwarded:
                            # Update database with new bin_message_id
                            await db.update_topic_bin_message_id(topic_id, forwarded.id)
                            # Generate stream URL
                            secure_hash = get_hash(forwarded)
                            if secure_hash:
                                stream_url = f"{Var.URL.rstrip('/')}/{secure_hash}{forwarded.id}/{safe_name}.mp4"
                                logger.info(f"Gallery stream URL (auto-forwarded): {stream_url}")
                            else:
                                stream_url = f"{Var.URL.rstrip('/')}/watch/{forwarded.id}"
                        else:
                            # Fallback to group streaming
                            stream_url = f"{Var.URL.rstrip('/')}/group/{group_id}/{video_msg_id}/{safe_name}.mp4"
                            logger.warning(f"Failed to forward, using group URL: {stream_url}")
                    else:
                        # Fallback to group streaming
                        stream_url = f"{Var.URL.rstrip('/')}/group/{group_id}/{video_msg_id}/{safe_name}.mp4"
                        logger.warning(f"Original message not found, using group URL: {stream_url}")
                except Exception as e:
                    logger.error(f"Error forwarding video for topic {topic_id}: {e}")
                    # Fallback to group streaming
                    stream_url = f"{Var.URL.rstrip('/')}/group/{group_id}/{video_msg_id}/{safe_name}.mp4"
                    logger.info(f"Gallery stream URL (group fallback): {stream_url}")
            
            # Thumbnail URL (if available)
            thumbnail_html = ""
            if thumbnail_msg_id:
                thumb_url = f"{Var.URL.rstrip('/')}/gallery/thumbnail/{topic_id}"
                thumbnail_html = f'<img src="{thumb_url}" alt="{topic_name}" loading="lazy">'
            else:
                thumbnail_html = f'<div class="no-thumbnail">{topic_name}</div>'
            
            item_html = f'''
            <div class="gallery-item">
                <a href="{stream_url}" class="video-link">
                    <div class="thumbnail">
                        {thumbnail_html}
                        <div class="play-overlay">
                            <svg viewBox="0 0 24 24" class="play-icon">
                                <path d="M8 5v14l11-7z"/>
                            </svg>
                        </div>
                    </div>
                    <div class="video-title">{topic_name}</div>
                </a>
            </div>
            '''
            gallery_items.append(item_html)
        
        # Build full HTML page
        html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{Var.GALLERY_TITLE}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            color: #fff;
            padding: 20px;
        }}
        
        .header {{
            text-align: center;
            padding: 40px 20px;
            margin-bottom: 30px;
        }}
        
        .header h1 {{
            font-size: 2.5rem;
            font-weight: 300;
            margin-bottom: 10px;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        
        .header p {{
            color: #888;
            font-size: 1.1rem;
        }}
        
        .gallery-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 25px;
            max-width: 1400px;
            margin: 0 auto;
            padding: 0 20px;
        }}
        
        .gallery-item {{
            background: rgba(255, 255, 255, 0.05);
            border-radius: 12px;
            overflow: hidden;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }}
        
        .gallery-item:hover {{
            transform: translateY(-5px);
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);
        }}
        
        .video-link {{
            text-decoration: none;
            color: inherit;
            display: block;
        }}
        
        .thumbnail {{
            position: relative;
            aspect-ratio: 16/9;
            overflow: hidden;
            background: #0a0a0a;
        }}
        
        .thumbnail img {{
            width: 100%;
            height: 100%;
            object-fit: cover;
            transition: transform 0.3s ease;
        }}
        
        .gallery-item:hover .thumbnail img {{
            transform: scale(1.05);
        }}
        
        .no-thumbnail {{
            width: 100%;
            height: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            font-size: 1.2rem;
            font-weight: 500;
            text-align: center;
            padding: 20px;
        }}
        
        .play-overlay {{
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.4);
            display: flex;
            align-items: center;
            justify-content: center;
            opacity: 0;
            transition: opacity 0.3s ease;
        }}
        
        .gallery-item:hover .play-overlay {{
            opacity: 1;
        }}
        
        .play-icon {{
            width: 60px;
            height: 60px;
            fill: #fff;
            filter: drop-shadow(0 2px 4px rgba(0,0,0,0.3));
        }}
        
        .video-title {{
            padding: 15px;
            font-size: 1rem;
            font-weight: 500;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            color: #fff;
        }}
        
        @media (max-width: 768px) {{
            .header h1 {{
                font-size: 1.8rem;
            }}
            
            .gallery-grid {{
                grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
                gap: 15px;
                padding: 0 10px;
            }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{Var.GALLERY_TITLE}</h1>
        <p>{len(topics)} video(s) available</p>
    </div>
    
    <div class="gallery-grid">
        {''.join(gallery_items)}
    </div>
</body>
</html>'''
        
        return web.Response(text=html_content, content_type='text/html')
        
    except Exception as e:
        error_id = secrets.token_hex(6)
        logger.error(f"Gallery error {error_id}: {e}", exc_info=True)
        raise web.HTTPInternalServerError(
            text=f"Error loading gallery: {error_id}") from e


@routes.get("/gallery/stream/{topic_id}", allow_head=True)
async def gallery_stream(request: web.Request):
    """Stream page for a specific topic video."""
    if not Var.GALLERY_ENABLED:
        raise web.HTTPNotFound(text="Gallery is disabled")
    
    try:
        topic_id = int(request.match_info["topic_id"])
        
        # Get topic info from database
        topic = await db.get_topic_video(topic_id)
        if not topic:
            raise web.HTTPNotFound(text="Video not found")
        
        topic_name = topic.get("topic_name", f"Topic {topic_id}")
        video_msg_id = topic.get("video_message_id")
        group_id = topic.get("group_id")
        
        # Build video source URL for group streaming
        base_url = Var.URL.rstrip('/')
        src = f"{base_url}/group/{group_id}/{video_msg_id}/{topic_name.replace(' ', '_')}.mp4"
        
        # Render streaming page
        html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{topic_name} - {Var.GALLERY_TITLE}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0a0a0a;
            min-height: 100vh;
            color: #fff;
        }}
        
        .header {{
            padding: 20px;
            background: rgba(255, 255, 255, 0.05);
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }}
        
        .header a {{
            color: #667eea;
            text-decoration: none;
            font-size: 0.9rem;
        }}
        
        .header h1 {{
            margin-top: 10px;
            font-size: 1.5rem;
            font-weight: 500;
        }}
        
        .video-container {{
            max-width: 1200px;
            margin: 30px auto;
            padding: 0 20px;
        }}
        
        .video-wrapper {{
            position: relative;
            padding-bottom: 56.25%; /* 16:9 */
            background: #000;
            border-radius: 12px;
            overflow: hidden;
        }}
        
        video {{
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            border-radius: 12px;
        }}
        
        .download-btn {{
            display: inline-block;
            margin-top: 20px;
            padding: 12px 24px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #fff;
            text-decoration: none;
            border-radius: 8px;
            font-weight: 500;
            transition: transform 0.2s ease;
        }}
        
        .download-btn:hover {{
            transform: translateY(-2px);
        }}
    </style>
</head>
<body>
    <div class="header">
        <a href="/gallery">&larr; Back to Gallery</a>
        <h1>{topic_name}</h1>
    </div>
    
    <div class="video-container">
        <div class="video-wrapper">
            <video controls autoplay playsinline>
                <source src="{src}" type="video/mp4">
                Your browser does not support the video tag.
            </video>
        </div>
        
        <a href="{src}" download class="download-btn">Download Video</a>
    </div>
</body>
</html>'''
        
        return web.Response(text=html_content, content_type='text/html')
        
    except ValueError:
        raise web.HTTPBadRequest(text="Invalid topic ID")
    except web.HTTPException:
        raise
    except Exception as e:
        error_id = secrets.token_hex(6)
        logger.error(f"Stream page error {error_id}: {e}", exc_info=True)
        raise web.HTTPInternalServerError(
            text=f"Error loading video: {error_id}") from e


@routes.get("/gallery/thumbnail/{topic_id}", allow_head=True)
async def gallery_thumbnail(request: web.Request):
    """Serve a thumbnail image for a topic."""
    if not Var.GALLERY_ENABLED:
        raise web.HTTPNotFound(text="Gallery is disabled")
    
    try:
        topic_id = int(request.match_info["topic_id"])
        
        # Get random thumbnail for this topic
        thumbnail_msg_id = await db.get_random_topic_thumbnail(topic_id)
        if not thumbnail_msg_id:
            raise web.HTTPNotFound(text="No thumbnail available")
        
        # Get topic info for group_id
        topic = await db.get_topic_video(topic_id)
        if not topic:
            raise web.HTTPNotFound(text="Topic not found")
        
        group_id = topic.get("group_id")
        
        # Get the image message from the group
        try:
            message = await StreamBot.get_messages(chat_id=group_id, message_ids=thumbnail_msg_id)
            if not message or not message.photo:
                raise web.HTTPNotFound(text="Thumbnail not found")
            
            # Download the photo
            photo = message.photo
            file_obj = await StreamBot.download_media(photo.file_id, in_memory=True)
            
            if not file_obj:
                raise web.HTTPNotFound(text="Could not download thumbnail")
            
            # Get file data
            file_obj.seek(0)
            file_data = file_obj.read()
            
            headers = {
                "Cache-Control": "public, max-age=86400",
                "Content-Length": str(len(file_data)),
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
            }
            
            return web.Response(
                body=file_data,
                content_type='image/jpeg',
                headers=headers
            )
            
        except Exception as e:
            logger.error(f"Error fetching thumbnail: {e}", exc_info=True)
            raise web.HTTPNotFound(text="Error loading thumbnail")
            
    except ValueError:
        raise web.HTTPBadRequest(text="Invalid topic ID")
    except web.HTTPException:
        raise
    except Exception as e:
        error_id = secrets.token_hex(6)
        logger.error(f"Thumbnail error {error_id}: {e}", exc_info=True)
        raise web.HTTPInternalServerError(
            text=f"Error loading thumbnail: {error_id}") from e


@routes.get("/api/gallery/videos")
async def api_gallery_videos(request: web.Request):
    """JSON API endpoint for gallery videos."""
    if not Var.GALLERY_ENABLED:
        return web.json_response({"error": "Gallery is disabled"}, status=404)
    
    try:
        topics = await db.get_all_topic_videos(Var.GROUP_DATABASE_ID)
        
        videos = []
        for topic in topics:
            topic_id = topic.get("topic_id")
            videos.append({
                "topic_id": topic_id,
                "topic_name": topic.get("topic_name"),
                "stream_url": f"{Var.URL.rstrip('/')}/gallery/stream/{topic_id}",
                "thumbnail_url": f"{Var.URL.rstrip('/')}/gallery/thumbnail/{topic_id}",
                "created_at": topic.get("created_at").isoformat() if topic.get("created_at") else None
            })
        
        return web.json_response({
            "gallery_title": Var.GALLERY_TITLE,
            "total_videos": len(videos),
            "videos": videos
        }, headers={"Access-Control-Allow-Origin": "*"})
        
    except Exception as e:
        error_id = secrets.token_hex(6)
        logger.error(f"API error {error_id}: {e}", exc_info=True)
        return web.json_response(
            {"error": f"Server error: {error_id}"}, status=500)
