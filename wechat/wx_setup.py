# this should be a stand alone program, only use for the first time setup

from aiohttp import web
import hashlib


async def get_handler(request):

    try:
        signature = request.query['signature']
        timestamp = request.query['timestamp']
        nonce = request.query['nonce']
        echostr = request.query['echostr']
        token = 'osram'

        token_list = [token, timestamp, nonce]
        token_list.sort()
        token_str = ''.join(token_list).encode()
        hashcode = hashlib.sha1(token_str).hexdigest()

        # official example didn't work without encode()
        # sha1 = hashlib.sha1()
        # map(sha1.update, token_list)
        # hashcode = sha1.hexdigest()

        if hashcode == signature:
            return web.Response(body=echostr.encode())
        else:
            print('signature no match')
            return web.Response()

    except Exception as e:
        print(f'error is: {e}')
        return web.Response()

app = web.Application()
app.add_routes([web.get('/wx', get_handler)])

try:
    web.run_app(app)
except KeyboardInterrupt:
    pass
