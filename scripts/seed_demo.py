"""本地开发测试数据。复用已登记记录，不重置用户已经操作过的订单。"""
import argparse
import hashlib
import json
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text

from orders import repository as order_repository
from product import repository as product_repository


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ACCOUNT_PHONES = {"a": "19900000101", "b": "19900000102"}
PREFIX = "hmdp-demo/v1"
ENTITY_TABLES = {"user": "users", "shop": "shops", "product": "products", "order": "orders"}


def _lookup(connection, key: str, kind: str) -> dict | None:
    entry = connection.execute(
        text("SELECT entity_type, entity_id FROM demo_seed_registry WHERE seed_key = :key"),
        {"key": key},
    ).mappings().first()
    if entry is None:
        return None
    if entry["entity_type"] != kind:
        raise RuntimeError("测试数据登记类型不一致")
    table = ENTITY_TABLES[kind]
    row = connection.execute(text(f"SELECT * FROM {table} WHERE id = :id"), {"id": entry["entity_id"]}).mappings().first()
    if row is None:
        raise RuntimeError(f"登记的测试记录已被手动删除：{key}；请检查 demo_seed_registry")
    return dict(row)


def _register(connection, key: str, kind: str, entity_id: int) -> None:
    connection.execute(
        text("INSERT INTO demo_seed_registry(seed_key, entity_type, entity_id) VALUES (:key, :kind, :id)"),
        {"key": key, "kind": kind, "id": entity_id},
    )


def _account(connection, label: str) -> dict:
    key = f"{PREFIX}/users/{label}"
    user = _lookup(connection, key, "user")
    phone = ACCOUNT_PHONES[label]
    if user is not None:
        if user["phone"] != phone:
            raise ValueError("测试账号手机号已被修改，拒绝自动覆盖")
        return user
    existing = connection.execute(text("SELECT id FROM users WHERE phone = :phone"), {"phone": phone}).first()
    if existing is not None:
        raise ValueError(f"测试手机号 {phone} 已被非脚本账号使用，未覆盖；请修改 ACCOUNT_PHONES")
    user_id = connection.execute(
        text("INSERT INTO users(phone,nickname) VALUES (:phone,:nickname)"),
        {"phone": phone, "nickname": f"[DEMO] 测试账号{label.upper()}"},
    ).lastrowid
    _register(connection, key, "user", user_id)
    return _lookup(connection, key, "user")


def _shop(connection, base: str, label: str, user: dict) -> dict:
    key = f"{base}/shops/{label}"
    shop = _lookup(connection, key, "shop")
    if shop is None:
        shop_id = connection.execute(
            text("""INSERT INTO shops(name,address,phone,owner_id,status)
                    VALUES (:name,:address,:phone,:owner,1)"""),
            {"name": f"[DEMO] {base.split('/')[-1]} 店铺{label.upper()}", "address": "本地测试地址", "phone": user["phone"], "owner": user["id"]},
        ).lastrowid
        _register(connection, key, "shop", shop_id)
        shop = _lookup(connection, key, "shop")
    if shop["owner_id"] != user["id"]:
        raise ValueError("测试店铺归属已被修改，拒绝自动覆盖")
    return shop


def _product(connection, base: str, label: str, shop: dict, stock: int = 20) -> dict:
    key = f"{base}/products/{label}"
    product = _lookup(connection, key, "product")
    if product is None:
        product_id = product_repository.insert_product(
            connection, shop["id"], shop["owner_id"],
            {"name": f"[DEMO] {label} 套餐", "description": "脚本生成的本地测试数据", "price": "49.90", "stock": stock},
        )
        if product_id is None:
            raise RuntimeError("测试商品创建失败")
        product_repository.set_product_status(connection, product_id, shop["owner_id"], 1)
        _register(connection, key, "product", product_id)
        product = _lookup(connection, key, "product")
    if product["shop_id"] != shop["id"]:
        raise ValueError("测试商品所属店铺不一致，拒绝自动覆盖")
    return product


def _scenario(connection, base: str, label: str, target: str, user: dict, shop: dict) -> dict:
    product = _product(connection, base, label, shop)
    key = f"{base}/orders/{label}"
    order = _lookup(connection, key, "order")
    if order is None:
        order_id = order_repository.insert_order(connection, {
            "user_id": user["id"], "product_id": product["id"], "shop_id": shop["id"],
            "product_name": product["name"], "unit_price": "49.90", "quantity": 2,
            "total_amount": "99.80", "idempotency_key": f"demo-{base.split('/')[-1]}-{label}",
        })
        if not order_repository.deduct_stock(connection, product["id"], 2):
            raise RuntimeError("测试商品库存不足；未保留半完成场景")
        if target == "paid":
            if not order_repository.mark_pending_paid(connection, order_id, user["id"]):
                raise RuntimeError("测试支付失败")
        elif target == "cancelled":
            if not order_repository.cancel_pending_order(connection, order_id, user["id"]):
                raise RuntimeError("测试取消失败")
            order_repository.restore_stock(connection, product["id"], 2)
        elif target in ("expired", "due"):
            connection.execute(text("UPDATE orders SET expires_at = '2000-01-01 00:00:00' WHERE id = :id"), {"id": order_id})
            if target == "expired":
                if not order_repository.expire_pending_order(connection, order_id, user["id"]):
                    raise RuntimeError("测试关单失败")
                order_repository.restore_stock(connection, product["id"], 2)
        _register(connection, key, "order", order_id)
        order = _lookup(connection, key, "order")
    if order["user_id"] != user["id"] or order["product_id"] != product["id"]:
        raise ValueError("已登记订单与测试场景不一致，拒绝自动覆盖")
    product = _lookup(connection, f"{base}/products/{label}", "product")
    return {
        "order_id": order["id"], "user_id": user["id"], "product_id": product["id"],
        "status": order["status"], "quantity": order["quantity"], "stock": product["stock"],
        "expires_at": str(order["expires_at"]),
    }


