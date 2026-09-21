"""Pure-Python base class every minigame's logic class inherits from.

No Qt, camera, or AI-model imports belong here or in any subclass of `BaseGame`.
A minigame receives typed inputs (`GameContext` at start, `GestureRecognitionEvent`
per gesture) and reports outcomes through `GameEventSink`. Everything Qt-shaped
lives one layer up, in a view / dev-harness that drives `update_frame()` and
`handle_gesture()` from the outside.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any, ClassVar

from .events import GestureRecognitionEvent
from .game_context import GameContext, PlayerGameState, PlayerId
from .game_event_sink import GameEventSink
from .game_result import GameEndReason, GameResult
from .models import GameState

_ALLOWED_TRANSITIONS: Mapping[GameState, frozenset[GameState]] = {
    GameState.CREATED: frozenset({GameState.READY, GameState.ERROR}),
    GameState.READY: frozenset({GameState.RUNNING, GameState.ERROR}),
    GameState.RUNNING: frozenset({GameState.PAUSED, GameState.FINISHED, GameState.ERROR}),
    GameState.PAUSED: frozenset({GameState.RUNNING, GameState.FINISHED, GameState.ERROR}),
    GameState.FINISHED: frozenset(),
    GameState.ERROR: frozenset(),
}


class BaseGame(ABC):
    """Abstract base class (not a `QObject`) for a minigame's domain logic."""

    GAME_ID: ClassVar[str]

    def __init__(self, event_sink: GameEventSink) -> None:
        self._sink = event_sink
        self._state: GameState = GameState.CREATED
        self._context: GameContext | None = None
        self._player_states: dict[PlayerId, PlayerGameState] = {}
        self._result: GameResult | None = None
        self._started_at: datetime | None = None

    # ---- required — implemented by every minigame ----

    @abstractmethod
    def start(self, context: GameContext) -> None: ...

    @abstractmethod
    def update_frame(self, delta_ms: float) -> None: ...

    @abstractmethod
    def end(self, reason: GameEndReason = GameEndReason.COMPLETED) -> GameResult: ...

    @abstractmethod
    def _on_gesture(self, event: GestureRecognitionEvent) -> None:
        """Called only after `handle_gesture()` has confirmed the event is valid."""

    # ---- provided — do not override ----

    def handle_gesture(self, event: GestureRecognitionEvent) -> None:
        """Validate `event` against the active session/context, then dispatch it."""
        if self._state != GameState.RUNNING:
            self._sink.on_error(
                f"Odrzucono gest: gra nie jest w stanie RUNNING (stan={self._state.name})", True
            )
            return
        if self._context is None or event.session_id != self._context.session_id:
            self._sink.on_error("Odrzucono gest: niezgodny session_id", True)
            return
        if event.player_id not in self._context.player_camera_mapping:
            self._sink.on_error(f"Odrzucono gest: nieznany player_id {event.player_id!r}", True)
            return
        if self._context.player_camera_mapping[event.player_id] != event.camera_id:
            self._sink.on_error(
                f"Odrzucono gest: niezgodny camera_id dla gracza {event.player_id!r}", True
            )
            return
        self._on_gesture(event)

    def pause(self) -> None:
        self._transition(GameState.PAUSED)

    def resume(self) -> None:
        self._transition(GameState.RUNNING)

    def reset(self) -> None:
        """Unconditionally return to CREATED, ready for the next session."""
        self._state = GameState.CREATED
        self._context = None
        self._player_states = {}
        self._result = None
        self._started_at = None
        self._on_reset()
        self._sink.on_state_changed(self._state)

    def use_hint(self, player_id: PlayerId) -> None:
        if self._state != GameState.RUNNING:
            self._sink.on_error("Nie można poprosić o podpowiedź poza stanem RUNNING", True)
            return
        hint = self.get_expected_sign(player_id)
        if hint is None:
            return
        state = self.get_player_state(player_id)
        self._update_player(player_id, hint_count=state.hint_count + 1)
        self._sink.on_hint_requested(player_id, hint)

    def get_state(self) -> GameState:
        return self._state

    def get_result(self) -> GameResult | None:
        return self._result

    def get_expected_sign(self, player_id: PlayerId) -> str | None:
        return None

    def get_player_state(self, player_id: PlayerId) -> PlayerGameState:
        return self._player_states[player_id]

    # ---- helpers for subclasses ----

    def _begin(self, context: GameContext) -> None:
        if not self._transition(GameState.READY):
            return
        self._context = context
        self._player_states = {
            player_id: PlayerGameState(player_id=player_id)
            for player_id in context.player_camera_mapping
        }
        self._result = None

    def _enter_running(self) -> None:
        if self._transition(GameState.RUNNING):
            self._started_at = datetime.now(UTC)

    def _update_player(self, player_id: PlayerId, **changes: Any) -> PlayerGameState:
        updated = replace(self._player_states[player_id], **changes)
        self._player_states[player_id] = updated
        self._sink.on_score_changed(updated)
        return updated

    def _finalize(self, reason: GameEndReason) -> GameResult:
        if self._result is not None:
            return self._result
        assert self._context is not None and self._started_at is not None
        target = GameState.ERROR if reason is GameEndReason.ERROR else GameState.FINISHED
        self._transition(target)
        finished_at = datetime.now(UTC)
        result = GameResult(
            session_id=self._context.session_id,
            game_id=self._context.game_id,
            final_state=self._state,
            end_reason=reason,
            player_results=dict(self._player_states),
            started_at=self._started_at,
            finished_at=finished_at,
            duration_ms=(finished_at - self._started_at).total_seconds() * 1000,
            metadata=self._collect_metadata(),
        )
        self._result = result
        self._sink.on_finished(result)
        return result

    # ---- extension points (not part of the documented handgame-app contract,
    # added here so subclasses have a place to hook cleanup/metadata without
    # overriding `reset()`/`_finalize()` directly) ----

    def _collect_metadata(self) -> Mapping[str, Any]:
        return {}

    def _on_reset(self) -> None:
        return None

    # ---- internal ----

    def _transition(self, target: GameState) -> bool:
        if target not in _ALLOWED_TRANSITIONS.get(self._state, frozenset()):
            self._sink.on_error(
                f"Nieprawidłowe przejście stanu: {self._state.name} -> {target.name}", False
            )
            return False
        self._state = target
        self._sink.on_state_changed(target)
        return True
