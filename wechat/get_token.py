import aiohttp
import asyncio
from time import time


class AccessToken:
    def __init__(self):
        self.token = ''
        self.expires = 0.1

    async def get_token(self, url):

        if self.expires - time() > 1800:     # 30 minutes to expire
            return self.token

        async with aiohttp.ClientSession() as session:
            async with session.get(url=url, timeout=5) as response:
                j = await response.json()
                self.token = j['access_token']
                self.expires = j['expires_in'] + time()
                return self.token


if __name__ == '__main__':
    import sys
    sys.path.append('../')
    from utils.open_yaml import open_yaml

    name = './data_mart.yaml'
    loop = asyncio.get_event_loop()
    yaml_guy = loop.run_until_complete(open_yaml(name))

    app_id = yaml_guy['appID']
    app_secret = yaml_guy['appSecret']
    api_domain = yaml_guy['apiDomain']
    token_api = yaml_guy['accessTokenApi']
    token_url = token_api % (api_domain, app_id, app_secret)

    token_boy = AccessToken()
    token = loop.run_until_complete(token_boy.get_token(token_url))
    print(token)
    print(token_boy.fresh())


