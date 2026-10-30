import os
import sqlite3
import tempfile
import unittest

from bot import database


class PaymentSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = database.DB_PATH
        database.DB_PATH = os.path.join(self.temp_dir.name, "test.db")
        database.init_db()
        database.add_or_update_user(100, "customer", "Customer")
        database.add_customer_ledger_entry(100, 500, "opening debt")

    def tearDown(self):
        database.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def _order(self, user_id=100):
        return database.create_order(
            user_id=user_id, service_id=None, service_name="Test",
            order_type="buy", username="customer", original_price=1000,
            discount_percent=0, final_price=1000
        )

    def test_second_pending_order_is_blocked_until_first_is_rejected(self):
        first = self._order()
        with self.assertRaises(ValueError):
            self._order()
        self.assertTrue(database.reject_order(first))
        second = self._order()
        self.assertIsNotNone(second)

    def test_order_and_invoice_cannot_hold_parallel_balance_snapshots(self):
        first = self._order()
        with self.assertRaises(ValueError):
            database.create_invoice(100, "Extra", 1000)
        self.assertTrue(database.reject_order(first))
        invoice_id = database.create_invoice(100, "Extra", 1000)
        with self.assertRaises(ValueError):
            self._order()
        self.assertIsNotNone(invoice_id)

    def test_invoice_partial_payments_keep_individual_receipt_history(self):
        invoice_id = database.create_invoice(100, "Invoice", 1000)
        self.assertTrue(database.set_invoice_receipt(invoice_id, "receipt-one"))
        total = int(database.get_invoice(invoice_id)["total_amount"])
        first = database.record_invoice_partial_payment(invoice_id, 500, created_by=9)
        self.assertEqual(first["remaining"], total - 500)
        self.assertTrue(database.set_invoice_receipt(invoice_id, "receipt-two"))
        second = database.record_invoice_partial_payment(
            invoice_id, total - 500, created_by=9
        )
        self.assertTrue(second["completed"])
        payments = database.get_invoice_payments(invoice_id)
        self.assertEqual([p["amount"] for p in payments], [500, 1000])
        self.assertEqual([p["receipt_file_id"] for p in payments], ["receipt-one", "receipt-two"])

    def test_referral_reset_removes_rows_and_allows_recount(self):
        database.add_or_update_user(200, "invited", "Invited", referral_by=100)
        self.assertTrue(database.record_successful_referral(100, 200, 1))
        self.assertEqual(database.get_referral_count(100), 1)
        database.reset_user_info(100)
        self.assertEqual(database.get_referral_count(100), 0)
        with sqlite3.connect(database.DB_PATH) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM referral_success WHERE inviter_id = 100"
            ).fetchone()[0]
        self.assertEqual(count, 0)
        self.assertTrue(database.record_successful_referral(100, 200, 2))
        self.assertEqual(database.get_referral_count(100), 1)

    def test_approved_order_linked_to_subscription_cannot_be_deleted(self):
        order_id = self._order()
        self.assertTrue(database.set_receipt(order_id, "photo-file-id"))
        self.assertTrue(database.approve_order(order_id))
        database.save_subscription(
            user_id=100, order_id=order_id, service_name="Test",
            username="customer", subscription_url="https://example.invalid",
            config_text="config"
        )
        self.assertFalse(database.delete_order(order_id))
        self.assertIsNotNone(database.get_order(order_id))


if __name__ == "__main__":
    unittest.main()
