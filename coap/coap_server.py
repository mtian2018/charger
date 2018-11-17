import asyncio
import json
import logging
import re
import secrets
import string
import time
# from contextlib import suppress
from datetime import datetime
from pymongo import errors as mongoerr

import aiocoap
from aiocoap import resource
from aiocoap.numbers import BAD_REQUEST, CONTENT, CREATED, DELETED, EXCHANGE_LIFETIME, MAX_LATENCY, \
    MAX_TRANSMIT_SPAN, NOT_ACCEPTABLE, VALID, NON, ACK, PRECONDITION_FAILED, CHANGED, UNAUTHORIZED
from motor.motor_asyncio import AsyncIOMotorClient


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
                      if (obs.count == 0 and time.time() - obs.last_check
                          > EXCHANGE_LIFETIME)]

            # if remove is not None:
            for name in remove:
                path, obs = self.hub.pop(name)
                logging.info(f'deleted {obs.name} @ {datetime.now()}')
                root.remove_resource(('obs', path))

        # import sys, gc
        # print('refcount after', sys.getrefcount(o))
        # print('referrers:', gc.get_referrers(o))

    def create_obs(self, name):
        if name not in self.hub:  # first time registration
            path = ''.join(secrets.choice(string.ascii_lowercase + string.ascii_uppercase + string.digits)
                           for _ in range(6))
            obs = Observation()
            obs.name = name
            obs.last_reg = time.time()
            root.add_resource(('obs', path), obs)
            self.hub[name] = (path, obs)
            logging.info(f'resource built for {name} @ {datetime.now()}')
        else:
            path, obs = self.hub[name]
            logging.info(f'resource reassigned to {name} @ {datetime.now()}')

        # read database to find status

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
        self.last_reg = 0
        self.last_add = None
        self.last_check = None
        self.is_working = False
        self.count = 0
        self.remote = None

    async def render_post(self, req):
        print(req.remote)

        if req.remote == self.remote:
            print('same address')
        else:
            print('wrong address')
            # return aiocoap.Message(code=UNAUTHORIZED)

        if req.mtype != NON:
            return aiocoap.Message(code=BAD_REQUEST)

        if self.count > 0:
            code = VALID
        else:
            code = PRECONDITION_FAILED

        return aiocoap.Message(mtype=NON, code=code)

    async def render_put(self, req):
        name = name_check(req.opt.uri_query)
        if name != self.name:
            return aiocoap.Message(code=BAD_REQUEST)

        if not len(self._observations) > 0:
            return aiocoap.Message(code=PRECONDITION_FAILED)

        # rate limit?

        self.last_check = time.time()
        raw = req.payload.decode()
        try:
            raw = json.loads(raw)
        except Exception as err:
            logging.warning(f'json error: {raw}')
            print(err)
            return aiocoap.Message(code=NOT_ACCEPTABLE)
        print(raw)

        data_entry = data_template
        for k, v in raw.items():
            if k is 'S':
                try:
                    # if v.islower():
                    # write db
                    v = status_mapping[v.upper()]
                    # v = status_mapping.get(v.upper(), 'unknown')
                except KeyError:
                    logging.warning(f'key {v} is not in status_mapping')

            try:
                data_entry[key_mapping[k]] = v
            except KeyboardInterrupt:
                logging.warning(f'key {k} is not in key_mapping')

        data_entry['serial'] = name
        data_entry['time'] = datetime.now()
        if data_entry['st' \
                      'atus'] in ('charging', 'finished'):
            await db.jobs.replace_one({'$and': [
                {'serial': {'$eq': name}},
                {'status': {'$in': ['charging']}}
            ]}, data_entry, upsert=True)
        elif data_entry['status'] in ('waiting', 'start'):
            await db.jobs.replace_one({'$and': [
                {'serial': {'$eq': name}},
                {'status': {'$in': ['waiting']}}
            ]}, data_entry, upsert=True)
        else:
            await db.jobs.insert_one(data_entry)

        return aiocoap.Message(code=CHANGED, payload=b'data received')

    def update_observation_count(self, count):
        assert count < 2, 'double observation'

        if count > 0:
            self.last_add = time.time()

            logging.info(f'observation started for {self.name} @ {datetime.now()}')
            # loop.create_task doesn't work here
            asyncio.ensure_future(db.devices.insert_one({'serial': self.name,
                                                         'status': 'observing',
                                                         'time': datetime.now()})
                                  )
        else:
            logging.info(f'observation ended for {self.name} @ {datetime.now()}')
            asyncio.ensure_future(db.devices.insert_one({'serial': self.name,
                                                         'status': 'offline',
                                                         'time': datetime.now()})
                                  )

        self.count = count

    async def add_observation(self, request, serverobservation):
        """overrides parent method,
        this function runs before render_get"""

        name = name_check(request.opt.uri_query)
        if name is None or self.name != name:
            return

        if (self.last_add is not None
                and time.time() - self.last_add < 5):
            return

        if self.count > 0:     # cancel previous observation
            self.updated_state(aiocoap.Message(mtype=NON, code=DELETED))

        self._observations.add(serverobservation)
        serverobservation.accept(lambda: self._cancel(serverobservation))
        self.update_observation_count(len(self._observations))
        self.remote = request.remote

    def _cancel(self, obs):
        self._observations.remove(obs)
        self.update_observation_count(len(self._observations))

    def updated_state(self, response=None):
        all_obs = list(self._observations)
        for o in all_obs:
            o.trigger(response)

    async def render_get(self, req):
        return aiocoap.Message()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("coap-server").setLevel(logging.WARNING)

    INTERVAL_CLEANING = 900
    INTERVAL_WORK_POLL = EXCHANGE_LIFETIME
    INTERVAL_IDLE_POLL = 120

    key_mapping = {'R': 'signal', 'V': 'voltage', 'I': 'current', 'T': 'temperature',
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
    # db = AsyncIOMotorClient('mongodb://db:27017').test

    db.jobs.drop()
    db.devices.drop()

    def name_check(name):
        if not (len(name) == 0
                or re.match('^sn=[0-9a-zA-Z]{8}$', name[0]) is None):
            return name[0].split('=')[1]

    root.add_resource(('.well-known', 'core'),
                      resource.WKCResource(root.get_resources_as_linkheader))
    root.add_resource(('obs',), reg)
    root.add_resource(('test',), Test())
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