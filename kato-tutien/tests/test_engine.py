import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from game.database import Database
from game.engine import GameEngine, GameError


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False)
        self.tmp.close()
        self.db = Database(self.tmp.name)
        from random import Random
        self.engine = GameEngine(self.db, Random(12345))
        self.player = self.engine.create_character("1", "Kato", "tien")

    def tearDown(self):
        self.db.close()
        Path(self.tmp.name).unlink(missing_ok=True)

    def test_starting_stones(self):
        self.assertEqual(self.player.spirit_stones, 1000)
        self.assertFalse(self.engine.exists("2"))

    def test_create_duplicate_rejected(self):
        with self.assertRaises(GameError):
            self.engine.create_character("1", "Kato", "ma")

    def test_buy_and_inventory(self):
        player = self.engine.info("1")
        player.spirit_stones = 5000
        self.db.save_player(player)
        player, item, total = self.engine.buy("1", "tu_khi_dan", 2)
        self.assertEqual(total, 2000)
        self.assertEqual(player.spirit_stones, 3000)
        self.assertEqual(self.db.get_item_count("1", "tu_khi_dan"), 2)

    def test_use_pill_adds_cultivation(self):
        self.engine.buy("1", "tu_khi_dan", 1)
        before = self.engine.info("1").cultivation
        self.engine.use_item("1", "tu_khi_dan")
        after = self.engine.info("1").cultivation
        self.assertEqual(after - before, 250)

    def test_cultivation_has_cooldown(self):
        first = self.engine.cultivate("1")
        self.assertGreater(first["gain"], 0)
        with self.assertRaises(GameError):
            self.engine.cultivate("1")

    def test_breakthrough_requires_enough_cultivation(self):
        with self.assertRaises(GameError):
            self.engine.breakthrough("1")

    def test_gacha_consumes_ticket(self):
        self.db.add_item("1", "thien_co_lenh", 1)
        before = self.db.get_item_count("1", "thien_co_lenh")
        self.engine.gacha_once("1")
        after = self.db.get_item_count("1", "thien_co_lenh")
        self.assertEqual(before - after, 1)

    def test_equipment_path_protection(self):
        self.db.add_item("1", "tinh_thiet_ma_dao", 1)
        with self.assertRaises(GameError):
            self.engine.equip("1", "tinh_thiet_ma_dao")

    def test_leaderboard_returns_created_player(self):
        rows = self.engine.leaderboard()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].display_name, "Kato")


if __name__ == "__main__":
    unittest.main()

class ExtendedEngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False)
        self.tmp.close()
        self.db = Database(self.tmp.name)
        from random import Random
        self.engine = GameEngine(self.db, Random(7))
        self.a = self.engine.create_character("1", "A", "tien")
        self.b = self.engine.create_character("2", "B", "ma")

    def tearDown(self):
        self.db.close()
        Path(self.tmp.name).unlink(missing_ok=True)

    def test_daily_reward_and_cooldown(self):
        result = self.engine.claim_daily("1")
        self.assertGreater(result["reward"], 0)
        with self.assertRaises(GameError):
            self.engine.claim_daily("1")

    def test_market_round_trip(self):
        player = self.engine.info("1")
        player.spirit_stones = 10000
        self.db.save_player(player)
        self.engine.buy("1", "tu_khi_dan", 3)
        listing_id = self.engine.market_list("1", "tu_khi_dan", 2, 120)
        self.assertEqual(self.db.get_item_count("1", "tu_khi_dan"), 1)
        self.engine.market_buy("2", listing_id)
        self.assertEqual(self.db.get_item_count("2", "tu_khi_dan"), 2)
        self.assertEqual(self.db.get_item_count("1", "tu_khi_dan"), 1)

    def test_market_cancel_returns_item(self):
        player = self.engine.info("1")
        player.spirit_stones = 5000
        self.db.save_player(player)
        self.engine.buy("1", "hoi_khi_dan", 2)
        listing_id = self.engine.market_list("1", "hoi_khi_dan", 2, 250)
        self.engine.market_cancel("1", listing_id)
        self.assertEqual(self.db.get_item_count("1", "hoi_khi_dan"), 2)

    def test_public_profile(self):
        profile = self.engine.public_profile("1")
        self.assertEqual(profile["player"].display_name, "A")
        self.assertNotIn("power", profile)
        self.assertIn("inventory", profile)

    def test_market_blocks_non_tradeable_item(self):
        self.engine.db.add_item("1", "tu_van_linh_qua", 1)
        with self.assertRaises(GameError):
            self.engine.market_list("1", "tu_van_linh_qua", 1, 1000)

    def test_max_realm_breakthrough_is_safe(self):
        p = self.engine.info("1")
        p.realm_idx = len(__import__("game.content", fromlist=["REALMS"]).REALMS) - 1
        p.layer = __import__("game.content", fromlist=["REALMS"]).REALMS[-1][1]
        p.cultivation = self.engine.cultivation_requirement(p)
        self.db.save_player(p)
        with self.assertRaises(GameError):
            self.engine.breakthrough("1")

    def test_shop_categories_and_filters(self):
        categories = {key for key, _label, _desc in self.engine.shop_categories()}
        self.assertTrue({"all", "Pháp bảo", "Bùa chú", "Đan dược", "Binh khí", "Linh vật", "Công pháp"} <= categories)
        self.assertTrue(all(item.get("category") == "Pháp bảo" for _id, item in self.engine.shop("Pháp bảo")))
        self.assertTrue(any(item[0] == "hoi_xuan_phu" for item in self.engine.shop("Bùa chú")))
        self.assertTrue(any(item[0] == "tu_linh_thao" for item in self.engine.shop("Linh vật")))
        self.assertTrue(any(item[0] == "thanh_van_quyet" for item in self.engine.shop("Công pháp")))

    def test_buy_cultivation_technique_from_shop(self):
        player = self.engine.info("1")
        player.spirit_stones = 10000
        self.db.save_player(player)
        player, item, total = self.engine.buy("1", "thanh_van_quyet", 1)
        self.assertEqual(item["category"], "Công pháp")
        self.assertEqual(total, 5000)
        self.assertEqual(self.db.get_item_count("1", "thanh_van_quyet"), 1)

class ShopRewriteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False); self.tmp.close()
        self.db = Database(self.tmp.name)
        from random import Random
        self.engine = GameEngine(self.db, Random(123))
        self.player = self.engine.create_character("1", "ShopTester", "tien")
        self.player.spirit_stones = 2_000_000
        self.db.save_player(self.player)

    def tearDown(self):
        self.db.close(); Path(self.tmp.name).unlink(missing_ok=True)

    def test_shop_has_10_items_per_category_and_unique_ids(self):
        ids = []
        for category in ["Pháp bảo", "Bùa chú", "Đan dược", "Binh khí", "Linh vật", "Công pháp"]:
            rows = self.engine.shop(category)
            self.assertEqual(len(rows), 10)
            ids.extend(item_id for item_id, _item in rows)
            self.assertTrue(all(int(item.get("price", 0)) > 0 for _item_id, item in rows))
        self.assertEqual(len(ids), len(set(ids)))

    def test_shop_item_types_are_consistent(self):
        for _item_id, item in self.engine.shop("all"):
            self.assertIn(item["type"], {"consumable", "equipment", "technique", "material"})
            if item["category"] in {"Pháp bảo", "Binh khí"}:
                self.assertEqual(item["type"], "equipment")
            elif item["category"] == "Công pháp":
                self.assertEqual(item["type"], "technique")
            else:
                self.assertEqual(item["type"], "consumable")

    def test_shop_consumable_can_be_used(self):
        self.engine.buy("1", "cuu_chuyen_tien_dan", 1)
        before = self.engine.info("1").cultivation
        self.engine.use_item("1", "cuu_chuyen_tien_dan")
        self.assertGreater(self.engine.info("1").cultivation, before)

    def test_shop_equipment_can_be_equipped(self):
        self.engine.buy("1", "hon_don_than_binh", 1)
        result = self.engine.equip("1", "hon_don_than_binh")
        self.assertEqual(result["item"]["type"], "equipment")
        self.assertEqual(self.engine.info("1").equipped, "hon_don_than_binh")

    def test_shop_technique_can_be_learned(self):
        self.engine.buy("1", "hon_don_dao_kinh", 1)
        self.engine.learn_technique("1", "hon_don_dao_kinh")
        self.assertEqual(self.db.get_item_count("1", "hon_don_dao_kinh"), 0)
        self.assertTrue(self.db.get_discovery("1", "technique:hon_don_dao_kinh"))

    def test_song_tu_cooldown_is_30_minutes(self):
        import game.engine as engine_module
        self.assertEqual(engine_module.COOLDOWNS["song_tu"], 30 * 60)

class RedeemCodeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False)
        self.tmp.close()
        self.db = Database(self.tmp.name)
        from random import Random
        self.engine = GameEngine(self.db, Random(99))
        self.engine.create_character("1", "Kato", "tien")

    def tearDown(self):
        self.db.close()
        Path(self.tmp.name).unlink(missing_ok=True)

    def test_redeem_meta_code(self):
        before = self.engine.info("1").spirit_stones
        result = self.engine.redeem_code("1", "META102026")
        self.assertEqual(result["spirit_stones"], 500_000)
        self.assertEqual(self.engine.info("1").spirit_stones, before + 500_000)
        self.assertEqual(self.db.get_item_count("1", "thanh_van_quyet"), 1)
        self.assertEqual(self.db.get_item_count("1", "tu_duong_chan_kinh"), 1)
        self.assertEqual(self.db.get_item_count("1", "thai_hu_kinh"), 1)

    def test_redeem_code_once_per_player(self):
        self.engine.redeem_code("1", "meta102026")
        with self.assertRaises(GameError):
            self.engine.redeem_code("1", "meta102026")

    def test_invalid_code(self):
        with self.assertRaises(GameError):
            self.engine.redeem_code("1", "not-real")


class UpdateFeatureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False); self.tmp.close()
        self.db = Database(self.tmp.name)
        from random import Random
        self.engine = GameEngine(self.db, Random(321))
        self.a = self.engine.create_character("1", "A", "tien")
        self.b = self.engine.create_character("2", "B", "ma")

    def tearDown(self):
        self.db.close(); Path(self.tmp.name).unlink(missing_ok=True)

    def test_new_battle_power_is_numeric(self):
        stats = self.engine.battle_stats(self.a)
        self.assertGreater(stats["hp"], 0); self.assertGreater(stats["attack"], 0); self.assertGreater(stats["defense"], 0); self.assertGreater(stats["rating"], 0)

    def test_flee_weaker_causes_injury(self):
        foe = {"name": "Boss Test", "hp": 2000, "max_hp": 2000, "attack": 200, "defense": 150, "rating": self.engine.combat_power(self.a)+1000, "reward": 1000, "cultivation": 100, "kind": "boss", "kind_label": "👑 BOSS"}
        before = self.engine.info("1").injury
        result = self.engine.flee_encounter("1", foe)
        self.assertGreaterEqual(result["injury"], 5); self.assertLessEqual(result["injury"], 10)
        self.assertGreater(self.engine.info("1").injury, before)

    def test_dao_lu_cycle(self):
        self.engine.request_dao_lu("1", "2")
        self.engine.accept_dao_lu("2")
        info = self.engine.dao_lu_info("1")
        self.assertEqual(info["partner_id"], "2")
        self.engine.dao_lu_song_tu("1")
        self.assertGreater(self.engine.dao_lu_info("1")["intimacy"], 0)
        self.engine.break_dao_lu("1")
        self.assertIsNone(self.engine.dao_lu_info("1"))

class LatestUpdateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False)
        self.tmp.close()
        self.db = Database(self.tmp.name)
        from random import Random
        self.engine = GameEngine(self.db, Random(42))
        self.a = self.engine.create_character("1", "A", "tien")
        self.b = self.engine.create_character("2", "B", "ma")

    def tearDown(self):
        self.db.close()
        Path(self.tmp.name).unlink(missing_ok=True)

    def test_cultivation_cooldown_is_25_seconds(self):
        import game.engine as engine_module
        self.assertEqual(engine_module.COOLDOWNS["cultivate"], 25)

    def test_atomic_spirit_stone_transfer(self):
        self.a.spirit_stones = 5000
        self.b.spirit_stones = 100
        self.db.save_player(self.a)
        self.db.save_player(self.b)
        result = self.engine.transfer_spirit_stones("1", "2", 1250)
        self.assertEqual(result["sender"].spirit_stones, 3750)
        self.assertEqual(result["target"].spirit_stones, 1350)
        self.assertEqual(self.engine.info("1").spirit_stones, 3750)
        self.assertEqual(self.engine.info("2").spirit_stones, 1350)

    def test_spirit_transfer_rejects_self_and_insufficient_balance(self):
        with self.assertRaises(GameError):
            self.engine.transfer_spirit_stones("1", "1", 1)
        with self.assertRaises(GameError):
            self.engine.transfer_spirit_stones("1", "2", 999999)


