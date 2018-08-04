from datetime import datetime
import logging
import asyncio
from aiocoap import resource as resource
import aiocoap

logging.basicConfig(level=logging.INFO)
# logging.getLogger("coap-server").setLevel(logging.DEBUG)

root = resource.Site()


class TimeResource(resource.Resource):

    def __init__(self):
        super().__init__()
        self.handle = None

    async def render_get(self, req):
        print(req)
        payload = datetime.now().\
                strftime("%Y-%m-%d %H:%M").encode('ascii')
        return aiocoap.Message(payload=payload)

class DataEntry(resource.Resource):

    def __init__(self):
        super().__init__()

        self.handle = None

    async def render_get(self, req):

        # print(req)
        return aiocoap.Message(payload=req.remote.hostinfo.encode())


class Report(resource.Resource):

    def __init__(self):
        super().__init__()

        self.handle = None

    async def render_get(self, req):
        return aiocoap.Message()


class Register(resource.Resource):

    def __init__(self):
        super().__init__()
        self.handle = None

    async def render_get(self, req):
        name = req.opt.uri_query
        print(Reverse.hub)
        if name[0] not in Reverse.hub:
            root.add_resource(name, Reverse(name[0]))
            pay = f'resource {name[0]} built'
        else:
            pay = f'resource {name[0]} exists'

        # print(root.get_resources_as_linkheader())

        return aiocoap.Message(payload=pay.encode())


class Reverse(resource.ObservableResource):
    """Example resource that can be observed. The `notify` method keeps
    scheduling itself, and calls `update_state` to trigger sending
    notifications."""

    hub = {}

    def __init__(self, name):
        super().__init__()
        self.handle = None
        self.name = name
        Reverse.hub[name] = self
        print(f'{name} resource built.')

    def notify(self):
        self.updated_state()
        self.reschedule()

    def reschedule(self):
        self.handle = asyncio.get_event_loop().call_later(5, self.notify)

    # async def add_observation(self, request, serverObservation):
    #     super().add_observation(self, request, serverObservation)
    #
    #     ober = request.opt.uri_query
    #     remote = request.remote.hostinfo
    #     # self.observer[ober] = remote
    #     print(ober, remote)

    def update_observation_count(self, count):
        if count == 0 and self.handle:
            print("Stopping the clock")
            self.handle.cancel()
            self.handle = None

        if count and self.handle is None:
            print("Starting the clock")
            self.reschedule()

    async def render_get(self, req):
        if req.opt.observe == 0:
            # observer = self.observer[req.opt.uri_query]
            print(req.remote.hostinfo)

        payload = datetime.now(). \
            strftime("%Y-%m-%d %H:%M:%S").encode('ascii')

        return aiocoap.Message(payload=payload)


root.add_resource(('time',), TimeResource())
root.add_resource(('link',), DataEntry())
# root.add_resource(('report',), Report())
root.add_resource(('reg',), Register())
root.add_resource(('time_obs',), Reverse('first'))
root.add_resource(('.well-known', 'core'),
                  resource.WKCResource(root.get_resources_as_linkheader))

asyncio.Task(aiocoap.Context.create_server_context(root, bind=("::", 5683)))
loop = asyncio.get_event_loop()

try:
    loop.run_forever()
except KeyboardInterrupt:
    Reverse.hub.clear()
finally:
    loop.close()

