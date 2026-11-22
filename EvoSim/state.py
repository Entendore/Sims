# state.py
import numpy as np
from collections import deque
from config import (GRID_SIZE, NUM_SPECIES, DISASTER_INTERVAL,
                    RESOURCE_PULSE_INTERVAL, MASTER_VOLUME, MUTATION_RATE,
                    BRUSH_RADIUS_DEFAULT, INIT_DENSITY_DEFAULT, WARMTH_ALPHA)

def init_state(density=None) -> dict:
    if density is None:
        density = INIT_DENSITY_DEFAULT
    s = {}
    s['alive']   = np.random.rand(GRID_SIZE, GRID_SIZE) < density
    s['age']     = np.zeros((GRID_SIZE, GRID_SIZE), dtype=np.float32)
    s['energy']  = np.random.uniform(0.15, 0.45, (GRID_SIZE, GRID_SIZE)).astype(np.float32)
    s['stage']   = np.zeros((GRID_SIZE, GRID_SIZE), dtype=np.int8)
    s['species'] = np.random.randint(0, NUM_SPECIES, (GRID_SIZE, GRID_SIZE)).astype(np.int8)

    s['energy_gain']   = np.random.uniform(0.015, 0.055, (GRID_SIZE, GRID_SIZE)).astype(np.float32)
    s['rep_threshold'] = np.random.uniform(0.45, 0.85, (GRID_SIZE, GRID_SIZE)).astype(np.float32)
    s['tone_mod']      = np.random.uniform(0.88, 1.12, (GRID_SIZE, GRID_SIZE)).astype(np.float32)
    s['max_age']       = np.random.uniform(30, 75,   (GRID_SIZE, GRID_SIZE)).astype(np.float32)
    s['melody_offset'] = np.zeros((GRID_SIZE, GRID_SIZE), dtype=np.float32)
    s['fade']          = np.zeros((GRID_SIZE, GRID_SIZE), dtype=np.float32)

    s['generation']   = 0
    s['disaster_cd']  = DISASTER_INTERVAL  + np.random.randint(-20, 30)
    s['pulse_cd']     = RESOURCE_PULSE_INTERVAL + np.random.randint(-10, 20)
    s['paused']       = False
    s['show_zones']   = False
    s['show_energy']  = False
    s['volume']       = MASTER_VOLUME
    s['mutation_rate']= MUTATION_RATE
    s['sound_on']     = True
    s['recording']    = False

    # --- New settings ---
    s['sim_speed']      = 1        # 1-5 steps per frame
    s['brush_radius']   = BRUSH_RADIUS_DEFAULT
    s['init_density']   = density  # 0.05-0.50
    s['reverb_mix']     = 1.0      # 0.0-1.0
    s['warmth']         = (WARMTH_ALPHA - 0.5) / 0.5  # maps alpha 0.5-1.0 → 0.0-1.0; default ~0.76
    s['bloom_on']       = True
    s['bloom_strength'] = 0.40     # 0.0-1.0
    s['disaster_freq']  = 1.0      # 0.0-2.0 multiplier (0 = never)

    s['pop_history']     = deque(maxlen=300)
    s['species_hist']    = [deque(maxlen=300) for _ in range(NUM_SPECIES)]
    s['diversity_hist']  = deque(maxlen=300)
    s['energy_hist']     = deque(maxlen=300)
    s['disaster_flash']  = 0
    return s

S = init_state()

def update_stats(S):
    total_pop = int(S['alive'].sum())
    S['pop_history'].append(total_pop)

    sp_pops = []
    for sp in range(NUM_SPECIES):
        cnt = int((S['alive'] & (S['species'] == sp)).sum())
        S['species_hist'][sp].append(cnt)
        sp_pops.append(cnt)

    if total_pop > 0:
        props = np.array([p / total_pop for p in sp_pops if p > 0])
        diversity = float(-np.sum(props * np.log(props)))
    else:
        diversity = 0.0

    S['diversity_hist'].append(diversity)
    avg_e = float(S['energy'][S['alive']].mean()) if total_pop > 0 else 0.0
    S['energy_hist'].append(avg_e)

    return total_pop, sp_pops, diversity, avg_e