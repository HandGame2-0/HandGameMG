"""Frozen runtime state of an in-progress boss fight, replaced via `dataclasses.replace()`."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BossFightRuntimeState:
    boss_hp: int
    boss_max_hp: int
    player_hp: int
    player_max_hp: int
    time_remaining: float
    gesture_time_remaining: float
    current_target_letter: str

    def __post_init__(self) -> None:
        if self.boss_max_hp <= 0 or self.player_max_hp <= 0:
            raise ValueError("boss_max_hp i player_max_hp muszą być dodatnie")
        if self.time_remaining < 0 or self.gesture_time_remaining < 0:
            raise ValueError("czas pozostały nie może być ujemny")
