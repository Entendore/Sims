"""
Evolutionary Game of Life with food, mutation, lineage tracking, and visualization.

Run: python evo_game_of_life.py
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import random
from collections import deque

# ------------------------
# Configuration / Presets
# ------------------------
PRESETS = {
    "default": {
        "GRID_SIZE": 50,
        "INITIAL_CELLS": 50,
        "INITIAL_FOOD": 200,
        "FOOD_RESPAWN_RATE": 0.02,   # fraction of grid to attempt to spawn food each step
        "FOOD_SPREAD_RATE": 0.05,    # chance food spreads to orthogonal neighbor
        "BASE_LIFETIME": 8,
        "MAX_INIT_LIFETIME": 30,
        "BASE_BREED_PROB": 0.12,
        "MUTATION_RATE": 0.08,
        "FRAMES": 500,
        "INTERVAL": 200,
    },
    "high_food": {
        "GRID_SIZE": 50,
        "INITIAL_CELLS": 50,
        "INITIAL_FOOD": 800,
        "FOOD_RESPAWN_RATE": 0.05,
        "FOOD_SPREAD_RATE": 0.12,
        "BASE_LIFETIME": 10,
        "MAX_INIT_LIFETIME": 40,
        "BASE_BREED_PROB": 0.15,
        "MUTATION_RATE": 0.05,
        "FRAMES": 500,
        "INTERVAL": 150,
    },
    "fast_evolution": {
        "GRID_SIZE": 50,
        "INITIAL_CELLS": 30,
        "INITIAL_FOOD": 150,
        "FOOD_RESPAWN_RATE": 0.02,
        "FOOD_SPREAD_RATE": 0.05,
        "BASE_LIFETIME": 6,
        "MAX_INIT_LIFETIME": 20,
        "BASE_BREED_PROB": 0.18,
        "MUTATION_RATE": 0.25,
        "FRAMES": 600,
        "INTERVAL": 150,
    }
}

# Choose preset
CONFIG = PRESETS["default"]

# ------------------------
# Cell + Constants
# ------------------------
EMPTY = 0
FOOD = 1
CELL = 2

class CellObj:
    """Represents a single living cell; offspring inherit parent's lineage_id."""
    next_lineage_id = 0

    def __init__(self, lifetime, breed_prob, lineage_id=None):
        self.lifetime = int(lifetime)
        self.age = 0
        self.breed_prob = float(breed_prob)
        # lineage id: founders get unique lineage, offspring inherit parent lineage
        if lineage_id is None:
            self.lineage = CellObj.next_lineage_id
            CellObj.next_lineage_id += 1
        else:
            self.lineage = lineage_id
        self.fitness = 0  # accumulated score (e.g., food consumed / survival time)

    def mutate_inplace(self):
        """Mutate lifetime and breeding probability slightly."""
        mr = CONFIG["MUTATION_RATE"]
        # lifetime mutation: small integer change
        if random.random() < mr:
            self.lifetime = max(1, self.lifetime + int(np.random.randint(-2, 3)))
        if random.random() < mr:
            self.breed_prob = float(np.clip(self.breed_prob + np.random.normal(scale=0.03), 0.01, 1.0))

# ------------------------
# Grid / Initialization
# ------------------------
GRID_SIZE = CONFIG["GRID_SIZE"]
grid = np.zeros((GRID_SIZE, GRID_SIZE), dtype=np.int8)         # 0 empty, 1 food, 2 cell
cell_grid = np.full((GRID_SIZE, GRID_SIZE), None, dtype=object)

# place initial cells randomly
for _ in range(CONFIG["INITIAL_CELLS"]):
    x, y = np.random.randint(0, GRID_SIZE, 2)
    if grid[x, y] == EMPTY:
        grid[x, y] = CELL
        # random initial lifetime around BASE_LIFETIME..MAX_INIT_LIFETIME
        lifetime = np.random.randint(CONFIG["BASE_LIFETIME"], CONFIG["MAX_INIT_LIFETIME"] + 1)
        breed = CONFIG["BASE_BREED_PROB"] + np.random.uniform(-0.05, 0.05)
        cell_grid[x, y] = CellObj(lifetime=lifetime, breed_prob=breed)

