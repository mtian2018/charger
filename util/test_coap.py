# import os
# import sys
# sys.path.append(os.getcwd())

from aiohttp import web
from util.coap_server import TimeResource, Register, Report
from aiocoap import resource
import asyncio
import aiocoap
from aiocoap.numbers import CON, CONTENT


async def get_handler(req):
    name = req.match_info.get('name')

    if name is None or req.query_string is None:
        text = 'sucker, name or command is missing'
    else:
        if name in obs_hub:
            obs = obs_hub[name]
            msg = aiocoap.Message(payload=req.query_string.encode('ascii'),
                                  mtype=CON,
                                  code=CONTENT)
            obs.updated_state(msg)
            text = f'{name} will do {req.query_string}'
        else:
            text = 'device does not exit'

    return web.Response(text=text)


if __name__ == '__main__':
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    loop = asyncio.get_event_loop()

    # web server
    app = web.Application()
    app.add_routes([web.get('/', get_handler),
                    web.get('/{name}', get_handler),
                    ])

    async def web_server():
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, port=8080)
        await site.start()

    loop.create_task(web_server())

    # CoAP server
    root = resource.Site()
    root.add_resource(('time',), TimeResource())
    root.add_resource(('report',), Report())
    obs_hub = {}
    root.add_resource(('reg',), Register(root, obs_hub))

    asyncio.Task(aiocoap.Context.create_server_context(root))
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        obs_hub.clear()
        # await runner.cleanup()
    # finally:
    #     loop.close()

    import motor.motor_asyncio

    # database
    db_uri = "mongodb//localhost:27017"
    db_client = motor_asyncio.AsyncIOMotorClient()
    db = db_client.test
    coll = db.jobs