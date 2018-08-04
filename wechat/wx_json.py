# import json

# to_user = 'abcccc'
# temp_id = '123333443X343ddd'
# val = 8.8
# val2 = 32

j_dict = \
    {
        "touser": to_user,
        "template_id": temp_id,
        "data": {
            "label": {
                "value": "charge finished！",
                "color": "#173177"
            },
            "note1": {
                "value": val,
                "color": "#173177"
            },
            "note2": {
                "value": val2,
                "color": "#173177"
            },
            "note3": {
                "value": "2018年9月22日",
                "color": "#173177"
            },
            "end": {
                "value": "欢迎再次购买！",
                "color": "#173177"
            }
        }
    }

# j = json.dumps(result)
