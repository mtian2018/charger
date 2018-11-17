import aiofiles
import yaml


async def open_yaml(path):
    async with aiofiles.open(path, mode='r') as f:
        content = await f.read()
        return yaml.load(content)

if __name__ == '__main__':
    import asyncio

    name = '../wechat/wx_string.yaml'
    loop = asyncio.get_event_loop()
    y = loop.run_until_complete(open_yaml(name))
    for k, v in y.items():
        print(k, v)