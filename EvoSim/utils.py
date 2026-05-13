# utils.py
import numpy as np

def midi_to_freq(note: float) -> float:
    return 440.0 * (2.0 ** ((note - 69) / 12.0))

_ROLL_SHIFTS = [(-1, -1), (-1, 0), (-1, 1),
                ( 0, -1),          ( 0, 1),
                ( 1, -1), ( 1, 0), ( 1, 1)]

def count_neighbors(grid: np.ndarray) -> np.ndarray:
    n = np.zeros_like(grid, dtype=np.int32)
    for dx, dy in _ROLL_SHIFTS:
        n += np.roll(np.roll(grid, dx, axis=0), dy, axis=1)
    return n

def apply_bloom(img: np.ndarray, threshold=0.35, strength=0.4, passes=3) -> np.ndarray:
    """Bloom / glow effect — bright areas bleed light into neighbours."""
    brightness = np.max(img, axis=2)
    bright_mask = brightness > threshold
    bright = np.zeros_like(img)
    for c in range(3):
        bright[:, :, c] = np.where(bright_mask, img[:, :, c] - threshold, 0)
    blurred = bright.copy()
    for _ in range(passes):
        blurred = (
            np.roll(blurred, 1, axis=0) +
            np.roll(blurred, -1, axis=0) +
            np.roll(blurred, 1, axis=1) +
            np.roll(blurred, -1, axis=1) +
            blurred * 2.0
        ) / 6.0
    return np.clip(img + blurred * strength, 0, 1)