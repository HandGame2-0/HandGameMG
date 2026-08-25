"""Mutable runtime state of an in-progress boss fight."""

from dataclasses import dataclass


@dataclass
class BossFightState:
    boss_hp: int
    boss_max_hp: int
    player_hp: int
    player_max_hp: int
    time_remaining: float
    gesture_time_remaining: float
    current_target_letter: str
    hits: int = 0
    misses: int = 0
