"""Boss fight minigame: perform the shown gesture before time runs out."""

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QProgressBar, QSizePolicy, QVBoxLayout

from minigames_shared_API import shared_AI_communication as ai
from minigames_shared_API.minigame import Minigame

from .config import BossFightConfig
from .state import BossFightState

_TICK_MS = 100
_BOSS_IMAGE_PATH = Path(__file__).parent / "assets" / "boss.webp"
_BOSS_IMAGE_HEIGHT = 180
_GESTURE_IMAGE_WIDTH = 100
_GESTURE_IMAGE_HEIGHT = 140


class BossFight(Minigame):
    def __init__(self, config: BossFightConfig | None = None, parent=None):
        super().__init__(parent)
        self.config = config or BossFightConfig.load()
        self.state = self._new_state()
        self._gesture_pixmaps: dict[str, QPixmap] = {}

        self._timer = QTimer(self)
        self._timer.setInterval(_TICK_MS)
        self._timer.timeout.connect(self._on_tick)

        self._build_ui()
        self._refresh_ui()
        self.setFocusPolicy(Qt.StrongFocus)

    # ----- Minigame interface -----

    def start(self) -> None:
        ai.clear()
        self._timer.start()
        self.setFocus()

    def stop(self) -> None:
        self._timer.stop()

    def reset(self) -> None:
        self.stop()
        ai.clear()
        self.state = self._new_state()
        self._set_score(0)
        self._refresh_ui()

    def _new_state(self) -> BossFightState:
        return BossFightState(
            boss_hp=self.config.boss_max_hp,
            boss_max_hp=self.config.boss_max_hp,
            player_hp=self.config.player_max_hp,
            player_max_hp=self.config.player_max_hp,
            time_remaining=self.config.match_time_seconds,
            gesture_time_remaining=self.config.gesture_time_limit_seconds,
            current_target_letter=ai.get_random_letter(),
        )

    # ----- UI -----

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

    def _refresh_ui(self) -> None:
        self._player_hp_bar.setMaximum(self.state.player_max_hp)
        self._player_hp_bar.setValue(max(0, self.state.player_hp))
        self._boss_hp_bar.setMaximum(self.state.boss_max_hp)
        self._boss_hp_bar.setValue(max(0, self.state.boss_hp))
        self._target_label.setText(f"Show: {self.state.current_target_letter}")
        elapsed = self.config.gesture_time_limit_seconds - self.state.gesture_time_remaining
        reveal_after = self.config.gesture_time_limit_seconds * (
            min(100.0, max(0.0, self.config.gesture_image_reveal_percentage)) / 100
        )
        if elapsed + 1e-9 < reveal_after:
            self._gesture_image.clear()
        else:
            gesture_pixmap = self._gesture_pixmaps.get(self.state.current_target_letter)
            if gesture_pixmap is None:
                gesture_image = ai.get_gesture_image(self.state.current_target_letter)
                gesture_pixmap = QPixmap(str(gesture_image)) if gesture_image is not None else QPixmap()
                if not gesture_pixmap.isNull():
                    gesture_pixmap = gesture_pixmap.scaled(
                        _GESTURE_IMAGE_WIDTH,
                        _GESTURE_IMAGE_HEIGHT,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation,
                    )
                self._gesture_pixmaps[self.state.current_target_letter] = gesture_pixmap

            if not gesture_pixmap.isNull():
                self._gesture_image.setPixmap(gesture_pixmap)
            else:
                self._gesture_image.clear()
        self._gesture_timer_bar.setMaximum(int(self.config.gesture_time_limit_seconds * 1000))
        self._gesture_timer_bar.setValue(max(0, int(self.state.gesture_time_remaining * 1000)))
        self._match_timer_label.setText(f"Time left: {self.state.time_remaining:.1f}s")
        self._score_label.setText(f"Score: {self.score}")

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

    # ----- input -----

    def keyPressEvent(self, event) -> None:
        text = event.text()
        if len(text) == 1 and text.isalpha():
            ai.report_letter(text)
            if ai.check_letter(self.state.current_target_letter):
                self._on_hit()
        super().keyPressEvent(event)

    # ----- game loop -----

    def _on_tick(self) -> None:
        dt = _TICK_MS / 1000
        self.state.time_remaining -= dt
        self.state.gesture_time_remaining -= dt

        if self.state.time_remaining <= 0:
            self._end_game(won=False)
            return

        if self.state.gesture_time_remaining <= 0:
            self._on_miss()

        self._refresh_ui()

    # ----- rules -----

    def _on_hit(self) -> None:
        self.state.hits += 1
        self.state.boss_hp -= self.config.damage_per_hit
        self._set_score(self.score + self.config.points_per_hit)

        if self.state.boss_hp <= 0:
            self._end_game(won=True)
            return

        self._next_target()
        self._refresh_ui()

    def _on_miss(self) -> None:
        self.state.misses += 1
        self.state.player_hp = max(0, self.state.player_hp - self.config.player_damage_per_miss)
        self.state.time_remaining = max(0.0, self.state.time_remaining - self.config.time_penalty_seconds)
        self._set_score(max(0, self.score - self.config.score_penalty_points))
        self.state.boss_max_hp += self.config.boss_strengthen_hp
        self.state.boss_hp += self.config.boss_strengthen_hp

        if self.state.player_hp <= 0:
            self._end_game(won=False)
            return

        self._next_target()

    def _next_target(self) -> None:
        self.state.current_target_letter = ai.get_random_letter()
        self.state.gesture_time_remaining = self.config.gesture_time_limit_seconds

    def _end_game(self, won: bool) -> None:
        self.stop()
        self._refresh_ui()
        if won:
            self.game_won.emit()
        else:
            self.game_lost.emit()
