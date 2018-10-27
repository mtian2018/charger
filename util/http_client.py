import aiohttp


async def http_post(u, data):
    async with aiohttp.ClientSession() as session:
        async with session.post(u, data=data, timeout=5) as response:
            return await response.text()

if __name__ == '__main__':
    import asyncio

    url = 'http://127.0.0.1:8080/'
    loop = asyncio.get_event_loop()
    res = loop.run_until_complete(http_post(url, 'test'))
    print(res)


