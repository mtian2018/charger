def form_xml(root, content):
    """format wechat text response xml"""

    xml_form = '''<xml>
            <ToUserName><![CDATA[{ToUserName}]]></ToUserName>
            <FromUserName><![CDATA[{FromUserName}]]></FromUserName>
            <CreateTime>{CreateTime}</CreateTime>
            <MsgType><![CDATA[text]]></MsgType>
            <Content><![CDATA[{Content}]]></Content>
            </xml>'''

    to_user = root.find('FromUserName').text
    from_user = root.find('ToUserName').text

    xml_dict = {'ToUserName': to_user,
                'FromUserName': from_user,
                'CreateTime': int(time()),
                'Content': content}

    return xml_form.format_map(xml_dict)
