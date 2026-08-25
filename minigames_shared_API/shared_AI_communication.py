"""
Placeholder for the real camera + AI hand-sign recognition system.

The actual camera/AI pipeline is being built separately. For now this
module is fed by keyboard presses instead (see `report_letter`), so
minigames can be developed and tested against a stable interface without
waiting for the real recognition backend.
"""

import random
import string
from pathlib import Path

_LETTERS = string.ascii_uppercase
_GESTURE_IMAGES_DIR = Path(__file__).parent / "gestures_images"
_GESTURE_IMAGES = {
    path.stem.removesuffix("_image"): path
    for path in _GESTURE_IMAGES_DIR.glob("*_image.png")
    if path.stem.removesuffix("_image") in _LETTERS
}
_AVAILABLE_LETTERS = tuple(sorted(_GESTURE_IMAGES))
_current_letter: str | None = None


def _normalize(letter: str) -> str:
    if not isinstance(letter, str) or len(letter.strip()) != 1 or letter.strip().upper() not in _LETTERS:
        raise ValueError("letter must be a single A-Z character")
    return letter.strip().upper()


def report_letter(letter: str) -> None:
    """Feed a newly observed letter into the interface (currently: a keypress)."""
    global _current_letter
    _current_letter = _normalize(letter)


def get_most_likely_letter() -> str | None:
    """Return the letter the AI currently thinks is being shown, or None if nothing was reported yet."""
    return _current_letter


def check_letter(letter: str) -> bool:
    """Return True if `letter` is the one the AI currently thinks is being shown."""
    return _normalize(letter) == _current_letter


def get_gesture_image(letter: str) -> Path | None:
    """Return the image path for a letter, or None when no image is available."""
    return _GESTURE_IMAGES.get(_normalize(letter))


def get_random_letter() -> str:
    """Return a random letter that has a corresponding gesture image."""
    if not _AVAILABLE_LETTERS:
        raise RuntimeError(f"No gesture images found in {_GESTURE_IMAGES_DIR}")
    return random.choice(_AVAILABLE_LETTERS)


def clear() -> None:
    """Reset the current reading, e.g. between games or after it has been consumed."""
    global _current_letter
    _current_letter = None
