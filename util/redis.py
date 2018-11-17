import aioredis
import asyncio
import json


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

loop = asyncio.get_event_loop()
loop.create_task(sub_read())
loop.create_task(pub())

try:
    loop.run_forever()
except KeyboardInterrupt:
    asyncio.ensure_future(exit())
    loop.close()



