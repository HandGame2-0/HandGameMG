"""Application entry point: run with `./.venv/bin/python main.py` from the repository root."""

import sys

from PySide6.QtWidgets import QApplication

from boss_fight.boss_fight import BossFight


def main() -> None:
    app = QApplication(sys.argv)

    bossfight = BossFight()
    bossfight.setWindowTitle("Boss Fight")
    bossfight.resize(640, 560)
    bossfight.game_won.connect(lambda: print("You won!"))
    bossfight.game_lost.connect(lambda: print("You lost!"))
    bossfight.show()
    bossfight.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
