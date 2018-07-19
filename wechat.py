import asyncio
from aiohttp import web
from xml.etree import ElementTree as ET
# from lxml import etree
from time import time
from motor import motor_asyncio
import hashlib
import json
import yaml
import aiohttp
import async_timeout
import aiofiles


# database
db_uri = "mongodb//localhost:27017"     # didn't work
db_client = motor_asyncio.AsyncIOMotorClient()
db = db_client.test
coll = db.jobs


class ClientProtocol:
    def __init__(self, message, loop):
        self.message = message
        self.loop = loop
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport
        print('Send UDP from Wechat server: %s\n' % self.message)
        self.transport.sendto(self.message.encode())

    def datagram_received(self, data, addr):
        print("Warning: suspicious data received:", data.decode())
        self.transport.close()

    def error_received(self, exc):
        print('Error received:', exc)

    def connection_lost(self, exc):
        print("Socket closed, stop the event loop")
        self.transport.close()


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

                # send udp
                loop = asyncio.get_event_loop()
                udp_msg = '007'
                connect = loop.create_datagram_endpoint(
                        lambda: ClientProtocol(udp_msg, loop),
                        remote_addr=('127.0.0.1', 9999))

                try:
                    transport, protocol = await loop.create_task(connect)   # why await?
                except Exception as e:
                    print('udp error: {}'.format(e))

                # write db
                doc = {'device': '001', 'status': 'starting'}
                await coll.insert_one(doc)

                to_user = root.find('FromUserName').text
                from_user = root.find('ToUserName').text

                content = 'start charging'

                xml_dict = {'ToUserName': to_user,
                            'FromUserName': from_user,
                            'CreateTime': int(time()),
                            'Content': content}

                xml_form = """
                        <xml>
                        <ToUserName><![CDATA[{ToUserName}]]></ToUserName>
                        <FromUserName><![CDATA[{FromUserName}]]></FromUserName>
                        <CreateTime>{CreateTime}</CreateTime>
                        <MsgType><![CDATA[text]]></MsgType>
                        <Content><![CDATA[{Content}]]></Content>
                        </xml>
                        """

                result = xml_form.format_map(xml_dict)

        elif event_type == 'SCAN':
            event_key = root.find('EventKey').text

            loop = asyncio.get_event_loop()
            udp_msg = '001'
            connect = loop.create_datagram_endpoint(
                    lambda: ClientProtocol(udp_msg, loop),
                    remote_addr=('127.0.0.1', 9999))

            try:
                transport, protocol = await loop.create_task(connect)   # why await?
            except Exception as e:
                print('udp error: {}'.format(e))

            # write db
            doc = {'device': event_key, 'status': 'awaking'}
            await coll.insert_one(doc)

            to_user = root.find('FromUserName').text
            from_user = root.find('ToUserName').text

            content = 'your device number is: {}'.format(event_key)

            xml_dict = {'ToUserName': to_user,
                        'FromUserName': from_user,
                        'CreateTime': int(time()),
                        'Content': content}

            xml_form = """
                    <xml>
                    <ToUserName><![CDATA[{ToUserName}]]></ToUserName>
                    <FromUserName><![CDATA[{FromUserName}]]></FromUserName>
                    <CreateTime>{CreateTime}</CreateTime>
                    <MsgType><![CDATA[text]]></MsgType>
                    <Content><![CDATA[{Content}]]></Content>
                    </xml>
                    """

            result = xml_form.format_map(xml_dict)

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

        await asyncio.sleep(1)

        result = \
            {
                "touser": "ofdEZ0r27GCXJDqxmsdKbTcIk10I",
                "template_id": "dPC0eKtCuPSC4BTYuziQk1bVq4Ll0Oi7UUg3__0OnJc",
                "data": {
                    "label": {
                        "value": "charge finished！",
                        "color": "#173177"
                    },
                    "note1": {
                        "value": req,
                        "color": "#173177"
                    },
                    "note2": {
                        "value": "39.8元",
                        "color": "#173177"
                    },
                    "note3": {
                        "value": "2018年9月22日",
                        "color": "#173177"
                    },
                    "end": {
                        "value": "欢迎再次购买！",
                        "color": "#173177"
                    }
                }
            }

    result = json.dumps(result)

    async def send_http(data):
        token = '11_xL7b5M_hi_lMgwLtMZWmbGQGa-DVx1YThm8n25G' \
                'qtYELE18UoU02VY11uk_ljoLVfXkB4XDqjAvXhC6V6U5c_' \
                'rkeYmnx_PbGhOjtgw7gtr7STLeNuVe9VZavJAxgRqtPqK' \
                'R0hgfGfYYQEQIAMRIhADAFKB'

        url = 'https://api.weixin.qq.com/cgi-bin/message/template/send?access_token='
        url = '%s%s' % (url, token)
        url = f'{url}{token}'

        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data, timeout=5) as response:
                return await response.json()

    res = await send_http(result)
    print(res)
    return web.Response(body='')     # necessary?


async def get_handler(request):

    try:
        signature = request.query['signature']
        timestamp = request.query['timestamp']
        nonce = request.query['nonce']
        echostr = request.query['echostr']
        token = 'wechat'

        token_list = [token, timestamp, nonce]
        token_list.sort()
        token_str = ''.join(token_list).encode()
        hashcode = hashlib.sha1(token_str).hexdigest()

        # official example didn't work without encode()
        # sha1 = hashlib.sha1()
        # map(sha1.update, token_list)
        # hashcode = sha1.hexdigest()

        if hashcode == signature:
            return web.Response(body=echostr.encode())
        else:
            print('signature no match')
            return web.Response()

    except Exception as e:
        print('error is: {}'.format(e))
        return web.Response()


async def init_web(loop):
    app = web.Application(loop=loop)
    app.add_routes([web.post('/setup', post_handler),
                    web.get('/setup', get_handler),
                    web.post('/relay', relay_handler)])

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', 8080)
    await site.start()

    return app

try:
    loop = asyncio.get_event_loop()
    loop.run_until_complete(init_web(loop))
    loop.run_forever()
except KeyboardInterrupt:
    pass