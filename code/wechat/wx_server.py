import asyncio
from time import time
from xml.etree import ElementTree as ET

import aioredis
from aiohttp import web
from motor.motor_asyncio import AsyncIOMotorClient

from code.wechat import WxMart
from wx_msg import MSG_HELP, XML_REPLY


async def relay_receiver(req):
    # check serial, source ip, etc.
    # if req == 'finished':
    # send custom msg
    # if req = 'started':
    # if req = 'unplugged':
    # if req = 'error':
    print(req)
    # push msg
    return web.Response()


async def post_handler(req):
    req = await req.text()

    # if req.ip not in wx_info.ip:
    #   loop.create_task(wx_info.get_ip()
    #   return web.Response()

    root = ET.fromstring(req)
    msg_type = root.find('MsgType').text
    to_user = root.find('FromUserName').text
    from_user = root.find('ToUserName').text
    resp = 'success'     # wechat default reply

    if msg_type == 'text':
        content = root.find('Content').text
        if 'yy' in content:
            pass
        elif 'ms' in content:
            pass
        else:
            msg = MSG_HELP
    elif msg_type == 'event':
        event_type = root.find('Event').text

        if event_type == 'CLICK':
            event_key = root.find('EventKey').text

            serial = 'MA345678'     # check if online
            if event_key not in ('help', 'inquiry'):
                cmd, arg = event_key.split('_')

                if 'charge' in event_key:
                    arg = time() + int(arg) * 3600

                asyncio.ensure_future(mongo.devices.insert_one({'serial': serial,
                                                                'user': to_user,
                                                                'command': cmd,
                                                                'arg': arg,
                                                                'status': 'received'})
                                      )

            if event_key not in ('help', 'inquiry'):
                # loop.create_task gives warning
                asyncio.ensure_future(pub.publish_json('ch:1', [serial, event_key]))

            msg = wx_mart.msg_dict.get(event_key)

    resp = XML_REPLY.format(to_user, from_user, time(), msg)

    return web.Response(body=resp)


loop = asyncio.get_event_loop()
wx_mart = WxMart(loop)
mongo = AsyncIOMotorClient().test

pub = loop.run_until_complete(
    aioredis.create_redis('redis://112.74.112.57:6379'))

app = web.Application()
app.add_routes([web.post('/wx', post_handler)])


async def start_web():
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', 8080)
    await site.start()

loop.create_task(start_web())

try:
    loop.run_forever()
except KeyError:
    pass
finally:
    pub.close()

    loop.run_until_complete(pub.wait_closed())
    asyncio.ensure_future(exit())
    loop.close()


