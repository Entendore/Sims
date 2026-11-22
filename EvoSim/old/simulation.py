# simulation.py
import numpy as np
from Sims.EvoSim.old.config import GRID_SIZE, NUM_SPECIES
from Sims.EvoSim.old.utils import count_neighbors

def step(S, zone_energy_map, zone_harshness_map):
    alive = S['alive']
    age = S['age']
    energy = S['energy']
    stage = S['stage']
    species = S['species']
    mut_rate = S['mutation_rate']

    n_alive = count_neighbors(alive.astype(np.int32))

    sp_n = np.zeros((GRID_SIZE, GRID_SIZE, NUM_SPECIES), dtype=np.int32)
    for sp in range(NUM_SPECIES):
        sp_n[:, :, sp] = count_neighbors((species == sp).astype(np.int32))

    dominant_sp = np.argmax(sp_n, axis=2)
    max_sp_n = np.max(sp_n, axis=2)

    birth = (~alive) & (n_alive == 3) & (max_sp_n >= 2)

    surv_prob = 1.0 - zone_harshness_map * 0.4
    lucky = np.random.rand(GRID_SIZE, GRID_SIZE) < surv_prob
    survive = alive & ((n_alive == 2) | (n_alive == 3)) & lucky

    new_alive = birth | survive

    new_species = species.copy()
    new_species[birth] = dominant_sp[birth]

    new_age = np.where(new_alive, age + 1, 0).astype(np.float32)
    new_age[birth] = 0

    new_energy = np.where(
        new_alive,
        np.minimum(1.0, energy + S['energy_gain'] + zone_energy_map),
        energy * 0.3,
    ).astype(np.float32)
    
    n_birth = int(birth.sum())
    if n_birth:
        new_energy[birth] = np.random.uniform(0.15, 0.35, n_birth).astype(np.float32)

    old_mask = new_alive & (new_age > S['max_age'] * 0.7)
    new_energy[old_mask] -= 0.015

    mut = birth & (np.random.rand(GRID_SIZE, GRID_SIZE) < mut_rate)
    sp_mut = mut & (np.random.rand(GRID_SIZE, GRID_SIZE) < 0.25)
    n_sm = int(sp_mut.sum())
    if n_sm:
        new_species[sp_mut] = np.random.randint(0, NUM_SPECIES, n_sm)

    n_m = int(mut.sum())
    if n_m:
        S['energy_gain'][mut] = np.clip(
            S['energy_gain'][mut] + np.random.normal(0, 0.008, n_m), 0.003, 0.12
        ).astype(np.float32)
        S['rep_threshold'][mut] = np.clip(
            S['rep_threshold'][mut] + np.random.normal(0, 0.03, n_m), 0.25, 1.1
        ).astype(np.float32)
        S['tone_mod'][mut] = np.clip(
            S['tone_mod'][mut] + np.random.normal(0, 0.04, n_m), 0.6, 1.6
        ).astype(np.float32)
        S['max_age'][mut] = np.clip(
            S['max_age'][mut] + np.random.normal(0, 2.5, n_m), 15, 100
        ).astype(np.float32)

    S['melody_offset'] = np.where(
        new_alive,
        S['melody_offset'] + np.random.normal(0, 0.25, (GRID_SIZE, GRID_SIZE)),
        S['melody_offset'] * 0.95,
    ).astype(np.float32)

    S['alive'] = new_alive
    S['age'] = new_age
    S['energy'] = new_energy
    S['species'] = new_species.astype(np.int8)

    new_stage = np.zeros_like(stage)
    new_stage[birth] = 1
    new_stage[new_alive & ~birth & (new_energy < S['rep_threshold'])] = 2
    new_stage[new_alive & (new_energy >= S['rep_threshold'])] = 3
    new_stage[new_alive & (new_age > S['max_age'] * 0.85)] = 4
    S['stage'] = new_stage

    S['fade'] = np.where(new_alive, 1.0,
                         np.maximum(0, S['fade'] - 0.12)).astype(np.float32)