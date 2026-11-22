#!/usr/bin/env python3
"""
Evolutionary Cellular Automata with Polyphonic Sonification
============================================================
Features:
  - Multiple species with competition & genetic mutation
  - Environmental zones (energy, harshness, musical scale)
  - Musical sonification using real scales and harmonics
  - Real-time statistics dashboard (population, diversity, energy)
  - Environmental events (disasters, resource pulses)
  - Smooth audio with crossfade, envelopes, and reverb
  - Interactive controls

Controls:
  Left-click  : Add cells at cursor
  Right-click : Kill cells at cursor
  r           : Reset simulation
  p           : Pause / unpause
  d           : Trigger manual disaster
  z           : Toggle zone overlay
  + / -       : Adjust volume
  s           : Scatter random cells
"""

import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import matplotlib.gridspec as gridspec
import sounddevice as sd
from collections import deque

# ═══════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════
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


def midi_to_freq(note: float) -> float:
    """Convert MIDI note number (possibly fractional) to Hz."""
    return 440.0 * (2.0 ** ((note - 69) / 12.0))


# ═══════════════════════════════════════════════════════════════
# Environment – zone grids
# ═══════════════════════════════════════════════════════════════
num_zones_x = (GRID_SIZE + ZONE_SIZE - 1) // ZONE_SIZE
num_zones_y = (GRID_SIZE + ZONE_SIZE - 1) // ZONE_SIZE

zones_energy    = np.random.uniform(0.01, 0.06, (num_zones_x, num_zones_y))
zones_harshness = np.random.uniform(0.0, 0.20, (num_zones_x, num_zones_y))
zones_scale_key = np.random.choice(SCALE_NAMES, (num_zones_x, num_zones_y))


