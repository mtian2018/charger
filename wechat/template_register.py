import yaml
import aiohttp
import asyncio
import async_timeout

data = yaml.load(open('data_mart.yaml', 'r'))

app_id = data['appID']
app_secret = data['appSecret']
api_domain = data['apiDomain']
api_token = data['apiURL']['accessTokenApi']
url_token = api_token % (api_domain, app_id, app_secret)
api_template = data['apiURL']['templateRegister']


async def fetch_json(session, url):
    with async_timeout.timeout(10):     # then what?
        async with session.get(url) as response:
            return await response.json()


async def fetch_token(url):
    async with aiohttp.ClientSession() as session:
        result = await fetch_json(session, url)
        # print(result['access_token'])
        return result['access_token']
        # print(result['expires_in'] + int(time.time()) - 600)


loop = asyncio.get_event_loop()
token = loop.run_until_complete(fetch_token(url_token))
url = api_template % (api_domain, token)
data = {
          "industry_id1": "1",
          "industry_id2": "4"
       }

async def temp_reg(url, data):
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=data, timeout=5) as response:
            return await response.json()


# print(url, '\n', data)
temp_res = loop.run_until_complete(temp_reg(url, data))
print(temp_res)


