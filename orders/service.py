import logging
from decimal import Decimal

from sqlalchemy.exc import IntegrityError

from database import engine
from orders import repository
from orders.schemas import OrderCreate


class OrderNotFoundError(Exception):
    pass


class OrderConflictError(Exception):
    pass


def _check_replay(order: dict, data: OrderCreate) -> dict:
    if order["product_id"] != data.product_id or order["quantity"] != data.quantity:
        raise OrderConflictError("同一个幂等键不能用于不同的下单内容")
    return order


def place_order(user_id: int, data: OrderCreate, idempotency_key: str) -> tuple[dict, bool]:
    try:
        # 必须共用一个连接和事务；不能在两个各自提交的函数里扣库存、建订单。
        with engine.begin() as connection:
            existing = repository.find_order_by_key(connection, user_id, idempotency_key)
            if existing is not None:
                return _check_replay(existing, data), False

            product = repository.lock_product(connection, data.product_id)
            if product is None:
                raise OrderNotFoundError("套餐不存在")
            if product["status"] != 1 or product["shop_status"] != 1:
                raise OrderConflictError("套餐已下架或商铺休息中")

            unit_price = Decimal(str(product["price"]))
            total_amount = unit_price * data.quantity
            order_id = repository.insert_order(connection, {
                "user_id": user_id,
                "product_id": product["id"],
                "shop_id": product["shop_id"],
                "product_name": product["name"],
                "unit_price": str(unit_price),
                "quantity": data.quantity,
                "total_amount": str(total_amount),
                "idempotency_key": idempotency_key,
            })

            if not repository.deduct_stock(connection, data.product_id, data.quantity):
                # 抛出异常离开事务，刚插入的订单也会回滚。
                raise OrderConflictError("库存不足，请调整购买数量")

            order = repository.find_order_by_id(connection, order_id, user_id)
            if order is None:
                raise RuntimeError("订单创建后未能查询到")
        return order, True
    except IntegrityError:
        # 唯一约束兜底：并发请求可能都没有查到旧订单。
        # 此处原事务已回滚，重新取连接查询已提交的结果。
        with engine.connect() as connection:
            existing = repository.find_order_by_key(connection, user_id, idempotency_key)
        if existing is None:
            raise
        return _check_replay(existing, data), False


def get_my_order(order_id: int, user_id: int) -> dict:
    with engine.connect() as connection:
        order = repository.find_order_by_id(connection, order_id, user_id)
    if order is None:
        # 不泄露该订单是否属于其他用户。
        raise OrderNotFoundError("订单不存在")
    return order


def list_my_orders(user_id: int, page: int, page_size: int) -> dict:
    with engine.connect() as connection:
        result = repository.list_orders(connection, user_id, page, page_size)
    return {
        **result,
        "total_pages": (result["total"] + page_size - 1) // page_size,
        "page": page,
        "page_size": page_size,
    }

def cancel_order(order_id: int, user_id: int) -> dict:
    with engine.begin() as connection:
        order = repository.lock_order(connection, order_id, user_id)
        if order is None:
            raise OrderNotFoundError("订单不存在")
        if order["status"] == "cancelled":
            return order
        if order["status"] != "pending":
            raise OrderConflictError("当前订单不能直接取消，已支付订单需要申请退款")

        changed = repository.cancel_pending_order(connection, order_id, user_id)
        if not changed:
            raise OrderConflictError("订单状态已变化，请刷新后重试")
        repository.restore_stock(connection, order["product_id"], order["quantity"])
        order = repository.find_order_by_id(connection, order_id, user_id)
        if order is None:
            raise RuntimeError("取消后未能查询到订单")
    return order


def mock_pay_order(order_id: int, user_id: int) -> dict:
    """本地模拟支付，不代表支付平台回调，也不会发生真实资金交易。"""
    expired = False
    with engine.begin() as connection:
        order = repository.lock_order(connection, order_id, user_id)
        if order is None:
            raise OrderNotFoundError("订单不存在")
        if order["status"] == "paid":
            return order
        if order["status"] != "pending":
            raise OrderConflictError("订单已取消或已超时，不能支付")

        if not repository.mark_pending_paid(connection, order_id, user_id):
            expired = _expire_locked_order(connection, order)
            if not expired:
                raise OrderConflictError("订单状态已变化，请刷新后重试")
        # 库存在下单时已扣减，支付不能再扣一次。
        order = repository.find_order_by_id(connection, order_id, user_id)
        if order is None:
            raise RuntimeError("支付后未能查询到订单")
    # 必须先退出 with 提交关闭和返库存，再向客户端报告超时。
    # 在事务内 raise 会把刚完成的关单也回滚。
    if expired:
        raise OrderConflictError("订单支付超时，已关闭并返还库存")
    return order


def _expire_locked_order(connection, order: dict) -> bool:
    changed = repository.expire_pending_order(connection, order["id"], order["user_id"])
    if changed:
        repository.restore_stock(connection, order["product_id"], order["quantity"])
    return changed


def expire_order(order_id: int, user_id: int) -> bool:
    """内部清理任务使用，不对外提供可传任意 user_id 的接口。"""
    with engine.begin() as connection:
        order = repository.lock_order(connection, order_id, user_id)
        if order is None or order["status"] != "pending":
            return False
        return _expire_locked_order(connection, order)


def expire_pending_orders(batch_size: int = 100, max_batches: int = 10) -> dict:
    if not 1 <= batch_size <= 1000 or not 1 <= max_batches <= 1000:
        raise ValueError("batch_size 和 max_batches 必须在 1 到 1000 之间")
    summary = {"examined": 0, "expired": 0, "failed": 0}
    for _ in range(max_batches):
        with engine.connect() as connection:
            candidates = repository.find_due_orders(connection, batch_size)
        if not candidates:
            break
        for candidate in candidates:
            summary["examined"] += 1
            try:
                summary["expired"] += int(expire_order(candidate["id"], candidate["user_id"]))
            except Exception:
                # 单笔失败不阻止其他订单清理；事务会回滚，后续任务可重试。
                summary["failed"] += 1
                logging.getLogger(__name__).exception("超时订单清理失败 order_id=%s", candidate["id"])
        if len(candidates) < batch_size or summary["failed"]:
            break
    return summary
