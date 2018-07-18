import asyncio
from aiohttp import web
from xml.etree import ElementTree as ET
# from lxml import etree
from time import time
from motor import motor_asyncio
import hashlib


# database
db_uri = "mongodb//localhost:27017"
db_client = motor_asyncio.AsyncIOMotorClient(db_uri)
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
    xml_data = ET.fromstring(req)
    msg_type = xml_data.find('MsgType').text
    result = 'success'

    if msg_type == 'event':
        event_type = xml_data.find('Event').text
        event_key = xml_data.find('EventKey').text

        if event_type == 'CLICK':
            if event_key == 'menu_charge':
                to_user = xml_data.find('FromUserName').text
                from_user = xml_data.find('ToUserName').text

                # send udp
                loop = asyncio.get_event_loop()
                udp_msg = '007'
                connect = loop.create_datagram_endpoint(
                        lambda: ClientProtocol(udp_msg, loop),
                        remote_addr=('127.0.0.1', 9999))

                try:
                    transport, protocol = loop.create_task(connect)
                except Exception as e:
                    print('udp error: {}'.format(e))

                # write db
                # doc = {'device': '001', 'status': 'connecting'}
                # await coll.insert_one(doc)

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
    else:
        pass

    return web.Response(body=result)


async def setup_handler(request):

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
                    web.get('/setup', setup_handler)])

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