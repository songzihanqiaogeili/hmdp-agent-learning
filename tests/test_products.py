import unittest
from decimal import Decimal
from unittest.mock import patch
from sqlalchemy import create_engine, text
from pydantic import ValidationError
from product import service
from product.schemas import ProductCreate, ProductUpdate, ProductResponse

class ProductTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://')
        with self.engine.begin() as c:
            c.execute(text('CREATE TABLE shops (id INTEGER PRIMARY KEY, owner_id INTEGER, status INTEGER NOT NULL)'))
            c.execute(text('INSERT INTO shops VALUES (1, 7, 1), (2, 8, 1), (3, NULL, 1), (4, 7, 0)'))
            c.execute(text('''CREATE TABLE products (
                id INTEGER PRIMARY KEY AUTOINCREMENT, shop_id INTEGER NOT NULL,
                name TEXT NOT NULL, description TEXT NOT NULL,
                price DECIMAL(10,2) NOT NULL, stock INTEGER NOT NULL,
                status INTEGER NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP)'''))
        self.patcher = patch.object(service, 'engine', self.engine)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.addCleanup(self.engine.dispose)

    def data(self):
        return ProductCreate(name='  hotpot  ', description='set meal', price='99.90', stock=10)

    def test_create_default_offline_and_exact_price(self):
        product = service.create_product(1, self.data(), 7)
        response = ProductResponse(**product)
        self.assertEqual(response.status, 0)
        self.assertEqual(response.name, 'hotpot')
        self.assertEqual(response.price, Decimal('99.90'))

    def test_wrong_owner_and_unassigned_shop_forbidden(self):
        for shop_id in (2, 3):
            with self.subTest(shop_id=shop_id), self.assertRaises(service.ProductForbiddenError):
                service.create_product(shop_id, self.data(), 7)
        with self.engine.connect() as c:
            self.assertEqual(c.execute(text('SELECT COUNT(*) FROM products')).scalar_one(), 0)

    def test_offline_hidden_then_publish_and_hide(self):
        p = service.create_product(1, self.data(), 7)
        self.assertEqual(service.list_products(1, 1, 10)['total'], 0)
        with self.assertRaises(service.ProductNotFoundError):
            service.get_product(p['id'])
        service.change_product_status(p['id'], 1, 7)
        service.change_product_status(p['id'], 1, 7)
        self.assertEqual(service.get_product(p['id'])['id'], p['id'])
        self.assertEqual(service.list_products(1, 1, 1)['total'], 1)
        service.change_product_status(p['id'], 0, 7)
        with self.assertRaises(service.ProductNotFoundError):
            service.get_product(p['id'])

    def test_stranger_cannot_edit_or_change_status(self):
        p = service.create_product(1, self.data(), 7)
        with self.assertRaises(service.ProductForbiddenError):
            service.update_product(p['id'], ProductUpdate(name='bad', description='', price='1.00'), 8)
        with self.assertRaises(service.ProductForbiddenError):
            service.change_product_status(p['id'], 1, 8)
        with self.engine.connect() as c:
            row = c.execute(text('SELECT name, stock, status FROM products')).mappings().first()
            self.assertEqual(dict(row), {'name': 'hotpot', 'stock': 10, 'status': 0})

    def test_update_does_not_replace_stock_or_status(self):
        p = service.create_product(1, self.data(), 7)
        service.change_product_status(p['id'], 1, 7)
        updated = service.update_product(p['id'], ProductUpdate(name='new', description='new', price='88.88'), 7)
        self.assertEqual((updated['stock'], updated['status']), (10, 1))
        self.assertEqual(ProductResponse(**updated).price, Decimal('88.88'))

    def test_listing_pagination_and_shop_isolation(self):
        for _ in range(3):
            p = service.create_product(1, self.data(), 7)
            service.change_product_status(p['id'], 1, 7)
        p = service.create_product(2, self.data(), 8)
        service.change_product_status(p['id'], 1, 8)
        page = service.list_products(1, 2, 2)
        self.assertEqual((page['total'], page['total_pages'], len(page['items'])), (3, 2, 1))
        self.assertEqual(service.list_products(1, 99, 2)['items'], [])

    def test_missing_resource(self):
        with self.assertRaises(service.ProductNotFoundError):
            service.create_product(99, self.data(), 7)
        with self.assertRaises(service.ProductNotFoundError):
            service.change_product_status(99, 1, 7)

    def test_resting_shop_hides_products(self):
        p = service.create_product(4, self.data(), 7)
        service.change_product_status(p['id'], 1, 7)
        self.assertEqual(service.list_products(4, 1, 10)['total'], 0)
        with self.assertRaises(service.ProductNotFoundError):
            service.get_product(p['id'])

    def test_schema_rejects_bad_money_stock_and_extra_fields(self):
        for changes in ({'price': '0'}, {'price': '-1'}, {'price': '1.001'}, {'price': '100000000'}, {'price': 'NaN'}, {'stock': -1}, {'stock': True}, {'name': '   '}, {'owner_id': 8}, {'status': 1}):
            payload = {'name': 'meal', 'description': '', 'price': '10.00', 'stock': 1}
            payload.update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                ProductCreate(**payload)
        with self.assertRaises(ValidationError):
            ProductUpdate(name='meal', price='10.00', stock=100)
