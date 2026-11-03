"""Tests for BossFightGame: pure Python, no Qt/qtbot/event loop required."""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Any

import pytest

from boss_fight.boss_fight_game import BossFightGame
from boss_fight.config import BossFightConfig
from game_framework.events import GameActionEvent, GestureRecognitionEvent
from game_framework.game_context import GameContext, PlayerGameState, build_difficulty_profile
from game_framework.game_result import GameEndReason, GameResult
from game_framework.models import GameMode, GameState

_SESSION_ID = "session-1"
_PLAYER_ID = "p1"
_CAMERA_ID = "cam1"


@dataclass
class RecordingSink:
    states: list[GameState] = field(default_factory=list)
    scores: list[PlayerGameState] = field(default_factory=list)
    hints: list[tuple[str, str]] = field(default_factory=list)
    actions: list[GameActionEvent] = field(default_factory=list)
    results: list[GameResult] = field(default_factory=list)
    errors: list[tuple[str, bool]] = field(default_factory=list)

    def on_state_changed(self, state: GameState) -> None:
        self.states.append(state)

    def on_score_changed(self, player_state: PlayerGameState) -> None:
        self.scores.append(player_state)

    def on_hint_requested(self, player_id: str, hint: str) -> None:
        self.hints.append((player_id, hint))

    def on_action_ready(self, action: GameActionEvent) -> None:
        self.actions.append(action)

    def on_finished(self, result: GameResult) -> None:
        self.results.append(result)

    def on_error(self, message: str, recoverable: bool) -> None:
        self.errors.append((message, recoverable))


def make_config(**overrides: Any) -> BossFightConfig:
    defaults = dict(
        charge_max=20,
        charge_per_hit=10,
        points_per_hit=100,
        charge_loss_per_miss=5,
        match_time_seconds=100.0,
        gesture_time_limit_seconds=5.0,
        gesture_image_reveal_percentage=50.0,
        time_penalty_seconds=1.0,
        score_penalty_points=50,
    )
    defaults.update(overrides)
    return BossFightConfig(**defaults)


def make_context(config: BossFightConfig) -> GameContext:
    return GameContext(
        session_id=_SESSION_ID,
        game_id=BossFightGame.GAME_ID,
        mode=GameMode.SINGLE_PLAYER,
        difficulty=build_difficulty_profile(1),
        player_camera_mapping={_PLAYER_ID: _CAMERA_ID},
        selected_algorithms={_CAMERA_ID: "stub"},
        config=config,
    )


def make_game(
    config: BossFightConfig | None = None,
) -> tuple[BossFightGame, RecordingSink, GameContext]:
    config = config or make_config()
    sink = RecordingSink()
    letters = itertools.cycle(["A", "B", "C", "D", "E"])
    game = BossFightGame(event_sink=sink, letter_provider=lambda: next(letters))
    context = make_context(config)
    game.start(context)
    return game, sink, context


def send_hit(game: BossFightGame, context: GameContext) -> None:
    target = game.get_expected_sign(_PLAYER_ID)
    assert target is not None
    game.handle_gesture(
        GestureRecognitionEvent(
            session_id=context.session_id,
            player_id=_PLAYER_ID,
            camera_id=_CAMERA_ID,
            recognized_sign=target,
            confidence=1.0,
        )
    )


def send_sign(game: BossFightGame, context: GameContext, sign: str) -> None:
    game.handle_gesture(
        GestureRecognitionEvent(
            session_id=context.session_id,
            player_id=_PLAYER_ID,
            camera_id=_CAMERA_ID,
            recognized_sign=sign,
            confidence=1.0,
        )
    )


def force_gesture_timeout(game: BossFightGame, config: BossFightConfig) -> None:
    game.update_frame(config.gesture_time_limit_seconds * 1000 + 1)


def test_start_transitions_to_running_and_sets_first_target() -> None:
    game, sink, _ = make_game()
    assert game.get_state() == GameState.RUNNING
    assert game.get_expected_sign(_PLAYER_ID) == "A"
    assert GameState.READY in sink.states
    assert GameState.RUNNING in sink.states


def test_hit_fills_charge_increases_score_and_advances_target() -> None:
    config = make_config()
    game, sink, context = make_game(config)

    send_hit(game, context)

    runtime = game.get_runtime_state()
    player = game.get_player_state(_PLAYER_ID)
    assert runtime.charge == config.charge_per_hit
    assert player.score == config.points_per_hit
    assert player.current_step == 1
    assert runtime.current_target_letter == "B"
    assert sink.actions[-1].action_type == "hit"
    assert sink.actions[-1].is_success is True


def test_full_charge_finalizes_as_completed_win() -> None:
    config = make_config(charge_max=20, charge_per_hit=10)
    game, sink, context = make_game(config)

    send_hit(game, context)
    send_hit(game, context)

    assert game.get_state() == GameState.FINISHED
    assert len(sink.results) == 1
    result = sink.results[0]
    assert result.end_reason == GameEndReason.COMPLETED
    assert result.metadata["outcome"] == "win"


