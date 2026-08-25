"""Universal base class every hg2 minigame's main class inherits from."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget


class Minigame(QWidget):
    """Common contract for a minigame: a widget with a start/stop/reset lifecycle and a score."""

    game_won = Signal()
    game_lost = Signal()
    score_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._score = 0

    @property
    def score(self) -> int:
        return self._score

    def _set_score(self, value: int) -> None:
        self._score = value
        self.score_changed.emit(self._score)

    def start(self) -> None:
        """Begin (or resume) the game loop."""
        raise NotImplementedError

    def stop(self) -> None:
        """Pause the game loop."""
        raise NotImplementedError

    def reset(self) -> None:
        """Return the game to its initial state."""
        raise NotImplementedError
