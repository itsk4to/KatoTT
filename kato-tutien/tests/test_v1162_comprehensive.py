import ast
import sqlite3
import tempfile
import unittest
from pathlib import Path
from random import Random

from game.content import REALMS
from game.database import Database
from game.engine import GameEngine, GameError

ROOT = Path(__file__).resolve().parents[1]


class V1162ComprehensiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False)
        self.tmp.close()
        self.db = Database(self.tmp.name)
        self.engine = GameEngine(self.db, Random(1234))
        self.a = self.engine.create_character("1", "A", "tien")
        self.b = self.engine.create_character("2", "B", "tien")

    def tearDown(self):
        self.db.close()
        Path(self.tmp.name).unlink(missing_ok=True)

    def test_all_cultivation_sources_stop_at_cap(self):
        p = self.engine.info("1")
        cap = self.engine.cultivation_requirement(p)
        p.cultivation = cap - 1
        p.be_quan_active = 1
        p.be_quan_prepaid = 1
        p.be_quan_last_tick = 1
        self.db.save_player(p)
        results = self.engine.process_be_quan(now=301, max_cycles=1)
        self.assertEqual(self.engine.info("1").cultivation, cap)
        self.assertEqual(results[0]["gain"], 1)

        # Combat reward must also go through the canonical cap-safe path.
        p = self.engine.info("1")
        p.cultivation = cap - 1
        self.db.save_player(p)
        encounter = {"name": "Test Yêu Thú", "attack": 1, "defense": 1, "reward": 10, "cultivation": 500, "kind": "normal"}
        result = self.engine._battle_enemy_turn("1", encounter, 999, 1, 999999, "⚔️ Đánh thường")
        self.assertTrue(result["victory"])
        self.assertEqual(self.engine.info("1").cultivation, cap)

    def test_song_tu_rewards_both_partners_and_respects_cap(self):
        self.engine.request_dao_lu("1", "2")
        self.engine.accept_dao_lu("2")
        p1 = self.engine.info("1")
        p2 = self.engine.info("2")
        cap1 = self.engine.cultivation_requirement(p1)
        cap2 = self.engine.cultivation_requirement(p2)
        p1.cultivation = cap1 - 2
        p2.cultivation = cap2 - 3
        self.db.save_player(p1)
        self.db.save_player(p2)
        result = self.engine.dao_lu_song_tu("1")
        self.assertGreaterEqual(result["gain"], 0)
        self.assertGreaterEqual(result["partner_gain"], 0)
        self.assertEqual(self.engine.info("1").cultivation, cap1)
        self.assertEqual(self.engine.info("2").cultivation, cap2)

    def test_permanent_stat_growth_has_diminishing_returns(self):
        self.assertEqual(self.engine._soft_capped_stat_gain(40, 20), 20)
        self.assertEqual(self.engine._soft_capped_stat_gain(70, 20), 12)
        self.assertEqual(self.engine._soft_capped_stat_gain(90, 20), 7)
        self.assertEqual(self.engine._soft_capped_stat_gain(100, 20), 0)

    def test_dao_progression_uses_common_helper(self):
        p = self.engine.choose_dao("1", "kiem")
        self.assertEqual(p["stage"], 0)
        self.db.add_item("1", "thiet_kiem", 1)
        before = self.engine.info("1").dao_progress
        self.engine.equip("1", "thiet_kiem")
        self.assertGreater(self.engine.info("1").dao_progress, before)
        # Direct insight path must use the same stage thresholds.
        self.engine.gain_dao_insight("1", 10000)
        info = self.engine.dao_info("1")
        self.assertEqual(info["stage"], len(__import__("game.content", fromlist=["DAO_PATHS"]).DAO_PATHS["kiem"]["stages"]) - 1)

    def test_sect_mission_cannot_follow_player_to_new_sect(self):
        self.engine.create_sect("1", "Thanh Long Tông", "Đạo thống thử nghiệm")
        self.engine.create_sect("2", "Huyền Minh Tông", "Đạo thống đối chứng")
        day = "20990101"
        self.db.add_mission_progress("1", "player_1", "cultivate", 5, day)
        self.assertIsNotNone(self.db.get_mission_progress("1", "player_1", "cultivate"))
        self.engine.leave_sect("1")
        self.engine.join_sect("1", "player_2")
        self.assertIsNone(self.db.get_mission_progress("1", "player_2", "cultivate"))

    def test_sect_levels_up_and_treasury_can_upgrade_linh_mach(self):
        sect = self.engine.create_sect("1", "Tông Môn Hắc Sơn", "Tông môn cân bằng")
        p = self.engine.info("1")
        p.spirit_stones = 50000
        self.db.save_player(p)
        result = self.engine.sect_contribute("1", 15000)
        self.assertGreaterEqual(int(result["level"]), 2)
        self.assertEqual(self.db.get_sect_treasury(sect["id"]), 15000)
        upgraded = self.engine.upgrade_sect_linh_mach("1")
        self.assertEqual(int(upgraded["linh_mach_level"]), 1)
        self.assertGreaterEqual(int(upgraded["bonus_percent"]), int(sect["bonus_percent"]))
        self.assertEqual(self.db.get_sect_treasury(sect["id"]), 0)

    def test_sect_mission_reward_does_not_charge_stones_twice(self):
        self.engine.create_sect("1", "Thiên Hạc Tông", "Nhiệm vụ")
        day = __import__("time").strftime("%Y%m%d")
        mission = self.engine.sect_mission_list("1")[0]
        key = mission["key"]
        target = mission["target"]
        self.db.add_mission_progress("1", "player_1", key, target, day)
        before = self.engine.info("1")
        result = self.engine.sect_mission_claim("1", key)
        after = self.engine.info("1")
        self.assertEqual(after.spirit_stones, before.spirit_stones + result["reward"])
        self.assertEqual(int(self.db.get_sect_membership("1")["contribution"]), 5000 + result["contribution"])

    def test_seed_npc_sects_are_visible(self):
        sects = self.engine.list_all_sects()
        ids = {s["id"] for s in sects}
        self.assertTrue({"thanh_van", "kiem_ho", "dan_dinh", "van_ma", "thai_hu"} <= ids)
        self.assertTrue(any(s.get("owner_id") is None for s in sects))

    def test_contribution_rank_is_not_role(self):
        self.engine.create_sect("1", "Thiên Kiếm Tông", "Kiếm tu")
        p = self.engine.sect_info("1")
        self.assertEqual(p["role"], "Tông Chủ")
        self.assertEqual(self.engine.sect_rank(int(p["contribution"])), "Chân Truyền")
        self.assertNotEqual(p["role"], self.engine.sect_rank(int(p["contribution"])))

    def test_pvp_engine_round_trip(self):
        p1 = self.engine.info("1")
        p2 = self.engine.info("2")
        p1.spirit_stones = p2.spirit_stones = 5000
        self.db.save_player(p1)
        self.db.save_player(p2)
        challenge = self.engine.pvp_challenge("1", "2", "stones", None, 500)
        self.assertIsNotNone(self.engine.get_pvp_challenge(challenge["id"]))
        result = self.engine.resolve_pvp(challenge["id"], "2")
        self.assertIn(str(result["winner_id"]), {"1", "2"})
        self.assertIsNone(self.engine.get_pvp_challenge(challenge["id"]))

    def test_mission_schema_migration_from_legacy(self):
        self.engine.create_sect("1", "Diệp Tông", "Migration")
        db_path = self.tmp.name
        self.db.close()
        conn = sqlite3.connect(db_path)
        conn.execute("ALTER TABLE sect_mission_progress RENAME TO sect_mission_progress_current_backup")
        conn.execute("CREATE TABLE sect_mission_progress (user_id TEXT NOT NULL, mission_key TEXT NOT NULL, progress INTEGER NOT NULL DEFAULT 0, completed_at INTEGER NOT NULL DEFAULT 0, day_key TEXT NOT NULL DEFAULT '', PRIMARY KEY(user_id, mission_key))")
        conn.execute("INSERT INTO sect_mission_progress(user_id,mission_key,progress,completed_at,day_key) VALUES(?,?,?,?,?)", ("1", "cultivate", 7, 0, "20990101"))
        conn.commit()
        conn.close()

        self.db = Database(db_path)
        migrated = self.db.get_mission_progress("1", "player_1", "cultivate")
        self.assertIsNotNone(migrated)
        self.assertEqual(int(migrated["progress"]), 7)

    def test_bot_static_integrity_for_fixed_views_and_help(self):
        source = (ROOT / "bot.py").read_text()
        tree = ast.parse(source)
        names = {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
        for name in {"PvpChallengeView", "command_admin", "AdminPanelView"}:
            self.assertIn(name, names)
        self.assertIn("`.thaptong`", source)
        self.assertIn("`.thienkiep`", source)
        self.assertIn("KATO_ADMIN_PASSWORD", source)
        self.assertNotIn("default hash", source.lower())


if __name__ == "__main__":
    unittest.main()
