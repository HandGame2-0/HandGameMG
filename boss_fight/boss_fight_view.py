"""Qt rendering for the boss fight minigame — no game rules live here.

Reads `BossFightConfig` / `BossFightRuntimeState` / `PlayerGameState` snapshots
handed to it by whoever drives the game (see `dev_harness.py`) and paints them.

Visual concept: a retro handheld-RPG battle screen. The top 2/3 paints a
layered scene (starfield, astronaut, alien boss) with score and match time in
its top corners and the communication bar along its bottom edge. The bottom
1/3 is a white message box: the letter to sign, its gesture flashcard, and a
countdown.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QSizePolicy,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from game_framework.game_context import PlayerGameState
from minigames_shared_API.gesture_assets import get_gesture_image

from .config import BossFightConfig
from .state import BossFightRuntimeState

_ASSETS_DIR = Path(__file__).parent / "assets"
# Full-canvas layers of one scene, drawn bottom -> top.
_SCENE_LAYER_PATHS = tuple(
    _ASSETS_DIR / name for name in ("bg-war.png", "player-war.png", "boss-war.png")
)
# The source art is 3508 px wide; composite it once and keep it at this width.
_SCENE_MAX_WIDTH = 1920
_GESTURE_IMAGE_WIDTH = 100
_GESTURE_IMAGE_HEIGHT = 140
_CHARGE_BAR_HEIGHT = 14

_TARGET_LETTER_PIXEL_SIZE = 72
_NAME_PIXEL_SIZE = 15
_CHARGE_VALUE_PIXEL_SIZE = 12
_INSTRUCTION_PIXEL_SIZE = 16
_FOOTER_PIXEL_SIZE = 15
_HINT_LABEL_PIXEL_SIZE = 16
_REVEAL_RING_DIAMETER = 36
_REVEAL_RING_STROKE = 4

# The target letter and the gesture flashcard ("hint box") scale with the
# window, using this size as their 1.0x reference point. Height counts too, so
# they keep fitting in the message box's fixed 1/3 of the window.
_SCALE_REFERENCE_WIDTH = 720
_SCALE_REFERENCE_HEIGHT = 760
_MIN_SCALE = 0.6
_MAX_SCALE = 2.2


def _scale_for_size(width: int, height: int) -> float:
    scale = min(width / _SCALE_REFERENCE_WIDTH, height / _SCALE_REFERENCE_HEIGHT)
    return min(_MAX_SCALE, max(_MIN_SCALE, scale))


# No bundled pixel-font file ships with this repo, so this falls back to a
# system monospace face — still reads as "retro HUD" thanks to the fixed
# pitch, even without true 8-bit glyphs.
_FONT_FAMILIES = ["Press Start 2P", "VT323", "Courier New", "DejaVu Sans Mono", "Liberation Mono"]

_BOX_BG = "#FFFFFF"
_BOX_BORDER = "#000000"
_CHIP_BG = "#F2F2F2"
_TEXT = "#000000"
_CHARGE = "#30C8F0"
_TRACK = "#303030"
_ACCENT = "#E8A800"

_STYLE_SHEET = f"""
BossFightView {{
    background-color: {_BOX_BORDER};
}}
QFrame#chargeBox {{
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
    background-color: {_TRACK};
    min-height: 8px;
    max-height: 8px;
}}
QProgressBar#gestureTimerBar::chunk {{
    background-color: {_ACCENT};
    border-radius: 3px;
}}
QProgressBar#chargeBar {{
    border: 2px solid {_BOX_BORDER};
    border-radius: 6px;
    background-color: {_TRACK};
}}
QProgressBar#chargeBar::chunk {{
    background-color: {_CHARGE};
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


