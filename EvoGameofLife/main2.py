"""
Evolutionary Game of Life — Musical Sonification + Rolling Spectrogram
Run: python evo_game_of_life_musical.py
Requires: numpy, matplotlib. Optional: sounddevice for live audio.
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import random
import math
from collections import deque, defaultdict

# Try to import sounddevice for live audio
try:
    import sounddevice as sd
    HAVE_SD = True
except Exception:
    HAVE_SD = False
    print("sounddevice not installed — running without live audio.")

# ------------------------
# Configuration
# ------------------------
SIM = {
    "GRID_SIZE": 48,
    "INITIAL_CELLS": 50,
    "INITIAL_FOOD": 240,
    "FOOD_SPAWN_RATE": 0.02,
    "FOOD_SPREAD_RATE": 0.06,
    "BASE_LIFETIME": 8,
    "MAX_INIT_LIFETIME": 30,
    "BASE_BREED_PROB": 0.12,
    "MUTATION_RATE": 0.08,
    "FRAMES": 800,
    "INTERVAL_MS": 120,
}

AUDIO = {
    "ENABLED": HAVE_SD,
    "SR": 22050,
    "ROLL_SECONDS": 5.0,
    "FRAME_SAMPLES": 512,
    "MASTER_VOL": 0.22,
    "MAX_VOICES": 140,
    "EVENT_LIMIT": 40,
    "BIRTH_DUR": 0.10,
    "DEATH_DUR": 0.12,
    "EXTINCT_DUR": 0.36,
    "DRONE_BASE_FREQ": 45.0,
}

# Derived audio constants
ROLL_SAMPLES = int(AUDIO["ROLL_SECONDS"] * AUDIO["SR"])
FRAME_SAMPLES = AUDIO["FRAME_SAMPLES"]

# ------------------------
# Music scale (pentatonic) and helpers
# ------------------------
PENTATONIC = [261.63, 293.66, 329.63, 392.00, 440.00]  # C major pentatonic

def lineage_to_pitch(lineage_id, octave_offset=0):
    base = PENTATONIC[lineage_id % len(PENTATONIC)]
    octave = (lineage_id // len(PENTATONIC)) % 4 + octave_offset
    return base * (2 ** octave)

# Simple one-pole low-pass filter (fast)
def lowpass_onepole(signal, cutoff_hz, sr=AUDIO["SR"]):
    if cutoff_hz <= 0:
        return np.zeros_like(signal)
    # RC filter alpha from cutoff
    dt = 1.0 / sr
    rc = 1.0 / (2 * math.pi * cutoff_hz)
    alpha = dt / (rc + dt)
    out = np.zeros_like(signal)
    y = 0.0
    for i, x in enumerate(signal):
        y = y + alpha * (x - y)
        out[i] = y
    return out

# Small feedback delay reverb (comb-like) — controlled by depth and delay_ms
def simple_reverb(signal, depth=0.2, delay_ms=30, sr=AUDIO["SR"]):
    delay_samples = int(sr * (delay_ms / 1000.0))
    if delay_samples <= 0 or depth <= 0:
        return signal
    out = np.copy(signal)
    for i in range(delay_samples, len(signal)):
        out[i] += depth * out[i - delay_samples]
    # normalize mildly
    peak = np.max(np.abs(out)) if np.max(np.abs(out))>0 else 1.0
    return (out / peak) * np.max(np.abs(signal))

# ------------------------
# Simulation state
# ------------------------
EMPTY, FOOD, CELL = 0, 1, 2
N = SIM["GRID_SIZE"]
grid = np.zeros((N, N), dtype=np.int8)
cell_grid = np.full((N, N), None, dtype=object)

_next_lineage = 0
def alloc_lineage():
    global _next_lineage
    lid = _next_lineage
    _next_lineage += 1
    return lid

class Cell:
    def __init__(self, lifetime, breed_prob, lineage=None):
        self.lifetime = int(lifetime)
        self.age = 0
        self.breed_prob = float(breed_prob)
        self.lineage = lineage if lineage is not None else alloc_lineage()
        self.fitness = 0.0
    def mutate(self):
        mr = SIM["MUTATION_RATE"]
        if random.random() < mr:
            self.lifetime = max(1, self.lifetime + int(np.random.randint(-2, 3)))
        if random.random() < mr:
            self.breed_prob = float(np.clip(self.breed_prob + np.random.normal(scale=0.03), 0.01, 1.0))

# initialize cells
for _ in range(SIM["INITIAL_CELLS"]):
    x, y = np.random.randint(0, N, 2)
    if grid[x,y] == EMPTY:
        grid[x,y] = CELL
        lifetime = np.random.randint(SIM["BASE_LIFETIME"], SIM["MAX_INIT_LIFETIME"]+1)
        breed = SIM["BASE_BREED_PROB"] + np.random.uniform(-0.05, 0.05)
        cell_grid[x,y] = Cell(lifetime, breed)

# initial food
placed, attempts = 0, 0
while placed < SIM["INITIAL_FOOD"] and attempts < SIM["INITIAL_FOOD"] * 8:
    x,y = np.random.randint(0, N, 2)
    if grid[x,y] == EMPTY:
        grid[x,y] = FOOD
        placed += 1
    attempts += 1

# tracking structures
population_history = deque(maxlen=2000)
avg_lifetime_history = deque(maxlen=2000)
avg_fitness_history = deque(maxlen=2000)
lineage_history = []
lineage_birth = {}
lineage_death = {}
extinct_lineages = {}
current_step = 0
cmap = plt.cm.get_cmap('tab20')

# ------------------------
# Rolling audio engine (musical)
# ------------------------
class MusicalAudioEngine:
    def __init__(self, cfg):
        self.enabled = cfg["ENABLED"]
        self.sr = cfg["SR"]
        self.roll = np.zeros(ROLL_SAMPLES, dtype=np.float32)
        self.frame_len = FRAME_SAMPLES
        self.master = cfg["MASTER_VOL"]
        self.max_voices = cfg["MAX_VOICES"]
        self.event_limit = cfg["EVENT_LIMIT"]
        self.events = []
        self.cache = {}
        if self.enabled:
            try:
                self.stream = sd.OutputStream(samplerate=self.sr, channels=1, dtype='float32')
                self.stream.start()
            except Exception as e:
                print("audio stream error — disabling audio:", e)
                self.enabled = False

    def make_event(self, kind, lineage, lifetime, breed_prob, fitness):
        key = (kind, lineage, lifetime, round(float(breed_prob),3), int(fitness))
        if key in self.cache:
            return self.cache[key]
        base = lineage_to_pitch(lineage, octave_offset=(lineage//len(PENTATONIC))%3)
        if kind == 'birth':
            dur = AUDIO['BIRTH_DUR']
            freqs = [base, base*2]
        elif kind == 'death':
            dur = AUDIO['DEATH_DUR']
            freqs = [base*0.5, base*0.9]
        elif kind == 'extinct':
            dur = AUDIO['EXTINCT_DUR']
            freqs = [base*0.25, base*0.5, base*0.75]
        elif kind == 'begin':
            dur = 0.45
            freqs = [base, base*1.5, base*2.0]
        else:
            dur = 0.08
            freqs = [base]
        n = max(64, int(self.sr * dur))
        t = np.arange(n) / self.sr
        wave = np.zeros(n, dtype=np.float32)
        # fitness -> partials richness
        partials = 1 + int(min(4, fitness//1)) if isinstance(fitness, (int,float)) else 1
        for i in range(partials):
            wave += (1.0/(i+1)) * np.sin(2*np.pi*freqs[min(i,len(freqs)-1)] * (i+1) * t)
        # envelope
        att = int(0.01*self.sr)
        rel = int(0.03*self.sr)
        env = np.ones(n)
        if att>0: env[:att] = np.linspace(0,1,att)
        if rel>0: env[-rel:] = np.linspace(1,0,rel)
        wave *= env
        # breeding prob mapped to brightness via LPF: we simulate by filtering after synthesis when playing
        # store raw wave; filtering will be applied during mixing
        wave = wave / (np.max(np.abs(wave))+1e-12)
        wave = (wave * self.master).astype(np.float32)
        self.cache[key] = wave
        return wave

    def queue_event(self, kind, lineage, lifetime, breed_prob, fitness):
        if not self.enabled:
            return
        if len(self.events) >= self.event_limit:
            return
        w = self.make_event(kind, lineage, lifetime, breed_prob, fitness)
        # also attach metadata for brightness mapping
        self.events.append((w, breed_prob, lineage, lifetime, fitness))

    def synth_frame_from_voices(self, voices):
        # voices: list of dicts {freq, amp, vibrato(not used), age, lifetime, harmonics, breed_prob, lineage}
        t = np.arange(self.frame_len) / self.sr
        frame = np.zeros(self.frame_len, dtype=np.float32)
        if not voices:
            return frame
        # cap voices
        if len(voices) > self.max_voices:
            voices = random.sample(voices, self.max_voices)
        for v in voices:
            f = v['freq']
            a = v['amp']
            harmonics = v.get('harmonics', 1)
            for h in range(1, harmonics+1):
                frame += (a/(h)) * np.sin(2*np.pi * f * h * t)
            # short age-based tail: delayed low amp copy (gives warmth)
            age = v.get('age', 0.0)
            if age > 0.2:
                delay = int(0.01 * self.sr)
                if delay < self.frame_len:
                    tail = 0.06 * np.roll(frame, delay)
                    frame += tail
        # normalize and global scale
        peak = np.max(np.abs(frame)) if np.max(np.abs(frame))>0 else 1.0
        frame = (frame / peak) * self.master
        return frame

    def mix_and_play(self, voices, step_index):
        # synth continuous voice frame
        frame = self.synth_frame_from_voices(voices)

        # sum events (apply brightness filter per event using breed_prob)
        if self.events:
            max_ev_len = max(len(ev[0]) for ev in self.events)
            ev_mix = np.zeros(max_ev_len, dtype=np.float32)
            for w, breed_prob, lineage, lifetime, fitness in self.events:
                # apply LPF based on breeding prob: higher breed_prob -> higher cutoff -> brighter
                cutoff = 300 + breed_prob * 7000  # 300Hz -> 7.3kHz
                w_filt = lowpass_onepole(w, cutoff, sr=self.sr)
                ev_mix[:len(w_filt)] += w_filt
            # trim/pad ev_mix to frame length
            if len(ev_mix) >= len(frame):
                ev_slice = ev_mix[:len(frame)]
            else:
                ev_slice = np.zeros_like(frame)
                ev_slice[:len(ev_mix)] = ev_mix
            out = frame + ev_slice
        else:
            out = frame

        # drone/pad is already included in voices if used by caller
        # normalize
        peak = np.max(np.abs(out)) if np.max(np.abs(out))>0 else 1.0
        if peak > 1.0:
            out = out / peak

        # update rolling buffer
        shift = len(out)
        if shift >= len(self.roll):
            self.roll[:] = out[-len(self.roll):]
        else:
            self.roll[:-shift] = self.roll[shift:]
            self.roll[-shift:] = out

        self.events.clear()
        # play audio
        if self.enabled:
            try:
                self.stream.write(out.astype(np.float32))
            except Exception:
                try:
                    sd.play(out, self.sr, blocking=False)
                except Exception:
                    pass

# instantiate engine
ENG = MusicalAudioEngine(AUDIO)

# ------------------------
# Simulation functions
# ------------------------
def neighbors_orth(x,y):
    return [((x-1)%N, y), ((x+1)%N, y), (x, (y-1)%N), (x, (y+1)%N)]

def step_simulation():
    global grid, cell_grid, lineage_history
    new_grid = grid.copy()
    new_cells = cell_grid.copy()
    events_count = 0
    voices = []

    # food spread
    for (x,y) in np.argwhere(grid==FOOD):
        for nx,ny in neighbors_orth(x,y):
            if new_grid[nx,ny]==EMPTY and random.random() < SIM["FOOD_SPREAD_RATE"]:
                new_grid[nx,ny] = FOOD

    # food spawn attempts
    for _ in range(int(N*N*SIM["FOOD_SPAWN_RATE"])):
        rx,ry = np.random.randint(0,N,2)
        if new_grid[rx,ry] == EMPTY:
            new_grid[rx,ry] = FOOD

    # update cells
    for x in range(N):
        for y in range(N):
            if grid[x,y] == CELL and cell_grid[x,y] is not None:
                c = cell_grid[x,y]
                c.age += 1
                # eat food if present (in new_grid)
                if new_grid[x,y] == FOOD:
                    c.fitness += 1.0
                    c.lifetime += 1
                    new_grid[x,y] = CELL
                # death by age
                if c.age >= c.lifetime:
                    new_grid[x,y] = EMPTY
                    new_cells[x,y] = None
                    if events_count < AUDIO['EVENT_LIMIT'] and ENG.enabled:
                        ENG.queue_event('death', c.lineage, c.lifetime, c.breed_prob, c.fitness)
                        events_count += 1
                    continue
                # breed into orthogonal empties
                for nx,ny in neighbors_orth(x,y):
                    if new_grid[nx,ny] == EMPTY and random.random() < c.breed_prob:
                        baby = Cell(c.lifetime, c.breed_prob, lineage=c.lineage)
                        baby.mutate()
                        new_grid[nx,ny] = CELL
                        new_cells[nx,ny] = baby
                        if events_count < AUDIO['EVENT_LIMIT'] and ENG.enabled:
                            ENG.queue_event('birth', baby.lineage, baby.lifetime, baby.breed_prob, c.fitness)
                            events_count += 1
                # build a voice entry for continuous synthesis
                base = lineage_to_pitch(c.lineage, octave_offset=(c.age//20)%3)
                # breeding prob -> filter cutoff (we will use breed_prob later when filtering events)
                vibr = 0.0
                amp = min(1.0, 0.35 + 0.6 * min(1.0, c.fitness/5.0))
                harmonics = 1 + int(min(4, c.fitness//1))
                age_norm = c.age / (c.lifetime + 1e-6)
                voices.append({'freq': base, 'amp': amp*0.5, 'age': age_norm, 'harmonics': harmonics, 'breed_prob': c.breed_prob, 'lineage': c.lineage, 'lifetime': c.lifetime})

    # apply new grid
    grid[:,:] = new_grid
    cell_grid[:,:] = new_cells

    # lineage snapshot
    counts = defaultdict(int)
    total = int(np.sum(grid==CELL))
    for x in range(N):
        for y in range(N):
            cc = cell_grid[x,y]
            if cc is not None:
                counts[cc.lineage] += 1
    lineage_history.append({lid: cnt/total for lid,cnt in counts.items()} if total>0 else {})

    # drone/pad voices based on population & avg fitness
    pop = total
    avg_fit = (sum(cc.fitness for row in cell_grid for cc in row if cc is not None) / pop) if pop>0 else 0.0
    drone_freq = AUDIO['DRONE_BASE_FREQ'] + pop * 0.6
    drone_amp = min(0.9, 0.02 + avg_fit * 0.5)
    # root + fifth
    voices.append({'freq': drone_freq, 'amp': drone_amp*0.6, 'age':0.0, 'harmonics':1, 'breed_prob':0.0, 'lineage': -1, 'lifetime':1})
    voices.append({'freq': drone_freq*1.5, 'amp': drone_amp*0.35, 'age':0.0, 'harmonics':1, 'breed_prob':0.0, 'lineage': -1, 'lifetime':1})

    # pass voices to engine to mix & play (engine also mixes queued event waves applying brightness filters)
    ENG.mix_and_play(voices, current_step)

def register_lineages():
    global lineage_birth, lineage_death, extinct_lineages, current_step
    active = {cell_grid[x,y].lineage for x in range(N) for y in range(N) if cell_grid[x,y] is not None}
    for lid in active:
        if lid not in lineage_birth:
            lineage_birth[lid] = current_step
    for lid in list(lineage_birth.keys()):
        if lid not in active and lid not in lineage_death:
            lineage_death[lid] = current_step
            extinct_lineages[lid] = lineage_death[lid] - lineage_birth[lid]
            if ENG.enabled:
                ENG.queue_event('extinct', lid, extinct_lineages[lid], 0.1, extinct_lineages[lid])

# ------------------------
# Visualization helpers
# ------------------------
def get_color_grid():
    img = np.zeros((N,N,3), dtype=float)
    # top lineage highlight
    counts = defaultdict(int)
    for x in range(N):
        for y in range(N):
            c = cell_grid[x,y]
            if c is not None:
                counts[c.lineage] += 1
    top = max(counts, key=counts.get) if counts else None
    for x in range(N):
        for y in range(N):
            if grid[x,y] == FOOD:
                img[x,y] = (0.03,0.8,0.03)
            elif grid[x,y] == CELL and cell_grid[x,y] is not None:
                c = cell_grid[x,y]
                base = np.array(cmap(c.lineage % cmap.N)[:3])
                age_norm = min(1.0, c.age / max(1, c.lifetime))
                col = base * (1.0 - 0.45 * age_norm)
                if top is not None and c.lineage == top:
                    col = col * 0.62 + np.array([0.38,0.38,0.38])
                img[x,y] = np.clip(col, 0.0, 1.0)
            else:
                img[x,y] = (0.0,0.0,0.0)
    return img

def get_density():
    dens = np.zeros((N,N), dtype=float)
    for x in range(N):
        for y in range(N):
            if cell_grid[x,y] is not None:
                dens[x,y] = 1.0
    return dens

# ------------------------
# Main / Animation (rolling spectrogram)
# ------------------------
def main():
    global current_step
    current_step = 0

    # initial 'begin' event
    if ENG.enabled:
        ENG.queue_event('begin', 0, SIM['BASE_LIFETIME'], SIM['BASE_BREED_PROB'], 0)
        ENG.mix_and_play([], -1)

    fig, axes = plt.subplots(1, 6, figsize=(26,5))
    ax_grid, ax_stats, ax_lineages, ax_persist, ax_heat, ax_spec = axes

    im_grid = ax_grid.imshow(get_color_grid(), interpolation='nearest')
    ax_grid.set_title('Grid')
    ax_grid.axis('off')
    pop_text = ax_grid.text(0.02, 0.96, "", transform=ax_grid.transAxes, color='white',
                            fontsize=11, bbox=dict(facecolor='black', alpha=0.6))

    line_pop, = ax_stats.plot([], [], label='Population', color='tab:blue')
    line_life, = ax_stats.plot([], [], label='Avg Lifetime', color='tab:green')
    line_fit, = ax_stats.plot([], [], label='Avg Fitness', color='tab:red')
    ax_stats.set_xlim(0, SIM['FRAMES'])
    ax_stats.set_ylim(0, max(10, SIM['MAX_INIT_LIFETIME']))
    ax_stats.set_title('Population Stats')
    ax_stats.legend()

    ax_lineages.set_title('Lineage Dominance')
    ax_lineages.set_ylim(0,1)

    ax_persist.set_title('Lineage Persistence (extinct)')
    ax_persist.set_xlabel('Lineage ID')
    ax_persist.set_ylabel('Lifetime (steps)')

    im_heat = ax_heat.imshow(get_density(), cmap='hot', vmin=0, vmax=1, interpolation='nearest')
    ax_heat.set_title('Population Density')
    ax_heat.axis('off')

    # spectrogram params
    nfft = 1024
    noverlap = nfft//2

    def update(frame):
        nonlocal nfft, noverlap
        global current_step
        current_step += 1

        step_simulation()
        register_lineages()

        # visuals
        im_grid.set_data(get_color_grid())
        pop = int(np.sum(grid==CELL))
        pop_text.set_text(f"Population: {pop}")

        lifetimes = [cell_grid[x,y].lifetime for x in range(N) for y in range(N) if cell_grid[x,y] is not None]
        fitnesses = [cell_grid[x,y].fitness for x in range(N) for y in range(N) if cell_grid[x,y] is not None]

        population_history.append(pop)
        avg_lifetime_history.append(float(np.mean(lifetimes)) if lifetimes else 0.0)
        avg_fitness_history.append(float(np.mean(fitnesses)) if fitnesses else 0.0)

        xs = range(len(population_history))
        line_pop.set_data(xs, population_history)
        line_life.set_data(xs, avg_lifetime_history)
        line_fit.set_data(xs, avg_fitness_history)
        ax_stats.set_xlim(0, max(50, len(population_history)))

        # lineage dominance stacked plot
        ax_lineages.clear()
        ax_lineages.set_title('Lineage Dominance')
        if lineage_history:
            all_ids = sorted({lid for snap in lineage_history for lid in snap.keys()})
            if all_ids:
                data = np.array([[snap.get(lid,0.0) for lid in all_ids] for snap in lineage_history])
                colors = [cmap(lid % cmap.N) for lid in all_ids]
                ax_lineages.stackplot(range(len(lineage_history)), data.T, colors=colors)
                ax_lineages.set_ylim(0,1)
                ax_lineages.set_xlim(0, max(50, len(lineage_history)))

        # persistence
        ax_persist.clear()
        ax_persist.set_title('Lineage Persistence (extinct)')
        if extinct_lineages:
            lids = list(extinct_lineages.keys())
            lifespans = [extinct_lineages[lid] for lid in lids]
            ax_persist.bar(range(len(lids)), lifespans, color=[cmap(lid% cmap.N) for lid in lids])
            ax_persist.set_xticks(range(len(lids)))
            ax_persist.set_xticklabels([str(lid) for lid in lids], rotation=90, fontsize=6)

        im_heat.set_data(get_density())

        # rolling spectrogram using ENG.roll
        ax_spec.clear()
        ax_spec.set_title('Rolling Spectrogram')
        if ENG.roll is not None and np.max(np.abs(ENG.roll))>1e-8:
            try:
                Pxx, freqs, bins, im = ax_spec.specgram(ENG.roll, NFFT=nfft, Fs=ENG.sr, noverlap=noverlap, cmap='magma')
                ax_spec.set_ylim(0, ENG.sr/2.0)
            except Exception:
                ax_spec.text(0.5,0.5,'spectrogram error', ha='center', va='center')
        else:
            ax_spec.text(0.5,0.5,'no audio yet', ha='center', va='center')

        return [im_grid, line_pop, line_life, line_fit, im_heat]

    ani = animation.FuncAnimation(fig, update, frames=SIM['FRAMES'], interval=SIM['INTERVAL_MS'], blit=False)
    plt.show()

    # cleanup
    if ENG.enabled and hasattr(ENG, 'stream'):
        try:
            ENG.stream.stop()
            ENG.stream.close()
        except Exception:
            pass

if __name__ == "__main__":
    main()
