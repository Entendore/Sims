"""
Evolutionary Game of Life with continuous sonification and rolling spectrogram.

Features:
- Food spawn + spread
- Cells with lifetime, breed_prob, mutation
- Evolution with lineage tracking (IDs, births, extinctions)
- Event sounds: birth / death / extinct
- Continuous soundscape: per-lineage partials, vibrato (breed_prob), age -> 'reverb' tail, fitness -> amp
- Background drone tied to population and avg fitness
- Rolling spectrogram showing the last R seconds of audio (smooth/continuous)
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import random
import time
import math
from collections import deque, defaultdict

# Attempt to import sounddevice. If not available, audio is disabled.
try:
    import sounddevice as sd
    HAVE_SD = True
except Exception:
    HAVE_SD = False
    print("sounddevice not available — running without audio. Install with `pip install sounddevice` for audio.")

# ------------------------
# CONFIG
# ------------------------
SIM = {
    "GRID_SIZE": 48,
    "INITIAL_CELLS": 50,
    "INITIAL_FOOD": 240,
    "FOOD_SPAWN_RATE": 0.02,   # fraction attempts per step
    "FOOD_SPREAD_RATE": 0.06,
    "BASE_LIFETIME": 8,
    "MAX_INIT_LIFETIME": 30,
    "BASE_BREED_PROB": 0.12,
    "MUTATION_RATE": 0.08,
    "FRAMES": 800,
    "INTERVAL_MS": 120,
}

AUDIO_CFG = {
    "ENABLED": HAVE_SD,
    "SR": 22050,
    "ROLL_SECONDS": 5.0,            # rolling spectrogram window
    "FRAME_SIZE": 512,              # audio frame size per simulation step (samples)
    "AUDIO_MASTER": 0.25,
    "AUDIO_MAX_VOICES": 120,        # max simultaneous sine voices to sum (safety)
    "EVENT_MAX_PER_STEP": 40,
    "BIRTH_DUR": 0.08,
    "DEATH_DUR": 0.10,
    "EXTINCT_DUR": 0.35,
    "DRONE_BASE_FREQ": 45.0,        # base freq for drone
}

# Derived
ROLL_SAMPLES = int(AUDIO_CFG["ROLL_SECONDS"] * AUDIO_CFG["SR"])
FRAME_SAMPLES = AUDIO_CFG["FRAME_SIZE"]

# ------------------------
# Simulation state
# ------------------------
EMPTY, FOOD, CELL = 0, 1, 2

GRID_N = SIM["GRID_SIZE"]
grid = np.zeros((GRID_N, GRID_N), dtype=np.int8)
cell_grid = np.full((GRID_N, GRID_N), None, dtype=object)

# lineage id generator
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

# place initial cells and food
for _ in range(SIM["INITIAL_CELLS"]):
    x, y = np.random.randint(0, GRID_N, 2)
    if grid[x,y] == EMPTY:
        grid[x,y] = CELL
        lifetime = np.random.randint(SIM["BASE_LIFETIME"], SIM["MAX_INIT_LIFETIME"]+1)
        breed = SIM["BASE_BREED_PROB"] + np.random.uniform(-0.05, 0.05)
        cell_grid[x,y] = Cell(lifetime, breed)

placed = 0
attempts = 0
while placed < SIM["INITIAL_FOOD"] and attempts < SIM["INITIAL_FOOD"] * 8:
    x,y = np.random.randint(0, GRID_N, 2)
    if grid[x,y] == EMPTY:
        grid[x,y] = FOOD
        placed += 1
    attempts += 1

# tracking
population_history = deque(maxlen=2000)
avg_lifetime_history = deque(maxlen=2000)
avg_fitness_history = deque(maxlen=2000)
lineage_history = []   # snapshots per step: dict lineage->proportion
lineage_birth = {}
lineage_death = {}
extinct_lineages = {}
current_step = 0

# ------------------------
# AUDIO ENGINE (continuous)
# ------------------------
class RollingAudioEngine:
    def __init__(self, cfg):
        self.enabled = cfg["ENABLED"]
        self.sr = cfg["SR"]
        self.roll_samples = ROLL_SAMPLES
        self.frame_samples = FRAME_SAMPLES
        self.master = cfg["AUDIO_MASTER"]
        self.max_voices = cfg["AUDIO_MAX_VOICES"]
        self.event_max = cfg["EVENT_MAX_PER_STEP"]
        self.last_mix = np.zeros(self.frame_samples, dtype=np.float32)
        # rolling buffer for spectrogram
        self.rolling = np.zeros(self.roll_samples, dtype=np.float32)
        # event queue for this step
        self.step_events = []
        # small cache of event waveforms keyed by attributes
        self.cache = {}
        # create a continuous output stream if sounddevice available
        if self.enabled:
            try:
                self.stream = sd.OutputStream(samplerate=self.sr, channels=1, dtype='float32')
                self.stream.start()
            except Exception as e:
                print("Warning: sounddevice OutputStream failed, disabling audio:", e)
                self.enabled = False

    def lineage_to_base_freq(self, lineage):
        # map lineage id deterministically to a base frequency (musical-like)
        semitone = (lineage * 5) % 48  # spread across 4 octaves-ish
        base = 110.0 * (2.0 ** (semitone / 12.0))
        return float(np.clip(base, 40.0, 3500.0))

    def synth_frame(self, voices):
        """Synthesize a short frame by summing simple partials (sine waves).
        voices: list of dicts: {'freq': f, 'amp': a, 'vibrato': v, 'age': age, 'lineage': id}"""
        if not voices:
            return np.zeros(self.frame_samples, dtype=np.float32)
        t = np.arange(self.frame_samples) / self.sr
        frame = np.zeros_like(t, dtype=np.float32)
        # limit voices to max_voices
        if len(voices) > self.max_voices:
            voices = random.sample(voices, self.max_voices)
        for v in voices:
            f = v['freq']
            a = v['amp']
            vib = v.get('vibrato', 0.0)
            age = v.get('age', 0.0)
            # vibrato as frequency modulation
            if vib > 0.001:
                f_t = f + 0.5 * vib * np.sin(2*np.pi * vib * t)
            else:
                f_t = f
            # basic partials: fundamental + some harmonics influenced by fitness
            harmonics = v.get('harmonics', 2)
            for h in range(1, harmonics+1):
                amp_h = a / h
                frame += amp_h * np.sin(2*np.pi * f_t * h * t)
            # simple age-based tail effect: add delayed low-amplitude copy
            # not convolutional reverb, but gives a sense of 'width' for older lineages
            if age > 0.1:
                tail_amp = 0.08 * min(1.0, age/ (v.get('lifetime',1) + 0.0001))
                delay_samples = min(self.frame_samples-1, int(self.sr * 0.01))  # 10ms delay
                # add delayed copy
                frame[delay_samples:] += tail_amp * np.roll(frame, delay_samples)[delay_samples:]
        # normalize
        peak = np.max(np.abs(frame)) if np.max(np.abs(frame)) > 0 else 1.0
        frame = (frame / peak).astype(np.float32) * self.master
        return frame

    def make_event_wave(self, kind, lineage, lifetime, breed_prob, fitness):
        key = (kind, lineage, lifetime, round(float(breed_prob),3), int(fitness))
        if key in self.cache:
            return self.cache[key]
        base = self.lineage_to_base_freq(lineage)
        if kind == 'birth':
            dur = AUDIO_CFG["BIRTH_DUR"]
            freqs = [base * (1 + 0.02*lineage), base*2]
            mags = [1.0, 0.5 + 0.5*fitness]
        elif kind == 'death':
            dur = AUDIO_CFG["DEATH_DUR"]
            freqs = [base*0.5, base*0.8]
            mags = [1.0, 0.4]
        elif kind == 'extinct':
            dur = AUDIO_CFG["EXTINCT_DUR"]
            freqs = [base*0.25, base*0.5, base*0.75]
            mags = [1.0, 0.7, 0.4]
        elif kind == 'begin':
            dur = 0.45
            freqs = [base, base*1.5, base*2.2]
            mags = [1.0, 0.7, 0.45]
        else:
            dur = 0.08
            freqs = [base]
            mags = [1.0]
        n = max(64, int(self.sr * dur))
        t = np.arange(n) / self.sr
        wave = np.zeros(n, dtype=np.float32)
        for f, m in zip(freqs, mags):
            wave += m * np.sin(2*np.pi * f * t)
        # envelope
        att = int(0.01 * self.sr)
        rel = int(0.02 * self.sr)
        env = np.ones(n, dtype=np.float32)
        if att>0: env[:att] = np.linspace(0,1,att)
        if rel>0: env[-rel:] = np.linspace(1,0,rel)
        wave *= env
        if np.max(np.abs(wave))>0:
            wave /= np.max(np.abs(wave))
        wave *= self.master
        self.cache[key] = wave
        return wave

    def queue_event(self, kind, lineage, lifetime, breed_prob, fitness):
        if not self.enabled:
            return
        if len(self.step_events) >= self.event_max:
            return
        w = self.make_event_wave(kind, lineage, lifetime, breed_prob, fitness)
        self.step_events.append(w)

    def mix_and_play_step(self, voices_for_frame, step_index):
        """Synthesize continuous frame + mix queued event sounds and play; also update rolling buffer for spectrogram."""
        # synth continuous frame from voices
        frame = self.synth_frame(voices_for_frame)

        # mix events: pad to frame length and add
        if self.step_events:
            max_len = max(len(w) for w in self.step_events)
            # if events longer than frame, we'll mix them clipped
            mix_ev = np.zeros(max_len, dtype=np.float32)
            for w in self.step_events:
                mix_ev[:len(w)] += w
            # trim or pad mix_ev to frame length
            if len(mix_ev) >= len(frame):
                ev_slice = mix_ev[:len(frame)]
            else:
                ev_slice = np.zeros_like(frame)
                ev_slice[:len(mix_ev)] = mix_ev
            out = frame + ev_slice
        else:
            out = frame

        # normalize to avoid clipping
        peak = np.max(np.abs(out)) if np.max(np.abs(out))>0 else 1.0
        if peak > 1.0:
            out = out / peak

        # update rolling buffer
        shift = len(out)
        if shift >= len(self.rolling):
            # keep only the tail
            self.rolling[:] = out[-len(self.rolling):]
        else:
            self.rolling[:-shift] = self.rolling[shift:]
            self.rolling[-shift:] = out

        self.last_mix = out.copy()
        self.step_events.clear()

        # play via sounddevice if enabled
        if self.enabled:
            try:
                # non-blocking: write to stream
                self.stream.write(out.astype(np.float32))
            except Exception:
                # fallback to blocking sd.play
                try:
                    sd.play(out, self.sr, blocking=False)
                except Exception:
                    pass

# instantiate audio engine
AUDIO = RollingAudioEngine(AUDIO_CFG)

# ------------------------
# Simulation functions
# ------------------------
def neighbors_orthogonal(x, y):
    return [((x-1)%GRID_N, y), ((x+1)%GRID_N, y), (x, (y-1)%GRID_N), (x, (y+1)%GRID_N)]

def step_simulation():
    """One sim tick: food spawn/spread, cell updates, breeding, death; queue audio events and build voices for continuous sound."""
    global grid, cell_grid, lineage_history

    new_grid = grid.copy()
    new_cells = cell_grid.copy()
    events_count = 0

    # food spread
    for (x,y) in np.argwhere(grid == FOOD):
        for nx,ny in neighbors_orthogonal(x,y):
            if new_grid[nx,ny] == EMPTY and random.random() < SIM["FOOD_SPREAD_RATE"]:
                new_grid[nx,ny] = FOOD

    # random spawn attempts
    spawn_attempts = int(GRID_N * GRID_N * SIM["FOOD_SPAWN_RATE"])
    for _ in range(spawn_attempts):
        rx, ry = np.random.randint(0, GRID_N, 2)
        if new_grid[rx,ry] == EMPTY:
            new_grid[rx,ry] = FOOD

    # collect voices list (per-living-cell) to synthesize continuous frame
    voices = []

    # update cells
    for x in range(GRID_N):
        for y in range(GRID_N):
            if grid[x,y] == CELL and cell_grid[x,y] is not None:
                c = cell_grid[x,y]
                c.age += 1

                # consume food if present
                if new_grid[x,y] == FOOD:
                    c.fitness += 1.0
                    c.lifetime += 1
                    new_grid[x,y] = CELL

                # death by age
                if c.age >= c.lifetime:
                    new_grid[x,y] = EMPTY
                    new_cells[x,y] = None
                    # queue death sound
                    if events_count < AUDIO.event_max:
                        AUDIO.queue_event("death", c.lineage, c.lifetime, c.breed_prob, c.fitness)
                        events_count += 1
                    continue

                # attempt to breed to orthogonal empty neighbors
                for nx, ny in neighbors_orthogonal(x,y):
                    if new_grid[nx,ny] == EMPTY and random.random() < c.breed_prob:
                        baby = Cell(c.lifetime, c.breed_prob, lineage=c.lineage)
                        baby.mutate()
                        new_grid[nx,ny] = CELL
                        new_cells[nx,ny] = baby
                        if events_count < AUDIO.event_max:
                            AUDIO.queue_event("birth", baby.lineage, baby.lifetime, baby.breed_prob, c.fitness)
                            events_count += 1

                # prepare voice parameters for this living cell
                base = AUDIO.lineage_to_base_freq(c.lineage)
                # map breed_prob -> vibrato Hz range
                vibrato = max(0.0, min(8.0, 6.0 * c.breed_prob))
                # fitness -> amplitude scaling (small)
                amp = min(1.0, 0.4 + 0.6 * min(1.0, c.fitness / 5.0))
                # number of harmonics increases with fitness
                harmonics = 1 + int(min(4, c.fitness // 1))
                # age normalized
                age_norm = c.age / (c.lifetime + 0.0001)
                voices.append({
                    'freq': base * (1.0 + 0.02 * (c.lineage % 12)),
                    'amp': amp * 0.3,        # keep per-cell amplitude small; global drone mixes in
                    'vibrato': vibrato,
                    'age': age_norm,
                    'lifetime': c.lifetime,
                    'harmonics': harmonics,
                    'lineage': c.lineage
                })

    # update grid & cells
    grid[:, :] = new_grid
    cell_grid[:, :] = new_cells

    # build lineage snapshot
    counts = defaultdict(int)
    total = int(np.sum(grid == CELL))
    for x in range(GRID_N):
        for y in range(GRID_N):
            cc = cell_grid[x,y]
            if cc is not None:
                counts[cc.lineage] += 1
    lineage_history.append({lid: cnt / total for lid,cnt in counts.items()} if total>0 else {})

    # background drone voice(s) based on population and avg fitness
    pop = total
    avg_fitness = (sum(cc.fitness for row in cell_grid for cc in row if cc is not None) / pop) if pop>0 else 0.0
    # drone base freq increases slightly with population
    drone_freq = AUDIO_CFG["DRONE_BASE_FREQ"] + pop * 0.6
    drone_amp = min(0.8, 0.05 + avg_fitness * 0.6)
    # create a few slow partials for drone
    drone_voices = []
    for i in range(1,3):
        drone_voices.append({'freq': drone_freq*i, 'amp': drone_amp * (0.8 / i), 'vibrato': 0.25 * avg_fitness, 'age': 0.0, 'harmonics':1, 'lifetime':1, 'lineage': -1})

    # combine voices and queue to audio engine
    all_voices = voices + drone_voices
    # For CPU: downsample voices randomly if too many
    if len(all_voices) > AUDIO.max_voices:
        all_voices = random.sample(all_voices, AUDIO.max_voices)

    AUDIO.mix_and_play_step(all_voices, current_step)

def register_lineages_and_extinctions():
    global lineage_birth, lineage_death, extinct_lineages, current_step
    active = {cell_grid[x,y].lineage for x in range(GRID_N) for y in range(GRID_N) if cell_grid[x,y] is not None}
    for lid in active:
        if lid not in lineage_birth:
            lineage_birth[lid] = current_step
    for lid in list(lineage_birth.keys()):
        if lid not in active and lid not in lineage_death:
            lineage_death[lid] = current_step
            extinct_lineages[lid] = lineage_death[lid] - lineage_birth[lid]
            AUDIO.queue_event("extinct", lid, extinct_lineages[lid], 0.1, extinct_lineages[lid])

# ------------------------
# Visualization helpers
# ------------------------
cmap = plt.cm.get_cmap('tab20')

def get_color_grid():
    img = np.zeros((GRID_N, GRID_N, 3), dtype=float)
    # compute top lineage for highlight
    counts = defaultdict(int)
    for x in range(GRID_N):
        for y in range(GRID_N):
            c = cell_grid[x,y]
            if c is not None:
                counts[c.lineage] += 1
    top = max(counts, key=counts.get) if counts else None

    for x in range(GRID_N):
        for y in range(GRID_N):
            if grid[x,y] == FOOD:
                img[x,y] = np.array([0.03, 0.8, 0.03])
            elif grid[x,y] == CELL and cell_grid[x,y] is not None:
                c = cell_grid[x,y]
                base = np.array(cmap(c.lineage % cmap.N)[:3])
                age_norm = min(1.0, c.age / max(1, c.lifetime))
                col = base * (1.0 - 0.45 * age_norm)
                if top is not None and c.lineage == top:
                    col = col * 0.6 + np.array([0.4,0.4,0.4])
                img[x,y] = np.clip(col, 0.0, 1.0)
            else:
                img[x,y] = np.array([0.0,0.0,0.0])
    return img

def get_density():
    dens = np.zeros((GRID_N, GRID_N), dtype=float)
    for x in range(GRID_N):
        for y in range(GRID_N):
            if cell_grid[x,y] is not None:
                dens[x,y] = 1.0
    return dens

# ------------------------
# MAIN + Animation (rolling spectrogram)
# ------------------------
def main():
    global current_step
    current_step = 0

    # initial begin sound
    if AUDIO.enabled:
        AUDIO.queue_event("begin", 0, SIM["BASE_LIFETIME"], SIM["BASE_BREED_PROB"], 0)
        AUDIO.mix_and_play_step([], -1)

    fig, axes = plt.subplots(1, 6, figsize=(26, 5))
    ax_grid, ax_stats, ax_lineages, ax_persist, ax_heat, ax_spec = axes

    im_grid = ax_grid.imshow(get_color_grid(), interpolation='nearest')
    ax_grid.set_title("Grid")
    ax_grid.axis('off')
    pop_text = ax_grid.text(0.02, 0.96, "", transform=ax_grid.transAxes, color="white",
                            fontsize=11, bbox=dict(facecolor='black', alpha=0.6))

    # stats plot
    line_pop, = ax_stats.plot([], [], label='Population', color='tab:blue')
    line_life, = ax_stats.plot([], [], label='Avg Lifetime', color='tab:green')
    line_fit, = ax_stats.plot([], [], label='Avg Fitness', color='tab:red')
    ax_stats.set_xlim(0, SIM["FRAMES"])
    ax_stats.set_ylim(0, max(10, SIM["MAX_INIT_LIFETIME"]))
    ax_stats.set_title("Population Stats")
    ax_stats.legend()

    ax_lineages.set_title("Lineage Dominance")
    ax_lineages.set_ylim(0,1)

    ax_persist.set_title("Lineage Persistence (extinct)")
    ax_persist.set_xlabel("Lineage ID")
    ax_persist.set_ylabel("Lifetime (steps)")

    im_heat = ax_heat.imshow(get_density(), cmap='hot', vmin=0, vmax=1, interpolation='nearest')
    ax_heat.set_title("Population Density")
    ax_heat.axis('off')

    # Spectrogram init
    ax_spec.set_title("Rolling Spectrogram")
    spec_im = None

    # spec parameters
    nfft = 1024
    noverlap = nfft // 2
    hop = nfft - noverlap

    def update(frame):
        nonlocal spec_im
        global current_step
        current_step += 1

        # simulation step and audio synthesis
        step_simulation()
        register_lineages_and_extinctions()

        # Visual updates
        im_grid.set_data(get_color_grid())
        pop = int(np.sum(grid == CELL))
        pop_text.set_text(f"Population: {pop}")

        lifetimes = [cell_grid[x,y].lifetime for x in range(GRID_N) for y in range(GRID_N) if cell_grid[x,y] is not None]
        fitnesses = [cell_grid[x,y].fitness for x in range(GRID_N) for y in range(GRID_N) if cell_grid[x,y] is not None]

        population_history.append(pop)
        avg_lifetime_history.append(float(np.mean(lifetimes)) if lifetimes else 0.0)
        avg_fitness_history.append(float(np.mean(fitnesses)) if fitnesses else 0.0)

        xs = range(len(population_history))
        line_pop.set_data(xs, population_history)
        line_life.set_data(xs, avg_lifetime_history)
        line_fit.set_data(xs, avg_fitness_history)
        ax_stats.set_xlim(0, max(50, len(population_history)))

        # lineage dominance stacked area
        ax_lineages.clear()
        ax_lineages.set_title("Lineage Dominance")
        if lineage_history:
            all_ids = sorted({lid for snap in lineage_history for lid in snap.keys()})
            if all_ids:
                data = np.array([[snap.get(lid, 0.0) for lid in all_ids] for snap in lineage_history])
                colors = [cmap(lid % cmap.N) for lid in all_ids]
                ax_lineages.stackplot(range(len(lineage_history)), data.T, colors=colors)
                ax_lineages.set_ylim(0,1)
                ax_lineages.set_xlim(0, max(50, len(lineage_history)))

        # persistence
        ax_persist.clear()
        ax_persist.set_title("Lineage Persistence (extinct)")
        if extinct_lineages:
            lids = list(extinct_lineages.keys())
            lifespans = [extinct_lineages[lid] for lid in lids]
            ax_persist.bar(range(len(lids)), lifespans, color=[cmap(lid % cmap.N) for lid in lids])
            ax_persist.set_xticks(range(len(lids)))
            ax_persist.set_xticklabels([str(lid) for lid in lids], rotation=90, fontsize=6)

        im_heat.set_data(get_density())

        # draw rolling spectrogram using AUDIO.rolling
        ax_spec.clear()
        ax_spec.set_title("Rolling Spectrogram")
        if AUDIO.last_mix is not None:
            # use rolling buffer (most recent tail)
            data = AUDIO.rolling
            # compute spectrogram with matplotlib's specgram
            # to keep plot fast, downsample for specgram if sampling rate is high
            try:
                Pxx, freqs, bins, im = ax_spec.specgram(data, NFFT=nfft, Fs=AUDIO.sr, noverlap=noverlap, cmap='magma')
                ax_spec.set_ylim(0, AUDIO.sr/2.0)
            except Exception:
                # fallback small text if spec fails
                ax_spec.text(0.5,0.5,"spectrogram unavailable", ha='center', va='center')
        else:
            ax_spec.text(0.5,0.5,"no audio yet", ha='center', va='center')

        # return artists
        return [im_grid, line_pop, line_life, line_fit, im_heat]

    ani = animation.FuncAnimation(fig, update, frames=SIM["FRAMES"], interval=SIM["INTERVAL_MS"], blit=False)
    plt.show()

    # cleanup audio stream
    if AUDIO.enabled and hasattr(AUDIO, 'stream'):
        try:
            AUDIO.stream.stop()
            AUDIO.stream.close()
        except Exception:
            pass

if __name__ == "__main__":
    main()
