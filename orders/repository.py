from sqlalchemy import text
from sqlalchemy.engine import Connection


def find_order_by_key(connection: Connection, user_id: int, key: str) -> dict | None:
    row = connection.execute(
        text("SELECT * FROM orders WHERE user_id = :user_id AND idempotency_key = :key"),
        {"user_id": user_id, "key": key},
    ).mappings().first()
    return dict(row) if row is not None else None


def find_order_by_id(connection: Connection, order_id: int, user_id: int) -> dict | None:
    row = connection.execute(
        text("SELECT * FROM orders WHERE id = :order_id AND user_id = :user_id"),
        {"order_id": order_id, "user_id": user_id},
    ).mappings().first()
    return dict(row) if row is not None else None


def lock_order(connection: Connection, order_id: int, user_id: int) -> dict | None:
    lock = " FOR UPDATE" if connection.dialect.name == "mysql" else ""
    row = connection.execute(
        text("SELECT * FROM orders WHERE id = :order_id AND user_id = :user_id" + lock),
        {"order_id": order_id, "user_id": user_id},
    ).mappings().first()
    return dict(row) if row is not None else None


def lock_product(connection: Connection, product_id: int) -> dict | None:
    # MySQL 在事务内锁定商品和匹配的商铺行，稳定价格、状态和库存。
    # SQLite 仅用于快速测试业务与回滚，不用于证明 MySQL 的并发行为。
    lock = " FOR UPDATE" if connection.dialect.name == "mysql" else ""
    row = connection.execute(
        text("""SELECT p.id, p.shop_id, p.name, p.price, p.stock,
                    p.status, s.status AS shop_status
                FROM products p JOIN shops s ON s.id = p.shop_id
                WHERE p.id = :product_id""" + lock),
        {"product_id": product_id},
    ).mappings().first()
    return dict(row) if row is not None else None


def insert_order(connection: Connection, values: dict) -> int:
    deadline = "DATE_ADD(CURRENT_TIMESTAMP, INTERVAL 15 MINUTE)" if connection.dialect.name == "mysql" else "datetime('now', '+15 minutes')"
    result = connection.execute(
        text(f"""INSERT INTO orders
            (user_id, product_id, shop_id, product_name, unit_price,
             quantity, total_amount, idempotency_key, expires_at)
            VALUES (:user_id, :product_id, :shop_id, :product_name, :unit_price,
                    :quantity, :total_amount, :idempotency_key, {deadline})"""),
        values,
    )
    return int(result.lastrowid)


def deduct_stock(connection: Connection, product_id: int, quantity: int) -> bool:
    result = connection.execute(
        text("""UPDATE products SET stock = stock - :quantity
                WHERE id = :product_id AND status = 1 AND stock >= :quantity"""),
        {"product_id": product_id, "quantity": quantity},
    )
    return result.rowcount == 1


def list_orders(connection: Connection, user_id: int, page: int, page_size: int) -> dict:
    parameters = {"user_id": user_id, "limit": page_size, "offset": (page - 1) * page_size}
    total = connection.execute(
        text("SELECT COUNT(*) FROM orders WHERE user_id = :user_id"), parameters,
    ).scalar_one()
    rows = connection.execute(
        text("""SELECT * FROM orders WHERE user_id = :user_id
                ORDER BY id DESC LIMIT :limit OFFSET :offset"""), parameters,
    ).mappings()
    return {"total": total, "items": [dict(row) for row in rows]}


def cancel_pending_order(connection: Connection, order_id: int, user_id: int ) -> bool:
    result = connection.execute(
        text("""UPDATE orders SET status = 'cancelled'
                WHERE id = :order_id AND user_id = :user_id AND status = 'pending'"""),
        {"order_id": order_id, "user_id": user_id},
    )
    return result.rowcount == 1

def restore_stock(connection: Connection, product_id: int, quantity: int) -> None:
    result = connection.execute(
        text("""UPDATE products SET stock = stock + :quantity
                WHERE id = :product_id """),
        {"product_id": product_id, "quantity": quantity},
    )
    if result.rowcount != 1:
        raise RuntimeError("返还库存失败")


def mark_pending_paid(connection: Connection, order_id: int, user_id: int) -> bool:
    result = connection.execute(
        text("""UPDATE orders SET status = 'paid'
                WHERE id = :order_id AND user_id = :user_id AND status = 'pending'
                  AND expires_at > CURRENT_TIMESTAMP"""),
        {"order_id": order_id, "user_id": user_id},
    )
    return result.rowcount == 1


def expire_pending_order(connection: Connection, order_id: int, user_id: int) -> bool:
    result = connection.execute(
        text("""UPDATE orders SET status = 'expired'
                WHERE id = :order_id AND user_id = :user_id AND status = 'pending'
                  AND expires_at <= CURRENT_TIMESTAMP"""),
        {"order_id": order_id, "user_id": user_id},
    )
    return result.rowcount == 1


def find_due_orders(connection: Connection, limit: int) -> list[dict]:
    rows = connection.execute(
        text("""SELECT id, user_id FROM orders
                WHERE status = 'pending' AND expires_at <= CURRENT_TIMESTAMP
                ORDER BY expires_at, id LIMIT :limit"""),
        {"limit": limit},
    ).mappings()
    return [dict(row) for row in rows]
