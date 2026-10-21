import unittest
from unittest.mock import patch

from sqlalchemy import create_engine, text

from scripts import seed_demo


class DemoSeedTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        self.addCleanup(self.engine.dispose)
        with self.engine.begin() as c:
            for statement in (
                "CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, phone TEXT UNIQUE NOT NULL, nickname TEXT NOT NULL, status INTEGER NOT NULL DEFAULT 1)",
                "CREATE TABLE shops (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, address TEXT NOT NULL, phone TEXT NOT NULL, owner_id INTEGER, status INTEGER NOT NULL DEFAULT 1)",
                """CREATE TABLE products (id INTEGER PRIMARY KEY AUTOINCREMENT, shop_id INTEGER NOT NULL,
                   name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', price DECIMAL(10,2) NOT NULL,
                   stock INTEGER NOT NULL, status INTEGER NOT NULL DEFAULT 0, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)""",
                """CREATE TABLE orders (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
                   product_id INTEGER NOT NULL, shop_id INTEGER NOT NULL, product_name TEXT NOT NULL,
                   unit_price DECIMAL(10,2) NOT NULL, quantity INTEGER NOT NULL, total_amount DECIMAL(12,2) NOT NULL,
                   status TEXT NOT NULL DEFAULT 'pending', idempotency_key TEXT NOT NULL,
                   created_at DATETIME DEFAULT CURRENT_TIMESTAMP, expires_at DATETIME NOT NULL,
                   UNIQUE(user_id, idempotency_key))""",
            ):
                c.execute(text(statement))

    def counts(self):
        with self.engine.connect() as c:
            return {name: c.execute(text(f"SELECT COUNT(*) FROM {name}")).scalar_one() for name in ("users", "shops", "products", "orders")}

    def test_scenarios_have_consistent_stock(self):
        result = seed_demo.seed_database(self.engine)
        self.assertEqual(len(result["accounts"]), 2)
        expected = {"pending": ("pending", 18), "paid": ("paid", 18), "cancelled": ("cancelled", 20), "expired": ("expired", 20), "due": ("pending", 18)}
        for key, (status, stock) in expected.items():
            with self.subTest(key=key):
                self.assertEqual(result["scenarios"][key]["status"], status)
                self.assertEqual(result["scenarios"][key]["stock"], stock)

    def test_second_run_reuses_ids_and_does_not_reset_user_actions(self):
        first = seed_demo.seed_database(self.engine)
        counts = self.counts()
        order_id = first["scenarios"]["pending"]["order_id"]
        product_id = first["scenarios"]["pending"]["product_id"]
        with self.engine.begin() as c:
            c.execute(text("UPDATE orders SET status = 'paid' WHERE id = :id"), {"id": order_id})
        second = seed_demo.seed_database(self.engine)
        self.assertEqual(self.counts(), counts)
        self.assertEqual(second["scenarios"]["pending"]["order_id"], order_id)
        self.assertEqual(second["scenarios"]["pending"]["product_id"], product_id)
        self.assertEqual(second["scenarios"]["pending"]["status"], "paid")
        self.assertEqual(second["scenarios"]["pending"]["stock"], 18)

    def test_phone_collision_does_not_take_over_existing_account(self):
        with self.engine.begin() as c:
            c.execute(text("INSERT INTO users(phone,nickname) VALUES (:phone, 'existing')"), {"phone": seed_demo.ACCOUNT_PHONES["a"]})
        with self.assertRaises(ValueError):
            seed_demo.seed_database(self.engine)
        self.assertEqual(self.counts(), {"users": 1, "shops": 0, "products": 0, "orders": 0})

    def test_new_set_creates_new_scenarios_but_reuses_accounts(self):
        first = seed_demo.seed_database(self.engine)
        second = seed_demo.seed_database(self.engine, "demo-next")
        self.assertEqual(first["accounts"]["a"]["id"], second["accounts"]["a"]["id"])
        self.assertNotEqual(first["scenarios"]["pending"]["order_id"], second["scenarios"]["pending"]["order_id"])
        self.assertEqual(self.counts()["users"], 2)

    def test_mid_seed_failure_rolls_back_all_fixture_rows(self):
        with patch.object(seed_demo.order_repository, "restore_stock", side_effect=RuntimeError("test failure")):
            with self.assertRaises(RuntimeError):
                seed_demo.seed_database(self.engine)
        self.assertEqual(self.counts(), {"users": 0, "shops": 0, "products": 0, "orders": 0})

    def test_unrelated_business_rows_unchanged(self):
        with self.engine.begin() as c:
            c.execute(text("INSERT INTO users(phone,nickname) VALUES ('13811112222','unrelated')"))
            c.execute(text("INSERT INTO shops(name,address,phone,owner_id) VALUES ('original','original','original',1)"))
        seed_demo.seed_database(self.engine)
        with self.engine.connect() as c:
            row = c.execute(text("SELECT name,address,phone,owner_id FROM shops WHERE id=1")).mappings().first()
        self.assertEqual(dict(row), {"name": "original", "address": "original", "phone": "original", "owner_id": 1})
