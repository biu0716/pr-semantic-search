TERMINOLOGY_RULES = {
    "奔驰": "梅赛德斯-奔驰",
    "德国时间": "欧洲中部时间（CET）",
    "新车": "全新车型",
    "8座": "最多可提供8座选择",
    "发布会": "发布活动"
}


def normalize_text(text):

    for k, v in TERMINOLOGY_RULES.items():
        text = text.replace(k, v)

    return text