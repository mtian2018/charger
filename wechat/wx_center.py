import asyncio
import logging
from datetime import datetime, timedelta, time

import aiohttp

from util.open_yaml import open_yaml
from wechat.wx_msg import MSG_DICT

yaml_file = './wx_string.yaml'


class WxMart:
    def __init__(self, loop):
        self.loop = loop
        self.token = None
        self.ip_list = None
        self.token_url = None
        self.ip_url = None
        self.mold_url = None
        self.str_dict = None
        self.start()
        self.msg_dict = MSG_DICT

    def start(self):
        self.str_dict = self.loop.run_until_complete(open_yaml(yaml_file))

        self.token_url = self.str_dict['access_token_api'] % \
                         (self.str_dict['api_domain'], self.str_dict['app_id'], self.str_dict['app_secret'])
        self.loop.run_until_complete(self.fetch_token())

        self.ip_url = self.str_dict['ip_list_api'] % (self.str_dict['api_domain'], self.token)
        self.loop.run_until_complete(self.get_ip())

        self.loop.create_task(self.schedule_token())
        self.loop.create_task(self.schedule_ip())

    async def schedule_token(self):
        while True:
            await self.fetch_token()
            self.mold_url = self.str_dict['template_msg_api'] % (self.str_dict['api_domain'], self.token)
            await asyncio.sleep(6000)

    async def fetch_token(self):
        async with aiohttp.ClientSession() as session:
            async with session.get(url=self.token_url) as response:
                retries = 5
                while True:
                    try:
                        j= await response.json()
                        self.token = j['access_token']
                        return
                    except Exception as err:
                        logging.warning('get token failed, try again')
                        if retries == 0:
                            raise err
                        retries -= 1
                        await asyncio.sleep(1)

    async def schedule_ip(self):
        while True:
            # combine asks for date, but accepts datetime as well
            t4am = datetime.combine(datetime.now() + timedelta(days=1), time(hour=4))
            dt = (t4am - datetime.now()).total_seconds()
            await asyncio.sleep(dt)
            self.ip_url = self.str_dict['ip_list_api'] % (self.str_dict['api_domain'], self.token)
            await self.get_ip()

    async def get_ip(self):
        async with aiohttp.ClientSession() as session:
            async with session.get(url=self.ip_url) as response:
                retries = 5
                while True:
                    try:
                        j = await response.json()
                        self.ip_list = j['ip_list']
                        return
                    except Exception as err:
                        logging.warning('get token failed, try again')
                        if retries == 0:
                            raise err
                        retries -= 1
                        await asyncio.sleep(60)


if __name__ == '__main__':

    loop = asyncio.get_event_loop()
    wx_mart = WxMart(loop)

    async def pp():
        while True:
            print(wx_mart.token)
            await asyncio.sleep(5400)

    try:
        loop.run_until_complete(pp())
    except KeyError:
        pass
    finally:
        asyncio.ensure_future(exit())
        loop.close()
