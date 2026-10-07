import os
import sys
from pathlib import Path


def main() -> None:
    bot_directory = Path(__file__).resolve().parent / "kato-tutien"
    sys.path.insert(0, str(bot_directory))
    os.chdir(bot_directory)

    from bot import main as run_bot

    run_bot()


if __name__ == "__main__":
    main()
