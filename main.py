import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import random
from collections import deque

# ------------------------
# Configuration
# ------------------------
CONFIG = {
    "GRID_SIZE": 50,
    "INIT_CELL_DENSITY": 0.1,      # fraction of cells at start
    "MAX_INIT_LIFETIME": 30,
    "FOOD_RESPAWN_RATE": 0.02,     # chance of random food
    "FOOD_SPREAD_RATE": 0.05,      # chance food spreads to neighbor
    "MUTATION_RATE": 0.1,
    "FRAMES": 500,
    "INTERVAL": 200
}

FOOD = 1
CELL = 2
EMPTY = 0

# ------------------------
# Cell Class
# ------------------------
class Cell:
    next_id = 0
    def __init__(self, lifetime, breeding_prob, lineage_id=None):
        self.lifetime = lifetime
        self.age = 0
        self.breeding_prob = breeding_prob
        self.id = lineage_id if lineage_id is not None else Cell.next_id
        self.fitness = 0
        if lineage_id is None:
            Cell.next_id += 1

    def mutate(self):
        if random.random() < CONFIG["MUTATION_RATE"]:
            self.lifetime = max(5, int(self.lifetime + np.random.randint(-2, 3)))
        if random.random() < CONFIG["MUTATION_RATE"]:
            self.breeding_prob = min(1.0, max(0.01, self.breeding_prob + np.random.uniform(-0.05, 0.05)))

# ------------------------
# Initialization
# ------------------------
GRID_SIZE = CONFIG["GRID_SIZE"]
grid = np.zeros((GRID_SIZE, GRID_SIZE), dtype=int)
cell_grid = np.empty((GRID_SIZE, GRID_SIZE), dtype=object)

for _ in range(int(GRID_SIZE * GRID_SIZE * CONFIG["INIT_CELL_DENSITY"])):
    x, y = np.random.randint(0, GRID_SIZE, 2)
    grid[x, y] = CELL
    cell_grid[x, y] = Cell(lifetime=np.random.randint(5, CONFIG["MAX_INIT_LIFETIME"]),
                           breeding_prob=np.random.uniform(0.1, 0.5))

# ------------------------
# Evolution Tracking
# ------------------------
population_history = deque(maxlen=500)
avg_lifetime_history = deque(maxlen=500)
avg_fitness_history = deque(maxlen=500)
lineage_history = []
cmap = plt.cm.tab20
lineage_birth = {}
lineage_death = {}
extinct_lineages = {}
current_step = 0

# ------------------------
# Simulation Functions
# ------------------------
def step():
    global grid, cell_grid, current_step
    new_grid = np.copy(grid)
    new_cell_grid = np.copy(cell_grid)

    # Spread food
    food_positions = np.argwhere(grid == FOOD)
    for (x, y) in food_positions:
        for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
            nx, ny = (x+dx) % GRID_SIZE, (y+dy) % GRID_SIZE
            if new_grid[nx, ny] == EMPTY and random.random() < CONFIG["FOOD_SPREAD_RATE"]:
                new_grid[nx, ny] = FOOD

    # Random new food
    for _ in range(int(GRID_SIZE * GRID_SIZE * CONFIG["FOOD_RESPAWN_RATE"])):
        x, y = np.random.randint(0, GRID_SIZE, 2)
        if new_grid[x, y] == EMPTY:
            new_grid[x, y] = FOOD

    # Update cells
    for x in range(GRID_SIZE):
        for y in range(GRID_SIZE):
            if grid[x,y] == CELL and cell_grid[x,y] is not None:
                cell = cell_grid[x,y]
                cell.age += 1
                if new_grid[x,y] == FOOD:
                    cell.fitness += 1
                    cell.lifetime += 1
                    new_grid[x,y] = CELL
                if cell.age >= cell.lifetime:
                    new_grid[x,y] = EMPTY
                    new_cell_grid[x,y] = None
                    continue
                for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                    nx, ny = (x+dx) % GRID_SIZE, (y+dy) % GRID_SIZE
                    if new_grid[nx, ny] == EMPTY and random.random() < cell.breeding_prob:
                        offspring = Cell(cell.lifetime, cell.breeding_prob, lineage_id=cell.id)
                        offspring.mutate()
                        new_grid[nx, ny] = CELL
                        new_cell_grid[nx, ny] = offspring

    grid[:] = new_grid
    cell_grid[:] = new_cell_grid

    # Lineage dominance
    lineage_counts = {}
    total_cells = np.sum(grid==CELL)
    for x in range(GRID_SIZE):
        for y in range(GRID_SIZE):
            if cell_grid[x,y] is not None:
                lineage_counts[cell_grid[x,y].id] = lineage_counts.get(cell_grid[x,y].id, 0) + 1
    lineage_freq = {k: v/total_cells for k,v in lineage_counts.items()} if total_cells > 0 else {}
    lineage_history.append(lineage_freq)

