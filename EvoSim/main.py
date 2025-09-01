import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import sounddevice as sd

# --------------------------
# Parameters
# --------------------------
GRID_SIZE = 50
STEPS = 400
INITIAL_LIFE = 0.2
FPS = 15
SAMPLE_RATE = 44100
DURATION = 0.1
MUTATION_RATE = 0.05

lineage_counter = 0

# --------------------------
# Cell class with lineage
# --------------------------
class Cell:
    def __init__(self, parent=None):
        global lineage_counter
        if parent is None:
            self.alive = np.random.rand() < INITIAL_LIFE
            self.age = 0
            self.energy = np.random.rand()
            self.stage = "birth" if self.alive else "dead"
            self.energy_gain_rate = np.random.uniform(0.01, 0.1)
            self.reproduction_threshold = np.random.uniform(0.5, 1.0)
            self.tone_mod = np.random.uniform(0.5, 2.0)
            self.lineage = lineage_counter
            self.melody_base = np.random.uniform(220, 440)
            lineage_counter += 1
        else:
            self.alive = True
            self.age = 0
            self.energy = parent.energy * 0.5
            self.stage = "birth"
            self.energy_gain_rate = parent.energy_gain_rate * (1 + np.random.randn()*MUTATION_RATE)
            self.reproduction_threshold = parent.reproduction_threshold * (1 + np.random.randn()*MUTATION_RATE)
            self.tone_mod = parent.tone_mod * (1 + np.random.randn()*MUTATION_RATE)
            self.lineage = parent.lineage
            self.melody_base = parent.melody_base * (1 + np.random.randn()*0.01)

    def update(self, neighbors):
        alive_neighbors = sum(n.alive for n in neighbors)
        prev_alive = self.alive
        if self.alive:
            self.alive = alive_neighbors in [2,3]
        else:
            self.alive = alive_neighbors == 3

        if self.alive and not prev_alive:
            self.stage = "birth"
            self.age = 0
            self.energy = 0.1
        elif self.alive and prev_alive:
            self.stage = "growth" if self.energy < self.reproduction_threshold else "reproduction"
            self.age += 1
            self.energy = min(1.0, self.energy + self.energy_gain_rate)
        elif not self.alive and prev_alive:
            self.stage = "death"
            self.age = 0
            self.energy = 0
        elif not self.alive:
            self.stage = "dead"

    def reproduce(self):
        if self.stage == "reproduction" and self.energy >= self.reproduction_threshold:
            self.energy /= 2
            return Cell(parent=self)
        return None

# --------------------------
# Initialize grid
# --------------------------
grid = np.array([[Cell() for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)])

def get_neighbors(x, y):
    neighbors = []
    for dx in [-1,0,1]:
        for dy in [-1,0,1]:
            if dx==0 and dy==0: continue
            nx, ny = (x+dx)%GRID_SIZE, (y+dy)%GRID_SIZE
            neighbors.append(grid[nx][ny])
    return neighbors

def update_grid():
    new_grid = np.empty((GRID_SIZE,GRID_SIZE),dtype=object)
    for x in range(GRID_SIZE):
        for y in range(GRID_SIZE):
            cell = grid[x][y]
            neighbors = get_neighbors(x,y)
            new_cell = Cell(parent=None)
            new_cell.alive = cell.alive
            new_cell.age = cell.age
            new_cell.energy = cell.energy
            new_cell.stage = cell.stage
            new_cell.energy_gain_rate = cell.energy_gain_rate
            new_cell.reproduction_threshold = cell.reproduction_threshold
            new_cell.tone_mod = cell.tone_mod
            new_cell.lineage = cell.lineage
            new_cell.melody_base = cell.melody_base
            new_cell.update(neighbors)

            offspring = new_cell.reproduce()
            if offspring:
                empty_neighbors = [(nx,ny) for nx in range(GRID_SIZE) for ny in range(GRID_SIZE) if not grid[nx][ny].alive]
                if empty_neighbors:
                    ox, oy = empty_neighbors[np.random.randint(len(empty_neighbors))]
                    new_grid[ox,oy] = offspring

            new_grid[x,y] = new_cell
    return new_grid

# --------------------------
# Polyphonic audio synthesis
# --------------------------
def generate_tone(freq, duration=DURATION, amplitude=0.2):
    t = np.linspace(0, duration, int(SAMPLE_RATE*duration), False)
    return amplitude * np.sin(2*np.pi*freq*t)

def grid_to_audio(grid):
    # Collect tones by lineage
    lineage_dict = {}
    for row in grid:
        for cell in row:
            if cell.alive:
                if cell.lineage not in lineage_dict:
                    lineage_dict[cell.lineage] = []
                # Determine frequency and amplitude
                base = cell.melody_base
                if cell.stage=="birth":
                    freq = base
                    amp = 0.2
                elif cell.stage=="growth":
                    freq = base + cell.age*5
                    amp = 0.1 + cell.energy*0.2
                elif cell.stage=="reproduction":
                    freq = base*1.5
                    amp = 0.2
                else:
                    continue
                lineage_dict[cell.lineage].append(generate_tone(freq*cell.tone_mod, DURATION, amp))

    # Mix tones per lineage (polyphonic layering)
    layered_audio = np.zeros(int(SAMPLE_RATE*DURATION))
    for tones in lineage_dict.values():
        if tones:
            layered_audio += np.mean(tones, axis=0)
    # Normalize
    if np.max(np.abs(layered_audio))>0:
        layered_audio /= np.max(np.abs(layered_audio))
    return layered_audio

# --------------------------
# Visualization
# --------------------------
fig, ax = plt.subplots()
im = ax.imshow(np.zeros((GRID_SIZE,GRID_SIZE,3)), interpolation='none')

def step(frame):
    global grid
    grid = update_grid()

    # Visual mapping
    image = np.zeros((GRID_SIZE,GRID_SIZE,3))
    for x in range(GRID_SIZE):
        for y in range(GRID_SIZE):
            cell = grid[x][y]
            if cell.alive:
                hue = (cell.lineage % 20)/20
                if cell.stage=="birth": color=[1.0,0.5,0.2]
                elif cell.stage=="growth": color=[hue,cell.energy,0.2]
                elif cell.stage=="reproduction": color=[1.0,1.0,0.2]
                image[x,y,:]=color
            else:
                image[x,y,:]=[0,0,0]

    im.set_data(image)
    
    # Play polyphonic audio
    audio_frame = grid_to_audio(grid)
    sd.play(audio_frame, SAMPLE_RATE)
    return [im]

anim = FuncAnimation(fig, step, frames=STEPS, interval=1000/FPS, blit=True)
plt.show()
