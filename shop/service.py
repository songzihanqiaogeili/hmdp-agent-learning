from shop.repository import find_shop_by_id, insert_shop, find_shops
from shop.repository import update_shop as update_shop_record   
from shop.repository import update_shop_status as update_shop_status_record
def get_shop_by_id(shop_id: int) -> dict | None:
    return find_shop_by_id(shop_id)
def get_shops(page: int, page_size: int,keyword:str | None = None) -> dict:
    result=find_shops(page=page, page_size=page_size, keyword=keyword)
    total=result["total"]
    total_pages=(total+page_size-1)//page_size
    return {
        "total": total,
        "total_pages": total_pages,
        "page": page,
        "page_size": page_size,
        "items": result["items"],
    }
def require_shop_owner(shop: dict, user_id: int) -> None:
    """Exercise: understand and rewrite this ownership check yourself."""
    if shop["owner_id"] != user_id:
        raise PermissionError("只能修改自己的商铺")


def create_shop(name: str, address: str, phone: str, user_id: int) -> dict:
    shop_id = insert_shop(name, address, phone, user_id)
    shop = find_shop_by_id(shop_id)
    if shop is None:
        raise RuntimeError("商铺创建后未能查询到")
    return shop


def update_shop(shop_id: int, name: str, address: str, phone: str, user_id: int) -> dict | None:
    shop = find_shop_by_id(shop_id)
    if shop is None:
        return None
    require_shop_owner(shop, user_id)
    update_shop_record(shop_id, name, address, phone, user_id)
    return find_shop_by_id(shop_id)


def change_shop_status(shop_id: int, status: int, user_id: int) -> dict | None:
    shop = find_shop_by_id(shop_id)
    if shop is None:
        return None
    require_shop_owner(shop, user_id)
    update_shop_status_record(shop_id, status, user_id)
    return find_shop_by_id(shop_id)
