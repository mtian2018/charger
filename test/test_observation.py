import asyncio

import aiocoap
from aiocoap.numbers import GET, POST, CREATED
import random
import string


async def test_obs():
    uri = 'coap://192.168.1.124:5683/obs'
    # uri = 'coap://112.74.112.57:5683/obs'

    context = await aiocoap.Context.create_client_context()
    request = aiocoap.Message(code=POST, uri=uri)
    serial = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(8))
    request.opt.uri_query = (f'sn={serial}',)       # tuple
    resp = await context.request(request).response
    print(f'register: {resp.code}')

    uri = f'{uri}/{resp.opt.location_path[1]}'
    request = aiocoap.Message(code=GET, uri=uri)
    request.opt.observe = 0
    resp = await context.request(request).response
    print(f'observation: {resp.code}')

    for _ in range(1):
        await asyncio.sleep(random.randint(0, 30))
        request = aiocoap.Message(code=POST, uri=uri)
        resp = await context.request(request).response
        print(f'post: {resp.code}')

    request = aiocoap.Message(code=GET, uri=uri)
    request.opt.observe = 1
    await context.request(request).response
    print(f'cancel obs: {resp.code}')

loop = asyncio.get_event_loop()
loop.run_until_complete(test_obs())
loop.close()
