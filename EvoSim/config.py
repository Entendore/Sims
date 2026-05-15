# config.py
import numpy as np

# --- Grid & Simulation ---
GRID_SIZE            = 60
FPS                  = 15
SAMPLE_RATE          = 44100
DURATION_PER_FRAME   = 1.0 / FPS
MAX_STEPS            = 10000
MUTATION_RATE        = 0.08
ZONE_SIZE            = 12
NUM_SPECIES          = 4
MAX_VOICES           = 20
MASTER_VOLUME        = 0.65
BRUSH_RADIUS_DEFAULT = 3
INIT_DENSITY_DEFAULT = 0.10

DISASTER_INTERVAL    = 120
RESOURCE_PULSE_INTERVAL = 80

BASE_MIDI_NOTE       = 48      # C3

RECORD_FORMATS = {
    'YouTube 16:9 (1920x1080)': {'width': 1920, 'height': 1080},
    'Shorts 9:16 (1080x1920)':  {'width': 1080, 'height': 1920},
    'Square (1080x1080)':       {'width': 1080, 'height': 1080},
}

REVERB_TAPS = [
    (0.023, 0.28), (0.037, 0.22), (0.051, 0.16),
    (0.067, 0.11), (0.083, 0.07), (0.109, 0.04),
]
WARMTH_ALPHA = 0.88

SCALES = {
    'pentatonic_minor': [0, 3, 5, 7, 10],
    'pentatonic_major': [0, 2, 4, 7, 9],
    'major':            [0, 2, 4, 5, 7, 9, 11],
    'natural_minor':    [0, 2, 3, 5, 7, 8, 10],
    'dorian':           [0, 2, 3, 5, 7, 9, 10],
    'mixolydian':       [0, 2, 4, 5, 7, 9, 10],
    'blues':            [0, 3, 5, 6, 7, 10],
    'chromatic':        [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
}
SCALE_NAMES = list(SCALES.keys())

# --- Utilities ---
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