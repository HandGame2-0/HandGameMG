# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

HandGameMG (hg2) is a collection of Qt (PySide6) minigames controlled by hand-gesture
recognition (American Sign Language letters). Each minigame is a self-contained package
at the repo root (currently `boss_fight/`); more minigames are expected to be added the
same way.

The minigame contract mirrors the one used by the separate `handgame-app` project
(`src/handgame/games/base_game.py`, documented in its `docs/game_framework.md`), so
minigames built here can later be moved into that project with minimal changes. That
project's code is not available in this repo — `game_framework/` is a local
reimplementation of its documented contract, not a dependency on it. Treat any change to
`game_framework/`'s shape as something to keep close to that documented contract.

## Running

```
./.venv/bin/python main.py
```

There is no real hand-gesture recognition backend wired up yet, so `main.py` launches a
small local dev harness (`dev_harness.py`) that lets you play `boss_fight` with the
keyboard instead — see "Dev harness" below.

Dependencies: `PySide6`, plus `pytest`/`black`/`ruff`/`mypy` for the dev tooling declared
in `pyproject.toml`. If `.venv` doesn't exist or is missing packages:
`python -m venv .venv && ./.venv/bin/pip install -e ".[dev]"`.

Tests: `./.venv/bin/pytest tests/`. Lint/format/typecheck:
`./.venv/bin/black --check .`, `./.venv/bin/ruff check .`, `./.venv/bin/mypy game_framework boss_fight`.

## Architecture

### Game logic vs. Qt view split

Every minigame is split into two layers, and **game-logic classes must never import
`PySide6`, know about the camera, or run AI inference** — that split is what makes the
logic layer testable without Qt (`tests/test_boss_fight_game.py` constructs
`BossFightGame` directly, no qtbot/event loop):

- A **logic class** subclassing `game_framework.base_game.BaseGame` — pure Python, no Qt
  imports. It receives typed inputs (`GameContext` at `start()`, a `GestureRecognitionEvent`
  per gesture via `handle_gesture()` → `_on_gesture()`) and reports outcomes through a
  `GameEventSink` (score/state changes, per-gesture `GameActionEvent`s, a final
  `GameResult`). It never owns a `QTimer`/`QThread` — time is driven externally via
  `update_frame(delta_ms)`.
- A **Qt view** that only renders a state snapshot it's handed (no game rules, no
  gesture handling, no timers of its own).

See `boss_fight/boss_fight_game.py` (logic) and `boss_fight/boss_fight_view.py` (view)
for the reference pair.

### `game_framework/` — the shared contract

- `base_game.py` — `BaseGame(ABC)`: the state machine
  (`CREATED → READY → RUNNING ↔ PAUSED → FINISHED`, `ERROR` reachable from anywhere,
  `reset()` an unconditional escape hatch back to `CREATED`), the abstract
  `start()/update_frame()/end()/_on_gesture()` every minigame implements, and the
  provided `handle_gesture()` template method that validates an incoming
  `GestureRecognitionEvent` (state is RUNNING, `session_id`/`player_id`/`camera_id` match
  the active `GameContext`) before calling `_on_gesture()` — a minigame's `_on_gesture()`
  can assume the event is already valid. Protected helpers for subclasses: `_begin()`,
  `_enter_running()`, `_update_player()` (via `dataclasses.replace()`), `_finalize()`
  (idempotent, builds the `GameResult`). Subclasses may also override `_collect_metadata()`
  (extra fields for `GameResult.metadata`) and `_on_reset()` (clear subclass-private state).
- `game_context.py` — `PlayerId`/`CameraId` aliases, frozen `DifficultyProfile`,
  `PlayerGameState`, `GameContext` (mappings frozen via `MappingProxyType`),
  `build_difficulty_profile(level)`.
- `game_result.py` — `GameEndReason` (`COMPLETED, TIMEOUT, ABORTED, ERROR`) and frozen
  `GameResult`. `COMPLETED` covers any rule-driven ending (won or lost); `TIMEOUT` is
  reserved for the match clock running out. Which happened is in
  `GameResult.metadata["outcome"]` (`"win"|"loss"|"timeout"`).
