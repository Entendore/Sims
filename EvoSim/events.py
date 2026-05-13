# events.py
import numpy as np
from config import GRID_SIZE, DISASTER_INTERVAL, RESOURCE_PULSE_INTERVAL

def step_events(S, env):
    S['disaster_cd'] -= 1
    S['pulse_cd'] -= 1

    if S['disaster_cd'] <= 0:
        cx, cy = np.random.randint(5, GRID_SIZE - 5, size=2)
        rad = np.random.randint(4, 10)
        yy, xx = np.ogrid[:GRID_SIZE, :GRID_SIZE]
        dmask = ((xx - cx)**2 + (yy - cy)**2 < rad**2) & (np.random.rand(GRID_SIZE, GRID_SIZE) < 0.75)
        S['alive'][dmask] = False
        S['stage'][dmask] = 0
        S['disaster_cd'] = DISASTER_INTERVAL + np.random.randint(-30, 50)
        S['disaster_flash'] = 6

    if S['pulse_cd'] <= 0:
        zx = np.random.randint(0, env.num_zones_x)
        zy = np.random.randint(0, env.num_zones_y)
        env.zones_energy[zx, zy] = min(0.15, env.zones_energy[zx, zy] + 0.03)
        env.zone_energy_map[:] = env.expand(env.zones_energy)
        S['pulse_cd'] = RESOURCE_PULSE_INTERVAL + np.random.randint(-15, 25)

    if S['disaster_flash'] > 0:
        S['disaster_flash'] -= 1