# place initial food randomly
placed = 0
attempts = 0
while placed < CONFIG["INITIAL_FOOD"] and attempts < CONFIG["INITIAL_FOOD"] * 10:
    x, y = np.random.randint(0, GRID_SIZE, 2)
    if grid[x, y] == EMPTY:
        grid[x, y] = FOOD
        placed += 1
    attempts += 1

# ------------------------
# Evolution tracking structures
# ------------------------
population_history = deque(maxlen=1000)
avg_lifetime_history = deque(maxlen=1000)
avg_fitness_history = deque(maxlen=1000)
lineage_history = []   # list of dicts (lineage_id -> proportion) per step

lineage_birth = {}     # lineage_id -> birth_step
lineage_death = {}     # lineage_id -> death_step
extinct_lineages = {}  # lineage_id -> lifetime (death-birth)
current_step = 0

cmap = plt.cm.get_cmap("tab20")

# ------------------------
# Simulation functions
# ------------------------
def neighbors_orthogonal(x, y):
    """Return orthogonal neighbor coordinates (wrap-around)."""
    return [((x-1) % GRID_SIZE, y), ((x+1) % GRID_SIZE, y), (x, (y-1) % GRID_SIZE), (x, (y+1) % GRID_SIZE)]

def step_simulation():
    """Advance the grid by one tick: food spread/spawn, cell aging, breeding, death."""
    global grid, cell_grid, lineage_history

    new_grid = grid.copy()
    new_cell_grid = cell_grid.copy()

    # 1) Food spreads to orthogonal neighbors with some probability
    food_positions = np.argwhere(grid == FOOD)
    for (x, y) in food_positions:
        for nx, ny in neighbors_orthogonal(x, y):
            if new_grid[nx, ny] == EMPTY and random.random() < CONFIG["FOOD_SPREAD_RATE"]:
                new_grid[nx, ny] = FOOD

    # 2) Spawn some random new food tiles each step (approx)
    spawn_attempts = int(GRID_SIZE * GRID_SIZE * CONFIG["FOOD_RESPAWN_RATE"])
    for _ in range(spawn_attempts):
        x, y = np.random.randint(0, GRID_SIZE, 2)
        if new_grid[x, y] == EMPTY:
            new_grid[x, y] = FOOD

    # 3) Update cells: age, consume food (if same tile has food), reproduce to empty orthogonal neighbors
    for x in range(GRID_SIZE):
        for y in range(GRID_SIZE):
            if grid[x, y] == CELL and cell_grid[x, y] is not None:
                cell = cell_grid[x, y]
                cell.age += 1

                # if there is food on this tile in the *new_grid* (food could have persisted)
                # Note: We allow consuming food that remained in place (new_grid)
                if new_grid[x, y] == FOOD:
                    cell.fitness += 1
                    cell.lifetime += 1  # benefit: eating adds lifetime
                    new_grid[x, y] = CELL  # consume food -> tile now cell

                # death by age/lifetime
                if cell.age >= cell.lifetime:
                    new_grid[x, y] = EMPTY
                    new_cell_grid[x, y] = None
                    continue

                # survival check and reproduction: attempt to breed to orthogonal empty tiles
                for nx, ny in neighbors_orthogonal(x, y):
                    if new_grid[nx, ny] == EMPTY and random.random() < cell.breed_prob:
                        # offspring inherits parent's lineage
                        offspring = CellObj(lifetime=cell.lifetime, breed_prob=cell.breed_prob, lineage_id=cell.lineage)
                        # small mutation
                        offspring.mutate_inplace()
                        new_grid[nx, ny] = CELL
                        new_cell_grid[nx, ny] = offspring

    # Commit
    grid[:, :] = new_grid
    cell_grid[:, :] = new_cell_grid

    # Update lineage frequency snapshot this step
    lineage_counts = {}
    total_cells = np.sum(grid == CELL)
    for x in range(GRID_SIZE):
        for y in range(GRID_SIZE):
            c = cell_grid[x, y]
            if c is not None:
                lineage_counts[c.lineage] = lineage_counts.get(c.lineage, 0) + 1

    if total_cells > 0:
        lineage_freq = {lid: cnt / total_cells for lid, cnt in lineage_counts.items()}
    else:
        lineage_freq = {}
    lineage_history.append(lineage_freq)

