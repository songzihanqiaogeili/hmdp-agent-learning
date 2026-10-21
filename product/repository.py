from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.engine import Connection


PRODUCT_COLUMNS = "p.id, p.shop_id, p.name, p.description, p.price, p.stock, p.status, p.created_at"


def find_shop(connection: Connection, shop_id: int) -> dict | None:
    row = connection.execute(
        text("SELECT id, owner_id, status FROM shops WHERE id = :shop_id"),
        {"shop_id": shop_id},
    ).mappings().first()
    return dict(row) if row is not None else None


def find_product(connection: Connection, product_id: int, public_only: bool = False) -> dict | None:
    condition = "AND p.status = 1 AND s.status = 1" if public_only else ""
    row = connection.execute(
        text(f"""SELECT {PRODUCT_COLUMNS}, s.owner_id
                 FROM products p JOIN shops s ON s.id = p.shop_id
                 WHERE p.id = :product_id {condition}"""),
        {"product_id": product_id},
    ).mappings().first()
    return dict(row) if row is not None else None


def insert_product(connection: Connection, shop_id: int, user_id: int, data: dict) -> int | None:
    # 写入时再次限制归属；不接受请求体指定 owner_id 或 status。
    result = connection.execute(
        text("""INSERT INTO products (shop_id, name, description, price, stock)
             SELECT id, :name, :description, :price, :stock
             FROM shops WHERE id = :shop_id AND owner_id = :user_id"""),
        {**data, "shop_id": shop_id, "user_id": user_id},
    )
    return int(result.lastrowid) if result.rowcount == 1 else None


def update_product(connection: Connection, product_id: int, user_id: int, data: dict) -> None:
    connection.execute(
        text("""UPDATE products SET name = :name, description = :description, price = :price
             WHERE id = :product_id AND EXISTS (
                 SELECT 1 FROM shops WHERE shops.id = products.shop_id AND owner_id = :user_id
             )"""),
        {**data, "product_id": product_id, "user_id": user_id},
    )


def set_product_status(connection: Connection, product_id: int, user_id: int, status: int) -> None:
    connection.execute(
        text("""UPDATE products SET status = :status
             WHERE id = :product_id AND EXISTS (
                 SELECT 1 FROM shops WHERE shops.id = products.shop_id AND owner_id = :user_id
             )"""),
        {"product_id": product_id, "user_id": user_id, "status": status},
    )


def find_public_products(connection: Connection, shop_id: int, page: int, page_size: int) -> dict:
    parameters = {"shop_id": shop_id, "limit": page_size, "offset": (page - 1) * page_size}
    source = "FROM products p JOIN shops s ON s.id = p.shop_id WHERE p.shop_id = :shop_id AND p.status = 1 AND s.status = 1"
    total = connection.execute(text(f"SELECT COUNT(*) {source}"), parameters).scalar_one()
    rows = connection.execute(
        text(f"SELECT {PRODUCT_COLUMNS} {source} ORDER BY p.id LIMIT :limit OFFSET :offset"),
        parameters,
    ).mappings()
    return {"total": total, "items": [dict(row) for row in rows]}


def input_values(data) -> dict:
    values = data.model_dump()
    # 将十进制金额按精确文本交给驱动，不转换为 float。
    if isinstance(values.get("price"), Decimal):
        values["price"] = str(values["price"])
    return values
