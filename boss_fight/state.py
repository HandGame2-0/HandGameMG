"""Frozen runtime state of an in-progress boss fight, replaced via `dataclasses.replace()`."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BossFightRuntimeState:
    charge: int
    charge_max: int
    time_remaining: float
    gesture_time_remaining: float
    current_target_letter: str

    def __post_init__(self) -> None:
        if self.charge_max <= 0:
            raise ValueError("charge_max musi być dodatnie")
        if self.time_remaining < 0 or self.gesture_time_remaining < 0:
            raise ValueError("czas pozostały nie może być ujemny")