- `events.py` — frozen `GestureRecognitionEvent` and `GameActionEvent`.
- `game_event_sink.py` — `GameEventSink`, a `typing.Protocol` (structural — no
  inheritance needed) a minigame's logic class reports through.
- `game_registry.py` — `GAME_REGISTRY: dict[str, type[BaseGame]]`; adding a new minigame
  is one entry here, keyed by its `GAME_ID`.

Dataclasses across this package are `frozen=True` and modified via `dataclasses.replace()`;
externally-exposed mappings are wrapped in `MappingProxyType`; validation errors raised
in `__post_init__` are worded in Polish, matching the target framework's convention.

### `minigames_shared_API/`

- `gesture_assets.py` — the only shared module minigames may use for gesture content: it
  exposes `get_random_letter()` and `get_gesture_image(letter)`, driven by
  `gestures_images/` (one `<LETTER>_image.png` per currently-playable letter — currently
  17 of 26). This is asset/content lookup, not AI inference, so both a minigame's logic
  class (to pick a target letter) and its view (to render the reference image) may import
  it directly.
- There is no AI-polling module anymore — gestures reach a minigame as pushed
  `GestureRecognitionEvent`s (see above), never by polling a global.

### Dev harness

Real camera/AI recognition and session orchestration (`GameController`/`SessionManager`)
live in the separate `handgame-app` project and aren't present here. `dev_harness.py`
(`BossFightHarness`) stands in for that just enough to keep this repo playable locally:
it owns the `QTimer` game loop, turns keyboard presses into synthetic
`GestureRecognitionEvent`s, builds the `GameContext`, and implements `GameEventSink`
itself. It is intentionally outside the game-logic class and not meant to be a reusable
GUI framework — only `main.py`'s entry point.

### Minigame package pattern (see `boss_fight/`)

Each minigame is a top-level package containing:
- `<name>_game.py` — the `BaseGame` subclass: game rules, hit/miss logic, a `GAME_ID`.
- `<name>_view.py` — the paired Qt view, rendering only.
- `config.py` — a frozen `@dataclass` of tunable difficulty numbers, loaded from a
  `stats.json` in the same package via `Config.load()`. Difficulty tuning is meant to
  happen by editing `stats.json`, not code.
- `state.py` — a frozen `@dataclass` holding runtime state for one in-progress game (HP,
  timers, current target), replaced via `dataclasses.replace()`, never mutated in place.
- `blueprint.md` — design doc for the minigame (concept, state machine, data model,
  planned module layout), written before/alongside implementation. Historical context
  only — it predates the `game_framework` contract and is not kept in sync with the code.
- `assets/` — images used only by that minigame (e.g. boss portrait).

`boss_fight` specifically: the match timer and per-gesture timer both count down via
`update_frame(delta_ms)`, driven externally by `dev_harness.py`'s 10 Hz `QTimer`. A
matching `GestureRecognitionEvent` damages the boss and picks a new target letter; the
per-gesture timer expiring counts as a miss, which damages the player, penalizes score
and match time, and strengthens the boss's current HP (capped at `boss_max_hp`, which
itself does not grow). The gesture's reference image is intentionally hidden until
`gesture_image_reveal_percentage` of the per-gesture timer has elapsed, to force the
player to attempt the gesture from memory first.

### Adding a new minigame

Follow the `boss_fight` package pattern above: subclass `game_framework.base_game.BaseGame`
for the logic (no Qt/camera/AI imports, ever), pair it with a Qt view that only renders,
read gesture content only through `minigames_shared_API.gesture_assets`, put tunable
numbers in a `stats.json` + `config.py` dataclass, register the logic class's `GAME_ID`
in `game_framework/game_registry.py`, and write `tests/test_<name>_game.py` against the
logic class directly (no Qt).
