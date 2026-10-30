import os
import tempfile
import unittest

from bot.state_store import PersistentStateMap


class PersistentStateMapTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "state.db")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_state_survives_new_map_instance_and_top_level_mutations(self):
        first = PersistentStateMap("user", db_path=self.db_path)
        first[123] = {"step": "waiting_receipt", "order_id": 77}
        loaded = PersistentStateMap("user", db_path=self.db_path)
        state = loaded[123]
        self.assertEqual(state["order_id"], 77)

        state["step"] = "waiting_invoice_receipt"
        reloaded = PersistentStateMap("user", db_path=self.db_path)
        self.assertEqual(reloaded[123]["step"], "waiting_invoice_receipt")

    def test_namespaces_are_isolated(self):
        user = PersistentStateMap("user", db_path=self.db_path)
        admin = PersistentStateMap("admin", db_path=self.db_path)
        user[5] = {"step": "coupon"}
        self.assertNotIn(5, admin)
        self.assertIn(5, user)

    def test_expired_state_is_removed(self):
        state = PersistentStateMap("short", ttl_seconds=-1, db_path=self.db_path)
        state[9] = {"step": "temporary"}
        self.assertNotIn(9, state)

    def test_pop_with_none_default_matches_dict_behavior(self):
        state = PersistentStateMap("pop", db_path=self.db_path)
        self.assertIsNone(state.pop(999, None))


if __name__ == "__main__":
    unittest.main()
