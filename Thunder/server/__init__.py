# Thunder/server/__init__.py

from aiohttp import web
from .stream_routes import routes as stream_routes
from .gallery_routes import routes as gallery_routes


# Health check route for Render
async def health_check(request):
    return web.Response(text="OK", status=200)


async def web_server():
    web_app = web.Application(client_max_size=50 * 1024 * 1024)
    # Add health check route first (for Render)
    web_app.router.add_get('/', health_check)
    web_app.router.add_get('/health', health_check)
    web_app.add_routes(stream_routes)
    web_app.add_routes(gallery_routes)
    return web_app