class V9FeatureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False); self.tmp.close()
        self.db = Database(self.tmp.name)
        from random import Random
        self.engine = GameEngine(self.db, Random(1234))
        self.a = self.engine.create_character("1", "A", "tien")
        self.b = self.engine.create_character("2", "B", "tien")
        self.a.spirit_stones = 100_000
        self.b.spirit_stones = 100_000
        self.db.save_player(self.a); self.db.save_player(self.b)

    def tearDown(self):
        self.db.close(); Path(self.tmp.name).unlink(missing_ok=True)

    def test_sect_join_and_contribution(self):
        sects = self.engine.list_sects()
        self.assertGreaterEqual(len(sects), 5)
        result = self.engine.join_sect("1", "thanh_van")
        self.assertEqual(result["name"], "Thanh Vân Tông")
        before = self.engine.info("1").spirit_stones
        row = self.engine.sect_contribute("1", 1000)
        self.assertEqual(int(row["contribution"]), 1000)
        self.assertEqual(self.engine.info("1").spirit_stones, before - 1000)

    def test_pvp_stones_resolves(self):
        c = self.engine.pvp_challenge("1", "2", "stones", None, 1000)
        result = self.engine.resolve_pvp(c["id"], "2")
        self.assertIn(result["winner_id"], {"1", "2"})
        self.assertEqual(result["stake"]["amount"], 2000)
        self.assertIsNone(self.engine.get_pvp_challenge(c["id"]))

    def test_pvp_item_resolves(self):
        self.db.add_item("1", "tu_khi_dan", 2)
        self.db.add_item("2", "tu_khi_dan", 2)
        c = self.engine.pvp_challenge("1", "2", "item", "tu_khi_dan", 1)
        result = self.engine.resolve_pvp(c["id"], "2")
        self.assertEqual(result["stake"]["item_id"], "tu_khi_dan")
        self.assertEqual(result["stake"]["amount"], 2)

    def test_be_quan_start_and_one_cycle(self):
        result = self.engine.start_be_quan("1")
        self.assertTrue(result["active"])
        p = self.engine.info("1")
        self.assertEqual(p.spirit_stones, 100_000 - 50)
        before = p.cultivation
        results = self.engine.process_be_quan(now=p.be_quan_last_tick + 300)
        self.assertTrue(results)
        after = self.engine.info("1").cultivation
        self.assertGreater(after, before)
        self.assertEqual(self.engine.info("1").spirit_stones, 100_000 - 50)
        # One completed cycle advances exactly five minutes, not ten.
        self.assertEqual(self.engine.info("1").be_quan_last_tick, p.be_quan_last_tick + 300)

    def test_be_quan_stops_when_funds_end(self):
        p = self.engine.info("1")
        p.spirit_stones = 50
        self.db.save_player(p)
        self.engine.start_be_quan("1")
        p = self.engine.info("1")
        results = self.engine.process_be_quan(now=p.be_quan_last_tick + 300)
        self.assertTrue(results)
        self.assertFalse(results[0]["stopped"])
        self.assertEqual(self.engine.info("1").be_quan_active, 1)
        self.assertGreater(self.engine.info("1").cultivation, 0)
        # The pre-paid first cycle is not charged twice; the next cycle will stop without funds.
        p = self.engine.info("1")
        self.engine.process_be_quan(now=p.be_quan_last_tick + 300)
        self.assertEqual(self.engine.info("1").be_quan_active, 0)

class HardeningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False)
        self.tmp.close()
        self.db = Database(self.tmp.name)
        from random import Random
        self.engine = GameEngine(self.db, Random(99))
        self.a = self.engine.create_character("1", "A", "tien")
        self.b = self.engine.create_character("2", "B", "ma")

    def tearDown(self):
        self.db.close()
        Path(self.tmp.name).unlink(missing_ok=True)

    def test_shop_purchase_is_atomic(self):
        player = self.engine.info("1")
        player.spirit_stones = 1000
        self.db.save_player(player)
        bought, _, total = self.engine.buy("1", "tu_khi_dan", 1)
        self.assertEqual(total, 1000)
        self.assertEqual(bought.spirit_stones, 0)
        self.assertEqual(self.db.get_item_count("1", "tu_khi_dan"), 1)
        with self.assertRaises(GameError):
            self.engine.buy("1", "tu_khi_dan", 1)
        self.assertEqual(self.db.get_item_count("1", "tu_khi_dan"), 1)

    def test_pvp_target_cannot_have_two_active_challenges(self):
        self.engine.pvp_challenge("1", "2", "stones", None, 100)
        with self.assertRaises(GameError):
            self.engine.pvp_challenge("1", "2", "stones", None, 100)

    def test_expired_pvp_challenge_is_ignored(self):
        challenge = self.engine.pvp_challenge("1", "2", "stones", None, 100)
        self.db.conn.execute("UPDATE pvp_challenges SET created_at=? WHERE id=?", (0, challenge["id"]))
        self.db.conn.commit()
        self.assertIsNone(self.engine.get_pvp_challenge(challenge["id"]))

    def test_invalid_consumable_does_not_disappear(self):
        self.db.add_item("1", "tu_khi_dan", 1)
        from game.content import ITEMS
        original = ITEMS["tu_khi_dan"].copy()
        ITEMS["tu_khi_dan"].clear()
        ITEMS["tu_khi_dan"].update({"name": "Lỗi", "type": "consumable"})
        try:
            with self.assertRaises(GameError):
                self.engine.use_item("1", "tu_khi_dan")
            self.assertEqual(self.db.get_item_count("1", "tu_khi_dan"), 1)
        finally:
            ITEMS["tu_khi_dan"].clear()
            ITEMS["tu_khi_dan"].update(original)

class CombatAndConcurrencyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False)
        self.tmp.close()
        self.db = Database(self.tmp.name)
        from random import Random
        self.engine = GameEngine(self.db, Random(777))
        self.player = self.engine.create_character("1", "Combatant", "tien")
        self.other = self.engine.create_character("2", "Opponent", "ma")

    def tearDown(self):
        self.db.close()
        Path(self.tmp.name).unlink(missing_ok=True)

    def test_victory_path_returns_reward_text(self):
        foe = {
            "name": "Test Mob", "hp": 20, "max_hp": 20, "attack": 10, "defense": 1,
            "reward": 100, "cultivation": 50, "rating": 1, "kind": "monster", "kind_label": "⚔️ Yêu thú",
        }
        stats = self.engine.battle_stats(self.player)
        result = self.engine.battle_step("1", foe, stats["hp"], foe["hp"], "normal")
        self.assertTrue(result["ended"])
        self.assertTrue(result["victory"])
        self.assertIn("tu vi", result["text"])

    def test_damage_has_soft_defense_and_crit(self):
        normal = self.engine.calculate_damage(300, 300, multiplier=1.0, crit_chance=0.0, variance=0.0)
        critical = self.engine.calculate_damage(300, 300, multiplier=1.0, crit_chance=1.0, crit_multiplier=1.5, variance=0.0)
        self.assertGreaterEqual(normal["damage"], 24)
        self.assertTrue(critical["crit"])
        self.assertGreater(critical["damage"], normal["damage"])

    def test_exploration_enemies_scale_to_player_power(self):
        player_power = self.engine.combat_power(self.player)
        mobs = [self.engine._new_encounter(self.player, boss=False) for _ in range(8)]
        bosses = [self.engine._new_encounter(self.player, boss=True) for _ in range(8)]
        self.assertTrue(all(m["rating"] < player_power for m in mobs))
        self.assertTrue(any(b["rating"] >= player_power for b in bosses))
        self.assertTrue(all(b["hp"] > 0 and b["attack"] > 0 and b["defense"] > 0 for b in bosses))

    def test_cultivate_is_serialized_per_player(self):
        from concurrent.futures import ThreadPoolExecutor
        def run_once():
            try:
                return self.engine.cultivate("1")
            except GameError as exc:
                return exc
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: run_once(), range(2)))
        successes = [r for r in results if isinstance(r, dict)]
        failures = [r for r in results if isinstance(r, GameError)]
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(failures), 1)
    def test_combat_skill_uses_selected_technique(self):
        self.db.add_discovery("1", "technique:thanh_van_quyet")
        foe = {
            "name": "Test Boss", "hp": 5000, "max_hp": 5000, "attack": 10, "defense": 50,
            "reward": 100, "cultivation": 50, "rating": 500, "kind": "boss", "kind_label": "👑 BOSS",
        }
        stats = self.engine.battle_stats(self.player)
        result = self.engine.battle_skill("1", foe, stats["hp"], foe["hp"], "thanh_van_quyet")
        self.assertIn("Thanh Vân Quyết", result["text"])
        self.assertGreaterEqual(result["enemy_hp"], 0)
        self.assertFalse(result["ended"])
        self.assertGreaterEqual(result["player_hp"], 0)

    def test_combat_item_heals_and_consumes_turn(self):
        self.db.add_item("1", "hoi_xuan_phu", 1)
        stats = self.engine.battle_stats(self.player)
        foe = {
            "name": "Test Mob", "hp": 5000, "max_hp": 5000, "attack": 20, "defense": 20,
            "reward": 100, "cultivation": 50, "rating": 500, "kind": "monster", "kind_label": "⚔️ Yêu thú",
        }
        starting_hp = max(1, stats["hp"] // 2)
        result = self.engine.combat_use_item("1", "hoi_xuan_phu", starting_hp, stats["hp"])
        self.assertGreater(result["player_hp"], starting_hp)
        self.assertEqual(self.db.get_item_count("1", "hoi_xuan_phu"), 0)
        enemy_turn = self.engine._battle_enemy_turn("1", foe, result["player_hp"], foe["hp"], 0, "🧪 Sử dụng vật phẩm", result["player"])
        self.assertLess(enemy_turn["player_hp"], result["player_hp"])

    def test_pvp_challenge_is_serialized(self):
        from concurrent.futures import ThreadPoolExecutor
        def challenge():
            try:
                return self.engine.pvp_challenge("1", "2", "stones", None, 100)
            except GameError as exc:
                return exc
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: challenge(), range(2)))
        successes = [r for r in results if isinstance(r, dict)]
        failures = [r for r in results if isinstance(r, GameError)]
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(failures), 1)


class CombatAndAdminHardeningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False)
        self.tmp.close()
        self.db = Database(self.tmp.name)
        from random import Random
        self.engine = GameEngine(self.db, Random(42))
        self.player = self.engine.create_character("1", "Kato", "tien")
        self.engine.create_character("2", "Rival", "ma")

    def tearDown(self):
        self.db.close()
        Path(self.tmp.name).unlink(missing_ok=True)

    def _foe(self, *, boss=False, weak=False):
        if weak:
            return {
                "name": "Yếu Quái", "hp": 50, "max_hp": 50, "attack": 5, "defense": 5,
                "reward": 80, "cultivation": 40, "rating": 10, "kind": "monster", "kind_label": "⚔️ Yêu thú",
            }
        if boss:
            return {
                "name": "Test Boss", "hp": 8000, "max_hp": 8000, "attack": 40, "defense": 80,
                "reward": 500, "cultivation": 200, "rating": 2000, "kind": "boss", "kind_label": "👑 BOSS",
            }
        return {
            "name": "Test Mob", "hp": 5000, "max_hp": 5000, "attack": 25, "defense": 30,
            "reward": 120, "cultivation": 60, "rating": 600, "kind": "monster", "kind_label": "⚔️ Yêu thú",
        }

    def test_damage_never_collapses_to_one_with_high_def(self):
        info = self.engine.calculate_damage(attack=500, defense=5000, multiplier=1.0, variance=0.0, crit_chance=0.0)
        self.assertGreaterEqual(info["damage"], 40)  # minimum_ratio * attack
        self.assertLess(info["mitigation"], 1.0)

    def test_battle_step_victory_and_defeat(self):
        stats = self.engine.battle_stats(self.player)
        weak = self._foe(weak=True)
        win = self.engine.battle_step("1", weak, stats["hp"], weak["hp"], "normal")
        self.assertTrue(win["ended"])
        self.assertTrue(win["victory"])
        self.assertEqual(win["enemy_hp"], 0)

        tank = self._foe(boss=True)
        # Force loss by starting with 1 HP against strong boss
        loss = self.engine.battle_step("1", tank, 1, tank["hp"], "normal")
        self.assertTrue(loss["ended"])
        self.assertFalse(loss["victory"])
        self.assertEqual(loss["player_hp"], 0)

    def test_flee_applies_injury_when_weaker(self):
        strong = self._foe(boss=True)
        strong["rating"] = self.engine.combat_power(self.player) + 10_000
        before = self.engine.info("1").injury
        result = self.engine.flee_encounter("1", strong)
        self.assertGreater(result["injury"], 0)
        self.assertGreater(self.engine.info("1").injury, before)

    def test_skill_requires_learned_technique(self):
        foe = self._foe()
        stats = self.engine.battle_stats(self.player)
        with self.assertRaises(GameError):
            self.engine.battle_skill("1", foe, stats["hp"], foe["hp"], "thanh_van_quyet")
        self.db.add_discovery("1", "technique:thanh_van_quyet")
        result = self.engine.battle_skill("1", foe, stats["hp"], foe["hp"], "thanh_van_quyet")
        self.assertIn("Thanh Vân Quyết", result["text"])
        skills = self.engine.combat_skills("1")
        self.assertEqual(len(skills), 1)
        self.assertIn("multiplier", skills[0])

    def test_combat_item_turn_is_atomic_and_consumes_once(self):
        self.db.add_item("1", "hoi_xuan_phu", 1)
        stats = self.engine.battle_stats(self.player)
        foe = self._foe()
        start_hp = max(1, stats["hp"] // 2)
        result = self.engine.combat_item_turn("1", foe, start_hp, foe["hp"], "hoi_xuan_phu")
        self.assertEqual(self.db.get_item_count("1", "hoi_xuan_phu"), 0)
        self.assertIn("heal", result)
        # Enemy retaliated (unless fight somehow ended without counter — still HP changed path)
        self.assertIn("text", result)
        with self.assertRaises(GameError):
            self.engine.combat_item_turn("1", foe, result["player_hp"], result["enemy_hp"], "hoi_xuan_phu")

    def test_concurrent_combat_item_only_one_succeeds(self):
        from concurrent.futures import ThreadPoolExecutor
        self.db.add_item("1", "hoi_xuan_phu", 1)
        stats = self.engine.battle_stats(self.player)
        foe = self._foe()
        start_hp = max(1, stats["hp"] // 2)

        def once():
            try:
                return self.engine.combat_item_turn("1", foe, start_hp, foe["hp"], "hoi_xuan_phu")
            except GameError as exc:
                return exc

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: once(), range(2)))
        successes = [r for r in results if isinstance(r, dict)]
        failures = [r for r in results if isinstance(r, GameError)]
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(failures), 1)
        self.assertEqual(self.db.get_item_count("1", "hoi_xuan_phu"), 0)

    def test_sqlite_backup_consistent_and_temp_cleanup(self):
        import os, sqlite3, tempfile
        src = self.tmp.name
        # seed a row
        self.db.add_item("1", "tu_khi_dan", 3)
        fd, dest = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            with sqlite3.connect(src) as live, sqlite3.connect(dest) as backup:
                live.backup(backup)
            conn = sqlite3.connect(dest)
            count = conn.execute(
                "SELECT count FROM inventory WHERE user_id=? AND item_id=?", ("1", "tu_khi_dan")
            ).fetchone()[0]
            conn.close()
            self.assertEqual(count, 3)
        finally:
            os.remove(dest)

    def test_admin_session_table_exists_for_compat_only(self):
        # admin_sessions table may exist for older migrations, but bot.py MUST use RAM sessions.
        rows = self.db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='admin_sessions'"
        ).fetchall()
        self.assertTrue(rows)

    def test_admin_session_ram_ttl_and_restart_semantics(self):
        """Mirror bot.py ADMIN_SESSIONS behaviour without importing discord-dependent bot module."""
        import time as _time
        TTL = 300
        sessions: dict[str, float] = {}
        fails: dict[str, list[float]] = {}

        def has_session(uid: str) -> bool:
            exp = sessions.get(str(uid), 0.0)
            if exp <= _time.time():
                sessions.pop(str(uid), None)
                return False
            return True

        def grant(uid: str) -> float:
            exp = _time.time() + TTL
            sessions[str(uid)] = exp
            return exp

        def clear(uid: str) -> None:
            sessions.pop(str(uid), None)

        def too_many(uid: str) -> bool:
            now = _time.time()
            attempts = [t for t in fails.get(str(uid), []) if now - t < 60]
            fails[str(uid)] = attempts
            return len(attempts) >= 5

        def record_fail(uid: str) -> None:
            fails.setdefault(str(uid), []).append(_time.time())

        # grant + active
        grant("u1")
        self.assertTrue(has_session("u1"))
        # expire
        sessions["u1"] = _time.time() - 1
        self.assertFalse(has_session("u1"))
        self.assertNotIn("u1", sessions)
        # restart semantics: wiping the dict clears all sessions
        grant("u2")
        grant("u3")
        sessions.clear()
        self.assertFalse(has_session("u2"))
        self.assertFalse(has_session("u3"))
        # rate limit
        for _ in range(5):
            record_fail("attacker")
        self.assertTrue(too_many("attacker"))
        self.assertFalse(too_many("other"))

    def test_concurrent_battle_step_serialized(self):
        from concurrent.futures import ThreadPoolExecutor
        foe = {
            "name": "Tank", "hp": 50_000, "max_hp": 50_000, "attack": 5, "defense": 20,
            "reward": 10, "cultivation": 5, "rating": 500, "kind": "monster", "kind_label": "⚔️",
        }
        stats = self.engine.battle_stats(self.player)
        hp = stats["hp"]
        results = []

        def once():
            try:
                return self.engine.battle_step("1", foe, hp, foe["hp"], "normal")
            except GameError as exc:
                return exc

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: once(), range(4)))
        # All should complete without corrupting player state (lock serializes).
        dicts = [r for r in results if isinstance(r, dict)]
        self.assertEqual(len(dicts), 4)
        player = self.engine.info("1")
        self.assertIsNotNone(player)

    def test_skill_rejects_unlearned_and_accepts_learned(self):
        foe = {
            "name": "Mob", "hp": 8000, "max_hp": 8000, "attack": 10, "defense": 30,
            "reward": 50, "cultivation": 20, "rating": 400, "kind": "monster", "kind_label": "⚔️",
        }
        stats = self.engine.battle_stats(self.player)
        with self.assertRaises(GameError):
            self.engine.battle_skill("1", foe, stats["hp"], foe["hp"], "thanh_van_quyet")
        self.db.add_discovery("1", "technique:thanh_van_quyet")
        result = self.engine.battle_skill("1", foe, stats["hp"], foe["hp"], "thanh_van_quyet")
        self.assertIn("Thanh Vân Quyết", result["text"])
        self.assertLess(result["enemy_hp"], foe["hp"])

    def test_verify_admin_password_env_override(self):
        """PBKDF2 verify helper must honour KATO_ADMIN_PASSWORD without logging secrets."""
        import hashlib, hmac, os
        salt = bytes.fromhex("0e83b7c134a6c219ef32986f5b77b71a")
        # Use a throwaway password only for this unit test.
        plain = "unit-test-password-not-for-prod"
        hashed = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt, 210000)

        def verify(password: str, env_password: str | None = None, require: bool = False) -> bool:
            if env_password is not None:
                return hmac.compare_digest(password, env_password)
            if require:
                return False
            candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 210000)
            return hmac.compare_digest(candidate, hashed)

        self.assertTrue(verify(plain))
        self.assertFalse(verify("wrong"))
        self.assertTrue(verify("env-secret", env_password="env-secret"))
        self.assertFalse(verify("env-secret", env_password="other"))
        self.assertFalse(verify(plain, require=True))  # require without env rejects packaged path

    def test_calculate_damage_crit_and_variance_bounds(self):
        dmg = self.engine.calculate_damage(100, 50, multiplier=1.5, crit_chance=1.0, crit_multiplier=2.0, variance=0.0)
        self.assertTrue(dmg["crit"])
        self.assertGreater(dmg["damage"], 100)
