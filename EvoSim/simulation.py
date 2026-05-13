# simulation.py
import numpy as np
from config import GRID_SIZE, NUM_SPECIES, DISASTER_INTERVAL, RESOURCE_PULSE_INTERVAL, count_neighbors

def step_events(S, env):
    S['disaster_cd'] -= 1
    S['pulse_cd'] -= 1

    if S['disaster_cd'] <= 0:
        cx, cy = np.random.randint(5, GRID_SIZE - 5, size=2)
        rad = np.random.randint(4, 10)
        yy, xx = np.ogrid[:GRID_SIZE, :GRID_SIZE]
        dmask = ((xx - cx)**2 + (yy - cy)**2 < rad**2) & (np.random.rand(GRID_SIZE, GRID_SIZE) < 0.75)
        S['alive'][dmask] = False; S['stage'][dmask] = 0
        S['disaster_cd'] = DISASTER_INTERVAL + np.random.randint(-30, 50)
        S['disaster_flash'] = 8

    if S['pulse_cd'] <= 0:
        zx, zy = np.random.randint(0, env.num_zones_x), np.random.randint(0, env.num_zones_y)
        env.zones_energy[zx, zy] = min(0.18, env.zones_energy[zx, zy] + 0.035)
        env.zone_energy_map[:] = env.expand(env.zones_energy)
        S['pulse_cd'] = RESOURCE_PULSE_INTERVAL + np.random.randint(-15, 25)

    if S['generation'] % 60 == 0:
        delta = np.random.uniform(-0.005, 0.005, (env.num_zones_x, env.num_zones_y))
        env.zones_energy = np.clip(env.zones_energy + delta, 0.005, 0.20)
        env.zone_energy_map[:] = env.expand(env.zones_energy)

    if S['disaster_flash'] > 0:
        S['disaster_flash'] -= 1

def step(S, zone_energy_map, zone_harshness_map):
    alive, age, energy, stage, species = S['alive'], S['age'], S['energy'], S['stage'], S['species']
    mut_rate = S['mutation_rate']

    n_alive = count_neighbors(alive.astype(np.int32))
    sp_n = np.zeros((GRID_SIZE, GRID_SIZE, NUM_SPECIES), dtype=np.int32)
    for sp in range(NUM_SPECIES):
        sp_n[:, :, sp] = count_neighbors((species == sp).astype(np.int32))

    dominant_sp = np.argmax(sp_n, axis=2)
    max_sp_n = np.max(sp_n, axis=2)
    
    same_n = np.zeros((GRID_SIZE, GRID_SIZE), dtype=np.float32)
    for sp in range(NUM_SPECIES):
        same_n += sp_n[:, :, sp] * (species == sp).astype(np.float32)
    affinity_bonus = same_n * 0.004
    diff_n = (n_alive - same_n).astype(np.float32)
    competition_drain = diff_n * 0.002

    birth = (~alive) & (n_alive == 3) & (max_sp_n >= 2)
    birth |= (~alive) & (n_alive == 2) & (same_n >= 2) & (zone_energy_map > 0.04)

    surv_prob = 1.0 - zone_harshness_map * 0.35
    lucky = np.random.rand(GRID_SIZE, GRID_SIZE) < surv_prob
    survive = alive & ((n_alive == 2) | (n_alive == 3)) & lucky

    old_penalty = alive & (age > S['max_age'] * 0.9)
    lucky_old = np.random.rand(GRID_SIZE, GRID_SIZE) > 0.12
    survive[old_penalty] &= lucky_old[old_penalty]

    new_alive = birth | survive
    new_species = species.copy()
    new_species[birth] = dominant_sp[birth]

    new_age = np.where(new_alive, age + 1, 0).astype(np.float32)
    new_age[birth] = 0

    base_gain = S['energy_gain'] + zone_energy_map + affinity_bonus - competition_drain
    new_energy = np.where(
        new_alive,
        np.minimum(1.0, energy + base_gain),
        energy * 0.25
    ).astype(np.float32)

    n_birth = int(birth.sum())
    if n_birth:
        new_energy[birth] = np.random.uniform(0.20, 0.40, n_birth).astype(np.float32)
    old_mask = new_alive & (new_age > S['max_age'] * 0.7)
    new_energy[old_mask] -= 0.012

    mut = birth & (np.random.rand(GRID_SIZE, GRID_SIZE) < mut_rate)
    sp_mut = mut & (np.random.rand(GRID_SIZE, GRID_SIZE) < 0.25)
    n_sm = int(sp_mut.sum())
    if n_sm:
        new_species[sp_mut] = np.random.randint(0, NUM_SPECIES, n_sm)

    n_m = int(mut.sum())
    if n_m:
        S['energy_gain'][mut] = np.clip(S['energy_gain'][mut] + np.random.normal(0, 0.006, n_m), 0.003, 0.10).astype(np.float32)
        S['rep_threshold'][mut] = np.clip(S['rep_threshold'][mut] + np.random.normal(0, 0.02, n_m), 0.25, 1.1).astype(np.float32)
        S['tone_mod'][mut] = np.clip(S['tone_mod'][mut] + np.random.normal(0, 0.03, n_m), 0.65, 1.50).astype(np.float32)
        S['max_age'][mut] = np.clip(S['max_age'][mut] + np.random.normal(0, 2.0, n_m), 15, 100).astype(np.float32)

    S['melody_offset'] = np.where(
        new_alive,
        S['melody_offset'] + np.random.normal(0, 0.20, (GRID_SIZE, GRID_SIZE)),
        S['melody_offset'] * 0.93
    ).astype(np.float32)

    S['alive'], S['age'], S['energy'], S['species'] = new_alive, new_age, new_energy, new_species.astype(np.int8)

    new_stage = np.zeros_like(stage)
    new_stage[birth] = 1
    new_stage[new_alive & ~birth & (new_energy < S['rep_threshold'])] = 2
    new_stage[new_alive & (new_energy >= S['rep_threshold'])] = 3
    new_stage[new_alive & (new_age > S['max_age'] * 0.85)] = 4
    S['stage'] = new_stage
    S['fade'] = np.where(new_alive, 1.0, np.maximum(0, S['fade'] - 0.10)).astype(np.float32)