from datetime import datetime
import logging
import asyncio
from aiocoap import resource, GET, POST
import aiocoap
from motor import motor_asyncio
from utils.http_client import http_post

# database
db_uri = "mongodb//localhost:27017"
db_client = motor_asyncio.AsyncIOMotorClient()
db = db_client.test
coll = db.jobs


logging.basicConfig(level=logging.INFO)
# logging.getLogger("coap-server").setLevel(logging.DEBUG)


class TimeResource(resource.Resource):

    def __init__(self):
        super().__init__()
        self.handle = None

    async def render_get(self, req):
        payload = datetime.now().\
                strftime('%Y-%m-%d %H:%M:%S').encode('ascii')
        return aiocoap.Message(payload=payload)


class DataEntry(resource.Resource):

    def __init__(self):
        super().__init__()
        self.handle = None

    async def render_get(self, req):
        # return aiocoap.Message(mtype=2, code=1, mid=req.mid)
        print(req.remote.port)
        content = req.payload.decode()

        result = f'code={req.code}, type={req.mtype},' + \
            f'  load={content}, token={req.token}'
        print(result)

        # notify wechat server
        # url = 'http://127.0.0.1:8080/relay'
        # if content == 'waking up':
        #     print('ready received, send http')
        #     await http_post(url, 'ready')
        # else:
        #     print('done received, send http')
        #     await http_post(url, content)

        # write db
        # doc = {'kwh': content}
        # await coll.insert_one(doc)

        # respond to coap client
        payload = f'{content} received by CoAP server'.encode()
        # payload = '{} received by CoAP server'.format(content).encode()
        return aiocoap.Message(payload=payload)     # payload are bytes

    async def render_post(self, req):

        if req.code == POST:
            content = req.payload.decode()

            note = ''
            if content == 'waking':
                note = 'ready'
            elif content == 'done':
                note = 'finished'

            # notify wechat server
            if note != '':
                url = 'http://127.0.0.1:8080/'
                res = await http_post(url, note)
                print(res)

        coap_msg = aiocoap.Message(payload=b'ok')
        coap_msg.set_request_uri(req.remote)
        return coap_msg

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
