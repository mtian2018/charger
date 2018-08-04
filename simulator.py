import logging
from aiocoap import Context, Message, GET, POST
import asyncio
import random


#udp server
class ServerProtocol:

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        message = data.decode()
        print('Received UDP %r from %s \n' % (message, addr))

        if message == '001':
            print('001 received')
            asyncio.get_event_loop().create_task(coap_send('awake'))
        elif message == '007':
            print('007 received')
            asyncio.get_event_loop().create_task(coap_send('charge'))
        # if message == "007":
            # print('message matched.\n')
            # async def wait5():
            #     i=0
            #     await asyncio.sleep(5)
            #     i+=1
            #
            # async for i in wait5():
            # async def repeat_task():
            #     i = 0
            #     while i < 5:
            #         await asyncio.sleep(3)
            #         await coap_send()
            #         i += 1


#coap client
async def coap_send(msg_id):
    logging.basicConfig(level=logging.INFO)

    protocol = await Context.create_client_context()
    if msg_id == 'awake':
        payload = 'waking up'
    elif msg_id == 'charge':
        payload = f'{random.random() * 10:.2f}'

    request = Message(code=GET, uri='coap://localhost/link', payload=payload.encode())

    try:
        print('Sending CoAP from UDP server\n')
        response = await protocol.request(request).response
    except Exception as e:
        print('Failed to fetch resource:')
        print(e)
    else:
        print('Received CoAP as client: %s\n%r\n'%(response.code, response.payload.decode()))


loop = asyncio.get_event_loop()
listen = loop.create_datagram_endpoint(
    ServerProtocol, local_addr=('127.0.0.1', 9999))
transport, protocol = loop.run_until_complete(listen)


try:
    loop.run_forever()
except KeyboardInterrupt:
    pass

transport.close()
loop.close()