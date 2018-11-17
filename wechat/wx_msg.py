MSG_SENT = ("command has been sent\n"
            "you will be notified")

MSG_LATER = "charging scheduled for later"

MSG_HELP = ("help\n"
            "help\n")

MSG_MODE = "changing mode"

msg_dict = {
            'charge_0': MSG_SENT,
            'charge_1': MSG_LATER,
            'charge_2': MSG_LATER,
            'charge_3': MSG_LATER,
            'stop': MSG_SENT,
            'set_0': MSG_MODE,
            'set_1': MSG_MODE,
            'inquiry': MSG_SENT,
            'help': MSG_HELP,
}

XML_REPLY = '''<xml>
        <ToUserName><![CDATA[{to_user}]]></ToUserName>
        <FromUserName><![CDATA[{from_user}]]></FromUserName>
        <CreateTime>{create_time}</CreateTime>
        <MsgType><![CDATA[text]]></MsgType>
        <Content><![CDATA[{content}]]></Content>
        </xml>'''