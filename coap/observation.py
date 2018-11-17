import asyncio
import json
import logging
import time

import aiocoap
from aiocoap import resource
from aiocoap.numbers import CHANGED, CON, CONTENT, DELETED, FORBIDDEN, NON, NOT_ACCEPTABLE, PRECONDITION_FAILED, \
    UNAUTHORIZED, VALID

from coap.mapping import data_template, key_mapping, status_mapping


class Observation(aiocoap.resource.ObservableResource):
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


