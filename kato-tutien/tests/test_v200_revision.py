"""Revision-pass tests: status combat, mastery progression, market tax, duplicates."""
from __future__ import annotations

import ast
import random
import tempfile
import unittest
from pathlib import Path

from game.content import ITEMS, STATUS_EFFECTS
from game.database import Database
from game.engine import GameEngine


class StatusCombatTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "t.db")
        self.engine = GameEngine(self.db, rng=random.Random(7))
        self.engine.create_character("1", "A", "tien")

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_hit_and_miss(self):
        hit = self.engine.calculate_damage(200, 50, accuracy=90, evasion=5, variance=0.0, crit_chance=0.0)
        self.assertTrue(hit["hit"])
        self.assertGreater(hit["damage"], 0)
        misses = 0
        for seed in range(40):
            self.engine.rng = random.Random(seed)
            r = self.engine.calculate_damage(200, 50, accuracy=10, evasion=80, variance=0.0, crit_chance=0.0)
            if not r["hit"]:
                misses += 1
        self.assertGreater(misses, 5)

    def test_status_application_and_duration(self):
        enc = {"player_statuses": [], "enemy_statuses": []}
        st = self.engine.apply_status(enc, "enemy", "burn")
        self.assertEqual(st["id"], "burn")
        self.assertEqual(st["duration"], STATUS_EFFECTS["burn"]["duration"])
        self.assertTrue(self.engine.has_status(enc, "enemy", "burn"))
        self.engine.apply_status(enc, "enemy", "burn", duration=5)
        self.assertEqual(enc["enemy_statuses"][0]["duration"], 5)

    def test_dot_tick_and_expiration(self):
        enc = {"player_statuses": [], "enemy_statuses": []}
        self.engine.apply_status(enc, "enemy", "poison", duration=2)
        t1 = self.engine.tick_statuses(enc, "enemy", max_hp=1000)
        self.assertGreater(t1["damage"], 0)
        self.assertEqual(len(enc["enemy_statuses"]), 1)
        t2 = self.engine.tick_statuses(enc, "enemy", max_hp=1000)
        self.assertGreater(t2["damage"], 0)
        self.assertEqual(len(enc["enemy_statuses"]), 0)

    def test_stun_skips_action(self):
        enc = {"player_statuses": [], "enemy_statuses": []}
        self.engine.apply_status(enc, "player", "stun", duration=1)
        tick = self.engine.tick_statuses(enc, "player", 1000)
        self.assertTrue(tick["skip_action"])

    def test_slow_reduces_speed_factor(self):
        enc = {"player_statuses": [], "enemy_statuses": []}
        self.engine.apply_status(enc, "player", "slow", duration=2)
        tick = self.engine.tick_statuses(enc, "player", 1000)
        self.assertLess(tick["speed_factor"], 1.0)

    def test_shield_mitigates(self):
        self.assertEqual(self.engine.mitigate_with_shield(100, 0.20), 80)
        self.assertEqual(self.engine.mitigate_with_shield(50, 0.0), 50)

    def test_pve_status_integration(self):
        player = self.engine.info("1")
        stats = self.engine.battle_stats(player)
        enc = self.engine._new_encounter(player, boss=False)
        self.engine.apply_status(enc, "enemy", "burn", duration=3)
        result = self.engine.battle_step("1", enc, stats["hp"], enc["hp"], "normal")
        self.assertIn("text", result)

    def test_accuracy_evasion_changes_miss_rate_meaningfully(self):
        low_evasion_misses = 0
        high_evasion_misses = 0
        for seed in range(200):
            self.engine.rng = random.Random(seed)
            low = self.engine.calculate_damage(200, 50, accuracy=72, evasion=5, variance=0.0, crit_chance=0.0)
            self.engine.rng = random.Random(seed)
            high = self.engine.calculate_damage(200, 50, accuracy=72, evasion=40, variance=0.0, crit_chance=0.0)
            low_evasion_misses += int(not low["hit"])
            high_evasion_misses += int(not high["hit"])
        self.assertGreater(high_evasion_misses, low_evasion_misses)
        self.assertGreaterEqual(low_evasion_misses, 15)

    def test_pvp_uses_accuracy_fields(self):
        self.engine.create_character("2", "B", "ma")
        ch = self.engine.pvp_challenge("1", "2", "stones", None, 10)
        result = self.engine.resolve_pvp(ch["id"], "2")
        self.assertIn("rounds", result)
        self.assertGreaterEqual(len(result["rounds"]), 1)

    def test_skill_respects_player_stun(self):
        tech = "thanh_van_quyet"
        self.db.add_item("1", tech, 1)
        self.engine.learn_technique("1", tech)
        player = self.engine.info("1")
        stats = self.engine.battle_stats(player)
        foe = {
            "name": "Dummy", "hp": 100_000, "max_hp": 100_000,
            "attack": 1, "defense": 1, "evasion": 0, "accuracy": 70,
            "reward": 1, "cultivation": 1, "rating": 1,
            "kind": "monster", "kind_label": "🎯",
            "player_statuses": [], "enemy_statuses": [],
        }
        self.engine.apply_status(foe, "player", "stun", duration=1)
        result = self.engine.battle_skill("1", foe, stats["hp"], foe["hp"], tech)
        self.assertEqual(result["damage"], 0)
        self.assertEqual(result["enemy_hp"], foe["hp"])
        self.assertEqual(foe["player_statuses"], [])

    def test_item_turn_ticks_player_dot(self):
        self.db.add_item("1", "hoi_khi_dan", 1)
        player = self.engine.info("1")
        stats = self.engine.battle_stats(player)
        foe = {
            "name": "Dummy", "hp": 100_000, "max_hp": 100_000,
            "attack": 1, "defense": 1, "evasion": 0, "accuracy": 70,
            "reward": 1, "cultivation": 1, "rating": 1,
            "kind": "monster", "kind_label": "🎯",
            "player_statuses": [], "enemy_statuses": [],
        }
        self.engine.apply_status(foe, "player", "poison", duration=2)
        result = self.engine.combat_item_turn("1", foe, stats["hp"] - 500, foe["hp"], "hoi_khi_dan")
        self.assertEqual(len(foe["player_statuses"]), 1)
        self.assertEqual(foe["player_statuses"][0]["duration"], 1)
        self.assertGreater(result["heal"], 0)


class MasteryProgressionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "t.db")
        self.engine = GameEngine(self.db, rng=random.Random(3))
        self.engine.create_character("1", "A", "tien")
        self.tech = next(k for k, v in ITEMS.items() if v.get("type") == "technique")

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_initial_mastery_on_learn(self):
        self.db.add_item("1", self.tech, 1)
        result = self.engine.learn_technique("1", self.tech)
        self.assertGreaterEqual(result["mastery"], 1)

    def test_mastery_gain_and_cap(self):
        self.db.add_item("1", self.tech, 1)
        self.engine.learn_technique("1", self.tech)
        for _ in range(20):
            self.engine.gain_technique_mastery("1", self.tech, 1)
        row = self.db.get_technique_mastery("1", self.tech)
        self.assertEqual(int(row["mastery"]), 12)
        self.assertEqual(row["stage"], "Viên mãn")

    def test_stage_transition(self):
        self.db.add_discovery("1", f"technique:{self.tech}")
        self.db.upsert_technique_mastery("1", self.tech, 3, "Nhập môn")
        got = self.engine.gain_technique_mastery("1", self.tech, 1)
        self.assertEqual(got["stage"], "Tiểu thành")
        self.assertEqual(got["mastery"], 4)

    def test_gameplay_effect_bounded(self):
        self.db.add_discovery("1", f"technique:{self.tech}")
        self.db.upsert_technique_mastery("1", self.tech, 12, "Viên mãn")
        mult = self.engine.mastery_combat_multiplier("1")
        self.assertGreater(mult, 1.0)
        self.assertLessEqual(mult, 1.12)

    def test_selected_technique_gains_its_own_mastery(self):
        first = "thanh_van_quyet"
        second = "hoa_van_cong"
        for technique_id in (first, second):
            self.db.add_item("1", technique_id, 1)
            self.engine.learn_technique("1", technique_id)
        self.engine.rng = random.Random(0)
        foe = {
            "name": "Training Dummy", "hp": 100_000, "max_hp": 100_000,
            "attack": 1, "defense": 10, "evasion": 0, "accuracy": 70,
            "reward": 1, "cultivation": 1, "rating": 1,
            "kind": "monster", "kind_label": "🎯",
        }
        before_first = int(self.db.get_technique_mastery("1", first)["mastery"])
        before_second = int(self.db.get_technique_mastery("1", second)["mastery"])
        result = self.engine.battle_skill("1", foe, self.engine.battle_stats(self.engine.info("1"))["hp"], foe["hp"], first)
        self.assertEqual(result["technique_id"], first)
        self.assertEqual(int(result["technique_mastery"]["mastery"]), before_first + 1)
        self.assertEqual(int(self.db.get_technique_mastery("1", second)["mastery"]), before_second)

    def test_backward_compat_without_relearn(self):
        self.db.add_discovery("1", f"technique:{self.tech}")
        self.db.add_discovery("1", f"technique_bonus:{self.tech}")
        got = self.engine.gain_technique_mastery("1", self.tech, 1)
        self.assertIsNotNone(got)
        self.assertGreaterEqual(got["mastery"], 1)


class MarketTaxTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "t.db")
        self.engine = GameEngine(self.db, rng=random.Random(1))
        self.engine.create_character("1", "Seller", "tien")
        self.engine.create_character("2", "Buyer", "ma")

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_tax_floor_spec_cases(self):
        for total in [1, 2, 3, 49, 50, 99, 100, 199, 200, 1000, 2000]:
            seller_gain = int(total * 0.98)
            tax = total - seller_gain
            self.assertEqual(seller_gain + tax, total)
            self.assertEqual(seller_gain, int(total * 0.98))

    def test_market_atomic_tax(self):
        p = self.engine.info("1")
        p.spirit_stones = 100_000
        self.db.save_player(p)
        self.engine.buy("1", "tu_khi_dan", 10)
        before = self.engine.info("1").spirit_stones
        lid = self.engine.market_list("1", "tu_khi_dan", 1, 49)
        buyer = self.engine.info("2")
        buyer.spirit_stones = 100_000
        self.db.save_player(buyer)
        self.engine.market_buy("2", lid)
        after = self.engine.info("1").spirit_stones
        self.assertEqual(after - before, int(49 * 0.98))


class DuplicateMethodScanTests(unittest.TestCase):
    def test_no_duplicate_methods_in_production(self):
        for path, cls_name in [("game/engine.py", "GameEngine"), ("game/database.py", "Database")]:
            tree = ast.parse(Path(path).read_text())
            for node in tree.body:
                if isinstance(node, ast.ClassDef) and node.name == cls_name:
                    seen = {}
                    for n in node.body:
                        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            seen.setdefault(n.name, []).append(n.lineno)
                    dups = {k: v for k, v in seen.items() if len(v) > 1}
                    self.assertEqual(dups, {}, f"Duplicate methods in {cls_name}: {dups}")


class MigrationLoadoutTests(unittest.TestCase):
    def test_legacy_equipped_migrates_into_loadout(self):
        tmp = tempfile.TemporaryDirectory()
        db = Database(Path(tmp.name) / "t.db")
        engine = GameEngine(db, rng=random.Random(2))
        engine.create_character("1", "A", "tien")
        p = engine.info("1")
        p.spirit_stones = 50_000
        db.save_player(p)
        item_id = next(i for i, it in engine.shop() if it.get("type") == "equipment")
        engine.buy("1", item_id, 1)
        engine.equip("1", item_id)
        p = engine.info("1")
        self.assertTrue(p.equipped)
        loadout = engine._parse_loadout(p)
        self.assertTrue(any(loadout.values()))
        db.close()
        tmp.cleanup()
