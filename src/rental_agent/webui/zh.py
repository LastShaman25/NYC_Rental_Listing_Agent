"""Chinese rendering for Studio facts (owner rule 2026-08-18: posts are
natural Chinese; no English except brand names, transit lines, and station
names). Facts are stored in English; translating them deterministically here
beats hoping the 7B model translates them itself."""

LAUNDRY_ZH = {
    "IN_UNIT_WASHER_DRYER_CONFIRMED": "室内洗烘（已确认）",
    "IN_UNIT_WASHER_ONLY": "室内洗衣机",
    "IN_UNIT_DRYER_ONLY": "室内烘干机",
    "IN_UNIT_HOOKUP_ONLY": "洗烘接口",
    "BUILDING_SHARED_LAUNDRY": "楼内洗衣房",
    "OFFSITE_OR_NEARBY_LAUNDRY": "附近有洗衣店",
    "EXPLICITLY_NO_LAUNDRY": "无洗衣设施",
}

# Substring (lowercased) -> Chinese label. First match wins; unmatched
# amenities are dropped from the facts block rather than shown in English.
_AMENITY_ZH = [
    ("fitness", "健身房"),
    ("gym", "健身房"),
    ("doorman", "门卫"),
    ("concierge", "礼宾服务"),
    ("elevator", "电梯"),
    ("laundry", "洗衣房"),
    ("washer", "室内洗烘"),
    ("dryer", "室内洗烘"),
    ("dishwasher", "洗碗机"),
    ("roof", "屋顶露台"),
    ("terrace", "露台"),
    ("balcon", "阳台"),
    ("pool", "泳池"),
    ("parking", "车库停车"),
    ("garage", "车库停车"),
    ("bike", "自行车房"),
    ("storage", "储物间"),
    ("package", "快递室"),
    ("mail", "快递室"),
    ("super", "驻楼super"),
    ("pet", "可养宠物"),
    ("playground", "儿童游乐区"),
    ("lounge", "住户休息室"),
    ("media", "影音室"),
    ("theater", "影音室"),
    ("yoga", "瑜伽房"),
    ("sauna", "桑拿"),
    ("bbq", "烧烤区"),
    ("grill", "烧烤区"),
    ("garden", "花园"),
    ("courtyard", "庭院"),
    ("shuttle", "班车"),
    ("business center", "商务中心"),
    ("coworking", "共享办公区"),
    ("hardwood", "木地板"),
    ("stainless", "不锈钢厨电"),
    ("central air", "中央空调"),
    ("air condition", "空调"),
    ("heat", "暖气"),
    ("wifi", "WiFi"),
    ("valet", "代客泊车"),
    ("spa", "水疗"),
    ("tennis", "网球场"),
    ("basketball", "篮球场"),
    ("playroom", "儿童活动室"),
    ("game", "游戏室"),
    ("golf", "高尔夫模拟室"),
    ("dry clean", "干洗服务"),
]

_CUISINE_ZH = [
    ("japanese", "日料"),
    ("sushi", "日料"),
    ("korean", "韩餐"),
    ("chinese", "中餐"),
    ("mexican", "墨西哥菜"),
    ("italian", "意大利菜"),
    ("thai", "泰餐"),
    ("vietnamese", "越南菜"),
    ("indian", "印度菜"),
    ("mediterranean", "地中海菜"),
    ("middle eastern", "中东菜"),
    ("halal", "清真"),
    ("american", "美式餐厅"),
    ("southern", "美式南方菜"),
    ("caribbean", "加勒比菜"),
    ("west african", "西非菜"),
    ("african", "非洲菜"),
    ("dominican", "多米尼加菜"),
    ("latin", "拉美菜"),
    ("spanish", "西班牙菜"),
    ("french", "法餐"),
    ("greek", "希腊菜"),
    ("pizza", "披萨"),
    ("burger", "汉堡"),
    ("cafe", "咖啡店"),
    ("coffee", "咖啡店"),
    ("bakery", "烘焙店"),
    ("dessert", "甜品店"),
    ("bar", "酒吧"),
    ("brunch", "早午餐"),
    ("seafood", "海鲜"),
    ("bbq", "烧烤"),
    ("steak", "牛排馆"),
    ("ramen", "拉面"),
    ("dumpling", "饺子馆"),
    ("bubble tea", "奶茶店"),
    ("deli", "熟食店"),
]

TRANSIT_MODE_ZH = {"SUBWAY": "地铁", "BUS": "公交", "PATH": "PATH"}


def _translate(items: list[str], table: list[tuple[str, str]]) -> list[str]:
    seen: list[str] = []
    for item in items:
        lowered = str(item).lower()
        for needle, zh in table:
            if needle in lowered:
                if zh not in seen:
                    seen.append(zh)
                break
    return seen


def amenities_zh(amenities: list[str]) -> list[str]:
    """Translate amenity labels; untranslatable ones are dropped (never shown
    in English — owner rule)."""
    return _translate(amenities, _AMENITY_ZH)


def cuisines_zh(categories: list[str]) -> list[str]:
    return _translate(categories, _CUISINE_ZH)
