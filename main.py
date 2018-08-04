# main server: coap server plus mongo server


from datetime import datetime
import logging
import asyncio
from aiocoap import resource
import aiocoap
from motor import motor_asyncio
import aiohttp

#database
db_uri = "mongodb//localhost:27017"
db_client = motor_asyncio.AsyncIOMotorClient()
db = db_client.test
coll = db.jobs


logging.basicConfig(level=logging.INFO)
logging.getLogger("coap-server").setLevel(logging.DEBUG)


class TimeResource(resource.Resource):

    def __init__(self):
        super().__init__()
        self.handle = None

    async def render_get(self, request):
        payload = datetime.now().\
                strftime('%Y-%m-%d %H:%M:%S').encode('ascii')
        return aiocoap.Message(payload=payload)


class DataEntry(resource.Resource):

    def __init__(self):
        super().__init__()
        self.handle = None

    loop = asyncio.get_event_loop()

    async def send_http(self, data):
        url = 'http://127.0.0.1:8080/relay'
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data, timeout=5) as response:
                return await response.text()

    async def render_get(self, req):
        # return aiocoap.Message(mtype=2, code=1, mid=req.mid)
        await asyncio.sleep(1)

        print("Receive CoAP request on CoAP server: \n\
            code=%s, type=%s, data=%s\n" % (req.code, req.mtype, req.payload))

        if req.payload.decode() == 'waking up':
            print('ready received, send http')
            await self.send_http('ready')
        else:
            print('done received, send http')
            await self.send_http(req.payload.decode())

        doc = {'kwh': req.payload.decode()}
        await coll.insert_one(doc)

        payload = '{} received by CoAP server'.format(req.payload.decode()).encode()
        return aiocoap.Message(payload=payload)     # payload are bytes


root = resource.Site()
root.add_resource(('time',), TimeResource())
root.add_resource(('link',), DataEntry())

asyncio.Task(aiocoap.Context.create_server_context(root))
loop = asyncio.get_event_loop()

try:
    loop.run_forever()
except KeyboardInterrupt:
    pass
finally:
    loop.close()
