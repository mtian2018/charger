import asyncio
import json
import logging
import re
import secrets
import string
import time
# from contextlib import suppress
from datetime import datetime

import aiocoap
from aiocoap import resource
from aiocoap.numbers import BAD_REQUEST, CONTENT, CREATED, DELETED, EXCHANGE_LIFETIME, MAX_LATENCY, \
    MAX_TRANSMIT_SPAN
from motor.motor_asyncio import AsyncIOMotorClient


class Data(resource.Resource):
    """receives charging data from devices"""

    def __init__(self):
        super().__init__()

    async def render_put(self, req):
        name = name_check(req.opt.uri_query)
        if name is None:
            return aiocoap.Message(code=BAD_REQUEST)

        reg.record_time(name)
        raw = json.loads(req.payload.decode())

        data_entry = data_template
        for k, v in raw.items():
            if k is 'S':
                v = status_mapping[v]
            data_entry[key_mapping[k]] = v
        data_entry['serial'] = name
        data_entry['time'] = datetime.now()

        if data_entry['status'] in ('charging', 'waiting'):
            await db.jobs.replace_one({'$and': [
                                        {'serial': {'$eq': name}},
                                        {'status': {'$in': ['charging', 'waiting']}}
                                        ]}, data_entry, upsert=True)
        else:
            await db.jobs.insert_one(data_entry)
        return aiocoap.Message()


class Test(resource.Resource):
    def __init__(self):
        super().__init__()

    async def render_put(self, req):
        name = name_check(req.opt.uri_query)
        if name is None:
            return aiocoap.Message(code=BAD_REQUEST)

        if name in reg.hub:
            _, obs = reg.hub[name]
            if obs.task is not None:
                msg = aiocoap.Message(code=CONTENT,
                                      payload=req.payload)
                obs.updated_state(msg)
                if 'BG' in req.payload.decode():
                    logging.info(f'work command sent to {obs.name}')
                    await obs.new_poll(True)

        return aiocoap.Message()


class TimeResource(resource.Resource):
    def __init__(self):
        super().__init__()

    async def render_get(self, req):
        payload = datetime.now().strftime("%Y-%m-%d %H:%M").encode('ascii')
        return aiocoap.Message(payload=payload)


class Registrar(resource.Resource):
    """creates and stores observation resources for devices"""

    def __init__(self,):
        super().__init__()
        self.hub = {}
        self.task = loop.create_task(self.cleaner())

    async def cleaner(self):
        while True:
            await asyncio.sleep(INTERVAL_CLEANING)

            # registered and offline for a while
            remove = [name for name, (_, obs) in self.hub.items()
                      if (obs.task is None and time.time() - obs.last_check
                          > EXCHANGE_LIFETIME)]

            # if remove is not None:
            for name in remove:
                path, obs = self.hub.pop(name)
                logging.info(f'deleted {obs.name} @ {datetime.now()}')
                root.remove_resource(('obs', path))

        # import sys, gc
        # print('refcount after', sys.getrefcount(o))
        # print('referrers:', gc.get_referrers(o))

    def record_time(self, name):
        _, obs = self.hub[name]
        obs.last_check = time.time()

    def create_obs(self, name):
        if name not in self.hub:  # first time registration
            path = ''.join(secrets.choice(string.ascii_lowercase + string.digits)
                           for _ in range(6))
            obs = Observation()
            obs.name = name
            obs.last_check = time.time()
            root.add_resource(('obs', path), obs)
            self.hub[name] = (path, obs)
            logging.info(f'resource built for {name} @ {datetime.now()}')
        else:
            path, obs = self.hub[name]
            logging.info(f'resource assigned to {name} @ {datetime.now()}')

        return path, obs

    async def render_post(self, req):
        name = name_check(req.opt.uri_query)
        if name is None:
            return aiocoap.Message(code=BAD_REQUEST)

        path, obs = self.create_obs(name)
        await db.devices.insert_one({'serial': name,
                                     'status': 'online',
                                     'time': datetime.now()})

        # new registration or registered but not observing (before or after)
        msg = f'observation built for {name} @ {path}'
        response = aiocoap.Message(code=CREATED,
                                   payload=msg.encode('ascii'),)
        response.opt.location_path = ('obs', path)
        return response


