# config.py
GRID_SIZE            = 60
FPS                  = 15
SAMPLE_RATE          = 44100
DURATION_PER_FRAME   = 1.0 / FPS
MAX_STEPS            = 10000
MUTATION_RATE        = 0.08
ZONE_SIZE            = 12
NUM_SPECIES          = 4
MAX_VOICES           = 16
MASTER_VOLUME        = 0.7
BRUSH_RADIUS         = 3

DISASTER_INTERVAL    = 120
RESOURCE_PULSE_INTERVAL = 80

BASE_MIDI_NOTE       = 48      # C3

SCALES = {
    'pentatonic_minor': [0, 3, 5, 7, 10],
    'pentatonic_major': [0, 2, 4, 7, 9],
    'major':            [0, 2, 4, 5, 7, 9, 11],
    'natural_minor':    [0, 2, 3, 5, 7, 8, 10],
    'dorian':           [0, 2, 3, 5, 7, 9, 10],
    'mixolydian':       [0, 2, 4, 5, 7, 9, 10],
    'blues':            [0, 3, 5, 6, 7, 10],
}
SCALE_NAMES = list(SCALES.keys())