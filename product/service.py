from database import engine
from product import repository
from product.schemas import ProductCreate, ProductUpdate


class ProductNotFoundError(Exception):
    pass


class ProductForbiddenError(Exception):
    pass


def require_shop_owner(shop: dict, user_id: int) -> None:
    # 重点练习：比较数据库中的店主与 Token 识别出的用户。
    if shop["owner_id"] != user_id:
        raise ProductForbiddenError("只能管理自己商铺的套餐")


def create_product(shop_id: int, data: ProductCreate, user_id: int) -> dict:
    with engine.begin() as connection:
        shop = repository.find_shop(connection, shop_id)
        if shop is None:
            raise ProductNotFoundError("商铺不存在")
        require_shop_owner(shop, user_id)
        product_id = repository.insert_product(connection, shop_id, user_id, repository.input_values(data))
        if product_id is None:
            raise ProductForbiddenError("商铺归属已变化，请重试")
        product = repository.find_product(connection, product_id)
        if product is None:
            raise RuntimeError("套餐创建后未能查询到")
    return product


def get_product(product_id: int) -> dict:
    with engine.connect() as connection:
        product = repository.find_product(connection, product_id, public_only=True)
        if product is None:
            raise ProductNotFoundError("套餐不存在或暂不可售")
        return product


def list_products(shop_id: int, page: int, page_size: int) -> dict:
    with engine.connect() as connection:
        if repository.find_shop(connection, shop_id) is None:
            raise ProductNotFoundError("商铺不存在")
        result = repository.find_public_products(connection, shop_id, page, page_size)
    return {
        **result,
        "total_pages": (result["total"] + page_size - 1) // page_size,
        "page": page,
        "page_size": page_size,
    }


def _require_owned_product(connection, product_id: int, user_id: int) -> dict:
    product = repository.find_product(connection, product_id)
    if product is None:
        raise ProductNotFoundError("套餐不存在")
    require_shop_owner(product, user_id)
    return product


def update_product(product_id: int, data: ProductUpdate, user_id: int) -> dict:
    with engine.begin() as connection:
        _require_owned_product(connection, product_id, user_id)
        repository.update_product(connection, product_id, user_id, repository.input_values(data))
        product = _require_owned_product(connection, product_id, user_id)
    return product


def change_product_status(product_id: int, status: int, user_id: int) -> dict:
    with engine.begin() as connection:
        _require_owned_product(connection, product_id, user_id)
        repository.set_product_status(connection, product_id, user_id, status)
        product = _require_owned_product(connection, product_id, user_id)
    return product
