import aiohttp
import asyncio
import async_timeout
import json
from wechat.wx_center import WxMart

GREEN = "#00FF00"
BLUE = "#0000FF"

msg = {
    "touser": to_user,
    "template_id": tmpl_id,
    "data": {
        "label": {
            "value": label,
            "color": GREEN
        },
        "note1": {
            "value": req,
            "color": BLUE
        },
        "note2": {
            "value": val,
            "color": BLUE
        },
        "note3": {
            "value": date,
            "color": BLUE
        },
        "end": {
            "value": greet,
            "color": BLUE
        }
    }
}

result = json.dumps(msg)


async def template_reg(url, data):
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=data) as response:
            return await response.json()


async def send_template(data):
    url = wx_mart.str_dict['template_msg_api'] % wx_mart.token

    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=result) as response:
            return await response.json()


loop = asyncio.get_event_loop()
wx_mart = WxMart(loop)

url = wx_mart.str_dict[] % (wx_mart.str_dict['api_domain'], wx_mart.token)
data = {
          "industry_id1": "1",
          "industry_id2": "4"
       }
loop.run_until_complete(template_reg(url, result))

loop.close()


# loop.run_until_complete(send_template())
