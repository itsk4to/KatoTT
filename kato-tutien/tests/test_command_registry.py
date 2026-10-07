from pathlib import Path
import ast


def test_start_commands_are_registered():
    bot_path = Path(__file__).parents[1] / "bot.py"
    tree = ast.parse(bot_path.read_text(encoding="utf-8"))

    specs = {}
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CommandSpec"
        ):
            values = [ast.literal_eval(arg) for arg in node.args]
            name, aliases, *_rest = values
            handler = values[5]
            specs[name] = (tuple(aliases), handler)

    assert specs["tutien"] == (("tamuontutien", "tao"), "command_create")
    aliases, handler = specs["tutien"]
    assert "tamuontutien" in aliases
    assert "tao" in aliases
    assert handler == "command_create"
