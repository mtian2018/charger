import asyncio
import logging
import re
import secrets
import string
import time
from contextlib import suppress
from datetime import datetime

import aiocoap
from aiocoap import resource
from aiocoap.numbers import ACK, BAD_REQUEST, CONTENT, CREATED, DELETED, EXCHANGE_LIFETIME, MAX_LATENCY, \
    MAX_TRANSMIT_SPAN, NON


class Data(resource.Resource):
    def __init__(self):
        super().__init__()

    async def render_put(self, req):
        name = name_check(req.opt.uri_query)
        if name is None:
            return aiocoap.Message(code=BAD_REQUEST)

        reg.record_time(name)
        pay = req.payload

        return aiocoap.Message(mtype=NON if req.mtype == NON else ACK,
                               code=CONTENT,)


class Test(resource.Resource):
    def __init__(self):
        super().__init__()

    async def render_put(self, req):
        name = name_check(req.opt.uri_query)
        if name is None:
            return aiocoap.Message(code=BAD_REQUEST)

        pay = req.payload.decode()
        if name in reg.hub:
            _, obs = reg.hub[name]

            if obs.task is not None:
                if pay == 'start':
                    await asyncio.sleep(MAX_LATENCY)
                    await obs.new_poll(True)

        return aiocoap.Message()


class TimeResource(resource.Resource):
    def __init__(self):
        super().__init__()

    @staticmethod
    async def render_get():
        payload = datetime.now().strftime("%Y-%m-%d %H:%M").encode('ascii')
        return aiocoap.Message(payload=payload)


class Registrar(resource.Resource):
    """creates and stores observation resources for devices"""

    def __init__(self,):
        super().__init__()
        self.hub = {}
        self.task = asyncio.ensure_future(self.cleaner())

    async def cleaner(self):
        while True:
            await asyncio.sleep(INTERVAL_CLEANING)

            # registered, used, offline
            remove = [name for name, (_, obs) in self.hub.items()
                      if (obs.task is None and time.time() - obs.last_off > EXCHANGE_LIFETIME)]

            for name in remove:
                path, obs = self.hub.pop(name)
                logging.info(f'delete {obs.name} @ {datetime.now()}')
                root.remove_resource(('obs', path))

        # import sys, gc
        # print('refcount after', sys.getrefcount(o))
        # print('referrers:', gc.get_referrers(o))

    def record_time(self, name):
        _, obs = self.hub[name]
        obs.last_checkin = time.time()

    def create_obs(self, name):
        if name not in self.hub:  # first time registration
            path = ''.join(secrets.choice(string.ascii_lowercase + string.digits)
                           for _ in range(6))
            obs = Observation()
            obs.name = name
            obs.last_off = time.time()
            root.add_resource(('obs', path), obs)
            self.hub[name] = (path, obs)
            logging.info(f'observation built for {name} @ {datetime.now()}')
        else:
            path, obs = self.hub[name]
            logging.info(f'observation reassigned to {name} @ {datetime.now()}')

        return path, obs

    async def render_post(self, req):
        name = name_check(req.opt.uri_query)
        if name is None:
            return aiocoap.Message(code=BAD_REQUEST)

        path, obs = self.create_obs(name)

        # new registration or registered but not observing (before or after)
        msg = f'observation built for {name} @ {path}'
        response = aiocoap.Message(code=CREATED,
                                   payload=msg.encode('ascii'),)
        response.opt.location_path = ('obs', path)
        return response

        # if await db.device.find_one({'serial': name}):
        #     await db.device.insert_one({'serial': name, 'time': datetime.now(), 'status': 'online'})
        # else:
        #     await db.device.insert_one({'serial': name, 'first_time': datetime.now(), 'status': 'online'})


class Observation(resource.ObservableResource):
    """create a observation resource for each device"""

    def __init__(self):
        super().__init__()
        self.name = None
        self.task = None
        self.is_working = False
        self.last_punch = None
        self.last_on = None
        self.last_off = None

    async def new_poll(self, is_working: bool):
        self.is_working = is_working

        if self.task is not None:
            self.task.cancel()
            with suppress(asyncio.CancelledError):
                await self.task
        self.task = asyncio.ensure_future(self._poll())

    async def _poll(self):
        while True:
            if self.is_working:
                await asyncio.sleep(INTERVAL_WORK_POLL)

                if (time.time() - self.last_punch) \
                        > (INTERVAL_WORK_POLL * 2 + MAX_LATENCY):
                    msg = aiocoap.Message(code=CONTENT,
                                          payload='report'.encode('ascii'))
                    self.updated_state(response=msg)
                # else:
                #     msg = aiocoap.Message(code=CONTENT, payload='working'.encode('ascii'))
                #     self.updated_state(response=msg)
            else:
                await asyncio.sleep(INTERVAL_IDLE_POLL)
                msg = aiocoap.Message(code=CONTENT, payload='idle'.encode('ascii'))
                self.updated_state(response=msg)

    def update_observation_count(self, count):
        if count > 1:
            print(f'{count} observations on {self.name}')

        if count > 0:
            self.task = asyncio.ensure_future(self.new_poll(self.is_working))
        else:
            assert (self.task is not None), "task is none when count is zero"
            self.task.cancel()
            self.task = None

    async def add_observation(self, request, serverobservation):
        """overrides parent method,
        this function runs before render_get"""

        name = name_check(request.opt.uri_query)
        if name is None or self.name != name:
            return

        if (self.last_on is not None
                and time.time() - self.last_on < MAX_TRANSMIT_SPAN):
                return

        if len(self._observations) > 0:
            self.updated_state(aiocoap.Message(code=DELETED))

        self._observations.add(serverobservation)
        serverobservation.accept(lambda: self._cancel(serverobservation))
        self.update_observation_count(len(self._observations))
        self.last_on = time.time()

        logging.info(f'observation started for {self.name} @ {datetime.now()}')
        # do online events

    def _cancel(self, obs):
        self._observations.remove(obs)
        self.update_observation_count(len(self._observations))
        self.last_off = time.time()
        # do offline events, database, etc.
        logging.info(f'observation ended for {self.name} @ {datetime.now()}')

    def updated_state(self, response=None):
        all_obs = list(self._observations)
        for o in all_obs:
            o.trigger(response)

    async def render_get(self, req):
        return aiocoap.Message()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("coap-server").setLevel(logging.WARNING)

    INTERVAL_CLEANING = EXCHANGE_LIFETIME * 2
    INTERVAL_WORK_POLL = 5
    INTERVAL_IDLE_POLL = 900

    # globals
    loop = asyncio.get_event_loop()
    root = resource.Site()
    reg = Registrar()
    # db = AsyncIOMotorClient().test

    def name_check(name):
        if not (len(name) == 0
                or re.match('^sn=[0-9]{5}$', name[0]) is None):
            return name[0].split('=')[1]

    root.add_resource(('.well-known', 'core'),
                      resource.WKCResource(root.get_resources_as_linkheader))
    root.add_resource(('time',), TimeResource())
    root.add_resource(('obs',), reg)
    root.add_resource(('test',), Test())
    root.add_resource(('data',), Data())
    asyncio.Task(aiocoap.Context.create_server_context(root))

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    except AssertionError as e:
        print(e)
    except asyncio.CancelledError as e:
        print(e)
    finally:
        # for task in asyncio.Task.all_tasks():
        #     task.cancel()
        # loop.run_until_complete(loop.shutdown_asyncgens())
        asyncio.ensure_future(exit())
        loop.close()
