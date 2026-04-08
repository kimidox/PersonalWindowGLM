import sys

from ui import main as main_desktop_agent
from ui_skill_agent import main as main_skill_agent


def main() -> None:

    main_skill_agent()

    # main_desktop_agent()


if __name__ == "__main__":
    main()
