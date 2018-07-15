from datetime import datetime
import logging
import asyncio
from aiocoap import resource as resource
import aiocoap


#coap server
class TimeResource(resource.Resource):

    def __init__(self):
        super().__init__()
        self.handle = None

    async def render_get(self, request):
        payload = datetime.now().\
                strftime("%Y-%m-%d %H:%M").encode('ascii')
        return aiocoap.Message(payload=payload)


class DataEntry(resource.Resource):

    def __init__(self):
        super().__init__()
        self.handle = None

    async def render_get(self, req):
        # return aiocoap.Message(mtype=2, code=1, mid=req.mid)
        import time
        # time.sleep(5)

        print("Receive CoAP request on CoAP server: \n\
            code=%s, type=%s, data=%s\n" % (req.code, req.mtype, req.payload))
        payload="{} received by CoAP server".format(req.payload).encode()
        return aiocoap.Message(payload=payload)


logging.basicConfig(level=logging.INFO)
# logging.getLogger("coap-server").setLevel(logging.DEBUG)

root = resource.Site()
root.add_resource(('time',), TimeResource())
root.add_resource(('link',), DataEntry())

asyncio.Task(aiocoap.Context.create_server_context(root))


#udp client
class EchoClientProtocol:
    def __init__(self, message, loop):
        self.message = message
        self.loop = loop
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport
        print('Send UDP from CoAP server: %s\n' % self.message)
        self.transport.sendto(self.message.encode())

    def datagram_received(self, data, addr):
        print("Warning: suspicious data received:", data.decode())
        self.transport.close()

    def error_received(self, exc):
        print('Error received:', exc)

    def connection_lost(self, exc):
        print("Socket closed, stop the event loop")
        loop = asyncio.get_event_loop()
        loop.stop()

loop = asyncio.get_event_loop()
message = "007"
connect = loop.create_datagram_endpoint(
    lambda: EchoClientProtocol(message, loop),
    remote_addr=('127.0.0.1', 9999))
transport, protocol = loop.run_until_complete(connect)


try:
    loop.run_forever()
except KeyboardInterrupt:
    pass
finally:
    transport.close()
    loop.close()


#database
import asyncio

from aiohttp import web
from motor.motor_asyncio import AsyncIOMotorClient

async def setup_db():
    db = AsyncIOMotorClient().test
    await db.pages.drop()
    html = '<html><body>{}</body></html>'
    await db.pages.insert_one({'_id': 'page-one',
                                    'body': html.format('Hello!')})

    await db.pages.insert_one({'_id': 'page-two',
                                    'body': html.format('Goodbye.')})

    return db

async def page_handler(request):
    page_name = request.match_info.get('page_name')

    # Retrieve the long-lived database handle.
    db = request.app['db']

    # Find the page by its unique id.
    document = await db.pages.find_one(page_name)

    if not document:
        return web.HTTPNotFound(text='No page named {!r}'.format(page_name))

    return web.Response(body=document['body'].encode(),
                        content_type='text/html')

loop = asyncio.get_event_loop()
db = loop.run_until_complete(setup_db())
app = web.Application()
app['db'] = db
# Route requests to the page_handler() coroutine.
app.router.add_get('/pages/{page_name}', page_handler)
web.run_app(app)