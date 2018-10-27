from datetime import datetime
import logging

import asyncio
import aiocoap
from aiocoap import resource
from motor.motor_asyncio import AsyncIOMotorClient


db = AsyncIOMotorClient().test

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
        # payload = req.text?
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
            if name not in self.hub:
                self.hub[name] = Observation(name)
                self.root.add_resource(('obs', name), self.hub[name])
                msg = f'resource built for {name}'

                if await db.device.find_one({'serial': name}):
                    await db.device.insert_one({'serial': name, 'time': datetime.now(), 'status': 'online'})
                else:
                    await db.device.insert_one({'serial': name, 'first_time': datetime.now(), 'status': 'online'})
            else:
                msg = f'observation for {name} exists'

        return aiocoap.Message(payload=msg.encode('ascii'))


class Observation(resource.ObservableResource):
    """create a observation resource for each device"""

    def __init__(self, name):
        super().__init__()
        # self.handle = None
        self.name = name

    async def add_observation(self, request, serverobservation):
        """Before the incoming request is sent to :meth:`.render`, the
        :meth:`.add_observation` method is called. If the resource chooses to
        accept the observation, it has to call the
        `serverobservation.accept(cb)` with a callback that will be called when
        the observation ends. After accepting, the ObservableResource should
        call `serverobservation.trigger()` whenever it changes its state; the
        ServerObservation will then initiate notifications by having the
        request rendered again."""

        self._observations.add(serverobservation)
        def _cancel(self=self, obs=serverobservation):
            self._observations.remove(serverobservation)
            self.update_observation_count(len(self._observations))
        serverobservation.accept(_cancel)
        self.update_observation_count(len(self._observations))

    async def render_get(self, req):
        name = req.opt.uri_query
        if name:
            name = name[0].split('=')[1]
            msg = "observation established".encode('ascii')
        else:
            msg = ''
            # how to reject?

        return aiocoap.Message(payload=msg)


if __name__ == '__main__':

    logging.basicConfig(level=logging.INFO)
    # logging.getLogger("coap-server").setLevel(logging.DEBUG)

    root = resource.Site()
    root.add_resource(('time',), TimeResource())
    root.add_resource(('report',), Report())
    obs_hub = {}
    root.add_resource(('reg',), Register(root, obs_hub))

    asyncio.Task(aiocoap.Context.create_server_context(root, bind=("::", 5683)))
    loop = asyncio.get_event_loop()

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        obs_hub.clear()
    finally:
        loop.close()

