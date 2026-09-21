"""Gesture reference images and the currently-supported letter alphabet.

This is game content (which letters are playable, and their reference PNGs),
not AI inference — the polling AI stand-in this was originally bundled with
has been removed; minigames now receive gestures as events, not by polling.
"""

from __future__ import annotations

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


def get_gesture_image(letter: str) -> Path | None:
    """Return the image path for a letter, or None when no image is available."""
    return _GESTURE_IMAGES.get(letter.strip().upper())


def get_random_letter() -> str:
    """Return a random letter that has a corresponding gesture image."""
    if not _AVAILABLE_LETTERS:
        raise RuntimeError(f"No gesture images found in {_GESTURE_IMAGES_DIR}")
    return random.choice(_AVAILABLE_LETTERS)
