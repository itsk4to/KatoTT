import random
import tempfile
import unittest
from pathlib import Path

from game.database import Database
from game.engine import GameEngine


class Phase1Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "t.db")
        self.engine = GameEngine(self.db, rng=random.Random(7))

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_minor_realm_and_contributions(self):
        player = self.engine.create_character("1", "Tester", "tien")
        player.realm_idx = 2
        player.layer = 5
        text = self.engine.realm_text(player)
        self.assertIn("Trúc Cơ", text)
        self.assertIn("kỳ", text)
        stats = self.engine.battle_stats(player)
        parts = stats["contributions"]
        raw_hp = parts["realm_hp"] + parts["foundation_hp"] + parts["equipment_hp"] + parts["dao_hp"]
        self.assertGreater(stats["hp"], 0)
        self.assertLessEqual(stats["hp"], raw_hp)
        self.assertIn("speed", stats)
        self.assertIn("spirit", stats)
        self.assertIn(stats["mental_state"], {"Tâm ma", "Bất ổn", "Ổn định", "Bình thường"})

    def test_breakthrough_preview_has_preparation_fields(self):
        player = self.engine.create_character("2", "Breaker", "ma")
        player.cultivation = self.engine.cultivation_requirement(player)
        self.db.save_player(player)
        preview = self.engine.breakthrough_preview("2")
        self.assertIn("chance", preview)
        self.assertIn("mental_state", preview)
        self.assertGreaterEqual(preview["chance"], 12)
        self.assertLessEqual(preview["chance"], 92)

    def test_technique_mastery_migration(self):
        player = self.engine.create_character("3", "Scholar", "tien")
        self.db.add_item(player.user_id, "thanh_phong_kiem_quyet", 1)
        # item may not exist; use any technique from content
        from game.content import ITEMS
        tech = next(k for k, v in ITEMS.items() if v.get("type") == "technique")
        self.db.add_item(player.user_id, tech, 1)
        result = self.engine.learn_technique(player.user_id, tech)
        row = self.db.get_technique_mastery(player.user_id, tech)
        self.assertIsNotNone(row)
        self.assertEqual(row["stage"], result["stage"])
        self.assertGreaterEqual(row["mastery"], 1)


if __name__ == "__main__":
    unittest.main()