# Smooth zone map builder (scipy if available, else nearest-neighbour)
def _expand_nearest(zones, gs, zs):
    out = np.zeros((gs, gs), dtype=np.float64)
    for x in range(gs):
        for y in range(gs):
            out[x, y] = zones[min(x // zs, zones.shape[0] - 1),
                              min(y // zs, zones.shape[1] - 1)]
    return out

try:
    from scipy.ndimage import zoom as _scipy_zoom

    def _expand_smooth(zones, gs, _zs):
        fx = gs / zones.shape[0]
        fy = gs / zones.shape[1]
        return _scipy_zoom(zones.astype(np.float64), (fx, fy), order=1)[:gs, :gs]

    _expand = _expand_smooth
except ImportError:
    _expand = _expand_nearest

zone_energy_map    = _expand(zones_energy,    GRID_SIZE, ZONE_SIZE)
zone_harshness_map = _expand(zones_harshness, GRID_SIZE, ZONE_SIZE)

# Per-cell MIDI note map (deterministic from position + zone scale)
note_map = np.zeros((GRID_SIZE, GRID_SIZE), dtype=np.int32)
for _x in range(GRID_SIZE):
    for _y in range(GRID_SIZE):
        _zx = min(_x // ZONE_SIZE, num_zones_x - 1)
        _zy = min(_y // ZONE_SIZE, num_zones_y - 1)
        _scale = SCALES[zones_scale_key[_zx, _zy]]
        _oct = (_x + _y) // 12
        _ni  = (_x + _y) % len(_scale)
        note_map[_x, _y] = BASE_MIDI_NOTE + _oct * 12 + _scale[_ni]


# ═══════════════════════════════════════════════════════════════
# Simulation state
# ═══════════════════════════════════════════════════════════════
def init_state() -> dict:
    """Create / reset every simulation variable."""
    s = {}
    s['alive']   = np.random.rand(GRID_SIZE, GRID_SIZE) < 0.12
    s['age']     = np.zeros((GRID_SIZE, GRID_SIZE), dtype=np.float32)
    s['energy']  = np.random.uniform(0.1, 0.4, (GRID_SIZE, GRID_SIZE)).astype(np.float32)
    s['stage']   = np.zeros((GRID_SIZE, GRID_SIZE), dtype=np.int8)
    # 0=dead 1=birth 2=growth 3=reproduction 4=dying
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

    s['pop_history']     = deque(maxlen=300)
    s['species_hist']    = [deque(maxlen=300) for _ in range(NUM_SPECIES)]
    s['diversity_hist']  = deque(maxlen=300)
    s['energy_hist']     = deque(maxlen=300)
    s['disaster_flash']  = 0        # frames to flash overlay
    return s


S = init_state()


# ═══════════════════════════════════════════════════════════════
# Vectorised helpers
# ═══════════════════════════════════════════════════════════════
_ROLL_SHIFTS = [(-1, -1), (-1, 0), (-1, 1),
                ( 0, -1),          ( 0, 1),
                ( 1, -1), ( 1, 0), ( 1, 1)]


def count_neighbors(grid: np.ndarray) -> np.ndarray:
    n = np.zeros_like(grid, dtype=np.int32)
    for dx, dy in _ROLL_SHIFTS:
        n += np.roll(np.roll(grid, dx, axis=0), dy, axis=1)
    return n


# ═══════════════════════════════════════════════════════════════
# Audio engine
# ═══════════════════════════════════════════════════════════════
frame_samples  = int(DURATION_PER_FRAME * SAMPLE_RATE)
audio_buffer   = np.zeros(frame_samples, dtype=np.float32)
prev_audio_buf = np.zeros(frame_samples, dtype=np.float32)
crossfade_len  = min(512, frame_samples // 4)

t_audio  = np.linspace(0, DURATION_PER_FRAME, frame_samples, endpoint=False).astype(np.float32)
fade_in  = np.linspace(0, 1, crossfade_len, dtype=np.float32)
fade_out = np.linspace(1, 0, crossfade_len, dtype=np.float32)

# Soft envelope for each frame (eliminates clicks)
_env_len = min(128, frame_samples // 8)
frame_envelope = np.ones(frame_samples, dtype=np.float32)
frame_envelope[:_env_len]  = np.linspace(0, 1, _env_len)
frame_envelope[-_env_len:] = np.linspace(1, 0, _env_len)


def synthesize_audio(active_notes: list):
    """Vectorised additive synthesis with crossfade and reverb."""
    global audio_buffer, prev_audio_buf

    # ---- silence path ----
    if not active_notes:
        new = np.zeros(frame_samples, dtype=np.float32)
        new[:crossfade_len] = prev_audio_buf[:crossfade_len] * fade_out
        audio_buffer[:] = new
        prev_audio_buf[:] = new
        return

    # ---- limit voices ----
    if len(active_notes) > MAX_VOICES:
        active_notes.sort(key=lambda n: n[1], reverse=True)
        active_notes = active_notes[:MAX_VOICES]

    freqs = np.array([n[0] for n in active_notes], dtype=np.float32)
    amps  = np.array([n[1] for n in active_notes], dtype=np.float32)

    # ---- additive: fundamental + 2 harmonics ----
    signal = np.zeros(frame_samples, dtype=np.float64)
    for h_idx, h_amp in enumerate([1.0, 0.35, 0.12]):
        h_freqs = freqs * (h_idx + 1)
        valid = h_freqs < (SAMPLE_RATE * 0.45)
        if not np.any(valid):
            break
        phases = 2.0 * np.pi * h_freqs[:, None] * t_audio[None, :]
        wave   = amps[:, None] * h_amp * np.sin(phases)
        wave[~valid] = 0.0
        signal += wave.sum(axis=0)

    signal *= frame_envelope

    # ---- simple multi-tap delay (reverb) ----
    for i in range(3):
        ds = int(SAMPLE_RATE * (0.025 + i * 0.018))
        if ds < frame_samples:
            signal[ds:] += (0.22 ** (i + 1)) * signal[:frame_samples - ds]

    # ---- normalise & volume ----
    mx = np.max(np.abs(signal))
    if mx > 0:
        signal = signal / mx * S['volume']
    signal = signal.astype(np.float32)

    # ---- crossfade ----
    signal[:crossfade_len] = (
        prev_audio_buf[:crossfade_len] * fade_out
        + signal[:crossfade_len] * fade_in
    )

    audio_buffer[:]   = signal
    prev_audio_buf[:] = signal


def audio_callback(outdata, frames, time_info, status):
    outdata[:] = audio_buffer.reshape(-1, 1)


# ═══════════════════════════════════════════════════════════════
# Colour palette
# ═══════════════════════════════════════════════════════════════
SPECIES_COLORS = np.array([
    [1.00, 0.25, 0.20],   # red
    [0.20, 0.85, 0.35],   # green
    [0.30, 0.55, 1.00],   # blue
    [1.00, 0.80, 0.15],   # gold
    [0.85, 0.30, 0.85],   # magenta
    [0.15, 0.90, 0.90],   # cyan
], dtype=np.float32)

# brightness multiplier per stage  (0=dead,1=birth,2=growth,3=rep,4=dying)
STAGE_GLOW = np.array([0.0, 0.65, 0.95, 1.30, 0.35], dtype=np.float32)


# ═══════════════════════════════════════════════════════════════
# Figure layout  (defined BEFORE update so update can reference them)
# ═══════════════════════════════════════════════════════════════
plt.style.use('dark_background')
fig = plt.figure(figsize=(16, 9))
fig.patch.set_facecolor('#080810')

gs = gridspec.GridSpec(2, 2, width_ratios=[2.5, 1], height_ratios=[2.5, 1],
                       hspace=0.30, wspace=0.25)

# ---- main CA grid ----
ax1 = fig.add_subplot(gs[0, 0])
im  = ax1.imshow(np.zeros((GRID_SIZE, GRID_SIZE, 3)),
                 interpolation='nearest', aspect='equal', origin='upper')
ax1.set_title('Evolutionary Cellular Automata', fontsize=12, color='#cccccc', pad=8)
ax1.set_xticks([]); ax1.set_yticks([])

# ---- population plot ----
ax2 = fig.add_subplot(gs[1, 0])
pop_line, = ax2.plot([], [], 'w-', lw=1.3, alpha=0.85, label='Total')
species_lines = []
for sp in range(NUM_SPECIES):
    c = SPECIES_COLORS[sp % len(SPECIES_COLORS)]
    ln, = ax2.plot([], [], '-', lw=0.9, color=c, label=f'Sp {sp}', alpha=0.85)
    species_lines.append(ln)
ax2.legend(loc='upper left', fontsize=7, ncol=NUM_SPECIES + 1, framealpha=0.25)
ax2.set_xlabel('Frame', fontsize=8, color='#888')
ax2.set_ylabel('Population', fontsize=8, color='#888')
ax2.set_title('Population Dynamics', fontsize=10, color='#cccccc')
ax2.tick_params(colors='#555', labelsize=7)
ax2.set_facecolor('#0a0a12')

# ---- info panel ----
ax3 = fig.add_subplot(gs[0, 1])
ax3.axis('off')
info_text = ax3.text(0.05, 0.97, '', transform=ax3.transAxes, fontsize=7.5,
                     verticalalignment='top', fontfamily='monospace',
                     color='#cccccc', linespacing=1.35)

# ---- diversity / energy ----
ax4 = fig.add_subplot(gs[1, 1])
div_line,    = ax4.plot([], [], '-', color='#ff88ff', lw=1, label='Shannon H′')
energy_line, = ax4.plot([], [], '-', color='#88ff88', lw=1, label='Avg Energy')
ax4.legend(loc='upper left', fontsize=7, framealpha=0.25)
ax4.set_xlabel('Frame', fontsize=8, color='#888')
ax4.set_title('Diversity & Energy', fontsize=10, color='#cccccc')
ax4.tick_params(colors='#555', labelsize=7)
ax4.set_facecolor('#0a0a12')


# ═══════════════════════════════════════════════════════════════
# Main update
# ═══════════════════════════════════════════════════════════════
def update(frame_num):
    if S['paused']:
        return [im, pop_line, info_text, div_line, energy_line] + species_lines

    alive   = S['alive']
    age     = S['age']
    energy  = S['energy']
    stage   = S['stage']
    species = S['species']

    S['generation'] += 1
    gen = S['generation']

    # ── neighbour counts (vectorised) ────────────────────────
    n_alive = count_neighbors(alive.astype(np.int32))

    sp_n = np.zeros((GRID_SIZE, GRID_SIZE, NUM_SPECIES), dtype=np.int32)
    for sp in range(NUM_SPECIES):
        sp_n[:, :, sp] = count_neighbors((species == sp).astype(np.int32))

    dominant_sp = np.argmax(sp_n, axis=2)
    max_sp_n    = np.max(sp_n, axis=2)

    # ── birth ────────────────────────────────────────────────
    birth = (~alive) & (n_alive == 3) & (max_sp_n >= 2)

    # ── survival ─────────────────────────────────────────────
    surv_prob = 1.0 - zone_harshness_map * 0.4
    lucky    = np.random.rand(GRID_SIZE, GRID_SIZE) < surv_prob
    survive  = alive & ((n_alive == 2) | (n_alive == 3)) & lucky

    new_alive = birth | survive

    # ── species of newborns ──────────────────────────────────
    new_species = species.copy()
    new_species[birth] = dominant_sp[birth]

    # ── age & energy ─────────────────────────────────────────
    new_age    = np.where(new_alive, age + 1, 0).astype(np.float32)
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

    # ── mutation ─────────────────────────────────────────────
    mut = birth & (np.random.rand(GRID_SIZE, GRID_SIZE) < MUTATION_RATE)
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

    # melody drift
    S['melody_offset'] = np.where(
        new_alive,
        S['melody_offset'] + np.random.normal(0, 0.25, (GRID_SIZE, GRID_SIZE)),
        S['melody_offset'] * 0.95,
    ).astype(np.float32)

    # ── commit state ─────────────────────────────────────────
    S['alive']   = new_alive
    S['age']     = new_age
    S['energy']  = new_energy
    S['species'] = new_species.astype(np.int8)

    # ── stage ────────────────────────────────────────────────
    new_stage = np.zeros_like(stage)
    new_stage[birth]                                               = 1
    new_stage[new_alive & ~birth & (new_energy < S['rep_threshold'])] = 2
    new_stage[new_alive & (new_energy >= S['rep_threshold'])]      = 3
    new_stage[new_alive & (new_age > S['max_age'] * 0.85)]        = 4
    S['stage'] = new_stage

    # ── fade for dead cells ──────────────────────────────────
    S['fade'] = np.where(new_alive, 1.0,
                         np.maximum(0, S['fade'] - 0.12)).astype(np.float32)

    # ── environmental events ─────────────────────────────────
    S['disaster_cd'] -= 1
    S['pulse_cd']    -= 1

    if S['disaster_cd'] <= 0:
        cx, cy = np.random.randint(5, GRID_SIZE - 5, size=2)
        rad = np.random.randint(4, 10)
        yy, xx = np.ogrid[:GRID_SIZE, :GRID_SIZE]
        dmask = ((xx - cx)**2 + (yy - cy)**2 < rad**2) & (np.random.rand(GRID_SIZE, GRID_SIZE) < 0.75)
        S['alive'][dmask] = False
        S['stage'][dmask] = 0
        S['disaster_cd'] = DISASTER_INTERVAL + np.random.randint(-30, 50)
        S['disaster_flash'] = 6       # flash frames

    if S['pulse_cd'] <= 0:
        zx = np.random.randint(0, num_zones_x)
        zy = np.random.randint(0, num_zones_y)
        zones_energy[zx, zy] = min(0.15, zones_energy[zx, zy] + 0.03)
        zone_energy_map[:] = _expand(zones_energy, GRID_SIZE, ZONE_SIZE)
        S['pulse_cd'] = RESOURCE_PULSE_INTERVAL + np.random.randint(-15, 25)

    if S['disaster_flash'] > 0:
        S['disaster_flash'] -= 1

    # ── statistics ───────────────────────────────────────────
    total_pop = int(S['alive'].sum())
    S['pop_history'].append(total_pop)

    sp_pops = []
    for sp in range(NUM_SPECIES):
        cnt = int((S['alive'] & (S['species'] == sp)).sum())
        S['species_hist'][sp].append(cnt)
        sp_pops.append(cnt)

    # Shannon diversity
    if total_pop > 0:
        props = np.array([p / total_pop for p in sp_pops if p > 0])
        diversity = float(-np.sum(props * np.log(props)))
    else:
        diversity = 0.0
    S['diversity_hist'].append(diversity)
    avg_e = float(S['energy'][S['alive']].mean()) if total_pop > 0 else 0.0
    S['energy_hist'].append(avg_e)

    # ── audio ────────────────────────────────────────────────
    active_notes = []
    cells_per_sp = max(1, MAX_VOICES // NUM_SPECIES)

    for sp in range(NUM_SPECIES):
        mask = S['alive'] & (S['species'] == sp)
        idx  = np.where(mask)
        nc   = len(idx[0])
        if nc == 0:
            continue
        if nc > cells_per_sp:
            chosen = np.random.choice(nc, cells_per_sp, replace=False)
            xs, ys = idx[0][chosen], idx[1][chosen]
        else:
            xs, ys = idx[0], idx[1]

        for x, y in zip(xs, ys):
            midi = note_map[x, y] + S['melody_offset'][x, y]
            freq = midi_to_freq(midi) * S['tone_mod'][x, y]
            freq = float(np.clip(freq, 30, 3500))
            stg  = int(S['stage'][x, y])
            e    = float(S['energy'][x, y])

            if   stg == 1: amp = 0.12
            elif stg == 2: amp = 0.06 + e * 0.12
            elif stg == 3: amp = 0.18; freq *= 1.5
            elif stg == 4: amp = 0.04
            else:          amp = 0.03
            active_notes.append((freq, amp))

    # subtle drone
    if total_pop > 0:
        active_notes.append((midi_to_freq(BASE_MIDI_NOTE) * 0.5, 0.015))

    synthesize_audio(active_notes)

    # ── visualisation ────────────────────────────────────────
    img = np.zeros((GRID_SIZE, GRID_SIZE, 3), dtype=np.float32)

    # dead-cell fade trail
    fading = (~S['alive']) & (S['fade'] > 0)
    if fading.any():
        for c in range(3):
            img[fading, c] = S['fade'][fading] * 0.07

    # zone grid overlay
    if S['show_zones']:
        for zx in range(num_zones_x + 1):
            xi = min(zx * ZONE_SIZE, GRID_SIZE - 1)
            img[xi, :] = np.maximum(img[xi, :], 0.12)
        for zy in range(num_zones_y + 1):
            yi = min(zy * ZONE_SIZE, GRID_SIZE - 1)
            img[:, yi] = np.maximum(img[:, yi], 0.12)

    # disaster flash overlay
    if S['disaster_flash'] > 0:
        flash_alpha = S['disaster_flash'] / 6.0 * 0.15
        img[:, :, 0] = np.maximum(img[:, :, 0], flash_alpha)

    # alive cells – vectorised per species × stage
    for sp in range(NUM_SPECIES):
        colour = SPECIES_COLORS[sp % len(SPECIES_COLORS)]
        sp_mask = (S['species'] == sp)

        for stg_val in (1, 2, 3, 4):
            cell_mask = sp_mask & (S['stage'] == stg_val) & S['alive']
            if not cell_mask.any():
                continue
            glow = STAGE_GLOW[stg_val]
            e    = S['energy'][cell_mask]
            bri  = glow * (0.5 + 0.5 * e)
            for c in range(3):
                img[cell_mask, c] = np.clip(colour[c] * bri, 0, 1)

    im.set_data(np.clip(img, 0, 1))

    # ── update line plots ────────────────────────────────────
    pd = list(S['pop_history'])
    pop_line.set_data(range(len(pd)), pd)
    ax2.set_xlim(0, max(1, len(pd)))
    ax2.set_ylim(0, max(10, max(pd) * 1.15) if pd else 10)

    for sp in range(NUM_SPECIES):
        sd_ = list(S['species_hist'][sp])
        species_lines[sp].set_data(range(len(sd_)), sd_)

    dd = list(S['diversity_hist'])
    ed = list(S['energy_hist'])
    div_line.set_data(range(len(dd)), dd)
    energy_line.set_data(range(len(ed)), ed)
    ax4.set_xlim(0, max(1, len(dd)))
    y_max = max(1.0, max(max(dd, default=0.5), max(ed, default=0.5)) * 1.2)
    ax4.set_ylim(0, y_max)

    # ── info panel text ──────────────────────────────────────
    active_sp = sum(1 for p in sp_pops if p > 0)
    lines = [
        "══════ EVOLUTIONARY CA ══════",
        "",
        f"  Generation   {gen:>6}",
        f"  Population   {total_pop:>6}",
        f"  Species      {active_sp}/{NUM_SPECIES}",
        f"  Shannon H′   {diversity:>6.3f}",
        f"  Avg Energy   {avg_e:>6.3f}",
        "",
        "── Species ──────────────────",
    ]
    for sp in range(NUM_SPECIES):
        bar = '█' * min(25, sp_pops[sp] // max(1, total_pop // 25 + 1))
        lines.append(f"  Sp{sp} {sp_pops[sp]:>5}  {bar}")
    lines += [
        "",
        "── Controls ─────────────────",
        "  Click    Add / Remove cells",
        "  r        Reset",
        "  p        Pause / Resume",
        "  d        Trigger disaster",
        "  z        Zone overlay",
        "  s        Scatter random cells",
        f"  +/-      Volume ({S['volume']:.0%})",
    ]
    info_text.set_text('\n'.join(lines))

    return [im, pop_line, info_text, div_line, energy_line] + species_lines


# ═══════════════════════════════════════════════════════════════
# Interactive callbacks
# ═══════════════════════════════════════════════════════════════
def _apply_brush(x, y, alive_val):
    r = BRUSH_RADIUS
    for dx in range(-r, r + 1):
        for dy in range(-r, r + 1):
            nx, ny = x + dx, y + dy
            if 0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE and dx*dx + dy*dy <= r*r:
                S['alive'][nx, ny]  = alive_val
                if alive_val:
                    S['energy'][nx, ny] = 0.5
                    S['stage'][nx, ny]  = 1
                    S['age'][nx, ny]    = 0
                else:
                    S['stage'][nx, ny]  = 0
                    S['fade'][nx, ny]   = 0.5


def on_click(event):
    if event.inaxes is not ax1 or event.xdata is None:
        return
    # imshow: row=y, col=x  → swap
    gy, gx = int(round(event.ydata)), int(round(event.xdata))
    if not (0 <= gx < GRID_SIZE and 0 <= gy < GRID_SIZE):
        return
    if event.button == 1:          # left = add
        _apply_brush(gx, gy, True)
    elif event.button == 3:        # right = kill
        _apply_brush(gx, gy, False)


def on_key(event):
    k = event.key
    if k == 'r':
        S.update(init_state())
    elif k == 'p':
        S['paused'] = not S['paused']
    elif k == 'd':
        cx, cy = np.random.randint(5, GRID_SIZE - 5, size=2)
        rad = 8
        yy, xx = np.ogrid[:GRID_SIZE, :GRID_SIZE]
        dm = ((xx - cx)**2 + (yy - cy)**2 < rad**2) & (np.random.rand(GRID_SIZE, GRID_SIZE) < 0.8)
        S['alive'][dm] = False; S['stage'][dm] = 0
        S['disaster_flash'] = 6
    elif k == 'z':
        S['show_zones'] = not S['show_zones']
    elif k in ('+', '='):
        S['volume'] = min(1.0, S['volume'] + 0.1)
    elif k == '-':
        S['volume'] = max(0.0, S['volume'] - 0.1)
    elif k == 's':
        # scatter random cells
        n = np.random.randint(10, 40)
        xs = np.random.randint(0, GRID_SIZE, n)
        ys = np.random.randint(0, GRID_SIZE, n)
        S['alive'][xs, ys] = True
        S['energy'][xs, ys] = 0.4
        S['stage'][xs, ys] = 1
        S['age'][xs, ys] = 0
        S['species'][xs, ys] = np.random.randint(0, NUM_SPECIES, n).astype(np.int8)


fig.canvas.mpl_connect('button_press_event', on_click)
fig.canvas.mpl_connect('key_press_event',    on_key)


# ═══════════════════════════════════════════════════════════════
# Launch
# ═══════════════════════════════════════════════════════════════
stream = sd.OutputStream(channels=1, callback=audio_callback,
                         samplerate=SAMPLE_RATE, blocksize=frame_samples,
                         dtype='float32')
stream.start()

anim = FuncAnimation(fig, update, frames=MAX_STEPS,
                     interval=1000 / FPS, blit=False, repeat=True)
plt.show()

stream.stop()
stream.close()