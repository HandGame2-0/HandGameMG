"""Qt rendering for the boss fight minigame — no game rules live here.

Reads `BossFightConfig` / `BossFightRuntimeState` / `PlayerGameState` snapshots
handed to it by whoever drives the game (see `dev_harness.py`) and paints them.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QProgressBar, QSizePolicy, QVBoxLayout, QWidget

from game_framework.game_context import PlayerGameState
from minigames_shared_API.gesture_assets import get_gesture_image

from .config import BossFightConfig
from .state import BossFightRuntimeState

_BOSS_IMAGE_PATH = Path(__file__).parent / "assets" / "boss.webp"
_BOSS_IMAGE_HEIGHT = 180
_GESTURE_IMAGE_WIDTH = 100
_GESTURE_IMAGE_HEIGHT = 140


class BossFightView(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._gesture_pixmaps: dict[str, QPixmap] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        self._boss_hp_bar = QProgressBar()
        self._boss_hp_bar.setTextVisible(True)
        self._boss_hp_bar.setFormat("Boss HP: %v / %m")

        self._player_hp_bar = QProgressBar()
        self._player_hp_bar.setTextVisible(True)
        self._player_hp_bar.setFormat("Player HP: %v / %m")

        self._boss_image = QLabel()
        self._boss_image.setAlignment(Qt.AlignCenter)
        self._boss_image.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._boss_image.setFixedHeight(_BOSS_IMAGE_HEIGHT)
        self._boss_pixmap = QPixmap(str(_BOSS_IMAGE_PATH))
        if self._boss_pixmap.isNull():
            self._boss_image.setText("Boss")

        self._target_label = QLabel()
        self._target_label.setAlignment(Qt.AlignCenter)
        self._target_label.setStyleSheet("font-size: 48px; font-weight: bold;")

        self._gesture_image = QLabel()
        self._gesture_image.setAlignment(Qt.AlignCenter)
        self._gesture_image.setFixedSize(_GESTURE_IMAGE_WIDTH, _GESTURE_IMAGE_HEIGHT)

        self._gesture_timer_bar = QProgressBar()
        self._gesture_timer_bar.setTextVisible(False)

        self._match_timer_label = QLabel()
        self._score_label = QLabel()

        layout = QVBoxLayout(self)
        layout.addWidget(self._player_hp_bar)
        layout.addWidget(self._boss_hp_bar)
        layout.addWidget(self._boss_image)
        layout.addWidget(self._target_label)
        layout.addWidget(self._gesture_image, alignment=Qt.AlignCenter)
        layout.addWidget(self._gesture_timer_bar)
        layout.addWidget(self._match_timer_label)
        layout.addWidget(self._score_label)
        self._refresh_boss_image()

    def render_state(
        self,
        config: BossFightConfig,
        runtime: BossFightRuntimeState,
        player: PlayerGameState,
    ) -> None:
        self._player_hp_bar.setMaximum(runtime.player_max_hp)
        self._player_hp_bar.setValue(max(0, runtime.player_hp))
        self._boss_hp_bar.setMaximum(runtime.boss_max_hp)
        self._boss_hp_bar.setValue(max(0, runtime.boss_hp))
        self._target_label.setText(f"Show: {runtime.current_target_letter}")

        elapsed = config.gesture_time_limit_seconds - runtime.gesture_time_remaining
        reveal_after = config.gesture_time_limit_seconds * (
            min(100.0, max(0.0, config.gesture_image_reveal_percentage)) / 100
        )
        if elapsed + 1e-9 < reveal_after:
            self._gesture_image.clear()
        else:
            gesture_pixmap = self._gesture_pixmaps.get(runtime.current_target_letter)
            if gesture_pixmap is None:
                gesture_image = get_gesture_image(runtime.current_target_letter)
                gesture_pixmap = (
                    QPixmap(str(gesture_image)) if gesture_image is not None else QPixmap()
                )
                if not gesture_pixmap.isNull():
                    gesture_pixmap = gesture_pixmap.scaled(
                        _GESTURE_IMAGE_WIDTH,
                        _GESTURE_IMAGE_HEIGHT,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation,
                    )
                self._gesture_pixmaps[runtime.current_target_letter] = gesture_pixmap

            if not gesture_pixmap.isNull():
                self._gesture_image.setPixmap(gesture_pixmap)
            else:
                self._gesture_image.clear()

        self._gesture_timer_bar.setMaximum(int(config.gesture_time_limit_seconds * 1000))
        self._gesture_timer_bar.setValue(max(0, int(runtime.gesture_time_remaining * 1000)))
        self._match_timer_label.setText(f"Time left: {runtime.time_remaining:.1f}s")
        self._score_label.setText(f"Score: {player.score}")

    def _refresh_boss_image(self) -> None:
        if self._boss_pixmap.isNull():
            return

        margins = self.layout().contentsMargins()
        width = max(1, self.width() - margins.left() - margins.right())
        scaled = self._boss_pixmap.scaled(
            width,
            _BOSS_IMAGE_HEIGHT,
            Qt.KeepAspectRatioByExpanding,
            Qt.SmoothTransformation,
        )
        left = max(0, (scaled.width() - width) // 2)
        top = max(0, (scaled.height() - _BOSS_IMAGE_HEIGHT) // 2)
        self._boss_image.setPixmap(scaled.copy(left, top, width, _BOSS_IMAGE_HEIGHT))

    def resizeEvent(self, event) -> None:
        self._refresh_boss_image()
        super().resizeEvent(event)
