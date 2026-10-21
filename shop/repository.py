from sqlalchemy import text
from database import engine
def find_shop_by_id(shop_id: int) -> dict | None:
    statement = text("SELECT id, name, address, phone, status, owner_id FROM shops WHERE id = :shop_id")
    with engine.connect() as connection:
        result = connection.execute(statement, {"shop_id": shop_id})
        row=result.mappings().first()
        if row is None:
            return None
        return dict(row)
def insert_shop(name: str, address: str, phone: str, owner_id: int) -> int:
    statement = text("INSERT INTO shops (name, address, phone, owner_id) VALUES (:name, :address, :phone, :owner_id)")
    with engine.begin() as connection:
        result = connection.execute(statement, {"name": name, "address": address, "phone": phone, "owner_id": owner_id})
        shop_id = result.lastrowid
        return int(shop_id)
def find_shops(page: int, page_size: int, keyword: str | None = None) -> dict:
    conditions=""
    paraneters={
        "limit": page_size,
        "offset": (page - 1) * page_size,
    }
    if keyword:
        conditions="WHERE name LIKE :keyword"
        paraneters["keyword"] = f"%{keyword}%"
    count_statement = text(f"SELECT COUNT(*) AS total FROM shops {conditions}")
    list_statement = text(f"SELECT id, name, address, phone, status, owner_id FROM shops {conditions} ORDER BY id LIMIT :limit OFFSET :offset")
    with engine.connect() as connection:
        total=connection.execute(count_statement, paraneters).scalar_one()
        result=connection.execute(list_statement, paraneters,)
        items=[]
        for row in result.mappings():
            items.append(dict(row))
    return {
        "total": total,
        "items": items,
     }

def update_shop(shop_id: int, name: str, address: str, phone: str, owner_id: int) -> None:
    statement = text("UPDATE shops SET name = :name, address = :address, phone = :phone WHERE id = :shop_id AND owner_id = :owner_id")
    with engine.begin() as connection:
        connection.execute(statement, {"shop_id": shop_id, "name": name, "address": address, "phone": phone, "owner_id": owner_id})


def update_shop_status(shop_id: int, status: int, owner_id: int) -> None:
    statement = text("UPDATE shops SET status = :status WHERE id = :shop_id AND owner_id = :owner_id")
    with engine.begin() as connection:
        connection.execute(statement, {"shop_id": shop_id, "status": status, "owner_id": owner_id})
