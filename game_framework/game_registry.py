"""Registry of playable minigames. Adding a new minigame is one line here."""

from __future__ import annotations

from boss_fight.boss_fight_game import BossFightGame

from .base_game import BaseGame

GAME_REGISTRY: dict[str, type[BaseGame]] = {
    BossFightGame.GAME_ID: BossFightGame,
}