class Observation(resource.ObservableResource):
    """create a observation resource for each device"""

    def __init__(self):
        super().__init__()
        self.name = None
        self.task = None
        self.last_add = None
        self.last_check = None
        self.is_working = False

    async def new_poll(self, is_working: bool):
        if self.task is not None:
            self.task.cancel()
            # with suppress(asyncio.CancelledError):
            #     await self.task

        self.is_working = is_working
        self.task = loop.create_task(self.poll())

    async def poll(self):
        new_job = True
        while True:
            if self.is_working:
                if new_job:
                    await asyncio.sleep(INTERVAL_WORK_POLL * 2 + MAX_LATENCY)
                    new_job = False
                else:
                    await asyncio.sleep(INTERVAL_WORK_POLL)

                if (time.time() - self.last_check) \
                        > (INTERVAL_WORK_POLL * 2 + MAX_LATENCY):
                    msg = aiocoap.Message(code=CONTENT,
                                          payload='RP300'.encode('ascii'))
                    self.updated_state(response=msg)
                    self.last_check = time.time()
                # else:
                #     msg = aiocoap.Message(code=CONTENT, payload='working'.encode('ascii'))
                #     self.updated_state(response=msg)
            else:
                await asyncio.sleep(INTERVAL_IDLE_POLL)

                msg = aiocoap.Message(code=CONTENT, payload='idle'.encode('ascii'))
                self.updated_state(response=msg)
                self.last_check = time.time()

    def update_observation_count(self, count):
        assert count < 2, 'double observation'

        if count > 0:
            if self.task is None:
                # poll will not run till this function finishes
                self.task = loop.create_task(self.poll())
            self.last_add = time.time()

            logging.info(f'observation started for {self.name} @ {datetime.now()}')
            # loop.create_task doesn't work here
            asyncio.ensure_future(db.devices.insert_one({'serial': self.name,
                                                         'status': 'observing',
                                                         'time': datetime.now()})
                                  )
        else:
            assert (self.task is not None), "task is none when count is zero"
            self.task.cancel()
            self.task = None

            logging.info(f'observation ended for {self.name} @ {datetime.now()}')
            asyncio.ensure_future(db.devices.insert_one({'serial': self.name,
                                                         'status': 'offline',
                                                         'time': datetime.now()})
                                  )

    async def add_observation(self, request, serverobservation):
        """overrides parent method,
        this function runs before render_get"""

        name = name_check(request.opt.uri_query)
        if name is None or self.name != name:
            return

        if (self.last_add is not None
                and time.time() - self.last_add < MAX_TRANSMIT_SPAN):
            return

        if len(self._observations) > 0:     # cancel previous observation
            self.updated_state(aiocoap.Message(code=DELETED))

        self._observations.add(serverobservation)
        serverobservation.accept(lambda: self._cancel(serverobservation))
        self.update_observation_count(len(self._observations))

    def updated_state(self, response=None):
        all_obs = list(self._observations)
        for o in all_obs:
            o.trigger(response)

    def _cancel(self, obs):
        self._observations.remove(obs)
        self.update_observation_count(len(self._observations))

    async def render_get(self, req):
        return aiocoap.Message()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("coap-server").setLevel(logging.WARNING)

    INTERVAL_CLEANING = 600
    INTERVAL_WORK_POLL = 300
    INTERVAL_IDLE_POLL = 5

    key_mapping = {'V': 'voltage', 'I': 'current', 'T': 'temperature',
                   't': 'duration', 'E': 'kwh', 'S': 'status'}
    status_mapping = {'S': 'start', 'C': 'charging', 'E': 'finished',
                      'U': 'unplugged', 'W': 'waiting', 'R': 'error'}
    data_template = {'serial': None, 'voltage': 220, 'current': 10, 'temperature': 40,
                     'duration': 0, 'kwh': 0, 'status': 'idle', 'time': None}

    # globals
    loop = asyncio.get_event_loop()
    root = resource.Site()
    reg = Registrar()
    db = AsyncIOMotorClient().test
    db.jobs.drop()
    db.devices.drop()

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
