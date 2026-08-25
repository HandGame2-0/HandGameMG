# Boss Fight — Minigame Blueprint

## Concept

An arcade-style minigame where the player defeats an opponent (the "boss")
by performing hand gestures. Each correct gesture deals damage to the
boss's health bar. Mistakes are punished by one or more of: less time
remaining, a lower score, or a stronger boss.

- **Genre:** reflex / gesture-matching, timed
- **Tech stack:** PySide6 (Qt widgets), Python
- **Gesture input:** [`shared_AI_communication`](../minigames_shared_API/shared_AI_communication.md)
  (`get_most_likely_letter`, `check_letter`) — the minigame never talks to
  the camera/AI directly, only through this shared interface, so the real
  recognition backend can be swapped in later without changing this game.

## Core loop

1. The game shows the player a target gesture (a letter) to perform.
2. On each tick, the game polls `get_most_likely_letter()` / calls
   `check_letter(target)`.
3. **Match found:**
   - Boss HP -= `damage_per_hit`
   - Score += `points_per_hit`
   - A new target gesture is chosen.
4. **Time runs out before a match (miss):**
   - One or more configured penalties apply (see below).
   - A new target gesture is chosen (round continues, unless out of time).
5. Loop continues until either:
   - Boss HP reaches 0 → **Win**
   - Match timer reaches 0 → **Lose**

## State machine

```
INTRO -> PROMPT_GESTURE -> WAITING_FOR_MATCH -> (HIT | MISS)
                                 |                   |
                                 v                   v
                          PROMPT_GESTURE      apply penalty
                                                      |
                                                      v
                                             PROMPT_GESTURE
                                             (or LOSE if time == 0)

WAITING_FOR_MATCH -> WIN   (when boss_hp <= 0)
WAITING_FOR_MATCH -> LOSE  (when match_time <= 0)
WIN / LOSE -> RESULTS
```

States map to a `QStackedWidget` (or an enum + explicit widget swap) with a
central `GameController` driving transitions on a `QTimer` tick.

## Data model

```python
@dataclass
class BossFightConfig:
    boss_max_hp: int = 100
    player_max_hp: int = 100
    damage_per_hit: int = 10
    points_per_hit: int = 100
    player_damage_per_miss: int = 10
    match_time_seconds: float = 60.0
    gesture_time_limit_seconds: float = 3.0   # time allowed per single gesture
    gesture_image_reveal_percentage: float = 50.0

    # miss penalties (all configurable independently, default: all active)
    time_penalty_seconds: float = 3.0
    score_penalty_points: int = 50
    boss_strengthen_hp: int = 5                # added to boss_max_hp / remaining hp
    boss_strengthen_damage_reduction: float = 0.0  # optional: reduce damage_per_hit

@dataclass
class BossFightState:
    boss_hp: int
    player_hp: int
    player_max_hp: int
    score: int
    time_remaining: float
    current_target_letter: str
    misses: int = 0
    hits: int = 0
```

`BossFightConfig` is the tunable difficulty knob set (easy/normal/hard
presets = different config instances). `BossFightState` is mutated each
tick by `GameController`.

## Miss penalty design

Polish spec says a miss can shorten time, reduce score, or strengthen the
boss. Rather than hard-coding one, `GameController.on_miss()` applies
whichever penalties are non-zero in `BossFightConfig`, so difficulty
presets can mix them (e.g. "easy" only reduces score a little; "hard" does
all three). Default recommendation for v1: apply all three at reduced
values so the mechanic reads clearly during playtesting.

```python
def on_miss(self, config: BossFightConfig, state: BossFightState) -> None:
    state.misses += 1
    state.player_hp = max(0, state.player_hp - config.player_damage_per_miss)
    state.time_remaining = max(0.0, state.time_remaining - config.time_penalty_seconds)
    state.score = max(0, state.score - config.score_penalty_points)
    state.boss_hp += config.boss_strengthen_hp
```

## UI layout (PySide6)

`QMainWindow`
- `QProgressBar` — boss health bar (top, styled red→yellow→green gradient
  as HP drops... or the reverse, boss-colored)
- `QProgressBar` — player health bar
- `QLabel` — boss sprite/portrait, changes on hit/miss for feedback
- `QLabel` — large "show this gesture" prompt (the target letter)
- `QLabel` — gesture image, revealed after the configured percentage of the
  per-gesture timer has elapsed
- `QProgressBar` or `QLCDNumber` — per-gesture countdown
- `QLabel` / `QLCDNumber` — match timer
- `QLabel` / `QLCDNumber` — score
- `QStackedWidget` pages: `IntroPage`, `FightPage`, `ResultsPage`

`GameController(QObject)` owns a `QTimer` (e.g. 10 Hz tick), reads
`shared_AI_communication`, mutates `BossFightState`, and emits Qt signals
(`hp_changed`, `score_changed`, `time_changed`, `gesture_changed`,
`game_won`, `game_lost`) that the view widgets connect to — keeps game
logic decoupled from Qt widgets for testability.

## Suggested module layout

```
boss_fight/
  blueprint.md          <- this file
  config.py              # BossFightConfig, difficulty presets
  state.py                # BossFightState dataclass
  controller.py           # GameController (QObject, timer, signals, rules)
  views/
    intro_page.py
    fight_page.py
    results_page.py
  main.py                 # QApplication entry point
```

## Open questions for next iteration

- Exact HP/damage/timing numbers — needs playtesting to tune.
- Should `gesture_time_limit_seconds` (per-gesture) exist separately from
  `match_time_seconds` (whole fight), or just the latter? Blueprint assumes
  both for tighter pacing, but could simplify to one.
- Visual/audio feedback on hit vs. miss — not scoped here, UI section only
  covers structural widgets.
- Difficulty presets (easy/normal/hard) — values not yet decided.
