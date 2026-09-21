"""Shared state-vocabulary enums used across the game framework."""

from __future__ import annotations

from enum import Enum, auto


class GameState(Enum):
    """Lifecycle state of a `BaseGame` instance."""

    CREATED = auto()
    READY = auto()
    RUNNING = auto()
    PAUSED = auto()
    FINISHED = auto()
    ERROR = auto()


class GameMode(Enum):
    """Player arrangement a `GameContext` was started with."""

    SINGLE_PLAYER = auto()
    MULTIPLAYER_COOP = auto()
    MULTIPLAYER_VERSUS = auto()
