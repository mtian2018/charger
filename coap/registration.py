import asyncio
import logging
import time
import aiocoap
from aiocoap import resource
from aiocoap.numbers import BAD_REQUEST, CON, CONTENT, CREATED, EXCHANGE_LIFETIME
import secrets
import string
import re
from motor.motor_asyncio import AsyncIOMotorClient
from coap.observation import Observation


INTERVAL_CLEANING = EXCHANGE_LIFETIME * 3


class Registrar(resource.Resource):
    """creates and stores observation resources for devices"""

    def __init__(self, ):
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

            for name in remove:
                path, obs = self.hub.pop(name)
                root.remove_resource(('obs', path))
                logging.info(f'deleted {obs.name} @ {time.ctime()}')

    def create_obs(self, name, remote):
        if name not in self.hub:  # first time registration
            obs = Observation()
            obs.name = name

            path = ''.join(secrets.choice(string.ascii_lowercase +
                                          string.ascii_uppercase +
                                          string.digits + '_')
                           for _ in range(4))

            root.add_resource(('obs', path), obs)
            self.hub[name] = (path, obs)
        else:
            path, obs = self.hub[name]

        obs.remote = remote
        # read database to find status

        return path, obs

    def name_check(self, name):
        if not (len(name) == 0
                or re.match('^sn=[0-9a-zA-Z]{8}$', name[0]) is None):
            return name[0].split('=')[1]

    async def render_post(self, req):

        name = self.name_check(req.opt.uri_query)
        if name is None:
            return aiocoap.Message(code=BAD_REQUEST)

        path, obs = self.create_obs(name, req.remote)
        logging.info(f'{name} registers from {req.remote} at {time.ctime()}')
        asyncio.ensure_future(db.devices.insert_one({'serial': name,
                                                     'status': 'online',
                                                     'time': time.time()})
                              )

        msg = f'observation built for {name} @ {path}'
        response = aiocoap.Message(code=CREATED,
                                   payload=msg.encode('ascii'), )
        response.opt.location_path = ('obs', path)
        return response


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("coap-server").setLevel(logging.WARNING)

    # globals
    loop = asyncio.get_event_loop()
    root = resource.Site()
    reg = Registrar()

    db = AsyncIOMotorClient('mongodb://db:27017').test
    db.jobs.drop()
    db.devices.drop()

    root.add_resource(('obs',), reg)
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
