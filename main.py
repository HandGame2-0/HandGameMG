"""Application entry point: run with `./.venv/bin/python main.py` from the repository root."""

import sys

from PySide6.QtWidgets import QApplication

from dev_harness import BossFightHarness


def main() -> None:
    app = QApplication(sys.argv)
    # Fusion renders the view's custom stylesheet (rounded progress bar chunks,
    # panel borders) consistently across platforms; native styles often ignore it.
    app.setStyle("Fusion")

    harness = BossFightHarness()
    harness.setWindowTitle("Boss Fight (dev harness)")
    harness.resize(720, 760)
    harness.show()
    harness.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
