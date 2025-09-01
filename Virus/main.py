"""
virus_mutation_sim.py

Run:
    python virus_mutation_sim.py

Dependencies:
    numpy, matplotlib

What it does:
    Simulates spreading viruses on a 2D grid. Each infected cell carries a strain id.
    During transmission there's a chance of mutation which creates a new strain
    (with slightly altered transmissibility). Visualized with matplotlib animation.
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib import colors
from matplotlib.animation import FuncAnimation
from matplotlib.widgets import Slider, Button
import random
import math

# -----------------------
# CONFIG
# -----------------------
GRID_SIZE = 120          # width/height of square grid
INIT_INFECTED = 6        # number of initially infected cells
INITIAL_STRAINS = 2      # how many distinct strains to seed
RECOVERY_TIME = 25       # steps until an infected cell recovers (and is immune)
BASE_DIFFUSION = 0.6     # weight of neighbor exposure vs self
SEED = 42                # random seed for reproducibility (None for random)
MAX_STRAINS = 2000       # safety cap on strain count to avoid runaway memory

# Visual & UI
FPS = 20
INTERVAL_MS = 1000 // FPS

# -----------------------
# STATE DATA STRUCTURES
# -----------------------
if SEED is not None:
    np.random.seed(SEED)
    random.seed(SEED)

# cell states:
# 0 = susceptible, >0 = infected with strain id (index into strains list), -1 = recovered/immune
state = np.zeros((GRID_SIZE, GRID_SIZE), dtype=int)
time_infected = np.zeros_like(state, dtype=int)  # how many steps a cell has been infected

# strain registry: list of dicts: {id, transmissibility, color_rgb, mutation_rate}
strains = []

# colormap for strains (we will build dynamic ListedColormap)
def strain_color_palette(n):
    """Generate n visually distinct colors (HSV spaced)."""
    hsv = np.zeros((n, 3))
    for i in range(n):
        hsv[i, 0] = (i / max(1, n))  # hue
        hsv[i, 1] = 0.8
        hsv[i, 2] = 0.95
    # convert to rgb
    import colorsys
    rgb = [colorsys.hsv_to_rgb(*hsv[i]) for i in range(n)]
    return rgb

def add_strain(transmissibility=0.25, mutation_rate=0.01):
    """Create new strain, return strain_id (1-based)."""
    new_id = len(strains) + 1
    strains.append({
        "id": new_id,
        "transmissibility": transmissibility,
        "mutation_rate": mutation_rate
    })
    return new_id

# Initialize base strains
for i in range(INITIAL_STRAINS):
    t = 0.15 + 0.15 * np.random.rand()  # transmissibility in [0.15, 0.30]
    m = 0.002 + 0.02 * np.random.rand() # mutation rate small
    add_strain(transmissibility=t, mutation_rate=m)

# place initial infected cells with random strains
coords = list(np.ndindex(GRID_SIZE, GRID_SIZE))
random.shuffle(coords)
for k in range(INIT_INFECTED):
    r, c = coords[k]
    strain_choice = random.randint(1, len(strains))
    state[r, c] = strain_choice
    time_infected[r, c] = 0

# recovered cells are -1 (immune)
# -----------------------
# HELPERS
# -----------------------
def neighbors8(r, c, grid_shape):
    R, C = grid_shape
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            rr = (r + dr) % R
            cc = (c + dc) % C
            yield rr, cc

def step_sim(global_transmissibility=1.0, global_mutation_multiplier=1.0):
    global state, time_infected, strains

    R, C = state.shape
    new_state = state.copy()
    new_time = time_infected.copy()

    # prepare neighbor counting per strain: for efficiency, we'll evaluate local exposures
    # We will compute for each cell the exposures as a dict {strain_id: exposure_score}
    # A simple approach: for each infected neighbor add a contribution weighted by BASE_DIFFUSION / 8

    # For speed: build boolean arrays per existing strain up to a reasonable count.
    max_considered_strains = min(len(strains), 200)  # avoid super heavy memory if many strains appear
    # If more strains exist we'll still count by iterating neighbors (slower but safe)
    # We'll iterate over cells and compute exposures by neighbor traversal (straightforward).

    for r in range(R):
        for c in range(C):
            cell = state[r, c]
            # If susceptible, check exposure
            if cell == 0:
                # accumulate exposures per strain
                exposures = {}
                # include self small exposure (if self infected? not relevant since cell==0)
                for rr, cc in neighbors8(r, c, state.shape):
                    nid = state[rr, cc]
                    if nid > 0:
                        # neighbor infected with strain nid
                        exposures[nid] = exposures.get(nid, 0.0) + BASE_DIFFUSION / 8.0
                # Choose strongest exposure strain (or none)
                if exposures:
                    # find strain with max exposure score
                    # tie-break randomly
                    top_strain, top_score = max(exposures.items(), key=lambda kv: (kv[1], random.random()))
                    # base transmissibility: per-strain transmissibility * exposure * global factor
                    if top_strain - 1 < len(strains):
                        strain_props = strains[top_strain - 1]
                        trans = strain_props["transmissibility"] * top_score * global_transmissibility
                        # stochastic infection
                        if np.random.rand() < trans:
                            # possible mutation? based on strain mutation_rate * global multiplier
                            mut_prob = strain_props["mutation_rate"] * global_mutation_multiplier
                            if (np.random.rand() < mut_prob) and (len(strains) < MAX_STRAINS):
                                # spawn new strain (mutate transmissibility slightly)
                                base_t = strain_props["transmissibility"]
                                # small random multiplicative change
                                new_t = base_t * (1.0 + np.random.normal(loc=0.0, scale=0.08))
                                new_t = max(0.01, min(new_t, 0.9))
                                # mutate mutation rate slightly
                                new_m = max(0.0, min(0.5, strain_props["mutation_rate"] * (1.0 + np.random.normal(0, 0.2))))
                                new_id = add_strain(transmissibility=new_t, mutation_rate=new_m)
                                new_state[r, c] = new_id
                                new_time[r, c] = 0
                            else:
                                # infected without mutation
                                new_state[r, c] = top_strain
                                new_time[r, c] = 0
            elif cell > 0:
                # infected: progress infection clock
                new_time[r, c] += 1
                if new_time[r, c] >= RECOVERY_TIME:
                    new_state[r, c] = -1  # recovered / immune
                    new_time[r, c] = 0
            else:
                # recovered: remain immune (no waning in this simple model)
                pass

    state = new_state
    time_infected = new_time

# -----------------------
# VISUALIZATION
# -----------------------
fig, ax = plt.subplots(figsize=(7, 7))
plt.subplots_adjust(left=0.12, bottom=0.24)

# initial colormap: entry 0 -> susceptible, -1 (recovered) -> separate color, then strains 1..N
def build_colormap():
    # build color list where index mapping is:
    # 0 -> susceptible (light gray), 1..N -> strains, special negative recovered -> last color (dark gray/black)
    n = len(strains)
    palette = strain_color_palette(max(8, n))
    # Convert palette to (R,G,B)
    strain_rgbs = palette[:n]
    # colors order: susceptible, strains..., recovered
    cmap_list = []
    cmap_list.append((0.95, 0.95, 0.95))  # susceptible (very light)
    for rgb in strain_rgbs:
        cmap_list.append(rgb)
    cmap_list.append((0.3, 0.3, 0.3))  # recovered (dark gray)
    return colors.ListedColormap(cmap_list)

def grid_to_image_array(grid):
    """
    Map internal states to integers in 0..(1 + n_strains + 1)
    mapping:
        0 (susceptible) -> 0
        strains 1..N -> 1..N
        recovered (-1) -> N+1
    """
    n = len(strains)
    mapped = np.zeros_like(grid, dtype=int)
    # susceptible already 0
    # infected: >0 -> same index
    infected_mask = grid > 0
    mapped[infected_mask] = grid[infected_mask]
    recovered_mask = grid == -1
    mapped[recovered_mask] = n + 1
    return mapped

# Image setup
cmap = build_colormap()
norm = colors.BoundaryNorm(boundaries=np.arange(0, 2 + len(strains) + 1) - 0.5,
                           ncolors=len(cmap.colors))
im = ax.imshow(grid_to_image_array(state), cmap=cmap, interpolation='nearest', norm=norm)
ax.set_title("Virus mutation & spread — strains shown by color")
ax.axis('off')

# Legend text place
strain_info_text = ax.text(0.01, 0.99, "", transform=ax.transAxes, va='top', ha='left', fontsize=9,
                           bbox=dict(boxstyle="round", fc="w", alpha=0.8))

# -----------------------
# Controls: sliders for global transmissibility and mutation multiplier
# -----------------------
axcolor = 'lightgoldenrodyellow'
ax_trans = plt.axes([0.12, 0.14, 0.76, 0.03], facecolor=axcolor)
ax_mut = plt.axes([0.12, 0.09, 0.76, 0.03], facecolor=axcolor)
s_trans = Slider(ax_trans, 'Global transmiss.', 0.1, 3.0, valinit=1.0, valstep=0.01)
s_mut = Slider(ax_mut, 'Mutation multiplier', 0.0, 5.0, valinit=1.0, valstep=0.01)

# Reset button
reset_ax = plt.axes([0.8, 0.02, 0.08, 0.04])
button_reset = Button(reset_ax, 'Reset', color='lightgray', hovercolor='0.975')


def reset(event):
    global state, time_infected, strains
    # reinitialize core arrays
    state = np.zeros((GRID_SIZE, GRID_SIZE), dtype=int)
    time_infected = np.zeros_like(state, dtype=int)
    strains = []
    for i in range(INITIAL_STRAINS):
        t = 0.15 + 0.15 * np.random.rand()
        m = 0.002 + 0.02 * np.random.rand()
        add_strain(transmissibility=t, mutation_rate=m)
    coords = list(np.ndindex(GRID_SIZE, GRID_SIZE))
    random.shuffle(coords)
    for k in range(INIT_INFECTED):
        r, c = coords[k]
        strain_choice = random.randint(1, len(strains))
        state[r, c] = strain_choice
    update_display(force_update_cmap=True)


button_reset.on_clicked(reset)

# -----------------------
# Animation loop
# -----------------------
step_count = 0
def update_display(force_update_cmap=False):
    global im, cmap, norm
    cmap = build_colormap()
    # re-create norm with correct number of colors
    norm = colors.BoundaryNorm(boundaries=np.arange(0, 2 + len(strains) + 1) - 0.5,
                               ncolors=len(cmap.colors))
    im.set_cmap(cmap)
    im.set_norm(norm)
    im.set_data(grid_to_image_array(state))

    # update strain_info_text: show top few strains with transmissibility and mutation_rate
    s = "Step: {}\nStrains: {}\n".format(update_display.step_counter, len(strains))
    # list top 6 strains by transmissibility
    sorted_strains = sorted(strains, key=lambda x: -x["transmissibility"])
    for st in sorted_strains[:8]:
        s += "ID {}: T={:.3f}, µ={:.3f}\n".format(st["id"], st["transmissibility"], st["mutation_rate"])
    strain_info_text.set_text(s)
    update_display.step_counter += 1

# static attribute
update_display.step_counter = 0

def animate(frame):
    # read sliders
    gt = s_trans.val
    gm = s_mut.val
    step_sim(global_transmissibility=gt, global_mutation_multiplier=gm)
    # occasionally rebuild colormap if strains changed
    if len(cmap.colors) != (2 + len(strains) + 1):
        update_display(force_update_cmap=True)
    else:
        im.set_data(grid_to_image_array(state))
    update_display()
    return (im,)

anim = FuncAnimation(fig, animate, interval=INTERVAL_MS, blit=False)

# -----------------------
# Show counts plot in separate figure (optional small window)
# -----------------------
def summarize_counts():
    # returns dict of counts: susceptible, recovered, infections per strain
    counts = {}
    counts["susceptible"] = np.sum(state == 0)
    counts["recovered"] = np.sum(state == -1)
    for st in strains:
        counts[f"strain_{st['id']}"] = np.sum(state == st["id"])
    return counts

# Update title periodically to show totals
def update_title_text(event):
    counts = summarize_counts()
    total_infected = sum(counts[k] for k in counts if k.startswith("strain_"))
    ax.set_xlabel(f"Susceptible: {counts['susceptible']}  Infected: {total_infected}  Recovered: {counts['recovered']}")

# connect to animation event
fig.canvas.mpl_connect('draw_event', update_title_text)

# -----------------------
# Run
# -----------------------
if __name__ == "__main__":
    plt.show()
