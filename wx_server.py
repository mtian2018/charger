import asyncio
from aiohttp import web
from xml.etree import ElementTree as ET
# from lxml import etree
from motor import motor_asyncio
import json
from py.utils.udp_client import send_udp
from py.wechat.wx_xml import form_xml
from py.wechat.get_token import AccessToken
from py.utils.open_yaml import open_yaml
from py.utils.http_client import http_post
from py.wechat.wx_json import j_dict
import logging

# asyncio.AbstractEventLoop.set_debug(enabled=True)
# logging.getLogger('asyncio').setLevel(logging.WARNING)
logging.basicConfig(level=logging.WARNING)
# logging.basicConfig(level=logging.INFO)
# logging.basicConfig(level=logging.DEBUG)

# database
db_uri = "mongodb//localhost:27017"     # didn't work
db_client = motor_asyncio.AsyncIOMotorClient()
db = db_client.test
coll = db.jobs

loop = asyncio.get_event_loop()
yaml_guy = open_yaml('./data_mart.yaml')
token_boy = AccessToken()
token_boy.get_token()


async def post_handler(request):

    req = await request.text()
    root = ET.fromstring(req)
    msg_type = root.find('MsgType').text
    result = 'success'

    if msg_type == 'event':

        event_type = root.find('Event').text

        if event_type == 'CLICK':
            event_key = root.find('EventKey').text

            if event_key == 'menu_charge':

                msg = '007'
                doc = {'device': '001', 'status': 'starting'}
                content = 'start charging'

        elif event_type == 'SCAN':
            event_key = root.find('EventKey').text

            msg = '001'
            doc = {'device': event_key, 'status': 'awaking'}
            content = f'your device number is: {event_key}'

        await send_udp(loop, msg)
        await coll.insert_one(doc)
        result = form_xml(root, content)

    else:
        pass

    return web.Response(body=result)


async def relay_handler(request):

    req = await request.text()
    await asyncio.sleep(1)

    if req == 'ready':
        print('ready')
        result = {
            "touser": "ofdEZ0r27GCXJDqxmsdKbTcIk10I",
            "template_id": "hz1GJfToavKMhLl8v0boo5y-C1QpUEpAWzr2NjDtTJI"
        }

    else:
        print('done')
        # write db
        doc = {'device': '001', 'status': 'starting'}
        await coll.insert_one(doc)
        # to_user = await coll.find_one({})

    await asyncio.sleep(1)


    result = json.dumps(j_dict)

    token = await token_boy.get_token()
    # print(token) try delay 5 seconds
    url = yaml_guy['templateMsgApi'] + token     # timing?

    res = await http_post(url, result)
    # print(res)
    return web.Response(body='')     # necessary?


app = web.Application()
app.add_routes([web.post('/setup', post_handler),
                web.post('/relay', relay_handler)])
web.run_app(app)
