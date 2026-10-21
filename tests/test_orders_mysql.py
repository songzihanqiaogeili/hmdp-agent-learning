"""Opt-in MySQL integration tests. Creates and removes only its own fixture rows.

Run after sql/004_orders.sql:
python -c "import os,unittest; os.environ['RUN_MYSQL_TESTS']='1'; unittest.main(module=None, argv=['test','discover','-s','tests','-p','test_orders_mysql.py','-v'])"
"""
import os
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import text

from database import engine
from orders import service
from orders.schemas import OrderCreate


@unittest.skipUnless(os.environ.get("RUN_MYSQL_TESTS") == "1", "opt-in real MySQL test")
class MySQLOrderConcurrencyTests(unittest.TestCase):
    def setUp(self):
        self.user_id = self.shop_id = self.product_id = None
        self.addCleanup(self.cleanup_rows)
        with engine.begin() as c:
            self.user_id = c.execute(
                text("INSERT INTO users(phone,nickname) VALUES (:phone,'order test')"),
                {"phone": "test" + uuid.uuid4().hex[:12]},
            ).lastrowid
            self.shop_id = c.execute(
                text("INSERT INTO shops(name,address,phone,owner_id) VALUES ('order test','test','test',:owner)"),
                {"owner": self.user_id},
            ).lastrowid
            self.product_id = c.execute(
                text("""INSERT INTO products(shop_id,name,description,price,stock,status)
                        VALUES (:shop,'order test','test',19.90,5,1)"""),
                {"shop": self.shop_id},
            ).lastrowid

    def cleanup_rows(self):
        if self.user_id is None:
            return
        with engine.begin() as c:
            c.execute(text("DELETE FROM orders WHERE user_id = :id"), {"id": self.user_id})
            if self.product_id is not None:
                c.execute(text("DELETE FROM products WHERE id = :id"), {"id": self.product_id})
            if self.shop_id is not None:
                c.execute(text("DELETE FROM shops WHERE id = :id"), {"id": self.shop_id})
            c.execute(text("DELETE FROM users WHERE id = :id"), {"id": self.user_id})

    def test_concurrent_buyers_cannot_oversell(self):
        def buy(index):
            try:
                service.place_order(self.user_id, OrderCreate(product_id=self.product_id, quantity=1), f"stock-test-{index}")
                return True
            except service.OrderConflictError:
                return False
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(buy, range(16)))
        self.assertEqual(sum(results), 5)
        with engine.connect() as c:
            stock = c.execute(text("SELECT stock FROM products WHERE id = :id"), {"id": self.product_id}).scalar_one()
        self.assertEqual(stock, 0)
        self.assertEqual(service.list_my_orders(self.user_id, 1, 20)["total"], 5)

    def test_concurrent_same_key_creates_one_order(self):
        def buy(_):
            return service.place_order(self.user_id, OrderCreate(product_id=self.product_id, quantity=2), "same-key-test")
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(buy, range(16)))
        self.assertEqual(len({order["id"] for order, _ in results}), 1)
        self.assertEqual(sum(created for _, created in results), 1)
        with engine.connect() as c:
            stock = c.execute(text("SELECT stock FROM products WHERE id = :id"), {"id": self.product_id}).scalar_one()
        self.assertEqual(stock, 3)
        self.assertEqual(service.list_my_orders(self.user_id, 1, 20)["total"], 1)

    def test_concurrent_cancel_restores_stock_once(self):
        order, _ = service.place_order(self.user_id, OrderCreate(product_id=self.product_id, quantity=2), "cancel-test")
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: service.cancel_order(order["id"], self.user_id), range(16)))
        self.assertTrue(all(item["status"] == "cancelled" for item in results))
        with engine.connect() as c:
            stock = c.execute(text("SELECT stock FROM products WHERE id = :id"), {"id": self.product_id}).scalar_one()
        self.assertEqual(stock, 5)

    def test_pay_and_cancel_race_has_one_terminal_state(self):
        order, _ = service.place_order(self.user_id, OrderCreate(product_id=self.product_id, quantity=2), "pay-cancel-test")
        def act(index):
            operation = service.mock_pay_order if index % 2 == 0 else service.cancel_order
            try:
                return operation(order["id"], self.user_id)["status"]
            except service.OrderConflictError:
                return "conflict"
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(act, range(16)))
        order = service.get_my_order(order["id"], self.user_id)
        self.assertIn(order["status"], ("paid", "cancelled"))
        self.assertEqual(set(results), {order["status"], "conflict"})
        with engine.connect() as c:
            stock = c.execute(text("SELECT stock FROM products WHERE id = :id"), {"id": self.product_id}).scalar_one()
        self.assertEqual(stock, 3 if order["status"] == "paid" else 5)

    def test_concurrent_expiry_restores_once(self):
        order, _ = service.place_order(self.user_id, OrderCreate(product_id=self.product_id, quantity=2), "expiry-test")
        with engine.begin() as c:
            c.execute(text("UPDATE orders SET expires_at = '2000-01-01 00:00:00' WHERE id = :id"), {"id": order["id"]})
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: service.expire_order(order["id"], self.user_id), range(16)))
        self.assertEqual(sum(results), 1)
        self.assertEqual(service.get_my_order(order["id"], self.user_id)["status"], "expired")
        with engine.connect() as c:
            stock = c.execute(text("SELECT stock FROM products WHERE id = :id"), {"id": self.product_id}).scalar_one()
        self.assertEqual(stock, 5)

    def test_due_order_cannot_pay_during_cleanup(self):
        order, _ = service.place_order(self.user_id, OrderCreate(product_id=self.product_id, quantity=2), "expiry-test")
        with engine.begin() as c:
            c.execute(text("UPDATE orders SET expires_at = '2000-01-01 00:00:00' WHERE id = :id"), {"id": order["id"]})
        def act(index):
            if index % 2:
                return service.expire_order(order["id"], self.user_id)
            try:
                service.mock_pay_order(order["id"], self.user_id)
                raise AssertionError("due order was paid")
            except service.OrderConflictError:
                return False
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(act, range(16)))
        self.assertEqual(service.get_my_order(order["id"], self.user_id)["status"], "expired")
        with engine.connect() as c:
            stock = c.execute(text("SELECT stock FROM products WHERE id = :id"), {"id": self.product_id}).scalar_one()
        self.assertEqual(stock, 5)
