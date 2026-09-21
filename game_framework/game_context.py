"""Typed inputs a `BaseGame` receives when a match starts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from .models import GameMode

PlayerId = str
CameraId = str

_NON_NEGATIVE_FIELDS = (
    "gesture_timeout_ms",
    "hint_delay_ms",
    "hint_duration_ms",
    "sequence_length",
    "board_size",
    "allowed_mistakes",
)


@dataclass(frozen=True)
class DifficultyProfile:
    """A difficulty preset. Mirrors handgame-app's games/game_context.py."""

    level: int
    gesture_timeout_ms: int
    hint_delay_ms: int
    hint_duration_ms: int
    sequence_length: int
    board_size: int
    allowed_mistakes: int
    speed_multiplier: float = 1.0
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not 1 <= self.level <= 5:
            raise ValueError("level musi być w zakresie 1-5")
        for name in _NON_NEGATIVE_FIELDS:
            if getattr(self, name) < 0:
                raise ValueError(f"{name} nie może być ujemne")
        if self.speed_multiplier <= 0:
            raise ValueError("speed_multiplier musi być dodatnie")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True)
class PlayerGameState:
    """Per-player, per-match progress. Replace with `dataclasses.replace()`, never mutate."""

    player_id: PlayerId
    score: int = 0
    mistakes: int = 0
    hint_count: int = 0
    current_step: int = 0
    is_active: bool = True


@dataclass(frozen=True)
class GameContext:
    """Everything a minigame needs to start a match."""

    session_id: str
    game_id: str
    mode: GameMode
    difficulty: DifficultyProfile
    player_camera_mapping: Mapping[PlayerId, CameraId]
    selected_algorithms: Mapping[CameraId, str]
    config: Any = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "player_camera_mapping", MappingProxyType(dict(self.player_camera_mapping))
        )
        object.__setattr__(
            self, "selected_algorithms", MappingProxyType(dict(self.selected_algorithms))
        )
        if not self.player_camera_mapping:
            raise ValueError("player_camera_mapping nie może być puste")


DIFFICULTY_PRESETS: Mapping[int, DifficultyProfile] = MappingProxyType(
    {
        1: DifficultyProfile(
            level=1,
            gesture_timeout_ms=8000,
            hint_delay_ms=3000,
            hint_duration_ms=2000,
            sequence_length=3,
            board_size=3,
            allowed_mistakes=5,
            speed_multiplier=0.75,
        ),
        2: DifficultyProfile(
            level=2,
            gesture_timeout_ms=6500,
            hint_delay_ms=2500,
            hint_duration_ms=1800,
            sequence_length=4,
            board_size=3,
            allowed_mistakes=4,
            speed_multiplier=0.9,
        ),
        3: DifficultyProfile(
            level=3,
            gesture_timeout_ms=5000,
            hint_delay_ms=2000,
            hint_duration_ms=1500,
            sequence_length=5,
            board_size=4,
            allowed_mistakes=3,
            speed_multiplier=1.0,
        ),
        4: DifficultyProfile(
            level=4,
            gesture_timeout_ms=3500,
            hint_delay_ms=1500,
            hint_duration_ms=1200,
            sequence_length=6,
            board_size=4,
            allowed_mistakes=2,
            speed_multiplier=1.15,
        ),
        5: DifficultyProfile(
            level=5,
            gesture_timeout_ms=2500,
            hint_delay_ms=1000,
            hint_duration_ms=800,
            sequence_length=8,
            board_size=5,
            allowed_mistakes=1,
            speed_multiplier=1.3,
        ),
    }
)


def build_difficulty_profile(level: int) -> DifficultyProfile:
    """Return the preset `DifficultyProfile` for `level` (1-5).

    The preset numbers are placeholders picked to be internally consistent
    (harder = shorter timeouts, fewer allowed mistakes, faster pace) but have
    not been playtested.
    """
    try:
        return DIFFICULTY_PRESETS[level]
    except KeyError as exc:
        raise ValueError(f"brak profilu trudności dla poziomu {level}") from exc
