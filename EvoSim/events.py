# events.py
import numpy as np
from config import GRID_SIZE, DISASTER_INTERVAL, RESOURCE_PULSE_INTERVAL

def step_events(S, env):
    S['disaster_cd'] -= 1
    S['pulse_cd'] -= 1

    # --- Disasters ---
    if S['disaster_cd'] <= 0:
        cx, cy = np.random.randint(5, GRID_SIZE - 5, size=2)
        rad = np.random.randint(4, 10)
        yy, xx = np.ogrid[:GRID_SIZE, :GRID_SIZE]
        dmask = ((xx - cx)**2 + (yy - cy)**2 < rad**2) & (np.random.rand(GRID_SIZE, GRID_SIZE) < 0.75)
        S['alive'][dmask] = False; S['stage'][dmask] = 0
        S['disaster_cd'] = DISASTER_INTERVAL + np.random.randint(-30, 50)
        S['disaster_flash'] = 8

    # --- Resource pulses ---
    if S['pulse_cd'] <= 0:
        zx, zy = np.random.randint(0, env.num_zones_x), np.random.randint(0, env.num_zones_y)
        env.zones_energy[zx, zy] = min(0.18, env.zones_energy[zx, zy] + 0.035)
        env.zone_energy_map[:] = env.expand(env.zones_energy)
        S['pulse_cd'] = RESOURCE_PULSE_INTERVAL + np.random.randint(-15, 25)

    # --- Seasonal energy shift: gently fluctuate global energy ---
    if S['generation'] % 60 == 0:
        delta = np.random.uniform(-0.005, 0.005, (env.num_zones_x, env.num_zones_y))
        env.zones_energy = np.clip(env.zones_energy + delta, 0.005, 0.20)
        env.zone_energy_map[:] = env.expand(env.zones_energy)

    if S['disaster_flash'] > 0:
        S['disaster_flash'] -= 1