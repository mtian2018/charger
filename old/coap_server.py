"""yes, yes, yes, yes, remembe remote, remove query"""
import sys
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
    MAX_TRANSMIT_SPAN, NOT_ACCEPTABLE, VALID, NON, ACK, PRECONDITION_FAILED, CHANGED, UNAUTHORIZED, CON, FORBIDDEN
from motor.motor_asyncio import AsyncIOMotorClient
import ast
import aioredis


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

    def send_command(self, name, msg):
        if name in self.hub:
            _, obs = self.hub[name]
            if obs.count > 0:
                msg = aiocoap.Message(mtype=CON,
                                      code=CONTENT,
                                      payload=msg.encode())
                obs.updated_state(msg)
                return True

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
                logging.info(f'deleted {obs.name} @ {time.ctime()}')
                root.remove_resource(('obs', path))

        # import sys, gc
        # print('refcount after', sys.getrefcount(o))
        # print('referrers:', gc.get_referrers(o))

    def create_obs(self, name, remote):
        logging.info(f'{name} from {remote} at {time.ctime()}')
        if name not in self.hub:  # first time registration
            path = ''.join(secrets.choice(string.ascii_lowercase + string.ascii_uppercase + string.digits + '_')
                           for _ in range(4))
            obs = Observation()
            obs.name = name
            root.add_resource(('obs', path), obs)
            self.hub[name] = (path, obs)
            logging.info(f'resource built for {name} @ {time.ctime()}')
        else:
            path, obs = self.hub[name]
            logging.info(f'resource reassigned to {name} @ {time.ctime()}')

        obs.remote = remote
        # read database to find status

        return path, obs

    async def render_post(self, req):
        name = name_check(req.opt.uri_query)
        if name is None:
            return aiocoap.Message(code=BAD_REQUEST)

        path, obs = self.create_obs(name, req.remote)
        await db.devices.insert_one({'serial': name,
                                     'status': 'online',
                                     'time': time.time()})

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
        self.last_add = None
        self.last_check = None
        self.count = 0
        self.remote = None

    async def render_post(self, req):
        if req.remote != self.remote:
            logging.warning(f'{self.name} from {req.remote} at {time.ctime()}')
            return aiocoap.Message(code=UNAUTHORIZED)

        if self.count > 0:
            code = VALID
        else:
            code = PRECONDITION_FAILED

        return aiocoap.Message(mtype=NON if req.mtype == NON else CON, code=code)

    async def render_put(self, req):
        if req.remote != self.remote:
            return aiocoap.Message(code=UNAUTHORIZED)

        # name = name_check(req.opt.uri_query)
        # if name != self.name:
        #     return aiocoap.Message(code=BAD_REQUEST)

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

        data_entry['serial'] = self.name
        data_entry['time'] = time.time()
        if data_entry['st'
                      'atus'] in ('charging', 'finished'):
            await db.jobs.replace_one({'$and': [
                {'serial': {'$eq': self.name}},
                {'status': {'$in': ['charging']}}
            ]}, data_entry, upsert=True)
        elif data_entry['status'] in ('waiting', 'start'):
            await db.jobs.replace_one({'$and': [
                {'serial': {'$eq': self.name}},
                {'status': {'$in': ['waiting']}}
            ]}, data_entry, upsert=True)
        else:
            await db.jobs.insert_one(data_entry)

        return aiocoap.Message(code=CHANGED, payload=b'data received')

    def update_observation_count(self, count):
        assert count < 2, 'double observation'

        self.count = count
        if count > 0:
            self.last_add = time.time()

            logging.info(f'observation started for {self.name} @ {time.ctime()}')
            # loop.create_task doesn't work here
            asyncio.ensure_future(db.devices.insert_one({'serial': self.name,
                                                         'status': 'observing',
                                                         'time': time.time()})
                                  )
        else:
            logging.info(f'observation ended for {self.name} @ {time.ctime()}')
            asyncio.ensure_future(db.devices.insert_one({'serial': self.name,
                                                         'status': 'offline',
                                                         'time': time.time()})
                                  )

    async def add_observation(self, request, serverobservation):
        """overrides parent method,
        this function runs before render_get"""

        if request.remote != self.remote:
            return

        # name = name_check(request.opt.uri_query)
        # if name is None or self.name != name:
        #     return

        if (self.last_add is not None
                and time.time() - self.last_add < 5):
            return

        if self.count > 0:     # cancel previous observation
            self.updated_state(aiocoap.Message(mtype=NON, code=DELETED))

        self._observations.add(serverobservation)
        serverobservation.accept(lambda: self._cancel(serverobservation))
        self.update_observation_count(len(self._observations))

        loop.create_task(self.check_cmd())
        self.remote = request.remote

    async def check_cmd(self):
        # check db and resend command
        doc = await db.devices.find_one({'$and': [
                                        {'serial': {'$eq': self.name}},
                                        {'command': {'$eq': 'charge'}},
                                        ]})
        if doc and doc['status'] != 'finished':
            if int(doc['arg']) < time.time():
                msg = b'BG0'
            else:
                dt = (int(doc['arg']) - time.time()) / 60
                msg = f'BG{dt:.0f}'.encode()

            self.updated_state(aiocoap.Message(code=CONTENT, payload=msg))

    def _cancel(self, obs):
        self._observations.remove(obs)
        self.update_observation_count(len(self._observations))

    def updated_state(self, response=None):
        all_obs = list(self._observations)
        for o in all_obs:
            o.trigger(response)

    async def render_get(self, req):
        if req.remote != self.remote:
            return aiocoap.Message(code=FORBIDDEN)

        return aiocoap.Message()


async def redis_sub(ch):
    while await ch.wait_message():
        msg = await ch.get_json()
        logging.info(msg)
        name = msg[0]
        msg = command_mapping[msg[1]]
        reg.send_command(name, msg)
        await asyncio.sleep(0.01)


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
    command_mapping = {'serial': '', 'charge_0': 'BG0', 'charge_1': f'BG60',
                       'charge_2': f'BG120', 'charge_3': f'BG180',
                       'set_0': 'AA', 'set_1': 'BB'}

    # globals
    loop = asyncio.get_event_loop()
    root = resource.Site()
    reg = Registrar()

    db = AsyncIOMotorClient('mongodb://db:27017').test
    db.jobs.drop()
    db.devices.drop()

    sub = loop.run_until_complete(
        aioredis.create_redis('redis://redis:6379'))
    [ch] = loop.run_until_complete(sub.subscribe('ch:1'))
    loop.create_task(redis_sub(ch))

    def name_check(name):
        if not (len(name) == 0
                or re.match('^sn=[0-9a-zA-Z]{8}$', name[0]) is None):
            return name[0].split('=')[1]

    root.add_resource(('.well-known', 'core'),
                      resource.WKCResource(root.get_resources_as_linkheader))
    root.add_resource(('obs',), reg)
    root.add_resource(('test',), Test())
    # root.add_resource(('relay',), Relay())
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
