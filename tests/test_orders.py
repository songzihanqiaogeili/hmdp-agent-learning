import unittest
from decimal import Decimal
from unittest.mock import patch

from pydantic import ValidationError
from sqlalchemy import create_engine, text

from orders import service
from orders.schemas import OrderCreate, OrderResponse


class OrderTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        with self.engine.begin() as c:
            c.execute(text("CREATE TABLE shops (id INTEGER PRIMARY KEY, status INTEGER NOT NULL)"))
            c.execute(text("INSERT INTO shops VALUES (1, 1)"))
            c.execute(text("""CREATE TABLE products (
                id INTEGER PRIMARY KEY, shop_id INTEGER NOT NULL, name TEXT NOT NULL,
                price DECIMAL(10,2) NOT NULL, stock INTEGER NOT NULL CHECK(stock >= 0), status INTEGER NOT NULL)"""))
            c.execute(text("INSERT INTO products VALUES (1, 1, 'meal', 19.90, 5, 1)"))
            c.execute(text("""CREATE TABLE orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL, shop_id INTEGER NOT NULL,
                product_name TEXT NOT NULL, unit_price DECIMAL(10,2) NOT NULL,
                quantity INTEGER NOT NULL, total_amount DECIMAL(12,2) NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending', idempotency_key TEXT NOT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                expires_at DATETIME NOT NULL DEFAULT (datetime('now', '+15 minutes')),
                UNIQUE(user_id, idempotency_key))"""))
        self.patcher = patch.object(service, "engine", self.engine)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.addCleanup(self.engine.dispose)

    def stock(self):
        with self.engine.connect() as c:
            return c.execute(text("SELECT stock FROM products WHERE id = 1")).scalar_one()

    def test_order_uses_database_price_and_reduces_stock(self):
        order, created = service.place_order(7, OrderCreate(product_id=1, quantity=2), "key-0001")
        self.assertTrue(created)
        parsed = OrderResponse(**order)
        self.assertEqual(parsed.total_amount, Decimal("39.80"))
        self.assertEqual(self.stock(), 3)

    def test_same_request_returns_same_order_without_second_deduction(self):
        first, _ = service.place_order(7, OrderCreate(product_id=1, quantity=2), "key-0001")
        second, created = service.place_order(7, OrderCreate(product_id=1, quantity=2), "key-0001")
        self.assertFalse(created)
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(self.stock(), 3)

    def test_same_key_different_payload_is_conflict(self):
        service.place_order(7, OrderCreate(product_id=1, quantity=1), "key-0001")
        with self.assertRaises(service.OrderConflictError):
            service.place_order(7, OrderCreate(product_id=1, quantity=2), "key-0001")
        self.assertEqual(self.stock(), 4)

    def test_key_is_scoped_to_user(self):
        a, _ = service.place_order(7, OrderCreate(product_id=1, quantity=1), "key-0001")
        b, _ = service.place_order(8, OrderCreate(product_id=1, quantity=1), "key-0001")
        self.assertNotEqual(a["id"], b["id"])
        self.assertEqual(self.stock(), 3)

    def test_insufficient_stock_leaves_no_order(self):
        with self.assertRaises(service.OrderConflictError):
            service.place_order(7, OrderCreate(product_id=1, quantity=6), "key-0001")
        self.assertEqual(self.stock(), 5)
        self.assertEqual(service.list_my_orders(7, 1, 10)["total"], 0)

    def test_failure_after_deduction_rolls_back_both_changes(self):
        with patch.object(service.repository, "find_order_by_id", side_effect=RuntimeError("test failure")):
            with self.assertRaises(RuntimeError):
                service.place_order(7, OrderCreate(product_id=1, quantity=2), "key-0001")
        self.assertEqual(self.stock(), 5)
        self.assertEqual(service.list_my_orders(7, 1, 10)["total"], 0)

    def test_other_user_cannot_read_order(self):
        order, _ = service.place_order(7, OrderCreate(product_id=1, quantity=1), "key-0001")
        with self.assertRaises(service.OrderNotFoundError):
            service.get_my_order(order["id"], 8)
        self.assertEqual(service.list_my_orders(8, 1, 10)["total"], 0)

    def test_offline_product_or_resting_shop_is_rejected(self):
        for table in ("products", "shops"):
            with self.subTest(table=table):
                with self.engine.begin() as c:
                    c.execute(text(f"UPDATE {table} SET status = 0"))
                with self.assertRaises(service.OrderConflictError):
                    service.place_order(7, OrderCreate(product_id=1, quantity=1), "key-0001")
                with self.engine.begin() as c:
                    c.execute(text(f"UPDATE {table} SET status = 1"))
        self.assertEqual(self.stock(), 5)

    def test_price_snapshot_and_replay_after_product_change(self):
        first, _ = service.place_order(7, OrderCreate(product_id=1, quantity=2), "key-0001")
        with self.engine.begin() as c:
            c.execute(text("UPDATE products SET price = 88.88, name = 'new', status = 0"))
        replay, created = service.place_order(7, OrderCreate(product_id=1, quantity=2), "key-0001")
        self.assertFalse(created)
        self.assertEqual(replay["id"], first["id"])
        self.assertEqual(OrderResponse(**replay).total_amount, Decimal("39.80"))
        self.assertEqual(replay["product_name"], "meal")

    def test_quantity_and_client_price_validation(self):
        for fields in ({"quantity": 0}, {"quantity": -1}, {"quantity": True}, {"quantity": 100}, {"price": "0.01"}, {"user_id": 8}):
            payload = {"product_id": 1, "quantity": 1, **fields}
            with self.subTest(fields=fields), self.assertRaises(ValidationError):
                OrderCreate(**payload)

    def test_cancel_returns_stock_only_once(self):
        order, _ = service.place_order(7, OrderCreate(product_id=1, quantity=2), "cancel-001")
        for _ in range(2):
            cancelled = service.cancel_order(order["id"], 7)
            self.assertEqual(OrderResponse(**cancelled).status, "cancelled")
            self.assertEqual(self.stock(), 5)

    def test_cancel_failure_rolls_back_status(self):
        order, _ = service.place_order(7, OrderCreate(product_id=1, quantity=2), "cancel-001")
        with patch.object(service.repository, "restore_stock", side_effect=RuntimeError("test failure")):
            with self.assertRaises(RuntimeError):
                service.cancel_order(order["id"], 7)
        self.assertEqual(service.get_my_order(order["id"], 7)["status"], "pending")
        self.assertEqual(self.stock(), 3)

    def test_mock_pay_idempotent_and_does_not_deduct_again(self):
        order, _ = service.place_order(7, OrderCreate(product_id=1, quantity=2), "payment-001")
        for _ in range(2):
            paid = service.mock_pay_order(order["id"], 7)
            self.assertEqual(OrderResponse(**paid).status, "paid")
            self.assertEqual(self.stock(), 3)

    def test_paid_cannot_cancel(self):
        order, _ = service.place_order(7, OrderCreate(product_id=1, quantity=2), "payment-001")
        service.mock_pay_order(order["id"], 7)
        with self.assertRaises(service.OrderConflictError):
            service.cancel_order(order["id"], 7)
        self.assertEqual(self.stock(), 3)
        self.assertEqual(service.get_my_order(order["id"], 7)["status"], "paid")

    def test_cancelled_cannot_pay(self):
        order, _ = service.place_order(7, OrderCreate(product_id=1, quantity=2), "payment-001")
        service.cancel_order(order["id"], 7)
        with self.assertRaises(service.OrderConflictError):
            service.mock_pay_order(order["id"], 7)
        self.assertEqual(self.stock(), 5)
        self.assertEqual(service.get_my_order(order["id"], 7)["status"], "cancelled")

    def test_stranger_cannot_pay_or_cancel(self):
        order, _ = service.place_order(7, OrderCreate(product_id=1, quantity=2), "payment-001")
        for operation in (service.mock_pay_order, service.cancel_order):
            with self.subTest(operation=operation), self.assertRaises(service.OrderNotFoundError):
                operation(order["id"], 8)
        self.assertEqual(self.stock(), 3)
        self.assertEqual(service.get_my_order(order["id"], 7)["status"], "pending")

    def set_expired(self, order_id):
        with self.engine.begin() as c:
            c.execute(text("UPDATE orders SET expires_at = '2000-01-01 00:00:00' WHERE id = :id"), {"id": order_id})

    def test_expire_only_due_pending_and_restore_once(self):
        order, _ = service.place_order(7, OrderCreate(product_id=1, quantity=2), "expiry-001")
        self.assertFalse(service.expire_order(order["id"], 7))
        self.set_expired(order["id"])
        self.assertTrue(service.expire_order(order["id"], 7))
        self.assertFalse(service.expire_order(order["id"], 7))
        self.assertEqual(self.stock(), 5)
        self.assertEqual(OrderResponse(**service.get_my_order(order["id"], 7)).status, "expired")

    def test_pay_due_order_closes_and_commits_before_returning_error(self):
        order, _ = service.place_order(7, OrderCreate(product_id=1, quantity=2), "expiry-001")
        self.set_expired(order["id"])
        with self.assertRaises(service.OrderConflictError):
            service.mock_pay_order(order["id"], 7)
        self.assertEqual(self.stock(), 5)
        self.assertEqual(service.get_my_order(order["id"], 7)["status"], "expired")
        with self.assertRaises(service.OrderConflictError):
            service.mock_pay_order(order["id"], 7)
        self.assertEqual(self.stock(), 5)

    def test_expire_failure_rolls_back_state(self):
        order, _ = service.place_order(7, OrderCreate(product_id=1, quantity=2), "expiry-001")
        self.set_expired(order["id"])
        with patch.object(service.repository, "restore_stock", side_effect=RuntimeError("test failure")):
            with self.assertRaises(RuntimeError):
                service.expire_order(order["id"], 7)
        self.assertEqual(service.get_my_order(order["id"], 7)["status"], "pending")
        self.assertEqual(self.stock(), 3)

    def test_paid_order_is_not_expired(self):
        order, _ = service.place_order(7, OrderCreate(product_id=1, quantity=2), "expiry-001")
        service.mock_pay_order(order["id"], 7)
        self.set_expired(order["id"])
        self.assertFalse(service.expire_order(order["id"], 7))
        self.assertEqual(self.stock(), 3)

    def test_sweep_processes_only_due_pending(self):
        first, _ = service.place_order(7, OrderCreate(product_id=1, quantity=1), "expiry-001")
        service.place_order(7, OrderCreate(product_id=1, quantity=1), "expiry-002")
        self.set_expired(first["id"])
        result = service.expire_pending_orders(batch_size=1, max_batches=5)
        self.assertEqual(result, {"examined": 1, "expired": 1, "failed": 0})
        self.assertEqual(self.stock(), 4)
