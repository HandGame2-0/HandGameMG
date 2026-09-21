"""Events that flow into and out of a `BaseGame`."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from .game_context import CameraId, PlayerId


@dataclass(frozen=True)
class GestureRecognitionEvent:
    """A single recognized gesture, pushed into `BaseGame.handle_gesture()`."""

    session_id: str
    player_id: PlayerId
    camera_id: CameraId
    recognized_sign: str
    confidence: float
    latency_ms: float = 0.0

    def __post_init__(self) -> None:
        if not self.recognized_sign.strip():
            raise ValueError("recognized_sign nie może być puste")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence musi być w zakresie 0.0-1.0")
        if self.latency_ms < 0:
            raise ValueError("latency_ms nie może być ujemne")


@dataclass(frozen=True)
class GameActionEvent:
    """A per-gesture outcome a minigame reports via `GameEventSink.on_action_ready`."""

    session_id: str
    game_id: str
    player_id: PlayerId
    action_type: str
    is_success: bool
    points_delta: int
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not self.action_type.strip():
            raise ValueError("action_type nie może być puste")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
