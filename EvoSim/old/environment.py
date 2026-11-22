# environment.py
import numpy as np
from Sims.EvoSim.old.config import GRID_SIZE, ZONE_SIZE, BASE_MIDI_NOTE, SCALES, SCALE_NAMES

class Environment:
    def __init__(self):
        self.num_zones_x = (GRID_SIZE + ZONE_SIZE - 1) // ZONE_SIZE
        self.num_zones_y = (GRID_SIZE + ZONE_SIZE - 1) // ZONE_SIZE
        
        self.zones_energy = np.random.uniform(0.01, 0.06, (self.num_zones_x, self.num_zones_y))
        self.zones_harshness = np.random.uniform(0.0, 0.20, (self.num_zones_x, self.num_zones_y))
        self.zones_scale_key = np.random.choice(SCALE_NAMES, (self.num_zones_x, self.num_zones_y))
        
        self.zone_energy_map = self.expand(self.zones_energy)
        self.zone_harshness_map = self.expand(self.zones_harshness)
        self.note_map = self._build_note_map()

    def _expand_nearest(self, zones):
        gs, zs = GRID_SIZE, ZONE_SIZE
        out = np.zeros((gs, gs), dtype=np.float64)
        for x in range(gs):
            for y in range(gs):
                out[x, y] = zones[min(x // zs, zones.shape[0] - 1),
                                  min(y // zs, zones.shape[1] - 1)]
        return out

    def expand(self, zones):
        try:
            from scipy.ndimage import zoom as _scipy_zoom
            fx = GRID_SIZE / zones.shape[0]
            fy = GRID_SIZE / zones.shape[1]
            return _scipy_zoom(zones.astype(np.float64), (fx, fy), order=1)[:GRID_SIZE, :GRID_SIZE]
        except ImportError:
            return self._expand_nearest(zones)

    def _build_note_map(self):
        note_map = np.zeros((GRID_SIZE, GRID_SIZE), dtype=np.int32)
        for _x in range(GRID_SIZE):
            for _y in range(GRID_SIZE):
                _zx = min(_x // ZONE_SIZE, self.num_zones_x - 1)
                _zy = min(_y // ZONE_SIZE, self.num_zones_y - 1)
                _scale = SCALES[self.zones_scale_key[_zx, _zy]]
                _oct = (_x + _y) // 12
                _ni  = (_x + _y) % len(_scale)
                note_map[_x, _y] = BASE_MIDI_NOTE + _oct * 12 + _scale[_ni]
        return note_map