def _load_scene() -> QPixmap:
    """Stack the scene layers into one pixmap, downscaled once up front."""
    scene = QImage()
    painter: QPainter | None = None
    for path in _SCENE_LAYER_PATHS:
        layer = QImage(str(path))
        if layer.isNull():
            continue
        if painter is None:
            scene = layer.convertToFormat(QImage.Format_ARGB32_Premultiplied)
            painter = QPainter(scene)
        else:
            painter.drawImage(0, 0, layer)
    if painter is None:
        return QPixmap()
    painter.end()
    if scene.width() > _SCENE_MAX_WIDTH:
        scene = scene.scaledToWidth(_SCENE_MAX_WIDTH, Qt.SmoothTransformation)
    return QPixmap.fromImage(scene)


class _Battlefield(QFrame):
    """Paints the scene cover-style (fills the rect, keeps aspect, crops overflow)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._scene = _load_scene()
        self._scaled = QPixmap()
        self._scaled_for = QSize()

    def paintEvent(self, event) -> None:
        if self._scene.isNull():
            return
        if self._scaled_for != self.size():
            self._scaled_for = self.size()
            self._scaled = self._scene.scaled(
                self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
            )
        painter = QPainter(self)
        painter.drawPixmap(
            (self.width() - self._scaled.width()) // 2,
            (self.height() - self._scaled.height()) // 2,
            self._scaled,
        )
        painter.end()


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

        track_pen = QPen(QColor(_TRACK))
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
        battlefield = self._build_battlefield()
        message_box = self._build_message_box()
        # Ignore content size hints so the 2:1 split holds at every window size.
        for part in (battlefield, message_box):
            part.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Ignored)
        root.addWidget(battlefield, 2)
        root.addWidget(message_box, 1)

    def _build_charge_box(self) -> QFrame:
        box = QFrame()
        box.setObjectName("chargeBox")

        name_label = QLabel("Communication")
        name_label.setFont(_font(_NAME_PIXEL_SIZE, QFont.Weight.Bold))

        self._charge_bar = QProgressBar()
        self._charge_bar.setObjectName("chargeBar")
        self._charge_bar.setTextVisible(False)
        self._charge_bar.setFixedHeight(_CHARGE_BAR_HEIGHT)

        self._charge_value = QLabel()
        self._charge_value.setFont(_font(_CHARGE_VALUE_PIXEL_SIZE))

        layout = QHBoxLayout(box)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)
        layout.addWidget(name_label)
        layout.addWidget(self._charge_bar, 1)
        layout.addWidget(self._charge_value)

        return box

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
        battlefield = _Battlefield()

        score_chip, self._score_label = self._build_counter_chip()
        timer_chip, self._match_timer_label = self._build_counter_chip()

        top_row = QHBoxLayout()
        top_row.addWidget(score_chip)
        top_row.addStretch(1)
        top_row.addWidget(timer_chip)

        layout = QVBoxLayout(battlefield)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.addLayout(top_row)
        layout.addStretch(1)
        # 1:6:1 stretch keeps the bar at 3/4 of the width, centred.
        charge_row = QHBoxLayout()
        charge_row.addStretch(1)
        charge_row.addWidget(self._build_charge_box(), 6)
        charge_row.addStretch(1)
        layout.addLayout(charge_row)

        return battlefield

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

        letter_column = QVBoxLayout()
        letter_column.addStretch(1)
        letter_column.addWidget(self._instruction_label, alignment=Qt.AlignHCenter)
        letter_column.addWidget(self._target_label, alignment=Qt.AlignHCenter)
        letter_column.addStretch(1)

        layout = QHBoxLayout(message_box)
        layout.setContentsMargins(20, 12, 20, 12)
        layout.setSpacing(24)
        layout.addStretch(1)
        layout.addLayout(letter_column)
        layout.addLayout(gesture_column)
        layout.addStretch(1)

        return message_box

    def resizeEvent(self, event) -> None:
        self._apply_scale(_scale_for_size(self.width(), self.height()))
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
        self._charge_bar.setMaximum(runtime.charge_max)
        self._charge_bar.setValue(runtime.charge)
        self._charge_value.setText(f"{runtime.charge}/{runtime.charge_max}")

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
