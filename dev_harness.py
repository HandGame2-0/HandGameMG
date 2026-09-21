"""Local dev harness: plays the role of the missing GameController + camera/AI pipeline.

Real hand-gesture recognition and session/game orchestration live in the separate
handgame-app project. Until this app is wired into that pipeline, this harness lets
you play boss_fight locally: it owns the QTimer game loop, turns keyboard presses
into synthetic `GestureRecognitionEvent`s, and renders game state through
`BossFightView`. None of this lives inside `BossFightGame` itself.
"""

from __future__ import annotations

import uuid

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QVBoxLayout, QWidget

from boss_fight.boss_fight_game import BossFightGame
from boss_fight.boss_fight_view import BossFightView
from boss_fight.config import BossFightConfig
from game_framework.events import GameActionEvent, GestureRecognitionEvent
from game_framework.game_context import (
    CameraId,
    GameContext,
    PlayerGameState,
    PlayerId,
    build_difficulty_profile,
)
from game_framework.game_result import GameResult
from game_framework.models import GameMode, GameState

_TICK_MS = 100
_PLAYER_ID: PlayerId = "player-1"
_CAMERA_ID: CameraId = "keyboard-dev"


class BossFightHarness(QWidget):
    """A `GameEventSink` implementation plus a QTimer loop, for local manual play only."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = BossFightConfig.load()
        self._game = BossFightGame(event_sink=self)
        self._view = BossFightView(self)
        self._session_id = ""

        layout = QVBoxLayout(self)
        layout.addWidget(self._view)

        self._timer = QTimer(self)
        self._timer.setInterval(_TICK_MS)
        self._timer.timeout.connect(self._on_tick)

        self.setFocusPolicy(Qt.StrongFocus)

    def start(self) -> None:
        self._session_id = str(uuid.uuid4())
        context = GameContext(
            session_id=self._session_id,
            game_id=BossFightGame.GAME_ID,
            mode=GameMode.SINGLE_PLAYER,
            difficulty=build_difficulty_profile(1),
            player_camera_mapping={_PLAYER_ID: _CAMERA_ID},
            selected_algorithms={_CAMERA_ID: "keyboard-stub"},
            config=self._config,
        )
        self._game.start(context)
        self._render()
        self._timer.start()
        self.setFocus()

    def _on_tick(self) -> None:
        self._game.update_frame(_TICK_MS)
        self._render()

    def _render(self) -> None:
        if self._game.get_state() not in (GameState.RUNNING, GameState.PAUSED, GameState.FINISHED):
            return
        self._view.render_state(
            self._config, self._game.get_runtime_state(), self._game.get_player_state(_PLAYER_ID)
        )

    def keyPressEvent(self, event) -> None:
        text = event.text()
        if len(text) == 1 and text.isalpha():
            self._game.handle_gesture(
                GestureRecognitionEvent(
                    session_id=self._session_id,
                    player_id=_PLAYER_ID,
                    camera_id=_CAMERA_ID,
                    recognized_sign=text.upper(),
                    confidence=1.0,
                )
            )
            self._render()
        super().keyPressEvent(event)

    # ----- GameEventSink (structural Protocol implementation) -----

    def on_state_changed(self, state: GameState) -> None:
        pass

    def on_score_changed(self, player_state: PlayerGameState) -> None:
        self._render()

    def on_hint_requested(self, player_id: PlayerId, hint: str) -> None:
        print(f"Hint for {player_id}: {hint}")

    def on_action_ready(self, action: GameActionEvent) -> None:
        print(f"[action] {action}")

    def on_finished(self, result: GameResult) -> None:
        self._timer.stop()
        self._render()
        print(f"Game finished: {result.end_reason.name}, outcome={result.metadata.get('outcome')}")

    def on_error(self, message: str, recoverable: bool) -> None:
        print(f"[gesture rejected] {message}")
