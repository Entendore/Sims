import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import sounddevice as sd

# --------------------------
# Parameters
# --------------------------
GRID_SIZE = 50
FPS = 15
SAMPLE_RATE = 44100
DURATION_PER_FRAME = 1/FPS
STEPS = 400
MUTATION_RATE = 0.05
ZONE_SIZE = 10
lineage_counter = 0

# --------------------------
# Environment zones
# --------------------------
num_zones = GRID_SIZE // ZONE_SIZE
zones_energy = np.random.uniform(0.02,0.08,(num_zones,num_zones))
zones_melody = np.random.uniform(-50,50,(num_zones,num_zones))

# --------------------------
# Cellular Automata (vectorized)
# --------------------------
alive = np.random.rand(GRID_SIZE,GRID_SIZE) < 0.2
age = np.zeros((GRID_SIZE,GRID_SIZE))
energy = np.random.rand(GRID_SIZE,GRID_SIZE)
stage = np.full((GRID_SIZE,GRID_SIZE),'birth',dtype=object)

# Genetic traits
energy_gain_rate = np.random.uniform(0.01,0.1,(GRID_SIZE,GRID_SIZE))
reproduction_threshold = np.random.uniform(0.5,1.0,(GRID_SIZE,GRID_SIZE))
tone_mod = np.random.uniform(0.5,2.0,(GRID_SIZE,GRID_SIZE))
lineage = np.arange(GRID_SIZE*GRID_SIZE).reshape(GRID_SIZE,GRID_SIZE)
melody_base = np.random.uniform(220,440,(GRID_SIZE,GRID_SIZE))

# --------------------------
# Helper functions
# --------------------------
def get_zone(x,y):
    zx, zy = x//ZONE_SIZE, y//ZONE_SIZE
    return zones_energy[zx,zy], zones_melody[zx,zy]

def neighbors_count(alive_grid):
    # count alive neighbors with np.roll
    n = np.zeros_like(alive_grid)
    for dx in [-1,0,1]:
        for dy in [-1,0,1]:
            if dx==0 and dy==0: continue
            n += np.roll(np.roll(alive_grid,dx,axis=0),dy,axis=1)
    return n

# --------------------------
# Audio setup
# --------------------------
frame_samples = int(DURATION_PER_FRAME*SAMPLE_RATE)
audio_buffer = np.zeros(frame_samples, dtype=np.float32)

def generate_tone(freq, amp=0.2):
    t = np.linspace(0,DURATION_PER_FRAME,frame_samples,False)
    return amp*np.sin(2*np.pi*freq*t)

# --------------------------
# Update function
# --------------------------
def update(frame):
    global alive, age, energy, stage, melody_base, tone_mod

    neighbors = neighbors_count(alive)

    birth = (~alive) & (neighbors==3)
    survive = alive & ((neighbors==2)|(neighbors==3))
    dead = ~survive

    alive = birth | survive

    # Update age, energy, stage
    age = np.where(alive, age+1, 0)
    zone_energy = np.zeros_like(energy)
    for x in range(GRID_SIZE):
        for y in range(GRID_SIZE):
            z_energy, z_melody = get_zone(x,y)
            zone_energy[x,y] = z_energy
            melody_base[x,y] += z_melody*0.0  # melody drift small

    energy = np.where(alive, np.minimum(1.0, energy + energy_gain_rate + zone_energy), 0)
    stage = np.where(~alive,'dead',stage)
    stage = np.where((alive)&(energy<reproduction_threshold),'growth',stage)
    stage = np.where((alive)&(energy>=reproduction_threshold),'reproduction',stage)
    stage = np.where(birth,'birth',stage)

    # --------------------------
    # Audio (polyphonic layering)
    # --------------------------
    global audio_buffer
    audio_buffer[:] = 0
    for l in np.unique(lineage):
        mask = (lineage==l)&alive
        if not np.any(mask): continue
        base = melody_base[mask].mean()
        mod = tone_mod[mask].mean()
        stage_mask = stage[mask]
        amp = np.where(stage_mask=='birth',0.2,
                       np.where(stage_mask=='growth',0.1+energy[mask]*0.2,0.2))
        freq = np.where(stage_mask=='growth',base+age[mask]*5,
                        np.where(stage_mask=='reproduction',base*1.5,base))
        for f,a in zip(freq,amp):
            audio_buffer += generate_tone(f*mod, a)
    max_val = np.max(np.abs(audio_buffer))
    if max_val>0:
        audio_buffer/=max_val

    # --------------------------
    # Visualization
    # --------------------------
    img = np.zeros((GRID_SIZE,GRID_SIZE,3))
    for x in range(GRID_SIZE):
        for y in range(GRID_SIZE):
            if alive[x,y]:
                hue=(lineage[x,y]%20)/20
                if stage[x,y]=='birth': img[x,y]=[1,0.5,0.2]
                elif stage[x,y]=='growth': img[x,y]=[hue,energy[x,y],0.2]
                elif stage[x,y]=='reproduction': img[x,y]=[1,1,0.2]
            else:
                img[x,y]=[0,0,0]
    im.set_data(img)
    return [im]

# --------------------------
# Real-time audio streaming
# --------------------------
def audio_callback(outdata, frames, time, status):
    outdata[:] = audio_buffer.reshape(-1,1)

stream = sd.OutputStream(channels=1, callback=audio_callback,
                         samplerate=SAMPLE_RATE, blocksize=frame_samples)
stream.start()

# --------------------------
# Visualization
# --------------------------
fig,ax=plt.subplots()
im=ax.imshow(np.zeros((GRID_SIZE,GRID_SIZE,3)),interpolation='none')

anim = FuncAnimation(fig, update, frames=STEPS, interval=1000/FPS, blit=True)
plt.show()

stream.stop()
