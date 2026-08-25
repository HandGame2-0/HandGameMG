"""Tunable difficulty settings for the boss fight minigame, loaded from stats.json."""

import json
from dataclasses import dataclass
from pathlib import Path

_DEFAULT_STATS_PATH = Path(__file__).parent / "stats.json"


@dataclass
class BossFightConfig:
    boss_max_hp: int
    player_max_hp: int
    damage_per_hit: int
    points_per_hit: int
    player_damage_per_miss: int

    match_time_seconds: float
    gesture_time_limit_seconds: float
    gesture_image_reveal_percentage: float

    # Miss penalties. All apply on every miss; set to 0 in stats.json to disable one.
    time_penalty_seconds: float
    score_penalty_points: int
    boss_strengthen_hp: int

    @classmethod
    def load(cls, path: Path | str = _DEFAULT_STATS_PATH) -> "BossFightConfig":
        with open(path, encoding="utf-8") as f:
            return cls(**json.load(f))
