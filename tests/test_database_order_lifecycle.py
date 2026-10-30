import os
import sqlite3
import tempfile
import unittest

from bot import database


class OrderCouponLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = database.DB_PATH
        database.DB_PATH = os.path.join(self.temp_dir.name, "test.db")
        database.init_db()

    def tearDown(self):
        database.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def _coupon_used_count(self):
        with sqlite3.connect(database.DB_PATH) as conn:
            row = conn.execute(
                "SELECT used_count FROM coupons WHERE code = 'SAVE10'"
            ).fetchone()
        return row[0]

    def _create_coupon_order(self):
        self.assertTrue(database.create_coupon("SAVE10", 10, max_uses=1))
        return database.create_order(
            user_id=123,
            service_id=None,
            service_name="Test",
            order_type="buy",
            username="tester",
            original_price=1000,
            discount_percent=10,
            final_price=900,
            coupon="SAVE10",
        )

    def test_rejecting_pending_order_releases_coupon_reservation(self):
        order_id = self._create_coupon_order()
        self.assertEqual(self._coupon_used_count(), 1)

        self.assertTrue(database.reject_order(order_id))
        self.assertEqual(self._coupon_used_count(), 0)
        self.assertFalse(database.reject_order(order_id))

    def test_reopening_rejected_order_reserves_coupon_again(self):
        order_id = self._create_coupon_order()
        self.assertTrue(database.reject_order(order_id))

        self.assertTrue(database.update_order_status(order_id, "pending"))
        self.assertEqual(self._coupon_used_count(), 1)

        # The same order cannot reserve a second use while already pending.
        self.assertTrue(database.update_order_status(order_id, "pending"))
        self.assertEqual(self._coupon_used_count(), 1)

    def test_reopening_fails_if_coupon_capacity_was_taken(self):
        order_id = self._create_coupon_order()
        self.assertTrue(database.reject_order(order_id))

        other_order = database.create_order(
            user_id=456,
            service_id=None,
            service_name="Test",
            order_type="buy",
            username="other",
            original_price=1000,
            discount_percent=10,
            final_price=900,
            coupon="SAVE10",
        )
        self.assertIsNotNone(other_order)

        self.assertFalse(database.update_order_status(order_id, "pending"))
        self.assertEqual(self._coupon_used_count(), 1)


if __name__ == "__main__":
    unittest.main()
