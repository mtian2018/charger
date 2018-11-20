MSG_SENT = "命令已发送，请等待通知"

MSG_LATER = "预约中，届时充电"

MSG_HELP = ("帮助\n"
            "充电\n"
            "设置")

MSG_MODE = "模式设置中"
MSG_INQ = "查询中，请稍侯"

MSG_DICT = {
            'charge_0': MSG_SENT,
            'charge_1': MSG_LATER,
            'charge_2': MSG_LATER,
            'charge_3': MSG_LATER,
            'stop': MSG_SENT,
            'set_0': MSG_MODE,
            'set_1': MSG_MODE,
            'inquiry': MSG_INQ,
            'help': MSG_HELP,
}

XML_REPLY = '''<xml>
        <ToUserName><![CDATA[{}]]></ToUserName>
        <FromUserName><![CDATA[{}]]></FromUserName>
        <CreateTime>{}</CreateTime>
        <MsgType><![CDATA[text]]></MsgType>
        <Content><![CDATA[{}]]></Content>
        </xml>'''