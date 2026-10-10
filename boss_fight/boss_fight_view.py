"""Qt rendering for the boss fight minigame — no game rules live here.

Reads `BossFightConfig` / `BossFightRuntimeState` / `PlayerGameState` snapshots
handed to it by whoever drives the game (see `dev_harness.py`) and paints them.

Visual concept: a retro handheld-RPG battle screen. A green-field battlefield
holds the boss's HP window (top-left) and sprite-on-a-platform (top-right),
diagonally mirrored by the player's HP window (bottom-right) — the classic
Game Boy-era crisscross. Below it, a white dialogue box plays the role of the
message/command box: the letter to sign, its gesture flashcard, and a
countdown.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from game_framework.game_context import PlayerGameState
from minigames_shared_API.gesture_assets import get_gesture_image

from .config import BossFightConfig
from .state import BossFightRuntimeState

_ASSETS_DIR = Path(__file__).parent / "assets"
_BOSS_SPRITE_PATH = _ASSETS_DIR / "boss.png"
_PLAYER_SPRITE_PATH = _ASSETS_DIR / "player.png"
_BOSS_SPRITE_HEIGHT = 220
_PLAYER_SPRITE_HEIGHT = 150
_BOSS_PLATFORM_WIDTH = 260
_PLAYER_PLATFORM_WIDTH = 220
_PLATFORM_HEIGHT = 26
_GESTURE_IMAGE_WIDTH = 100
_GESTURE_IMAGE_HEIGHT = 140
_HP_BAR_HEIGHT = 14

_TARGET_LETTER_PIXEL_SIZE = 72
_NAME_PIXEL_SIZE = 15
_HP_TAG_PIXEL_SIZE = 12
_HP_VALUE_PIXEL_SIZE = 12
_INSTRUCTION_PIXEL_SIZE = 16
_FOOTER_PIXEL_SIZE = 15
_HINT_LABEL_PIXEL_SIZE = 16
_REVEAL_RING_DIAMETER = 36
_REVEAL_RING_STROKE = 4

# The target letter and the gesture flashcard ("hint box") scale up with the
# window, using this width as their 1.0x reference point.
_SCALE_REFERENCE_WIDTH = 720
_MIN_SCALE = 0.6
_MAX_SCALE = 2.2


def _scale_for_width(width: int) -> float:
    return min(_MAX_SCALE, max(_MIN_SCALE, width / _SCALE_REFERENCE_WIDTH))


# No bundled pixel-font file ships with this repo, so this falls back to a
# system monospace face — still reads as "retro HUD" thanks to the fixed
# pitch, even without true 8-bit glyphs.
_FONT_FAMILIES = ["Press Start 2P", "VT323", "Courier New", "DejaVu Sans Mono", "Liberation Mono"]

_FIELD_SKY = "#BEE7FA"
_FIELD_GROUND = "#BFE6A8"
_PLATFORM = "#8FB86B"
_BOX_BG = "#FFFFFF"
_BOX_BORDER = "#000000"
_CHIP_BG = "#F2F2F2"
_TEXT = "#000000"
_HP_GREEN = "#78C850"
_HP_YELLOW = "#F8D030"
_HP_RED = "#E03030"
_HP_TRACK = "#303030"
_ACCENT = "#E8A800"

_STYLE_SHEET = f"""
BossFightView {{
    background-color: {_BOX_BORDER};
}}
QFrame#battlefield {{
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 {_FIELD_SKY}, stop:0.62 {_FIELD_SKY},
        stop:0.62 {_FIELD_GROUND}, stop:1 {_FIELD_GROUND}
    );
    border: none;
}}
QFrame#platform {{
    background-color: {_PLATFORM};
    border: none;
    border-radius: {_PLATFORM_HEIGHT // 2}px;
}}
QFrame#hpBox {{
    background-color: {_BOX_BG};
    border: 3px solid {_BOX_BORDER};
    border-radius: 8px;
}}
QFrame#messageBox {{
    background-color: {_BOX_BG};
    border: 4px solid {_BOX_BORDER};
}}
QFrame#gestureCard {{
    background-color: {_BOX_BG};
    border: 3px solid {_BOX_BORDER};
    border-radius: 6px;
}}
QLabel {{
    color: {_TEXT};
    background: transparent;
}}
QFrame#counterChip {{
    background-color: {_CHIP_BG};
    border: 2px solid {_BOX_BORDER};
    border-radius: 6px;
}}
QProgressBar#gestureTimerBar {{
    border: 2px solid {_BOX_BORDER};
    border-radius: 4px;
    background-color: {_HP_TRACK};
    min-height: 8px;
    max-height: 8px;
}}
QProgressBar#gestureTimerBar::chunk {{
    background-color: {_ACCENT};
    border-radius: 3px;
}}
"""

_HP_BAR_STYLE = f"""
QProgressBar {{
    border: 2px solid {_BOX_BORDER};
    border-radius: 6px;
    background-color: {_HP_TRACK};
}}
QProgressBar::chunk {{
    background-color: __COLOR__;
    border-radius: 4px;
}}
"""


def _font(
    pixel_size: int, weight: QFont.Weight = QFont.Weight.Normal, italic: bool = False
) -> QFont:
    font = QFont()
    font.setFamilies(_FONT_FAMILIES)
    font.setStyleHint(QFont.StyleHint.Monospace, QFont.StyleStrategy.PreferMatch)
    font.setFixedPitch(True)
    font.setPixelSize(pixel_size)
    font.setWeight(weight)
    font.setItalic(italic)
    return font


def _hp_bar_color(current: int, maximum: int) -> str:
    ratio = current / maximum if maximum > 0 else 0.0
    if ratio > 0.5:
        return _HP_GREEN
    if ratio > 0.2:
        return _HP_YELLOW
    return _HP_RED


def _style_hp_bar(bar: QProgressBar, current: int, maximum: int) -> None:
    bar.setStyleSheet(_HP_BAR_STYLE.replace("__COLOR__", _hp_bar_color(current, maximum)))


def _key_out_light_background(image: QImage, brightness: int = 195, tolerance: int = 20) -> QImage:
    """Make near-white/grey pixels transparent — these sprite files bake in a flat
    canvas background instead of real alpha, which shows as a box on the field."""
    keyed = image.convertToFormat(QImage.Format_ARGB32)
    for y in range(keyed.height()):
        for x in range(keyed.width()):
            color = keyed.pixelColor(x, y)
            channels = (color.red(), color.green(), color.blue())
            if min(channels) > brightness and max(channels) - min(channels) <= tolerance:
                color.setAlpha(0)
                keyed.setPixelColor(x, y, color)
    return keyed


def _load_sprite(path: Path, target_height: int) -> QPixmap:
    """Load a small pixel-art sprite and blow it up crisply (no smoothing blur)."""
    image = QImage(str(path))
    if image.isNull():
        return QPixmap()
    pixmap = QPixmap.fromImage(_key_out_light_background(image))
    return pixmap.scaledToHeight(target_height, Qt.FastTransformation)


class _CountdownRing(QWidget):
    """A small ring that fills clockwise from noon as `fraction` goes 0.0 -> 1.0."""

    def __init__(self, diameter: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._fraction = 0.0
        self.setFixedSize(diameter, diameter)

    def set_fraction(self, fraction: float) -> None:
        fraction = min(1.0, max(0.0, fraction))
        if fraction != self._fraction:
            self._fraction = fraction
            self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        inset = _REVEAL_RING_STROKE // 2
        rect = self.rect().adjusted(inset, inset, -inset, -inset)

        track_pen = QPen(QColor(_HP_TRACK))
        track_pen.setWidth(_REVEAL_RING_STROKE)
        painter.setPen(track_pen)
        painter.drawArc(rect, 0, 360 * 16)

        progress_pen = QPen(QColor(_ACCENT))
        progress_pen.setWidth(_REVEAL_RING_STROKE)
        progress_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(progress_pen)
        painter.drawArc(rect, 90 * 16, -int(360 * 16 * self._fraction))
        painter.end()


class BossFightView(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._gesture_pixmaps: dict[str, QPixmap] = {}
        self._gesture_width = _GESTURE_IMAGE_WIDTH
        self._gesture_height = _GESTURE_IMAGE_HEIGHT
        self._current_scale = 1.0
        self._build_ui()

    def _build_ui(self) -> None:
        # A plain QWidget ignores its own stylesheet background unless told to paint it.
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(_STYLE_SHEET)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_battlefield(), 3)
        root.addWidget(self._build_message_box(), 2)

    def _build_hp_box(self, name: str) -> tuple[QFrame, QProgressBar, QLabel]:
        box = QFrame()
        box.setObjectName("hpBox")

        name_label = QLabel(name)
        name_label.setFont(_font(_NAME_PIXEL_SIZE, QFont.Weight.Bold))

        hp_tag = QLabel("HP")
        hp_tag.setFont(_font(_HP_TAG_PIXEL_SIZE, QFont.Weight.Bold))

        bar = QProgressBar()
        bar.setTextVisible(False)
        bar.setFixedHeight(_HP_BAR_HEIGHT)
        _style_hp_bar(bar, 1, 1)

        value_label = QLabel()
        value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        value_label.setFont(_font(_HP_VALUE_PIXEL_SIZE))

        bar_row = QHBoxLayout()
        bar_row.setSpacing(6)
        bar_row.addWidget(hp_tag)
        bar_row.addWidget(bar, 1)

        layout = QVBoxLayout(box)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)
        layout.addWidget(name_label)
        layout.addLayout(bar_row)
        layout.addWidget(value_label, alignment=Qt.AlignRight)

        return box, bar, value_label

    def _build_counter_chip(self) -> tuple[QFrame, QLabel]:
        chip = QFrame()
        chip.setObjectName("counterChip")

        label = QLabel()
        label.setFont(_font(_FOOTER_PIXEL_SIZE, QFont.Weight.Bold))

        layout = QHBoxLayout(chip)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.addWidget(label)

        return chip, label

    def _build_battlefield(self) -> QFrame:
        battlefield = QFrame()
        battlefield.setObjectName("battlefield")

        self._boss_box, self._boss_hp_bar, self._boss_value = self._build_hp_box("Boss")
        self._player_box, self._player_hp_bar, self._player_value = self._build_hp_box("You")

        boss_stack = self._build_sprite_stack(
            _BOSS_SPRITE_PATH, _BOSS_SPRITE_HEIGHT, _BOSS_PLATFORM_WIDTH, "Boss"
        )
        player_stack = self._build_sprite_stack(
            _PLAYER_SPRITE_PATH, _PLAYER_SPRITE_HEIGHT, _PLAYER_PLATFORM_WIDTH, "You"
        )

        grid = QGridLayout(battlefield)
        grid.setContentsMargins(16, 16, 16, 16)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(12)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 2)
        grid.setRowStretch(0, 2)
        grid.setRowStretch(1, 1)

        # Classic crisscross: each combatant's HP window sits diagonally
        # opposite its own sprite.
        grid.addWidget(self._boss_box, 0, 0, alignment=Qt.AlignTop | Qt.AlignLeft)
        grid.addLayout(boss_stack, 0, 1, alignment=Qt.AlignTop | Qt.AlignRight)
        grid.addLayout(player_stack, 1, 0, alignment=Qt.AlignBottom | Qt.AlignLeft)
        grid.addWidget(self._player_box, 1, 1, alignment=Qt.AlignBottom | Qt.AlignRight)

        return battlefield

    def _build_sprite_stack(
        self, path: Path, sprite_height: int, platform_width: int, fallback_text: str
    ) -> QVBoxLayout:
        image = QLabel()
        image.setAlignment(Qt.AlignCenter)
        sprite = _load_sprite(path, sprite_height)
        if sprite.isNull():
            image.setText(fallback_text)
        else:
            image.setPixmap(sprite)

        platform = QFrame()
        platform.setObjectName("platform")
        platform.setFixedSize(platform_width, _PLATFORM_HEIGHT)

        stack = QVBoxLayout()
        stack.setSpacing(0)
        stack.addWidget(image, alignment=Qt.AlignHCenter)
        stack.addWidget(platform, alignment=Qt.AlignHCenter)
        return stack

    def _build_message_box(self) -> QFrame:
        message_box = QFrame()
        message_box.setObjectName("messageBox")

        self._instruction_label = QLabel("Sign this letter!")
        self._instruction_label.setFont(_font(_INSTRUCTION_PIXEL_SIZE, QFont.Weight.Bold))

        self._target_label = QLabel()
        self._target_label.setAlignment(Qt.AlignCenter)
        self._target_label.setFont(_font(_TARGET_LETTER_PIXEL_SIZE, QFont.Weight.Black))

        self._gesture_image = QLabel()
        self._gesture_image.setAlignment(Qt.AlignCenter)

        self._hint_label = QLabel("HINT")
        self._hint_label.setAlignment(Qt.AlignCenter)
        self._hint_label.setFont(_font(_HINT_LABEL_PIXEL_SIZE, QFont.Weight.Bold))

        self._reveal_ring = _CountdownRing(_REVEAL_RING_DIAMETER)

        hint_placeholder = QWidget()
        hint_placeholder_layout = QVBoxLayout(hint_placeholder)
        hint_placeholder_layout.setContentsMargins(0, 0, 0, 0)
        hint_placeholder_layout.setSpacing(10)
        hint_placeholder_layout.addStretch(1)
        hint_placeholder_layout.addWidget(self._hint_label, alignment=Qt.AlignHCenter)
        hint_placeholder_layout.addWidget(self._reveal_ring, alignment=Qt.AlignHCenter)
        hint_placeholder_layout.addStretch(1)

        self._gesture_stack_widget = QWidget()
        self._gesture_stack_widget.setFixedSize(_GESTURE_IMAGE_WIDTH, _GESTURE_IMAGE_HEIGHT)
        self._gesture_stack = QStackedLayout(self._gesture_stack_widget)
        self._gesture_stack.addWidget(self._gesture_image)
        self._gesture_stack.addWidget(hint_placeholder)

        gesture_card = QFrame()
        gesture_card.setObjectName("gestureCard")
        gesture_card_layout = QVBoxLayout(gesture_card)
        gesture_card_layout.setContentsMargins(8, 8, 8, 8)
        gesture_card_layout.addWidget(self._gesture_stack_widget)

        self._gesture_timer_bar = QProgressBar()
        self._gesture_timer_bar.setObjectName("gestureTimerBar")
        self._gesture_timer_bar.setTextVisible(False)
        self._gesture_timer_bar.setFixedWidth(_GESTURE_IMAGE_WIDTH + 16)

        gesture_column = QVBoxLayout()
        gesture_column.setSpacing(8)
        gesture_column.addWidget(gesture_card, alignment=Qt.AlignHCenter)
        gesture_column.addWidget(self._gesture_timer_bar, alignment=Qt.AlignHCenter)

        practice_row = QHBoxLayout()
        practice_row.setSpacing(24)
        practice_row.addStretch(1)
        practice_row.addWidget(self._target_label)
        practice_row.addLayout(gesture_column)
        practice_row.addStretch(1)

        score_chip, self._score_label = self._build_counter_chip()
        timer_chip, self._match_timer_label = self._build_counter_chip()

        footer_row = QHBoxLayout()
        footer_row.addWidget(score_chip)
        footer_row.addStretch(1)
        footer_row.addWidget(timer_chip)

        layout = QVBoxLayout(message_box)
        layout.setContentsMargins(20, 16, 20, 12)
        layout.setSpacing(14)
        layout.addWidget(self._instruction_label)
        layout.addLayout(practice_row)
        layout.addStretch(1)
        layout.addLayout(footer_row)

        return message_box

    def resizeEvent(self, event) -> None:
        self._apply_scale(_scale_for_width(self.width()))
        super().resizeEvent(event)

    def _apply_scale(self, scale: float) -> None:
        if scale == self._current_scale:
            return
        self._current_scale = scale

        self._target_label.setFont(
            _font(round(_TARGET_LETTER_PIXEL_SIZE * scale), QFont.Weight.Black)
        )
        self._hint_label.setFont(_font(round(_HINT_LABEL_PIXEL_SIZE * scale), QFont.Weight.Bold))

        self._gesture_width = round(_GESTURE_IMAGE_WIDTH * scale)
        self._gesture_height = round(_GESTURE_IMAGE_HEIGHT * scale)
        self._gesture_stack_widget.setFixedSize(self._gesture_width, self._gesture_height)
        self._gesture_timer_bar.setFixedWidth(self._gesture_width + round(16 * scale))
        ring_diameter = round(_REVEAL_RING_DIAMETER * scale)
        self._reveal_ring.setFixedSize(ring_diameter, ring_diameter)

        # Cached flashcard pixmaps were rendered at the old size — drop them so
        # the next render_state() reloads/rescales at the new gesture size.
        self._gesture_pixmaps.clear()

    def render_state(
        self,
        config: BossFightConfig,
        runtime: BossFightRuntimeState,
        player: PlayerGameState,
    ) -> None:
        player_hp = max(0, runtime.player_hp)
        self._player_hp_bar.setMaximum(runtime.player_max_hp)
        self._player_hp_bar.setValue(player_hp)
        _style_hp_bar(self._player_hp_bar, player_hp, runtime.player_max_hp)
        self._player_value.setText(f"{player_hp}/{runtime.player_max_hp}")

        boss_hp = max(0, runtime.boss_hp)
        self._boss_hp_bar.setMaximum(runtime.boss_max_hp)
        self._boss_hp_bar.setValue(boss_hp)
        _style_hp_bar(self._boss_hp_bar, boss_hp, runtime.boss_max_hp)
        self._boss_value.setText(f"{boss_hp}/{runtime.boss_max_hp}")

        self._target_label.setText(runtime.current_target_letter)

        elapsed = config.gesture_time_limit_seconds - runtime.gesture_time_remaining
        reveal_after = config.gesture_time_limit_seconds * (
            min(100.0, max(0.0, config.gesture_image_reveal_percentage)) / 100
        )
        if elapsed + 1e-9 < reveal_after:
            self._gesture_stack.setCurrentIndex(1)
            self._reveal_ring.set_fraction(elapsed / reveal_after)
        else:
            self._gesture_stack.setCurrentIndex(0)
            gesture_pixmap = self._gesture_pixmaps.get(runtime.current_target_letter)
            if gesture_pixmap is None:
                gesture_image = get_gesture_image(runtime.current_target_letter)
                gesture_pixmap = (
                    QPixmap(str(gesture_image)) if gesture_image is not None else QPixmap()
                )
                if not gesture_pixmap.isNull():
                    gesture_pixmap = gesture_pixmap.scaled(
                        self._gesture_width,
                        self._gesture_height,
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
        self._match_timer_label.setText(f"Time: {runtime.time_remaining:.0f}s")
        self._score_label.setText(f"Score: {player.score}")
