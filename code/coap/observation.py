import json
import logging
import time
from functools import partial

import aiocoap
from aiocoap import resource
from aiocoap.numbers import ACK, CHANGED, CONTENT, DELETED, NON, NOT_ACCEPTABLE, PRECONDITION_FAILED, \
    UNAUTHORIZED, VALID

from common.mapping import data_template, key_mapping, status_mapping

logger = logging.getLogger(__name__)


class Observation(aiocoap.resource.ObservableResource):
    """create a observation resource for each device"""

    def __init__(self, db):
        super().__init__()

        self.name = None
        self.remote = None
        self.count = 0
        self.last_add = 0
        self.last_check = 0
        self.db = db

    def _cancel(self, obs):
        self._observations.remove(obs)
        self.update_observation_count(len(self._observations))
        logger.info(f'{self.name} ended observation')

    async def add_observation(self, request, serverobservation):
        """overrides parent method,
        this function runs before render_get"""

        if request.remote != self.remote:
            return

        if time.time() - self.last_add < 5:
            return

        if self.count > 0:     # cancel previous observation
            self.updated_state(aiocoap.Message(mtype=NON, code=DELETED))

        self._observations.add(serverobservation)
        serverobservation.accept(partial(self._cancel, serverobservation))
        self.update_observation_count(len(self._observations))

        # loop.create_task(self.check_cmd())
        self.remote = request.remote

    async def check_cmd(self):
        # check db and resend command
        doc = await self.db.devices.find_one({'$and': [
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

    async def render_get(self, req):
        if req.remote != self.remote:
            return aiocoap.Message(code=UNAUTHORIZED)

        return aiocoap.Message()

    async def render_post(self, req):
        if req.remote != self.remote:
            logger.warning(f'{self.name} from {req.remote} at {time.ctime()}')
            return aiocoap.Message(code=UNAUTHORIZED)

        if self.count > 0:
            code = VALID
            self.last_check = time.time()
        else:
            code = PRECONDITION_FAILED

        return aiocoap.Message(mtype=NON if req.mtype == NON else ACK, code=code)

    async def render_put(self, req):
        if req.remote != self.remote:
            return aiocoap.Message(code=UNAUTHORIZED)

        if self.count == 0:
            return aiocoap.Message(code=PRECONDITION_FAILED)

        # rate limit?

        self.last_check = time.time()
        raw = req.payload.decode()
        try:
            raw = json.loads(raw)
        except Exception as err:
            logger.warning(f'json error: {raw}')
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
                    logger.warning(f'key {v} is not in status_mapping')

            try:
                data_entry[key_mapping[k]] = v
            except KeyboardInterrupt:
                logger.warning(f'key {k} is not in key_mapping')

        data_entry['serial'] = self.name
        data_entry['time'] = time.time()
        if data_entry['st'
                      'atus'] in ('charging', 'finished'):
            await self.db.jobs.replace_one({'$and': [
                {'serial': {'$eq': self.name}},
                {'status': {'$in': ['charging']}}
            ]}, data_entry, upsert=True)
        elif data_entry['status'] in ('waiting', 'start'):
            await self.db.jobs.replace_one({'$and': [
                {'serial': {'$eq': self.name}},
                {'status': {'$in': ['waiting']}}
            ]}, data_entry, upsert=True)
        else:
            await self.db.jobs.insert_one(data_entry)

        return aiocoap.Message(code=CHANGED, payload=b'data received')

    def update_observation_count(self, count):
        self.count = count
        if count > 0:
            self.last_add = time.time()
            # loop.create_task doesn't work here

            # asyncio.ensure_future(self.db.devices.insert_one({'serial': self.name,
            #                                              'status': 'online',
            #                                              'time': time.time()})
            #                       )
            logger.info(f'{self.name} started observation')
        else:
            # asyncio.ensure_future(self.db.devices.insert_one({'serial': self.name,
            #                                              'status': 'offline',
            #                                              'time': time.time()})
            #                       )
            logger.info(f'{self.name} ended observation')

    def updated_state(self, response=None):
        all_obs = list(self._observations)
        for o in all_obs:
            o.trigger(response)



