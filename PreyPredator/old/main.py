import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import random
from collections import defaultdict

# -----------------------
# CONFIGURATION
# -----------------------
GRID_SIZE = 50
NUM_PREY = 100
NUM_PREDATORS = 30
PREY_REPRODUCE = 3
PREDATOR_STARVE = 5
MUTATION_RATE = 0.1
STEPS = 200

# -----------------------
# CELL TYPES
# -----------------------
EMPTY = 0
PREY = 1
PREDATOR = 2

# -----------------------
# ENTITY CLASSES
# -----------------------
class Creature:
    def __init__(self, type_, speed=1, reproduce_time=PREY_REPRODUCE, lineage_id=0):
        self.type = type_
        self.speed = speed
        self.reproduce_time = reproduce_time
        self.age = 0
        self.starve_time = 0
        self.lineage_id = lineage_id

    def mutate(self):
        if random.random() < MUTATION_RATE:
            self.speed = max(1, self.speed + random.choice([-1, 0, 1]))
        if random.random() < MUTATION_RATE:
            self.reproduce_time = max(1, self.reproduce_time + random.choice([-1, 0, 1]))

# -----------------------
# INITIALIZATION
# -----------------------
grid = np.zeros((GRID_SIZE, GRID_SIZE), dtype=object)
lineage_counter = 1
lineage_history = defaultdict(list)
lineage_colors = {}
prey_speeds = defaultdict(list)

def random_color():
    return np.random.rand(3,)

# Place prey
for _ in range(NUM_PREY):
    while True:
        x, y = np.random.randint(GRID_SIZE), np.random.randint(GRID_SIZE)
        if grid[x, y] is None or grid[x, y] == 0:
            grid[x, y] = Creature(PREY, lineage_id=lineage_counter)
            lineage_colors[lineage_counter] = random_color()
            lineage_counter += 1
            break

# Place predators
for _ in range(NUM_PREDATORS):
    while True:
        x, y = np.random.randint(GRID_SIZE), np.random.randint(GRID_SIZE)
        if grid[x, y] is None or grid[x, y] == 0:
            grid[x, y] = Creature(PREDATOR, lineage_id=lineage_counter)
            lineage_colors[lineage_counter] = random_color()
            lineage_counter += 1
            break

# -----------------------
# HELPERS
# -----------------------
def get_neighbors(x, y):
    neighbors = []
    for dx in [-1, 0, 1]:
        for dy in [-1, 0, 1]:
            if dx == 0 and dy == 0:
                continue
            nx, ny = (x + dx) % GRID_SIZE, (y + dy) % GRID_SIZE
            neighbors.append((nx, ny))
    return neighbors

def step():
    global lineage_counter
    new_grid = np.copy(grid)
    positions = [(x, y) for x in range(GRID_SIZE) for y in range(GRID_SIZE)]
    random.shuffle(positions)
    
    for x, y in positions:
        creature = grid[x, y]
        if creature is None or creature == 0:
            continue
        
        creature.age += 1
        if creature.type == PREY:
            creature.reproduce_time -= 1
        elif creature.type == PREDATOR:
            creature.starve_time += 1
        
        neighbors = get_neighbors(x, y)
        random.shuffle(neighbors)
        
        if creature.type == PREY:
            # Move to empty
            for nx, ny in neighbors:
                if grid[nx, ny] is None or grid[nx, ny] == 0:
                    new_grid[nx, ny] = creature
                    new_grid[x, y] = 0
                    x, y = nx, ny
                    break
            # Reproduce
            if creature.reproduce_time <= 0:
                for nx, ny in neighbors:
                    if new_grid[nx, ny] is None or new_grid[nx, ny] == 0:
                        offspring = Creature(PREY, creature.speed, PREY_REPRODUCE, lineage_counter)
                        offspring.mutate()
                        new_grid[nx, ny] = offspring
                        lineage_colors[lineage_counter] = random_color()
                        lineage_counter += 1
                        creature.reproduce_time = PREY_REPRODUCE
                        break
                        
        elif creature.type == PREDATOR:
            ate = False
            for nx, ny in neighbors:
                target = grid[nx, ny]
                if target is not None and target != 0 and target.type == PREY:
                    new_grid[nx, ny] = creature
                    new_grid[x, y] = 0
                    creature.starve_time = 0
                    ate = True
                    break
            if not ate:
                for nx, ny in neighbors:
                    if grid[nx, ny] is None or grid[nx, ny] == 0:
                        new_grid[nx, ny] = creature
                        new_grid[x, y] = 0
                        break
            if creature.starve_time > PREDATOR_STARVE:
                new_grid[x, y] = 0
                
    return new_grid

# -----------------------
# RECORD DATA FOR LIVE PLOTS
# -----------------------
def record_data(step_num):
    counts = defaultdict(int)
    for x in range(GRID_SIZE):
        for y in range(GRID_SIZE):
            cell = grid[x, y]
            if cell is not None and cell != 0:
                counts[cell.lineage_id] += 1
                if cell.type == PREY:
                    prey_speeds[cell.lineage_id].append(cell.speed)
    for lineage_id, count in counts.items():
        lineage_history[lineage_id].append((step_num, count))

# -----------------------
# LIVE VISUALIZATION
# -----------------------
fig, axs = plt.subplots(1, 2, figsize=(12,6))

def draw_grid():
    img = np.ones((GRID_SIZE, GRID_SIZE, 3))
    for x in range(GRID_SIZE):
        for y in range(GRID_SIZE):
            cell = grid[x, y]
            if cell is not None and cell != 0:
                img[x, y] = lineage_colors[cell.lineage_id]
    axs[0].clear()
    axs[0].imshow(img)
    axs[0].set_title("Predator-Prey Grid with Lineages")
    axs[0].set_xticks([])
    axs[0].set_yticks([])

def draw_traits(step_num):
    axs[1].clear()
    for lineage_id, speeds in prey_speeds.items():
        if speeds:
            axs[1].hist(speeds, bins=range(1, max(speeds)+2), alpha=0.5, color=lineage_colors[lineage_id])
    axs[1].set_title(f"Prey Speed Distribution at Step {step_num}")
    axs[1].set_xlabel("Speed")
    axs[1].set_ylabel("Frequency")

def update(frame):
    global grid
    grid = step()
    record_data(frame)
    draw_grid()
    draw_traits(frame)

ani = animation.FuncAnimation(fig, update, frames=STEPS, repeat=False, interval=200)
plt.show()
