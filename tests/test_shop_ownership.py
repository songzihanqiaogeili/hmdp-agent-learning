import unittest
from unittest.mock import patch
from shop import service

class OwnershipTests(unittest.TestCase):
    def test_non_owner_cannot_update(self):
        with patch.object(service, 'find_shop_by_id', return_value={'id': 1, 'owner_id': 7}), patch.object(service, 'update_shop_record') as write:
            with self.assertRaises(PermissionError):
                service.update_shop(shop_id=1, name='n', address='a', phone='p', user_id=8)
            write.assert_not_called()

    def test_unassigned_shop_cannot_change_status(self):
        with patch.object(service, 'find_shop_by_id', return_value={'id': 1, 'owner_id': None}), patch.object(service, 'update_shop_status_record') as write:
            with self.assertRaises(PermissionError):
                service.change_shop_status(shop_id=1, status=0, user_id=8)
            write.assert_not_called()

    def test_owner_can_update(self):
        shop = {'id': 1, 'owner_id': 7}
        with patch.object(service, 'find_shop_by_id', return_value=shop), patch.object(service, 'update_shop_record') as write:
            self.assertEqual(service.update_shop(1, 'n', 'a', 'p', user_id=7), shop)
            write.assert_called_once_with(1, 'n', 'a', 'p', 7)

    def test_missing_shop(self):
        with patch.object(service, 'find_shop_by_id', return_value=None), patch.object(service, 'update_shop_status_record') as write:
            self.assertIsNone(service.change_shop_status(99, 0, user_id=7))
            write.assert_not_called()

    def test_creation_uses_authenticated_owner(self):
        with patch.object(service, 'insert_shop', return_value=3) as insert, patch.object(service, 'find_shop_by_id', return_value={'id': 3, 'owner_id': 7}):
            service.create_shop('n', 'a', 'p', user_id=7)
            insert.assert_called_once_with('n', 'a', 'p', 7)
