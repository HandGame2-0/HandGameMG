"""Outcome of a finished (or errored) match."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from types import MappingProxyType
from typing import Any

from .game_context import PlayerGameState, PlayerId
from .models import GameState


class GameEndReason(Enum):
    """Why a match ended. Only ERROR maps to `GameResult.final_state == GameState.ERROR`."""

    COMPLETED = auto()
    TIMEOUT = auto()
    ABORTED = auto()
    ERROR = auto()


@dataclass(frozen=True)
class GameResult:
    """What `BaseGame._finalize()` builds and hands to `GameEventSink.on_finished`."""

    session_id: str
    game_id: str
    final_state: GameState
    end_reason: GameEndReason
    player_results: Mapping[PlayerId, PlayerGameState]
    started_at: datetime
    finished_at: datetime
    duration_ms: float
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if self.duration_ms < 0:
            raise ValueError("duration_ms nie może być ujemne")
        object.__setattr__(self, "player_results", MappingProxyType(dict(self.player_results)))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
