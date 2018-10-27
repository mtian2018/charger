from datetime import datetime
import logging

import asyncio
import aiocoap
from aiocoap import resource
from aiocoap.numbers import GET, PUT, CON, CONTENT, VALID
from random import randint


class TimeResource(resource.Resource):

    def __init__(self):
        super().__init__()
        self.handle = None

    async def render_get(self, req):
        print(req)
        payload = datetime.now().\
                strftime("%Y-%m-%d %H:%M").encode('ascii')
        return aiocoap.Message(payload=payload)


class Report(resource.Resource):

    def __init__(self):
        super().__init__()
        # self.handle = None

    async def render_get(self, req):
        name = req.opt.uri_query
        payload = req.text?
        return aiocoap.Message()


class Register(resource.Resource):

    def __init__(self, root, hub):
        super().__init__()
        # self.handle = None
        self.root = root
        self.hub = hub

    async def render_get(self, req):
        name = req.opt.uri_query

        if name is None:
            msg = "name is needed"
        else:
            name = name[0].split('=')[1]
            if name not in obs_hub:
                self.hub[name] = Observation(name)
                self.root.add_resource(('obs_' + name,), self.hub[name])
                msg = f'observation built for {name}'
            else:
                msg = f'observation for {name} exists'

        print(self.hub)
        msg = msg.encode('ascii')
        return aiocoap.Message(payload=msg)


class Observation(resource.ObservableResource):
    """create a observation resource for each device"""

    def __init__(self, name):
        super().__init__()
        self.handle = None
        self.name = name

    def notify(self):
        msg = aiocoap.Message(payload=f'from {self.name}'.encode('ascii'),
                              mtype=CON,
                              code=CONTENT,
                              )
        self.updated_state(msg)
        self.reschedule()

    def updated_state(self, response=None):
        super().updated_state(response)

    def reschedule(self):
        self.handle = asyncio.get_event_loop().call_later(5, self.notify)

    def update_observation_count(self, count):
        if count == 0 and self.handle:
            print("Stopping the clock")
            self.handle.cancel()
            self.handle = None

        if count and self.handle is None:
            print("Starting the clock")
            self.reschedule()

    async def render_get(self, req):
        msg = "observation established".encode('ascii')
        return aiocoap.Message(payload=msg)


if __name__ == '__main__':

    logging.basicConfig(level=logging.INFO)
    # logging.getLogger("coap-server").setLevel(logging.DEBUG)

    root = resource.Site()
    root.add_resource(('time',), TimeResource())
    # root.add_observation()
    # root.add_resource(('link',), DataEntry())
    # root.add_resource(('report',), Report())
    obs_hub = {}
    root.add_resource(('reg',), Register(root, obs_hub))
    # root.add_resource(('time_obs',), Observation())

    # asyncio.Task(aiocoap.Context.create_server_context(root, bind=("::", 5683)))
    asyncio.Task(aiocoap.Context.create_server_context(root))
    loop = asyncio.get_event_loop()

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        Observation.hub.clear()
    finally:
        loop.close()

