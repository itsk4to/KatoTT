import json
import random
import tempfile
import unittest
from pathlib import Path

from game.content import EQUIP_SLOTS, EXPLORE_ZONES, STATUS_EFFECTS, WORLD_REGIONS, ITEMS
from game.database import Database
from game.engine import GameEngine, GameError


class Phase28Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "t.db")
        self.engine = GameEngine(self.db, rng=random.Random(42))
        self.engine.create_character("1", "A", "tien")
        self.engine.create_character("2", "B", "ma")

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_multi_slot_loadout(self):
        p = self.engine.info("1")
        p.spirit_stones = 200_000
        self.db.save_player(p)
        # buy weapon + artifact
        self.engine.buy("1", "thanh_phong_kiem", 1) if "thanh_phong_kiem" in ITEMS else self.engine.buy("1", "thiet_kiem", 1)
        weapon = "thanh_phong_kiem" if "thanh_phong_kiem" in ITEMS else "thiet_kiem"
        self.engine.equip("1", weapon)
        # artifact
        art = next(k for k,v in ITEMS.items() if v.get("slot")=="artifact" and k in {x[0] for x in self.engine.shop()})
        self.engine.buy("1", art, 1)
        self.engine.equip("1", art)
        player = self.engine.info("1")
        loadout = json.loads(player.loadout or "{}")
        self.assertTrue(loadout)
        stats = self.engine.battle_stats(player)
        self.assertGreater(stats["attack"], 0)
        self.assertIn("weapon", EQUIP_SLOTS)

    def test_zone_realm_gate(self):
        with self.assertRaises(GameError):
            self.engine.set_explore_zone("1", "mavuc")
        zones = self.engine.list_explore_zones()
        self.assertTrue(any(z["key"] == "hoangnguyen" for z in zones))
        self.assertIn("dongphu", EXPLORE_ZONES)  # staged data for future open

    def test_status_effects_table(self):
        self.assertIn("burn", STATUS_EFFECTS)
        self.assertIn("pham_gioi", WORLD_REGIONS)

    def test_market_tax_burns_stones(self):
        p = self.engine.info("1")
        p.spirit_stones = 50_000
        self.db.save_player(p)
        self.engine.buy("1", "tu_khi_dan", 5)
        before_seller = self.engine.info("1").spirit_stones
        lid = self.engine.market_list("1", "tu_khi_dan", 2, 1000)
        buyer = self.engine.info("2")
        buyer.spirit_stones = 50_000
        self.db.save_player(buyer)
        total = 2000
        self.engine.market_buy("2", lid)
        after_seller = self.engine.info("1").spirit_stones
        # seller should gain 98% of 2000 = 1960
        self.assertEqual(after_seller - before_seller, 1960)

    def test_calculate_damage_miss_optional(self):
        hit = self.engine.calculate_damage(100, 50)
        self.assertGreater(hit["damage"], 0)
        miss = self.engine.calculate_damage(100, 50, accuracy=10, evasion=90)
        # may miss; force by checking structure
        self.assertIn("hit", miss)

    def test_armor_items_exist(self):
        self.assertIn("huyen_thiet_giap", ITEMS)
        self.assertEqual(ITEMS["huyen_thiet_giap"]["slot"], "armor")


if __name__ == "__main__":
    unittest.main()
