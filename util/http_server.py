from aiohttp import web


async def get_handler(req):
    name = req.match_info.get('name', 'sucker')
    text = 'ok ' + name + ', you are a sucker.'
    print(req.remote)
    return web.Response(text=text)


async def post_handler(req):

    return web.Response(text='post received')


if __name__ == '__main__':
    app = web.Application()
    app.add_routes([web.get('/', get_handler),
                    web.get('/{name}', get_handler),
                    web.post('/', post_handler)])
    web.run_app(app)