def register_lineages():
    """Record birth times and death times for lineages (persistence)."""
    global lineage_birth, lineage_death, extinct_lineages, current_step
    active_lineages = {cell_grid[x, y].lineage for x in range(GRID_SIZE) for y in range(GRID_SIZE) if cell_grid[x, y] is not None}

    # record births
    for lid in active_lineages:
        if lid not in lineage_birth:
            lineage_birth[lid] = current_step

    # record deaths for previously-known lineages now absent
    for lid in list(lineage_birth.keys()):
        if lid not in active_lineages and lid not in lineage_death:
            lineage_death[lid] = current_step
            extinct_lineages[lid] = lineage_death[lid] - lineage_birth[lid]

# ------------------------
# Visualization helpers
# ------------------------
def get_color_grid():
    """Return an RGB image for the grid: empty black, food green, cells colored by lineage (age reduces brightness)."""
    image = np.zeros((GRID_SIZE, GRID_SIZE, 3), dtype=float)

    # count lineage sizes to detect top lineage for highlighting
    counts = {}
    for x in range(GRID_SIZE):
        for y in range(GRID_SIZE):
            c = cell_grid[x, y]
            if c is not None:
                counts[c.lineage] = counts.get(c.lineage, 0) + 1
    top_lineage = max(counts, key=counts.get) if counts else None

    for x in range(GRID_SIZE):
        for y in range(GRID_SIZE):
            if grid[x, y] == FOOD:
                image[x, y] = np.array([0.05, 0.8, 0.05])  # green
            elif grid[x, y] == CELL and cell_grid[x, y] is not None:
                cell = cell_grid[x, y]
                # base lineage color from colormap
                base_col = np.array(cmap(cell.lineage % cmap.N)[:3])
                age_factor = min(1.0, cell.age / max(1, cell.lifetime))
                # dim older cells a bit
                color = base_col * (1.0 - 0.5 * age_factor)
                # if top lineage, brighten to white-ish highlight
                if top_lineage is not None and cell.lineage == top_lineage:
                    color = color * 0.6 + np.array([0.4, 0.4, 0.4])
                image[x, y] = np.clip(color, 0.0, 1.0)
            else:
                image[x, y] = np.array([0.0, 0.0, 0.0])  # empty -> black
    return image

def get_population_density():
    """Return density grid (0 or 1 per cell; could be extended to counters)."""
    density = np.zeros((GRID_SIZE, GRID_SIZE), dtype=float)
    for x in range(GRID_SIZE):
        for y in range(GRID_SIZE):
            if cell_grid[x, y] is not None:
                density[x, y] = 1.0
    return density

