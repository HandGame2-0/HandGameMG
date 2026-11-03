"""Tunable difficulty settings for the boss fight minigame, loaded from stats.json."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

_DEFAULT_STATS_PATH = Path(__file__).parent / "stats.json"

_POSITIVE_FIELDS = (
    "charge_max",
    "charge_per_hit",
    "match_time_seconds",
    "gesture_time_limit_seconds",
)
_NON_NEGATIVE_FIELDS = (
    "points_per_hit",
    "charge_loss_per_miss",
    "time_penalty_seconds",
    "score_penalty_points",
)


@dataclass(frozen=True)
class BossFightConfig:
    # The communication bar starts empty and the match is won when it's full.
    charge_max: int
    charge_per_hit: int
    points_per_hit: int
    # Drained on a wrong letter and on a per-gesture timeout.
    charge_loss_per_miss: int

    match_time_seconds: float
    gesture_time_limit_seconds: float
    gesture_image_reveal_percentage: float

    # Extra per-gesture-timeout penalties; set to 0 in stats.json to disable one.
    time_penalty_seconds: float
    score_penalty_points: int

    def __post_init__(self) -> None:
        for name in _POSITIVE_FIELDS:
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} musi być dodatnie")
        for name in _NON_NEGATIVE_FIELDS:
            if getattr(self, name) < 0:
                raise ValueError(f"{name} nie może być ujemne")
        if not 0.0 <= self.gesture_image_reveal_percentage <= 100.0:
            raise ValueError("gesture_image_reveal_percentage musi być w zakresie 0-100")

    @classmethod
    def load(cls, path: Path | str = _DEFAULT_STATS_PATH) -> BossFightConfig:
        with open(path, encoding="utf-8") as f:
            return cls(**json.load(f))
