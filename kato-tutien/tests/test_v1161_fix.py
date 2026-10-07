import tempfile
import unittest
from pathlib import Path
from random import Random

from game.database import Database
from game.engine import GameEngine, GameError
from game.content import REALMS


class V1161FixTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False)
        self.tmp.close()
        self.db = Database(self.tmp.name)
        self.engine = GameEngine(self.db, Random(42))
        self.player = self.engine.create_character("1", "Tester", "tien")

    def tearDown(self):
        self.db.close()
        Path(self.tmp.name).unlink(missing_ok=True)

    def _set_ready_for_tribulation(self):
        p = self.engine.info("1")
        p.realm_idx = 9
        p.layer = REALMS[9][1]
        p.cultivation = self.engine.cultivation_requirement(p)
        self.db.save_player(p)
        return p

    def test_tribulation_requires_final_dujie_and_full_cultivation(self):
        p = self.engine.info("1")
        p.realm_idx = 9
        p.layer = 2
        p.cultivation = self.engine.cultivation_requirement(p)
        self.db.save_player(p)
        with self.assertRaises(GameError):
            self.engine.face_tribulation("1")
        p.layer = 3
        p.cultivation = 0
        self.db.save_player(p)
        with self.assertRaises(GameError):
            self.engine.face_tribulation("1")

    def test_successful_tribulation_advances_once(self):
        self._set_ready_for_tribulation()
        self.engine.rng = Random(1)
        result = self.engine.face_tribulation("1")
        self.assertTrue(result["success"])
        p2 = self.engine.info("1")
        self.assertEqual((p2.realm_idx, p2.layer), (10, 1))
        self.assertEqual(p2.cultivation, 0)
        with self.assertRaises(GameError):
            self.engine.face_tribulation("1")

    def test_breakthrough_cannot_skip_thien_kiep(self):
        self._set_ready_for_tribulation()
        with self.assertRaises(GameError):
            self.engine.breakthrough("1")

    def test_public_profile_has_no_power_field(self):
        self.assertNotIn("power", self.engine.public_profile("1"))

    def test_external_tower_really_climbs_sequentially_without_stat_buff(self):
        p = self.engine.info("1")
        before = (p.root, p.insight, p.foundation, p.mind)
        first = self.engine.trial_challenge("1")
        self.assertEqual(first["floor"], 1)
        p2 = self.engine.info("1")
        if first["success"]:
            self.assertEqual((p2.root, p2.insight, p2.foundation, p2.mind), before)
            self.assertEqual(p2.trial_best, 1)
            second = self.engine.trial_challenge("1")
            if second["success"]:
                self.assertEqual(second["floor"], 2)

    def test_external_tower_has_daily_limit(self):
        for _ in range(5):
            try:
                self.engine.trial_challenge("1")
            except GameError:
                break
        with self.assertRaises(GameError):
            self.engine.trial_challenge("1")

    def test_sect_tower_uses_sect_lock_state_consistently(self):
        self.engine.create_sect("1", "Cửu Thiên Kiếm Tông", "Kiếm đạo chính tông")
        first = self.engine.sect_tower_climb("1")
        self.assertEqual(first["floor"], 1)
        status = self.engine.sect_tower_status("1")
        self.assertEqual(status["attempts"], 1)


if __name__ == "__main__":
    unittest.main()
