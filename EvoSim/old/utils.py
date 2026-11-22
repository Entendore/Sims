# utils.py
import numpy as np

def midi_to_freq(note: float) -> float:
    """Convert MIDI note number (possibly fractional) to Hz."""
    return 440.0 * (2.0 ** ((note - 69) / 12.0))

_ROLL_SHIFTS = [(-1, -1), (-1, 0), (-1, 1),
                ( 0, -1),          ( 0, 1),
                ( 1, -1), ( 1, 0), ( 1, 1)]

def count_neighbors(grid: np.ndarray) -> np.ndarray:
    n = np.zeros_like(grid, dtype=np.int32)
    for dx, dy in _ROLL_SHIFTS:
        n += np.roll(np.roll(grid, dx, axis=0), dy, axis=1)
    return n