def get_color_grid():
    color_grid = np.zeros((GRID_SIZE, GRID_SIZE, 3))
    for x in range(GRID_SIZE):
        for y in range(GRID_SIZE):
            if grid[x,y] == FOOD:
                color_grid[x,y] = [0.2, 1.0, 0.2]
            elif grid[x,y] == CELL and cell_grid[x,y] is not None:
                cell = cell_grid[x,y]
                base = np.array(cmap(cell.id % cmap.N)[:3])
                age_factor = min(1.0, cell.age / cell.lifetime)
                color_grid[x,y] = base * (1 - 0.5*age_factor)
    return color_grid

def register_lineages():
    global lineage_birth, lineage_death, extinct_lineages, current_step
    active_lineages = {cell_grid[x,y].id for x in range(GRID_SIZE) for y in range(GRID_SIZE) if cell_grid[x,y] is not None}
    for lid in active_lineages:
        if lid not in lineage_birth:
            lineage_birth[lid] = current_step
    for lid in list(lineage_birth.keys()):
        if lid not in active_lineages and lid not in lineage_death:
            lineage_death[lid] = current_step
            extinct_lineages[lid] = lineage_death[lid] - lineage_birth[lid]

# ------------------------
# Main Function
# ------------------------
def main():
    global current_step
    fig, (ax_grid, ax_plot, ax_lineages, ax_persistence) = plt.subplots(1, 4, figsize=(22,6))

    im = ax_grid.imshow(get_color_grid(), interpolation='nearest')
    pop_text = ax_grid.text(0.02, 0.95, '', transform=ax_grid.transAxes, color='white', fontsize=12,
                            bbox=dict(facecolor='black', alpha=0.6))
    ax_grid.set_title('Cellular Grid')

    line_pop, = ax_plot.plot([], [], color='blue', label='Population')
    line_life, = ax_plot.plot([], [], color='green', label='Avg Lifetime')
    line_fit, = ax_plot.plot([], [], color='red', label='Avg Fitness')
    ax_plot.set_xlim(0,CONFIG["FRAMES"])
    ax_plot.set_ylim(0,100)
    ax_plot.set_title('Population Stats')
    ax_plot.legend()

    def update(frame):
        nonlocal im, pop_text
        global current_step
        current_step += 1
        step()
        im.set_data(get_color_grid())
        register_lineages()

        population = np.sum(grid==CELL)
        pop_text.set_text(f"Population: {population}")

        lifetimes = [cell_grid[x,y].lifetime for x in range(GRID_SIZE) for y in range(GRID_SIZE) if cell_grid[x,y] is not None]
        fitnesses = [cell_grid[x,y].fitness for x in range(GRID_SIZE) for y in range(GRID_SIZE) if cell_grid[x,y] is not None]

        population_history.append(population)
        avg_lifetime_history.append(np.mean(lifetimes) if lifetimes else 0)
        avg_fitness_history.append(np.mean(fitnesses) if fitnesses else 0)

        line_pop.set_data(range(len(population_history)), population_history)
        line_life.set_data(range(len(avg_lifetime_history)), avg_lifetime_history)
        line_fit.set_data(range(len(avg_fitness_history)), avg_fitness_history)
        ax_plot.set_xlim(0, max(50, len(population_history)))

        ax_lineages.clear()
        if lineage_history:
            all_ids = sorted({cid for frame in lineage_history for cid in frame.keys()})
            data = np.array([[frame.get(cid, 0) for cid in all_ids] for frame in lineage_history])
            if data.shape[0] > 0:
                ax_lineages.stackplot(range(len(lineage_history)), data.T, colors=[cmap(cid % cmap.N) for cid in all_ids])
                ax_lineages.set_title("Lineage Dominance Over Time")
                ax_lineages.set_ylim(0,1)

        ax_persistence.clear()
        if extinct_lineages:
            lids = list(extinct_lineages.keys())
            lifespans = list(extinct_lineages.values())
            ax_persistence.bar(range(len(lids)), lifespans, color=[cmap(lid % cmap.N) for lid in lids])
            ax_persistence.set_title("Lineage Persistence (Extinct)")
            ax_persistence.set_xlabel("Lineages")
            ax_persistence.set_ylabel("Lifetime (steps)")

        return [im, line_pop, line_life, line_fit, pop_text]

    ani = animation.FuncAnimation(fig, update, frames=CONFIG["FRAMES"], interval=CONFIG["INTERVAL"], blit=False)
    plt.show()

# ------------------------
# Run
# ------------------------
if __name__ == "__main__":
    main()
