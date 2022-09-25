import asyncio
import aiohttp
from aiohttp import web
import os


HERE = os.path.dirname(__file__)


async def slow(request):
    await asyncio.sleep(5)
    return web.Response(text="OK")


async def redirect(request):
    return aiohttp.web.HTTPFound("/")


def run(port=8888):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    app = web.Application()
    app.router.add_get('/slow', slow)
    app.router.add_get('/redirect', redirect)
    app.router.add_static('/', HERE, show_index=True)
    try:
        web.run_app(app, port=port, reuse_address=True, reuse_port=True,
                    print=None)
    finally:
        loop.close()


if __name__ == '__main__':
    run()
