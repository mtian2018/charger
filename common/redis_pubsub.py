import aioredis
import asyncio
from coap.mapping import command_mapping


async def sub_read():
    sub = await aioredis.create_redis(
        'redis://localhost')
    [ch] = await sub.subscribe('ch:1')

    while await ch.wait_message():
        msg = await ch.get_json()
        print(msg)
        await asyncio.sleep(0.001)


async def pub():
    res = await aioredis.create_redis(
        'redis://localhost')

    i = 0
    while i < 10:
        print(i)
        d = {'serial': '12344', 'cmd': 'start'}
        d = ['serial', 'cmd', 'arg']
        await res.publish_json('ch:1', d)
        await asyncio.sleep(0.5)
        i += 1


class RedisPubSub:
    def __int__(self, is_coap):
        sub = loop.run_until_complete(
            aioredis.create_redis('redis://redis:6379'))

        if is_coap:
            [ch] = loop.run_until_complete(sub.subscribe('ch:1'))
            loop.create_task(self.sub_command(ch))
        else:
            [ch] = loop.run_until_complete(sub.subscribe('ch:2'))
            loop.create_task(self.sub_status(ch))

    async def sub_command(self, ch):
        while await ch.wait_message():
            msg = await ch.get_json()
            name = msg[0]
            msg = command_mapping[msg[1]]
            reg.send_command(name, msg)
            await asyncio.sleep(0.01)

    async def sub_status(self, ch):
        pass


# if __name__ == '__main__':
#     loop = asyncio.get_event_loop()
#     loop.create_task(sub_read())
#     loop.create_task(pub())
#
#     from coap.registration import Registrar
#     reg = Registrar()
#
#     try:
#         loop.run_forever()
#     except KeyboardInterrupt:
#         asyncio.ensure_future(exit())
#         loop.close()
