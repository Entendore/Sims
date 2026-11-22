import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation

# -----------------------------
# Simulation parameters
# -----------------------------
GRID_SIZE = 50
INITIAL_FISSIONS = 3
BASE_PROB_FISSION = 0.3
STEPS = 150
ENERGY_DECAY = 0.8
MAX_ENERGY = 10.0
NEUTRON_DELAY = 2

# -----------------------------
# Define isotopes and nuclear processes
# -----------------------------
# Format: 'name': {'half_life': steps, 'energy_yield': per fission, 'fusion_pair': 'other', 'fusion_energy': value}
isotopes = {
    'U235': {'half_life': 50, 'energy_yield': 2.0, 'fusion_pair': 'U238', 'fusion_energy': 3.0},
    'Pu239': {'half_life': 70, 'energy_yield': 3.0, 'fusion_pair': 'U235', 'fusion_energy': 4.0},
    'U238': {'half_life': 100, 'energy_yield': 1.0, 'fusion_pair': 'Pu239', 'fusion_energy': 5.0},
}

# Assign isotopes randomly
isotope_grid = np.random.choice(list(isotopes.keys()), size=(GRID_SIZE, GRID_SIZE))

# -----------------------------
# Cell states
# -----------------------------
EMPTY = 0
FISSILE = 1
FISSION = 2
NEUTRON = 3

grid = np.zeros((GRID_SIZE, GRID_SIZE), dtype=int)
energy = np.zeros((GRID_SIZE, GRID_SIZE), dtype=float)
neutrons = [[[] for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]

# Initialize fissile material
for i in range(GRID_SIZE):
    for j in range(GRID_SIZE):
        if np.random.rand() < 0.5:
            grid[i, j] = FISSILE
            energy[i, j] = isotopes[isotope_grid[i, j]]['energy_yield']

# Initial fissions
for _ in range(INITIAL_FISSIONS):
    x, y = np.random.randint(0, GRID_SIZE, size=2)
    grid[x, y] = FISSION
    energy[x, y] = isotopes[isotope_grid[x, y]]['energy_yield']

# -----------------------------
# Helper functions
# -----------------------------
def get_neighbors(x, y):
    neighbors = []
    for dx in [-1, 0, 1]:
        for dy in [-1, 0, 1]:
            if dx == 0 and dy == 0:
                continue
            nx = (x + dx) % GRID_SIZE
            ny = (y + dy) % GRID_SIZE
            neighbors.append((nx, ny))
    return neighbors

def update(grid, energy, neutrons):
    new_grid = grid.copy()
    new_energy = energy.copy()
    new_neutrons = [[n.copy() for n in row] for row in neutrons]
    
    # --- FISSION AND DECAY ---
    for x in range(GRID_SIZE):
        for y in range(GRID_SIZE):
            if grid[x, y] == FISSION:
                isotope = isotope_grid[x, y]
                new_grid[x, y] = EMPTY
                new_energy[x, y] = 0.0
                # Emit neutrons to neighbors with delay
                for nx, ny in get_neighbors(x, y):
                    new_neutrons[nx][ny].append(NEUTRON_DELAY)
            elif grid[x, y] == FISSILE:
                # Natural decay
                isotope = isotope_grid[x, y]
                decay_prob = 1 - 0.5 ** (1 / isotopes[isotope]['half_life'])
                if np.random.rand() < decay_prob:
                    new_grid[x, y] = EMPTY
                    new_energy[x, y] = 0.0

    # --- NEUTRON TRIGGERED FISSION ---
    for x in range(GRID_SIZE):
        for y in range(GRID_SIZE):
            new_neutrons[x][y] = [t-1 for t in new_neutrons[x][y] if t > 1]
            if any(t <= 1 for t in neutrons[x][y]) and grid[x, y] == FISSILE:
                isotope = isotope_grid[x, y]
                prob = min(1.0, BASE_PROB_FISSION * energy[x, y])
                if np.random.rand() < prob:
                    new_grid[x, y] = FISSION
                    new_energy[x, y] += isotopes[isotope]['energy_yield']
    
    # --- FUSION BETWEEN NEIGHBORS ---
    for x in range(GRID_SIZE):
        for y in range(GRID_SIZE):
            if grid[x, y] == FISSILE:
                isotope = isotope_grid[x, y]
                fusion_target = isotopes[isotope]['fusion_pair']
                for nx, ny in get_neighbors(x, y):
                    if grid[nx, ny] == FISSILE and isotope_grid[nx, ny] == fusion_target:
                        # Fusion occurs
                        new_energy[x, y] += isotopes[isotope]['fusion_energy']
                        new_energy[nx, ny] += isotopes[isotope]['fusion_energy']
                        # Both cells become empty after fusion
                        new_grid[x, y] = EMPTY
                        new_grid[nx, ny] = EMPTY
    
    return new_grid, new_energy, new_neutrons

# -----------------------------
# Visualization
# -----------------------------
fig, ax = plt.subplots()
im = ax.imshow(energy, cmap='hot', vmin=0, vmax=MAX_ENERGY)
ax.set_title("Nuclear Chains: Decay, Fission & Fusion")

def animate(i):
    global grid, energy, neutrons
    grid, energy, neutrons = update(grid, energy, neutrons)
    im.set_array(energy)
    return [im]

ani = animation.FuncAnimation(fig, animate, frames=STEPS, interval=150, blit=True)
plt.show()
