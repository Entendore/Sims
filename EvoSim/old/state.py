# state.py
import numpy as np
from collections import deque
from Sims.EvoSim.old.config import GRID_SIZE, NUM_SPECIES, DISASTER_INTERVAL, RESOURCE_PULSE_INTERVAL, MASTER_VOLUME, MUTATION_RATE

def init_state() -> dict:
    s = {}
    s['alive']   = np.random.rand(GRID_SIZE, GRID_SIZE) < 0.12
    s['age']     = np.zeros((GRID_SIZE, GRID_SIZE), dtype=np.float32)
    s['energy']  = np.random.uniform(0.1, 0.4, (GRID_SIZE, GRID_SIZE)).astype(np.float32)
    s['stage']   = np.zeros((GRID_SIZE, GRID_SIZE), dtype=np.int8)
    s['species'] = np.random.randint(0, NUM_SPECIES, (GRID_SIZE, GRID_SIZE)).astype(np.int8)

    s['energy_gain']   = np.random.uniform(0.01, 0.06, (GRID_SIZE, GRID_SIZE)).astype(np.float32)
    s['rep_threshold'] = np.random.uniform(0.50, 0.90, (GRID_SIZE, GRID_SIZE)).astype(np.float32)
    s['tone_mod']      = np.random.uniform(0.85, 1.15, (GRID_SIZE, GRID_SIZE)).astype(np.float32)
    s['max_age']       = np.random.uniform(30, 70,   (GRID_SIZE, GRID_SIZE)).astype(np.float32)
    s['melody_offset'] = np.zeros((GRID_SIZE, GRID_SIZE), dtype=np.float32)
    s['fade']          = np.zeros((GRID_SIZE, GRID_SIZE), dtype=np.float32)

    s['generation']   = 0
    s['disaster_cd']  = DISASTER_INTERVAL  + np.random.randint(-20, 30)
    s['pulse_cd']     = RESOURCE_PULSE_INTERVAL + np.random.randint(-10, 20)
    s['paused']       = False
    s['show_zones']   = False
    s['volume']       = MASTER_VOLUME
    s['mutation_rate']= MUTATION_RATE
    
    # New settings
    s['sound_on']     = True
    s['recording']    = False

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