def test_wrong_letter_drains_charge_and_keeps_target() -> None:
    config = make_config(charge_max=100, charge_per_hit=10, charge_loss_per_miss=4)
    game, sink, context = make_game(config)
    send_hit(game, context)  # charge 10, target now "B"

    send_sign(game, context, "Z")

    runtime = game.get_runtime_state()
    assert runtime.charge == 6
    assert runtime.current_target_letter == "B"
    assert game.get_player_state(_PLAYER_ID).mistakes == 1
    assert sink.actions[-1].action_type == "wrong"


def test_wrong_letter_charge_floors_at_zero() -> None:
    game, _, context = make_game()

    send_sign(game, context, "Z")

    assert game.get_runtime_state().charge == 0


def test_miss_via_gesture_timeout_drains_charge_and_penalizes() -> None:
    config = make_config(charge_max=100, charge_per_hit=10, charge_loss_per_miss=4)
    game, sink, context = make_game(config)
    send_hit(game, context)  # charge 10, score 100

    force_gesture_timeout(game, config)

    runtime = game.get_runtime_state()
    player = game.get_player_state(_PLAYER_ID)
    assert player.mistakes == 1
    assert player.score == 50
    assert runtime.charge == 6
    assert runtime.current_target_letter == "C"
    dt = (config.gesture_time_limit_seconds * 1000 + 1) / 1000.0
    expected_time_remaining = config.match_time_seconds - dt - config.time_penalty_seconds
    assert runtime.time_remaining == pytest.approx(expected_time_remaining)
    assert sink.actions[-1].action_type == "miss"


def test_match_timeout_finalizes_with_timeout_reason() -> None:
    config = make_config(match_time_seconds=1.0, gesture_time_limit_seconds=100.0)
    game, sink, _ = make_game(config)

    game.update_frame(2000)

    assert game.get_state() == GameState.FINISHED
    result = sink.results[0]
    assert result.end_reason == GameEndReason.TIMEOUT
    assert result.metadata["outcome"] == "timeout"


def test_handle_gesture_rejects_wrong_session_id() -> None:
    game, sink, _ = make_game()
    charge_before = game.get_runtime_state().charge

    game.handle_gesture(
        GestureRecognitionEvent(
            session_id="other-session",
            player_id=_PLAYER_ID,
            camera_id=_CAMERA_ID,
            recognized_sign="A",
            confidence=1.0,
        )
    )

    assert game.get_runtime_state().charge == charge_before
    assert len(sink.errors) == 1
    assert sink.errors[0][1] is True  # recoverable


def test_handle_gesture_rejects_wrong_player_id() -> None:
    game, sink, context = make_game()
    game.handle_gesture(
        GestureRecognitionEvent(
            session_id=context.session_id,
            player_id="unknown-player",
            camera_id=_CAMERA_ID,
            recognized_sign="A",
            confidence=1.0,
        )
    )
    assert len(sink.errors) == 1


def test_handle_gesture_rejects_wrong_camera_id() -> None:
    game, sink, context = make_game()
    game.handle_gesture(
        GestureRecognitionEvent(
            session_id=context.session_id,
            player_id=_PLAYER_ID,
            camera_id="wrong-camera",
            recognized_sign="A",
            confidence=1.0,
        )
    )
    assert len(sink.errors) == 1


def test_handle_gesture_rejects_when_not_running() -> None:
    sink = RecordingSink()
    game = BossFightGame(event_sink=sink)
    game.handle_gesture(
        GestureRecognitionEvent(
            session_id=_SESSION_ID,
            player_id=_PLAYER_ID,
            camera_id=_CAMERA_ID,
            recognized_sign="A",
            confidence=1.0,
        )
    )
    assert len(sink.errors) == 1


def test_reset_from_running_returns_to_created_and_allows_restart() -> None:
    game, _, context = make_game()

    game.reset()
    assert game.get_state() == GameState.CREATED
    assert game.get_result() is None

    game.start(context)
    assert game.get_state() == GameState.RUNNING


def test_reset_from_finished_returns_to_created() -> None:
    config = make_config(charge_max=10, charge_per_hit=10)
    game, sink, context = make_game(config)
    send_hit(game, context)
    assert game.get_state() == GameState.FINISHED

    game.reset()
    assert game.get_state() == GameState.CREATED
    assert game.get_result() is None


def test_end_called_twice_is_idempotent() -> None:
    config = make_config(charge_max=10, charge_per_hit=10)
    game, sink, context = make_game(config)
    send_hit(game, context)

    first = game.get_result()
    second = game.end(GameEndReason.ERROR)

    assert first is second
    assert len(sink.results) == 1
