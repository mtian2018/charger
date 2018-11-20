import asyncio
import logging
import logging.config
import logging.config
import os
import re
import sys

import aiocoap
import yaml
from aiocoap import resource
from aiocoap.numbers import BAD_REQUEST, CONTENT
from motor.motor_asyncio import AsyncIOMotorClient

from common.redis_pubsub import RedisPubSub
from coap.registration import Registrar

# from contextlib import suppress
fdir = os.path.dirname(__file__)
fpath = os.path.abspath(os.path.join(fdir, './common/logging_cfg.yaml'))
with open(fpath, 'r') as f:
    config = yaml.load(f.read())
logging.config.dictConfig(config)
# may use queue handler
# logging.getLogger("asyncio").setLevel(logging.DEBUG)
# logging.getLogger("coap-server").setLevel(logging.DEBUG)


def name_check(name):
    if not (len(name) == 0
            or re.match('^sn=[0-9a-zA-Z]{8}$', name[0]) is None):
        return name[0].split('=')[1]


class Test(resource.Resource):
    def __init__(self):
        super().__init__()

    async def render_put(self, req):
        print('test:', req.payload)

        name = name_check(req.opt.uri_query)
        if name is None:
            return aiocoap.Message(code=BAD_REQUEST)

        if name in reg.hub:
            _, obs = reg.hub[name]
            if obs.count > 0:
                msg = aiocoap.Message(code=CONTENT,
                                      payload=req.payload)
                obs.updated_state(msg)

                if 'BG' in req.payload.decode():
                    logging.info(f'work command sent to {obs.name}')

        return aiocoap.Message()


# globals
mongo = AsyncIOMotorClient('mongodb://0.0.0.0:27017').test
# mongo = AsyncIOMotorClient('mongodb://db:27017').test
mongo.jobs.drop()
mongo.devices.drop()

loop = asyncio.get_event_loop()
loop.set_debug(True)
redis = RedisPubSub()
root = resource.Site()
reg = Registrar(loop, root, mongo)

root.add_resource(('.well-known', 'core'),
                  resource.WKCResource(root.get_resources_as_linkheader))
root.add_resource(('obs',), reg)
root.add_resource(('test',), Test())
asyncio.Task(aiocoap.Context.create_server_context(root))

logging.info('coap_server started')

try:
    loop.run_forever()
except KeyboardInterrupt:
    pass
except AssertionError as e:
    print(e)
except asyncio.CancelledError as e:
    print(e)
finally:
    loop.run_until_complete(loop.shutdown_asyncgens())
    for task in asyncio.Task.all_tasks():
        task.cancel()
    loop.close()
    sys.exit()

