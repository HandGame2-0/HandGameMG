"""Callback interface a `BaseGame` reports outcomes through."""

from __future__ import annotations

from typing import Protocol

from .events import GameActionEvent
from .game_context import PlayerGameState, PlayerId
from .game_result import GameResult
from .models import GameState


class GameEventSink(Protocol):
    """Structural interface: any object with these six methods satisfies it."""

    def on_state_changed(self, state: GameState) -> None: ...

    def on_score_changed(self, player_state: PlayerGameState) -> None: ...

    def on_hint_requested(self, player_id: PlayerId, hint: str) -> None: ...

    def on_action_ready(self, action: GameActionEvent) -> None: ...

    def on_finished(self, result: GameResult) -> None: ...

    def on_error(self, message: str, recoverable: bool) -> None: ...
