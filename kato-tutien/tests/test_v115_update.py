import sqlite3
import tempfile
import unittest
from pathlib import Path
from random import Random

from game.database import Database
from game.engine import GameEngine
from game.content import ASCENSION_TOWER, DAO_PATHS, EXPLORE_ZONES, SECT_TOWER


class V115UpdateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False)
        self.tmp.close()
        self.db = Database(self.tmp.name)
        self.engine = GameEngine(self.db, Random(1234))
        self.tien = self.engine.create_character("1", "Tien", "tien")
        self.ma = self.engine.create_character("2", "Ma", "ma")

    def tearDown(self):
        self.db.close()
        Path(self.tmp.name).unlink(missing_ok=True)

    def test_new_progression_fields_exist(self):
        cols = {r[1] for r in self.db.conn.execute("PRAGMA table_info(players)")}
        for name in {"foundation", "dao_type", "dao_stage", "dao_progress", "explore_zone", "trial_best", "trial_attempts", "trial_day", "last_trial", "tribulation_ready"}:
            self.assertIn(name, cols)

    def test_cultivation_caps_and_requires_breakthrough(self):
        p = self.engine.info("1")
        p.cultivation = self.engine.cultivation_requirement(p) - 1
        p.last_cultivate = 0
        self.db.save_player(p)
        result = self.engine.cultivate("1")
        self.assertLessEqual(result["player"].cultivation, self.engine.cultivation_requirement(result["player"]))
        p = self.engine.info("1")
        p.last_cultivate = 0
        p.cultivation = self.engine.cultivation_requirement(p)
        self.db.save_player(p)
        with self.assertRaises(Exception):
            self.engine.cultivate("1")

    def test_multi_use_consumable(self):
        self.db.add_item("1", "hoi_khi_dan", 20)
        p = self.engine.info("1")
        p.cultivation = 0
        self.db.save_player(p)
        result = self.engine.use_item("1", "hoi_khi_dan", 20)
        self.assertEqual(self.db.get_item_count("1", "hoi_khi_dan"), 0)
        self.assertGreaterEqual(result["player"].cultivation, 0)

    def test_tien_ma_leaderboards_are_separate(self):
        self.assertEqual([p.path for p in self.engine.leaderboard(10, "tien")], ["tien"])
        self.assertEqual([p.path for p in self.engine.leaderboard(10, "ma")], ["ma"])

    def test_dao_progression(self):
        info = self.engine.choose_dao("1", "kiem")
        self.assertEqual(info["name"], DAO_PATHS["kiem"]["name"])
        info = self.engine.gain_dao_insight("1", 500)
        self.assertGreaterEqual(info["stage"], 1)

    def test_exploration_zone(self):
        p = self.engine.info("1")
        p.realm_idx = 1
        p.layer = 1
        self.db.save_player(p)
        zone = self.engine.set_explore_zone("1", "yeuthusonmach")
        self.assertEqual(zone["name"], EXPLORE_ZONES["yeuthusonmach"]["name"])
        self.assertEqual(self.engine.info("1").explore_zone, "yeuthusonmach")

    def test_trial_has_daily_limit(self):
        for _ in range(5):
            self.engine.trial_challenge("1")
        with self.assertRaises(Exception):
            self.engine.trial_challenge("1")

    def test_player_sect_has_internal_management_data(self):
        self.engine.create_sect("1", "Cửu Thiên Kiếm Tông", "Kiếm đạo chính tông")
        overview = self.engine.sect_overview("1")
        self.assertEqual(overview["member"]["role"], "Tông Chủ")
        self.assertGreaterEqual(overview["treasury"], 0)
        self.assertEqual(overview["members"][0]["user_id"], "1")

    def test_sect_mission_progress_and_claim(self):
        self.engine.create_sect("1", "Cửu Thiên Kiếm Tông", "Kiếm đạo chính tông")
        for _ in range(3):
            self.engine._progress_sect_mission("1", "cultivate", 1)
        missions = {m["key"]: m for m in self.engine.sect_mission_list("1")}
        self.assertEqual(missions["cultivate"]["progress"], 3)
        reward = self.engine.sect_mission_claim("1", "cultivate")
        self.assertGreater(reward["contribution"], 0)

    def test_exploration_has_two_distinct_open_zone_pools(self):
        zones = self.engine.list_explore_zones()
        self.assertEqual([z["key"] for z in zones], ["hoangnguyen", "yeuthusonmach"])
        self.assertNotEqual(EXPLORE_ZONES["hoangnguyen"]["events"], EXPLORE_ZONES["yeuthusonmach"]["events"])

    def test_ascension_tower_progress_and_daily_limit(self):
        first = self.engine.ascension_tower_climb("1")
        self.assertEqual(first["floor"], 1)
        status = self.engine.ascension_tower_status("1")
        self.assertEqual(status["attempts"], 1)
        for _ in range(ASCENSION_TOWER["daily_attempts"] - 1):
            self.engine.ascension_tower_climb("1")
        with self.assertRaises(Exception):
            self.engine.ascension_tower_climb("1")

    def test_sect_tower_shared_daily_limit(self):
        self.engine.create_sect("1", "Cửu Thiên Kiếm Tông", "Kiếm đạo chính tông")
        first = self.engine.sect_tower_climb("1")
        self.assertEqual(first["floor"], 1)
        self.engine.sect_tower_climb("1")
        with self.assertRaises(Exception):
            self.engine.sect_tower_climb("1")


if __name__ == "__main__":
    unittest.main()
