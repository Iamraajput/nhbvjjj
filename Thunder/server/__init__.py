# Thunder/server/__init__.py

from aiohttp import web
from .stream_routes import routes as stream_routes
from .gallery_routes import routes as gallery_routes


async def web_server():
    web_app = web.Application(client_max_size=50 * 1024 * 1024)
    web_app.add_routes(stream_routes)
    web_app.add_routes(gallery_routes)
    return web_app