# ------------------------
# Main / Animation
# ------------------------
def main():
    global current_step
    current_step = 0

    fig, axes = plt.subplots(1, 5, figsize=(24, 5))
    ax_grid, ax_stats, ax_lineages, ax_persistence, ax_heatmap = axes

    # grid image
    im_grid = ax_grid.imshow(get_color_grid(), interpolation="nearest")
    ax_grid.set_title("Grid (lineages highlighted)")
    ax_grid.axis("off")
    pop_text = ax_grid.text(0.02, 0.96, "", transform=ax_grid.transAxes, color="white",
                            fontsize=12, bbox=dict(facecolor="black", alpha=0.6))

    # stats plot
    line_pop, = ax_stats.plot([], [], label="Population", color="tab:blue")
    line_life, = ax_stats.plot([], [], label="Avg Lifetime", color="tab:green")
    line_fit, = ax_stats.plot([], [], label="Avg Fitness", color="tab:red")
    ax_stats.set_xlim(0, CONFIG["FRAMES"])
    ax_stats.set_ylim(0, max(10, CONFIG["MAX_INIT_LIFETIME"]))
    ax_stats.set_title("Population Stats")
    ax_stats.legend(loc="upper left")
    ax_stats.grid(False)

    # lineage dominance (stackplot)
    ax_lineages.set_title("Lineage Dominance Over Time")
    ax_lineages.set_ylim(0, 1)
    ax_lineages.set_xlim(0, CONFIG["FRAMES"])

    # persistence bar chart
    ax_persistence.set_title("Lineage Persistence (Extinct)")
    ax_persistence.set_xlabel("Lineage ID")
    ax_persistence.set_ylabel("Lifetime (steps)")

    # heatmap
    heat = ax_heatmap.imshow(get_population_density(), cmap="hot", interpolation="nearest", vmin=0, vmax=1)
    ax_heatmap.set_title("Population Density")
    ax_heatmap.axis("off")
    fig.tight_layout()

    def update(frame):
        nonlocal im_grid, heat
        global current_step
        current_step += 1

        # advance sim one step
        step_simulation()
        register_lineages()

        # Update grid image and overlays
        im_grid.set_data(get_color_grid())
        population = int(np.sum(grid == CELL))
        pop_text.set_text(f"Population: {population}")

        # Update stats time series
        lifetimes = [cell_grid[x, y].lifetime for x in range(GRID_SIZE) for y in range(GRID_SIZE) if cell_grid[x, y] is not None]
        fitnesses = [cell_grid[x, y].fitness for x in range(GRID_SIZE) for y in range(GRID_SIZE) if cell_grid[x, y] is not None]

        population_history.append(population)
        avg_lifetime_history.append(float(np.mean(lifetimes)) if lifetimes else 0.0)
        avg_fitness_history.append(float(np.mean(fitnesses)) if fitnesses else 0.0)

        # redraw stat lines
        xs = range(len(population_history))
        line_pop.set_data(xs, population_history)
        line_life.set_data(xs, avg_lifetime_history)
        line_fit.set_data(xs, avg_fitness_history)
        ax_stats.set_xlim(0, max(50, len(population_history)))

        # lineage dominance stacked area (rebuild)
        ax_lineages.clear()
        ax_lineages.set_title("Lineage Dominance Over Time")
        if lineage_history:
            all_ids = sorted({lid for frame in lineage_history for lid in frame.keys()})
            if all_ids:
                data = np.array([[frame.get(lid, 0.0) for lid in all_ids] for frame in lineage_history])
                # choose colors for lineages
                colors = [cmap(lid % cmap.N) for lid in all_ids]
                ax_lineages.stackplot(range(len(lineage_history)), data.T, colors=colors)
                ax_lineages.set_ylim(0, 1)
                ax_lineages.set_xlim(0, max(50, len(lineage_history)))

        # persistence bar chart for extinct lineages
        ax_persistence.clear()
        ax_persistence.set_title("Lineage Persistence (Extinct)")
        if extinct_lineages:
            lids = list(extinct_lineages.keys())
            lifespans = [extinct_lineages[lid] for lid in lids]
            ax_persistence.bar(range(len(lids)), lifespans, color=[cmap(lid % cmap.N) for lid in lids])
            ax_persistence.set_xticks(range(len(lids)))
            ax_persistence.set_xticklabels([str(lid) for lid in lids], rotation=90, fontsize=6)
            ax_persistence.set_ylabel("Lifetime (steps)")

        # heatmap update
        heat.set_data(get_population_density())
        heat.set_clim(0, 1)  # density range

        # return artists that changed (blit=False still fine)
        return [im_grid, line_pop, line_life, line_fit, heat, pop_text]

    ani = animation.FuncAnimation(fig, update, frames=CONFIG["FRAMES"], interval=CONFIG["INTERVAL"], blit=False)
    plt.show()


if __name__ == "__main__":
    main()