def seed_database(engine, set_name: str = "demo-v1") -> dict:
    if re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,31}", set_name) is None:
        raise ValueError("批次名只能包含小写字母、数字、下划线、连字符，最长32位")
    with engine.begin() as c:
        c.execute(text("""CREATE TABLE IF NOT EXISTS demo_seed_registry (
            seed_key VARCHAR(160) PRIMARY KEY,
            entity_type VARCHAR(16) NOT NULL,
            entity_id BIGINT NOT NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""))

    # 防止两个初始化进程同时创建同一批数据；MySQL 命名锁持续到显式释放。
    lock_name = "hmdp-demo-" + hashlib.sha256(str(engine.url.database).encode()).hexdigest()[:16]
    with engine.connect() as c:
        acquired = False
        try:
            if c.dialect.name == "mysql":
                acquired = c.execute(text("SELECT GET_LOCK(:name, 10)"), {"name": lock_name}).scalar_one() == 1
                c.commit()
                if not acquired:
                    raise RuntimeError("另一个初始化脚本正在运行，请稍后重试")
            with c.begin():
                base = f"{PREFIX}/{set_name}"
                users = {label: _account(c, label) for label in ("a", "b")}
                shops = {label: _shop(c, base, label, users[label]) for label in ("a", "b")}
                ready = {label: _product(c, base, f"ready-{label}", shops[label], 100) for label in ("a", "b")}
                scenarios = {state: _scenario(c, base, state, state, users["a"], shops["a"]) for state in ("pending", "paid", "cancelled", "expired", "due")}
                scenarios["b_pending"] = _scenario(c, base, "b_pending", "pending", users["b"], shops["b"])
                report = {
                    "set": set_name,
                    "accounts": {label: {"id": user["id"], "phone": user["phone"], "nickname": user["nickname"], "shop_id": shops[label]["id"], "ready_product_id": ready[label]["id"]} for label, user in users.items()},
                    "scenarios": scenarios,
                    "note": "重复运行保留当前状态，不重置库存；需要新场景请更换 --set 批次名。",
                }
            return report
        finally:
            if acquired:
                c.execute(text("SELECT RELEASE_LOCK(:name)"), {"name": lock_name})


def write_report(report: dict) -> Path:
    folder = PROJECT_ROOT / ".local"
    folder.mkdir(exist_ok=True)
    path = folder / "demo-data.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_demo_logins(report: dict) -> Path:
    """仅供本地 CLI 使用。通过现有验证码登录业务生成两个测试账号的登录态。"""
    from redis_client import redis_client
    from user.service import login

    sessions = {}
    for label, account in report["accounts"].items():
        phone = account["phone"]
        code = f"{secrets.randbelow(1000000):06d}"
        key = f"hmdp:login:code:{phone}"
        with redis_client.pipeline(transaction=True) as pipe:
            pipe.set(key, code, ex=300)
            pipe.delete(f"{key}:attempts")
            pipe.set(f"hmdp:login:cooldown:{phone}", "1", ex=60)
            pipe.execute()
        result = login(phone, code)
        sessions[label] = {"phone": phone, **result}
    path = PROJECT_ROOT / ".local" / "demo-tokens.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps({"created_at_utc": datetime.now(timezone.utc).isoformat(), "accounts": sessions}, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="创建可复用的本地测试数据，不清空业务记录")
    parser.add_argument("--set", default="demo-v1", dest="set_name", help="相同批次复用；新批次创建新的商铺、商品和订单")
    parser.add_argument("--login", action="store_true", help="还需 Redis；把两个测试账号的 Token 写到 .local/demo-tokens.json")
    args = parser.parse_args()
    from database import engine
    report = seed_database(engine, args.set_name)
    path = write_report(report)
    print(f"数据清单: {path}")
    for label, account in report["accounts"].items():
        print(f"账号{label.upper()}: phone={account['phone']} user_id={account['id']} shop_id={account['shop_id']} product_id={account['ready_product_id']}")
    for label, item in report["scenarios"].items():
        print(f"{label}: order_id={item['order_id']} product_id={item['product_id']} status={item['status']} stock={item['stock']}")
    if args.login:
        print(f"测试 Token 文件（不在终端显示凭证）: {write_demo_logins(report)}")
    print(report["note"])


if __name__ == "__main__":
    main()
