shops = {
    1: {
        "id": 1,
        "name": "老街火锅",
        "address": "人民路 18 号",
        "phone": "13800000000",
    },
    2: {
        "id": 2,
        "name": "巷口咖啡",
        "address": "建设路 26 号",
        "phone": "13800000001",
    },
    3: {
    "id": 3,
    "name": "川味火锅",
    "address": "中山路 30 号",
    "phone": "010-11223344",
    },
}


def get_shop_by_id(shop_id: int) -> dict | None:
    return shops.get(shop_id)
def get_shop_id(shop: dict) -> int:
    return shop["id"]
def get_shops(page: int, page_size: int,keyword:str | None = None) -> dict:
    matched_shops = []
    for shop in shops.values():
        if keyword is None or keyword in shop["name"]:
            matched_shops.append(shop)
    all_shops = sorted(
        matched_shops,
        key=get_shop_id,
    )
    total = len(all_shops)
    total_pages = (total + page_size - 1) // page_size
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "total": total,
        "total_pages": total_pages,
        "page": page,
        "page_size": page_size,
        "items": all_shops[start:end],
    }
