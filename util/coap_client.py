
import logging
import asyncio
from aiocoap import Context, Message
from aiocoap.numbers.codes import GET

logging.basicConfig(level=logging.INFO)

async def main():
    protocol = await Context.create_client_context()
    request = Message(code=GET, uri='coap://localhost/link')
    # request = Message(mtype=3, code=5.04, uri='coap://192.168.1.2:60673')

    try:
        response = await protocol.request(request).response
    except Exception as e:
        print('Failed to fetch resource:')
        print(e)
    else:
        print('Result: %s\n%r'%(response.code, response.payload))

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())