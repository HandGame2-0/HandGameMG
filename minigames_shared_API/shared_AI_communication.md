# shared_AI_communication

Wspólny interfejs między minigrami a systemem rozpoznawania gestów
(kamera + AI). Docelowy system jest budowany osobno — na razie interfejs
jest zasilany klawiaturą (`report_letter`), więc minigry mogą powstawać bez
czekania na gotowe rozpoznawanie.

```python
from minigames_shared_API import shared_AI_communication as ai
```

## Funkcje

- `report_letter(letter: str) -> None` — zgłasza nową literę (obecnie:
  wciśnięty klawisz). `letter` musi być pojedynczym znakiem A-Z, inaczej
  `ValueError`.
- `get_most_likely_letter() -> str | None` — zwraca ostatnio zgłoszoną
  literę albo `None`, jeśli jeszcze żadnej nie zgłoszono.
- `check_letter(letter: str) -> bool` — czy `letter` zgadza się z ostatnio
  zgłoszoną literą.
- `get_gesture_image(letter: str) -> Path | None` — zwraca ścieżkę do grafiki
  gestu dla litery albo `None`, jeśli grafika nie istnieje.
- `get_random_letter() -> str` — zwraca losową literę spośród tych, dla których
  istnieje grafika gestu.
- `clear() -> None` — czyści bieżący odczyt (np. między grami).
