"""Boss fight game logic: perform the shown gesture before time runs out.

Pure Python — no Qt, camera, or AI-model imports. Time is driven externally via
`update_frame(delta_ms)`; gestures arrive as pre-validated `GestureRecognitionEvent`s
via `handle_gesture()` -> `_on_gesture()`. See `boss_fight/boss_fight_view.py` for
rendering and `dev_harness.py` for the local Qt harness that drives this class.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from types import MappingProxyType
from typing import Any, ClassVar

from game_framework.base_game import BaseGame
from game_framework.events import GameActionEvent, GestureRecognitionEvent
from game_framework.game_context import GameContext, PlayerId
from game_framework.game_event_sink import GameEventSink
from game_framework.game_result import GameEndReason, GameResult
from game_framework.models import GameState
from minigames_shared_API.gesture_assets import get_random_letter

from .config import BossFightConfig
from .state import BossFightRuntimeState


class BossFightGame(BaseGame):
    GAME_ID: ClassVar[str] = "boss_fight"

    def __init__(
        self,
        event_sink: GameEventSink,
        letter_provider: Callable[[], str] | None = None,
    ) -> None:
        super().__init__(event_sink)
        self._letter_provider = letter_provider or get_random_letter
        self._config: BossFightConfig | None = None
        self._runtime: BossFightRuntimeState | None = None
        self._player_id: PlayerId | None = None

    # ----- BaseGame interface -----

    def start(self, context: GameContext) -> None:
        self._begin(context)
        if self.get_state() != GameState.READY:
            return
        config = (
            context.config
            if isinstance(context.config, BossFightConfig)
            else BossFightConfig.load()
        )
        self._config = config
        self._player_id = next(iter(context.player_camera_mapping))
        self._runtime = BossFightRuntimeState(
            charge=0,
            charge_max=config.charge_max,
            time_remaining=config.match_time_seconds,
            gesture_time_remaining=config.gesture_time_limit_seconds,
            current_target_letter=self._letter_provider(),
        )
        self._enter_running()

    def update_frame(self, delta_ms: float) -> None:
        if self.get_state() != GameState.RUNNING or self._runtime is None:
            return
        dt = delta_ms / 1000.0
        self._runtime = replace(
            self._runtime,
            time_remaining=max(0.0, self._runtime.time_remaining - dt),
            gesture_time_remaining=max(0.0, self._runtime.gesture_time_remaining - dt),
        )
        if self._runtime.time_remaining <= 0:
            self.end(GameEndReason.TIMEOUT)
            return
        if self._runtime.gesture_time_remaining <= 0:
            self._on_miss()

    def end(self, reason: GameEndReason = GameEndReason.COMPLETED) -> GameResult:
        return self._finalize(reason)

    def _on_gesture(self, event: GestureRecognitionEvent) -> None:
        assert self._runtime is not None
        sign = event.recognized_sign.strip().upper()
        if len(sign) != 1 or not sign.isalpha():
            return
        if sign == self._runtime.current_target_letter:
            self._on_hit(event)
        else:
            self._on_wrong(event)

    # ----- game-specific accessors -----

    def get_expected_sign(self, player_id: PlayerId) -> str | None:
        if self._runtime is None or player_id != self._player_id:
            return None
        return self._runtime.current_target_letter

    def get_runtime_state(self) -> BossFightRuntimeState:
        assert self._runtime is not None
        return self._runtime

    # ----- BaseGame extension points -----

    def _on_reset(self) -> None:
        self._config = None
        self._runtime = None
        self._player_id = None

    def _collect_metadata(self) -> Mapping[str, Any]:
        assert self._runtime is not None and self._player_id is not None
        player = self.get_player_state(self._player_id)
        outcome = "win" if self._runtime.charge >= self._runtime.charge_max else "timeout"
        return MappingProxyType(
            {
                "outcome": outcome,
                "charge": self._runtime.charge,
                "charge_max": self._runtime.charge_max,
                "hits": player.current_step,
                "misses": player.mistakes,
            }
        )

    # ----- rules -----

    def _on_hit(self, event: GestureRecognitionEvent) -> None:
        assert (
            self._runtime is not None and self._config is not None and self._player_id is not None
        )
        player = self.get_player_state(self._player_id)
        charge = min(self._runtime.charge_max, self._runtime.charge + self._config.charge_per_hit)
        self._update_player(
            self._player_id,
            score=player.score + self._config.points_per_hit,
            current_step=player.current_step + 1,
        )
        self._sink.on_action_ready(
            GameActionEvent(
                session_id=event.session_id,
                game_id=self.GAME_ID,
                player_id=self._player_id,
                action_type="hit",
                is_success=True,
                points_delta=self._config.points_per_hit,
                metadata=MappingProxyType(
                    {"sign": event.recognized_sign, "confidence": event.confidence}
                ),
            )
        )
        self._runtime = replace(self._runtime, charge=charge)
        if charge >= self._runtime.charge_max:
            self.end(GameEndReason.COMPLETED)
            return
        self._next_target()

    def _on_wrong(self, event: GestureRecognitionEvent) -> None:
        """A wrong letter drains charge; the target stays so the player can retry."""
        assert (
            self._runtime is not None and self._config is not None and self._player_id is not None
        )
        player = self.get_player_state(self._player_id)
        self._update_player(self._player_id, mistakes=player.mistakes + 1)
        self._runtime = replace(self._runtime, charge=self._drained_charge())
        self._sink.on_action_ready(
            GameActionEvent(
                session_id=event.session_id,
                game_id=self.GAME_ID,
                player_id=self._player_id,
                action_type="wrong",
                is_success=False,
                points_delta=0,
                metadata=MappingProxyType(
                    {"sign": event.recognized_sign, "confidence": event.confidence}
                ),
            )
        )

    def _on_miss(self) -> None:
        assert (
            self._runtime is not None and self._config is not None and self._player_id is not None
        )
        assert self._context is not None
        player = self.get_player_state(self._player_id)
        self._update_player(
            self._player_id,
            score=max(0, player.score - self._config.score_penalty_points),
            mistakes=player.mistakes + 1,
        )
        self._runtime = replace(
            self._runtime,
            charge=self._drained_charge(),
            time_remaining=max(
                0.0, self._runtime.time_remaining - self._config.time_penalty_seconds
            ),
        )
        self._sink.on_action_ready(
            GameActionEvent(
                session_id=self._context.session_id,
                game_id=self.GAME_ID,
                player_id=self._player_id,
                action_type="miss",
                is_success=False,
                points_delta=-self._config.score_penalty_points,
                metadata=MappingProxyType({}),
            )
        )
        self._next_target()

    def _drained_charge(self) -> int:
        assert self._runtime is not None and self._config is not None
        return max(0, self._runtime.charge - self._config.charge_loss_per_miss)

    def _next_target(self) -> None:
        assert self._runtime is not None and self._config is not None
        self._runtime = replace(
            self._runtime,
            current_target_letter=self._letter_provider(),
            gesture_time_remaining=self._config.gesture_time_limit_seconds,
        )
