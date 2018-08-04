from functools import partial


class ClientProtocol:
    """UDP client"""

    def __init__(self, message):
        self.message = message

    def connection_made(self, transport):
        transport.sendto(self.message)
        transport.close()

    def datagram_received(self, data, addr):
        pass

    # noinspection PyMethodMayBeStatic
    def error_received(self, exc):
        """Called when a send or receive operation raises an OSError.
                (Other than BlockingIOError or InterruptedError.)"""

        print('Error received:', exc)

    def connection_lost(self, exc):
        pass


async def send_udp(l, msg):
    connect = l.create_datagram_endpoint(
                partial(ClientProtocol, msg),
                remote_addr=('127.0.0.1', 9999))
    await l.create_task(connect)

if __name__ == '__main__':
    import asyncio

    loop = asyncio.get_event_loop()
    connect = loop.create_datagram_endpoint(
                partial(ClientProtocol, b'test'),
                remote_addr=('123.98.6.175', 8341))
    transport, protocol = loop.run_until_complete(connect)
    transport.close()
    loop.close()


