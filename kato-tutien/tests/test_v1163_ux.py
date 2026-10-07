import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class V1163UXTests(unittest.TestCase):
    def setUp(self):
        self.source = (ROOT / "bot.py").read_text()
        self.tree = ast.parse(self.source)

    def test_command_registry_is_single_source(self):
        self.assertIn("class CommandSpec", self.source)
        self.assertIn("COMMAND_SPECS", self.source)
        self.assertIn("COMMAND_LOOKUP", self.source)
        self.assertIn("command_menu", self.source)

    def test_gui_views_exist(self):
        names = {n.name for n in ast.walk(self.tree) if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))}
        for name in {"MainMenuView", "InventoryView", "DaoView", "DaoLuView", "AscensionView", "SectTowerView", "TribulationView"}:
            self.assertIn(name, names)

    def test_no_manual_dispatch_dictionary_remains(self):
        self.assertNotIn('commands = {', self.source)
        self.assertIn('spec = COMMAND_LOOKUP.get(command)', self.source)

    def test_registry_handlers_are_declared(self):
        handler_names = {n.name for n in ast.walk(self.tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        self.assertIn("COMMAND_SPECS", self.source)
        # Every handler string in CommandSpec declarations must exist as a function.
        for line in self.source.splitlines():
            if "CommandSpec(" in line and "handler=" not in line:
                continue
        for handler in set(__import__("re").findall(r"CommandSpec\([^\n]*?\"(command_[a-z_]+)\"\)\s*$", self.source, __import__("re").M)): # smoke check for registry shape
            self.assertIn(handler, handler_names)

    def test_aliases_are_unique_in_registry_source(self):
        # Duplicate aliases are a UX bug because only the first command should own a name.
        registry_block = self.source.split("COMMAND_SPECS:", 1)[1].split("COMMAND_LOOKUP", 1)[0]
        import re
        aliases = []
        for match in re.finditer(r"CommandSpec\(\"[^\"]+\",\s*\(([^)]*)\)", registry_block):
            aliases.extend(re.findall(r"\"([^\"]+)\"", match.group(1)))
        self.assertEqual(len(aliases), len(set(aliases)))

    def test_key_ux_aliases_are_registered(self):
        for token in ['"menu"', '"mm"', '"trangchu"', '"kho"', '"thaptong"', '"top"']:
            self.assertIn(token, self.source)


if __name__ == "__main__":
    unittest.main()


def test_pvp_preview_exposes_balanced_stats_without_mutating_players():
    from game.database import Database
    from game.engine import GameEngine
    from pathlib import Path
    import tempfile
    from random import Random

    tmp = tempfile.NamedTemporaryFile(delete=False); tmp.close()
    db = Database(tmp.name)
    try:
        engine = GameEngine(db, Random(7))
        a = engine.create_character("p1", "A", "tien")
        b = engine.create_character("p2", "B", "ma")
        before = (a.cultivation, b.cultivation, a.spirit_stones, b.spirit_stones)
        preview = engine.pvp_preview("p1", "p2")
        assert 10 <= preview["challenger_chance"] <= 90
        assert abs(preview["challenger_chance"] + preview["target_chance"] - 100) < 0.001
        assert preview["challenger_stats"]["hp"] > 0
        assert preview["target_stats"]["hp"] > 0
        after_a, after_b = engine.info("p1"), engine.info("p2")
        assert before == (after_a.cultivation, after_b.cultivation, after_a.spirit_stones, after_b.spirit_stones)
    finally:
        db.close(); Path(tmp.name).unlink(missing_ok=True)
