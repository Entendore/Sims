"""
============================================================
  NUCLEAR CHAIN REACTION SIMULATOR
============================================================
A comprehensive nuclear physics simulation featuring:
  - 5 isotopes (U235, U238, Pu239, Th232, U233) with distinct properties
  - Neutron-induced fission with cross-sections
  - Spontaneous radioactive decay
  - Nuclear fusion between compatible isotopes
  - Breeder reactor mechanics (U238→Pu239, Th232→U233)
  - Moderator materials (graphite) that thermalize neutrons
  - Control rods (boron) that absorb neutrons
  - Thermal feedback with negative temperature coefficient
  - Heat diffusion across the grid
  - Meltdown mechanic when temperature exceeds threshold
  - Interactive controls (mouse + keyboard)
  - Real-time statistics and dual display modes
============================================================
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import matplotlib.gridspec as gridspec
from collections import deque


# ============================================================
# ISOTOPE DEFINITIONS
# ============================================================

class Isotope:
    """Represents a nuclear isotope with physical properties."""

    def __init__(self, name, half_life, energy_yield, fission_cross_section,
                 fusion_pair=None, fusion_energy=0.0, color_rgb=None,
                 can_breed=False, breed_product=None):
        self.name = name
        self.half_life = half_life                          # steps for half-life
        self.energy_yield = energy_yield                    # energy per fission
        self.fission_cross_section = fission_cross_section  # neutron fission probability
        self.fusion_pair = fusion_pair                      # compatible fusion partner
        self.fusion_energy = fusion_energy                  # energy released in fusion
        self.color_rgb = color_rgb or (1.0, 1.0, 1.0)      # display color (R,G,B)
        self.can_breed = can_breed                          # can absorb neutron to transmute
        self.breed_product = breed_product                  # product isotope after breeding


ISOTOPES = {
    'U235': Isotope('U235', half_life=50, energy_yield=2.0,
                    fission_cross_section=0.35, fusion_pair='U238',
                    fusion_energy=3.0, color_rgb=(0.20, 0.85, 0.20)),
    'U238': Isotope('U238', half_life=100, energy_yield=1.0,
                    fission_cross_section=0.05, fusion_pair='Pu239',
                    fusion_energy=5.0, color_rgb=(0.70, 0.65, 0.15),
                    can_breed=True, breed_product='Pu239'),
    'Pu239': Isotope('Pu239', half_life=70, energy_yield=3.0,
                     fission_cross_section=0.45, fusion_pair='U235',
                     fusion_energy=4.0, color_rgb=(0.85, 0.20, 0.75)),
    'Th232': Isotope('Th232', half_life=120, energy_yield=1.5,
                     fission_cross_section=0.08, fusion_pair='U235',
                     fusion_energy=2.5, color_rgb=(0.20, 0.60, 0.85),
                     can_breed=True, breed_product='U233'),
    'U233': Isotope('U233', half_life=60, energy_yield=2.5,
                    fission_cross_section=0.40, fusion_pair='Th232',
                    fusion_energy=3.5, color_rgb=(0.10, 0.90, 0.50)),
}


# ============================================================
# CELL STATE CONSTANTS
# ============================================================

EMPTY       = 0
FISSILE     = 1
FISSION     = 2
MODERATOR   = 3
CONTROL_ROD = 4


# ============================================================
# SIMULATION CLASS
# ============================================================

class NuclearSimulation:
    """
    Core simulation engine for nuclear chain reactions.

    Models fission, fusion, decay, neutron transport, breeding,
    moderation, and thermal feedback on a 2D toroidal grid.
    """

    def __init__(self, grid_size=50, initial_fissions=3, neutron_delay=2,
                 energy_decay=0.92, max_energy=8.0, fissile_density=0.45,
                 moderator_density=0.05, control_rod_density=0.02,
                 temperature_coefficient=-0.003, meltdown_threshold=7.5):
        # store params for reset
        self._params = {
            'grid_size': grid_size, 'initial_fissions': initial_fissions,
            'neutron_delay': neutron_delay, 'energy_decay': energy_decay,
            'max_energy': max_energy, 'fissile_density': fissile_density,
            'moderator_density': moderator_density,
            'control_rod_density': control_rod_density,
            'temperature_coefficient': temperature_coefficient,
            'meltdown_threshold': meltdown_threshold,
        }

        self.grid_size = grid_size
        self.initial_fissions = initial_fissions
        self.neutron_delay = neutron_delay
        self.energy_decay = energy_decay
        self.max_energy = max_energy
        self.temperature_coefficient = temperature_coefficient
        self.meltdown_threshold = meltdown_threshold

        # statistics
        self.step_count        = 0
        self.total_fissions    = 0
        self.total_fusions     = 0
        self.total_decays      = 0
        self.total_breeds      = 0
        self.fissions_this_step = 0
        self.meltdown          = False
        self.energy_history        = deque(maxlen=500)
        self.fission_rate_history  = deque(maxlen=500)
        self.active_cells_history  = deque(maxlen=500)
        self.temperature_history   = deque(maxlen=500)
        self.fusion_rate_history   = deque(maxlen=500)

        self._init_grids(fissile_density, moderator_density, control_rod_density)

    # ----------------------------------------------------------
    # Grid initialisation
    # ----------------------------------------------------------
    def _init_grids(self, fissile_density, moderator_density, control_rod_density):
        gs = self.grid_size
        self.grid          = np.zeros((gs, gs), dtype=int)
        self.energy        = np.zeros((gs, gs), dtype=float)
        self.temperature   = np.zeros((gs, gs), dtype=float)
        self.neutrons      = [[[] for _ in range(gs)] for _ in range(gs)]
        self.isotope_grid  = np.full((gs, gs), '', dtype='U5')
        self.fission_flash = np.zeros((gs, gs), dtype=float)

        isotope_names   = ['U235', 'U238', 'Pu239', 'Th232']
        isotope_weights = [0.35, 0.30, 0.20, 0.15]

        for i in range(gs):
            for j in range(gs):
                r = np.random.rand()
                if r < control_rod_density:
                    self.grid[i, j] = CONTROL_ROD
                elif r < control_rod_density + moderator_density:
                    self.grid[i, j] = MODERATOR
                elif r < control_rod_density + moderator_density + fissile_density:
                    self.grid[i, j] = FISSILE
                    iso = np.random.choice(isotope_names, p=isotope_weights)
                    self.isotope_grid[i, j] = iso
                    self.energy[i, j] = ISOTOPES[iso].energy_yield * 0.5

        # trigger initial fissions
        for _ in range(self.initial_fissions):
            for _attempt in range(200):
                x, y = np.random.randint(0, gs, size=2)
                if self.grid[x, y] == FISSILE:
                    self.grid[x, y] = FISSION
                    iso = self.isotope_grid[x, y]
                    self.energy[x, y] = ISOTOPES[iso].energy_yield
                    self.fission_flash[x, y] = 1.0
                    break

    def reset(self):
        """Re-initialise with the same parameters."""
        self.__init__(**self._params)

    # ----------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------
    def get_neighbors(self, x, y, radius=1):
        """Return list of (nx, ny) with toroidal wrapping."""
        neighbors = []
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if dx == 0 and dy == 0:
                    continue
                nx = (x + dx) % self.grid_size
                ny = (y + dy) % self.grid_size
                neighbors.append((nx, ny))
        return neighbors

    # ----------------------------------------------------------
    # Main update step
    # ----------------------------------------------------------
    def update(self):
        """Advance the simulation by one time step."""
        if self.meltdown:
            self._meltdown_update()
            self._record_stats(0, 0, 0, 0)
            return 0, 0, 0, 0

        gs = self.grid_size
        new_grid        = self.grid.copy()
        new_energy      = self.energy.copy()
        new_temperature = self.temperature.copy()
        new_neutrons    = [[n.copy() for n in row] for row in self.neutrons]
        new_flash       = self.fission_flash * 0.50   # decay flash

        fissions = fusions = decays = breeds = 0

        # ==== PHASE 1 — FISSION & SPONTANEOUS DECAY ====
        for x in range(gs):
            for y in range(gs):
                if self.grid[x, y] == FISSION:
                    iso = ISOTOPES[self.isotope_grid[x, y]]

                    # energy → heat
                    new_temperature[x, y] += iso.energy_yield * 2.5

                    # emit 2-3 neutrons
                    n_neutrons = np.random.choice([2, 3], p=[0.55, 0.45])
                    neighbors  = self.get_neighbors(x, y)
                    for _ in range(n_neutrons):
                        if np.random.rand() < 0.25:          # long-range neutron
                            nx, ny = neighbors[np.random.randint(len(neighbors))]
                            far = self.get_neighbors(nx, ny)
                            fx, fy = far[np.random.randint(len(far))]
                            new_neutrons[fx][fy].append(self.neutron_delay + 1)
                        else:
                            nx, ny = neighbors[np.random.randint(len(neighbors))]
                            new_neutrons[nx][ny].append(self.neutron_delay)

                    new_grid[x, y]   = EMPTY
                    new_energy[x, y] = 0.0
                    new_flash[x, y]  = 1.0
                    fissions += 1

                elif self.grid[x, y] == FISSILE:
                    iso = ISOTOPES[self.isotope_grid[x, y]]
                    decay_prob = (1 - 0.5 ** (1 / iso.half_life)) * 0.05
                    if np.random.rand() < decay_prob:
                        new_grid[x, y]   = EMPTY
                        new_energy[x, y] = 0.0
                        decays += 1

        # ==== PHASE 2 — NEUTRON INTERACTIONS ====
        for x in range(gs):
            for y in range(gs):
                # decrement timers
                new_neutrons[x][y] = [t - 1 for t in new_neutrons[x][y] if t > 1]

                # arriving neutrons
                arrived = sum(1 for t in self.neutrons[x][y] if t <= 1)
                if arrived == 0:
                    continue

                state = self.grid[x, y]

                if state == FISSILE:
                    iso = ISOTOPES[self.isotope_grid[x, y]]
                    temp_factor = 1.0 + self.temperature_coefficient * self.temperature[x, y]
                    prob = min(0.95,
                               iso.fission_cross_section
                               * temp_factor
                               * max(0.1, self.energy[x, y] / iso.energy_yield))
                    prob = min(0.95, 1 - (1 - prob) ** arrived)   # multi-neutron boost

                    # moderator bonus
                    for nx, ny in self.get_neighbors(x, y):
                        if self.grid[nx, ny] == MODERATOR:
                            prob = min(0.95, prob * 1.4)
                            break

                    if np.random.rand() < prob:
                        new_grid[x, y]   = FISSION
                        new_energy[x, y] += iso.energy_yield
                        new_flash[x, y]  = 1.0
                        fissions += 1
                    else:
                        # breeding (neutron capture without fission)
                        if iso.can_breed and np.random.rand() < 0.15 * arrived:
                            prod = iso.breed_product
                            if prod and prod in ISOTOPES:
                                self.isotope_grid[x, y] = prod
                                new_energy[x, y] = ISOTOPES[prod].energy_yield * 0.5
                                breeds += 1

                elif state == CONTROL_ROD:
                    pass  # absorbed

                elif state == MODERATOR:
                    # scatter / reflect neutrons
                    for _ in range(min(arrived, 2)):
                        nb = self.get_neighbors(x, y)
                        nx, ny = nb[np.random.randint(len(nb))]
                        new_neutrons[nx][ny].append(1)

                elif state == EMPTY:
                    for _ in range(arrived):
                        if np.random.rand() < 0.25:
                            nb = self.get_neighbors(x, y)
                            nx, ny = nb[np.random.randint(len(nb))]
                            new_neutrons[nx][ny].append(1)

        # ==== PHASE 3 — FUSION BETWEEN NEIGHBORS ====
        fused = set()
        for x in range(gs):
            for y in range(gs):
                if self.grid[x, y] != FISSILE or (x, y) in fused:
                    continue
                iso = ISOTOPES[self.isotope_grid[x, y]]
                if not iso.fusion_pair:
                    continue
                for nx, ny in self.get_neighbors(x, y):
                    if (self.grid[nx, ny] == FISSILE
                            and self.isotope_grid[nx, ny] == iso.fusion_pair
                            and (nx, ny) not in fused):
                        fusion_prob = 0.008 * (1 + self.temperature[x, y] * 0.08)
                        if np.random.rand() < fusion_prob:
                            fe = iso.fusion_energy
                            new_energy[x, y]      += fe
                            new_energy[nx, ny]     += fe
                            new_temperature[x, y]  += fe * 0.5
                            new_temperature[nx, ny] += fe * 0.5
                            new_grid[x, y]   = EMPTY
                            new_grid[nx, ny]  = EMPTY
                            new_flash[x, y]  = 0.85
                            new_flash[nx, ny] = 0.85
                            fused.update([(x, y), (nx, ny)])
                            fusions += 1
                            break

        # ==== PHASE 4 — ENERGY DECAY & HEAT DISSIPATION ====
        new_energy      *= self.energy_decay
        new_temperature *= 0.94

        # heat diffusion (fast numpy convolution)
        tp = np.pad(new_temperature, 1, mode='wrap')
        diffused = (tp[:-2, 1:-1] + tp[2:, 1:-1]
                    + tp[1:-1, :-2] + tp[1:-1, 2:]) * 0.05 \
                   + new_temperature * 0.80
        new_temperature = diffused

        new_energy      = np.clip(new_energy, 0, self.max_energy)
        new_temperature = np.clip(new_temperature, 0, 25.0)

        # ==== PHASE 5 — MELTDOWN CHECK ====
        if np.sum(new_temperature > self.meltdown_threshold) > gs * gs * 0.15:
            self.meltdown = True

        # commit
        self.grid          = new_grid
        self.energy        = new_energy
        self.temperature   = new_temperature
        self.neutrons      = new_neutrons
        self.fission_flash = new_flash
        self.fissions_this_step = fissions

        self._record_stats(fissions, fusions, decays, breeds)
        return fissions, fusions, decays, breeds

    # ----------------------------------------------------------
    # Meltdown mode — uncontrolled reaction
    # ----------------------------------------------------------
    def _meltdown_update(self):
        gs = self.grid_size
        for x in range(gs):
            for y in range(gs):
                if self.grid[x, y] == FISSILE and np.random.rand() < 0.25:
                    self.grid[x, y] = FISSION
                    self.fission_flash[x, y] = 1.0
                    self.temperature[x, y] += 4.0

        for x in range(gs):
            for y in range(gs):
                if self.grid[x, y] == FISSION:
                    self.grid[x, y] = EMPTY
                    self.temperature[x, y] += 3.0
                    self.fission_flash[x, y] = 1.0
                    for nx, ny in self.get_neighbors(x, y):
                        if self.grid[nx, ny] == FISSILE and np.random.rand() < 0.55:
                            self.grid[nx, ny] = FISSION

        self.temperature   *= 0.97
        self.fission_flash *= 0.55
        self.energy        *= 0.80

    # ----------------------------------------------------------
    # Statistics
    # ----------------------------------------------------------
    def _record_stats(self, fissions, fusions, decays, breeds):
        self.step_count     += 1
        self.total_fissions += fissions
        self.total_fusions  += fusions
        self.total_decays   += decays
        self.total_breeds   += breeds
        self.energy_history.append(np.sum(self.energy))
        self.fission_rate_history.append(fissions)
        self.active_cells_history.append(np.sum(self.grid == FISSILE))
        self.temperature_history.append(np.mean(self.temperature))
        self.fusion_rate_history.append(fusions)

    # ----------------------------------------------------------
    # Interactive actions
    # ----------------------------------------------------------
    def trigger_fission(self, x, y):
        gs = self.grid_size
        if 0 <= x < gs and 0 <= y < gs and self.grid[x, y] == FISSILE:
            self.grid[x, y] = FISSION
            iso = ISOTOPES[self.isotope_grid[x, y]]
            self.energy[x, y] = iso.energy_yield
            self.fission_flash[x, y] = 1.0

    def place_control_rod(self, x, y):
        gs = self.grid_size
        if 0 <= x < gs and 0 <= y < gs:
            if self.grid[x, y] == CONTROL_ROD:
                self.grid[x, y] = EMPTY
            elif self.grid[x, y] in (EMPTY, FISSILE):
                self.grid[x, y] = CONTROL_ROD
                self.energy[x, y] = 0.0

    def insert_control_rod_row(self, row):
        gs = self.grid_size
        if 0 <= row < gs:
            for j in range(gs):
                if self.grid[row, j] != MODERATOR:
                    self.grid[row, j] = CONTROL_ROD
                    self.energy[row, j] = 0.0

    def withdraw_control_rod_row(self, row):
        gs = self.grid_size
        if 0 <= row < gs:
            for j in range(gs):
                if self.grid[row, j] == CONTROL_ROD:
                    self.grid[row, j] = EMPTY

    # ----------------------------------------------------------
    # Rendering
    # ----------------------------------------------------------
    def render_grid(self):
        """Return an (gs, gs, 3) float RGB image of current state."""
        gs  = self.grid_size
        img = np.zeros((gs, gs, 3), dtype=float)

        # --- empty cells ---
        mask   = self.grid == EMPTY
        t_norm = np.clip(self.temperature / 12.0, 0, 1)
        img[mask, 0] = 0.04 + t_norm[mask] * 0.35
        img[mask, 1] = 0.02 + t_norm[mask] * 0.08
        img[mask, 2] = 0.06 + t_norm[mask] * 0.02

        # --- fissile cells (per-isotope colour) ---
        e_norm = np.clip(self.energy / self.max_energy, 0, 1)
        for iso_name, iso in ISOTOPES.items():
            m = (self.grid == FISSILE) & (self.isotope_grid == iso_name)
            if not np.any(m):
                continue
            brightness = 0.25 + 0.75 * e_norm
            img[m, 0] = iso.color_rgb[0] * brightness[m]
            img[m, 1] = iso.color_rgb[1] * brightness[m]
            img[m, 2] = iso.color_rgb[2] * brightness[m]

        # --- fission flash ---
        m = self.grid == FISSION
        img[m, 0] = 1.0
        img[m, 1] = 0.95
        img[m, 2] = 0.55

        # --- moderator ---
        m  = self.grid == MODERATOR
        em = np.clip(self.energy / self.max_energy, 0, 1)
        img[m, 0] = 0.08 + em[m] * 0.15
        img[m, 1] = 0.22 + em[m] * 0.28
        img[m, 2] = 0.55 + em[m] * 0.35

        # --- control rods ---
        m = self.grid == CONTROL_ROD
        img[m, 0] = 0.22
        img[m, 1] = 0.22
        img[m, 2] = 0.28

        # --- flash overlay ---
        fm = self.fission_flash > 0.1
        if np.any(fm):
            f = self.fission_flash[fm]
            img[fm, 0] = np.clip(img[fm, 0] + f * 0.70, 0, 1)
            img[fm, 1] = np.clip(img[fm, 1] + f * 0.55, 0, 1)
            img[fm, 2] = np.clip(img[fm, 2] + f * 0.20, 0, 1)

        # --- neutron glow (cyan) ---
        ncount = np.array([[len(self.neutrons[i][j])
                            for j in range(gs)] for i in range(gs)])
        gm = ncount > 0
        if np.any(gm):
            glow = np.clip(ncount * 0.25, 0, 1)
            img[gm, 0] = np.clip(img[gm, 0] + glow[gm] * 0.35, 0, 1)
            img[gm, 1] = np.clip(img[gm, 1] + glow[gm] * 0.50, 0, 1)
            img[gm, 2] = np.clip(img[gm, 2] + glow[gm] * 1.00, 0, 1)

        # --- meltdown red tint ---
        if self.meltdown:
            red = np.clip(self.temperature / 15.0, 0, 0.45)
            img[:, :, 0] = np.clip(img[:, :, 0] + red, 0, 1)

        return np.clip(img, 0, 1)

    def render_temperature(self):
        """Return an (gs, gs, 3) float RGB image of temperature field."""
        t_norm = np.clip(self.temperature / 15.0, 0, 1)
        img = np.zeros((self.grid_size, self.grid_size, 3), dtype=float)
        # hot = red/yellow, cool = dark blue
        img[:, :, 0] = np.clip(t_norm * 2.0, 0, 1)
        img[:, :, 1] = np.clip(t_norm * 1.2 - 0.3, 0, 1)
        img[:, :, 2] = np.clip(0.15 - t_norm * 0.3, 0, 0.15)
        # overlay cell outlines
        m = self.grid == CONTROL_ROD
        img[m] = [0.15, 0.15, 0.20]
        m = self.grid == MODERATOR
        img[m] = np.clip(img[m] + [0.0, 0.05, 0.15], 0, 1)
        return np.clip(img, 0, 1)


# ============================================================
# VISUALIZER CLASS
# ============================================================

class SimulationVisualizer:
    """
    Interactive matplotlib visualization for the nuclear simulation.

    Controls
    --------
    Left Click   — Trigger fission at cell
    Right Click  — Toggle control rod at cell
    Space        — Pause / Resume
    R            — Reset simulation
    Up Arrow     — Insert control rod row
    Down Arrow   — Withdraw most recent control rod row
    M            — Toggle energy / temperature display mode
    F            — Trigger 5 random fissions
    """

    def __init__(self, sim: NuclearSimulation):
        self.sim = sim
        self.paused = False
        self.control_rod_rows: list[int] = []
        self.display_mode = 'energy'        # 'energy' | 'temperature'
        self.next_rod_row = 5               # next row for control rod insertion

        # ---- figure layout ----
        self.fig = plt.figure(figsize=(17, 9.5), facecolor='#0d0d1a')
        try:
            self.fig.canvas.manager.set_window_title('Nuclear Chain Reaction Simulator')
        except Exception:
            pass

        gs_layout = gridspec.GridSpec(
            4, 2, width_ratios=[2.2, 1], height_ratios=[0.08, 1, 1, 1],
            hspace=0.45, wspace=0.25,
            left=0.04, right=0.97, top=0.96, bottom=0.06,
        )

        # title / status bar
        self.ax_title = self.fig.add_subplot(gs_layout[0, :])
        self.ax_title.set_facecolor('#0d0d1a')
        self.ax_title.axis('off')
        self.title_text = self.ax_title.text(
            0.5, 0.5, '', transform=self.ax_title.transAxes,
            ha='center', va='center', color='#ddddff',
            fontsize=12, fontweight='bold', fontfamily='monospace',
        )

        # main simulation panel
        self.ax_main = self.fig.add_subplot(gs_layout[1:, 0])
        self.ax_main.set_facecolor('#050510')
        self.im = self.ax_main.imshow(
            self.sim.render_grid(), interpolation='nearest', aspect='equal',
        )
        self.ax_main.tick_params(colors='#444466', labelsize=6)
        self.ax_main.set_xlabel('X', color='#666688', fontsize=8)
        self.ax_main.set_ylabel('Y', color='#666688', fontsize=8)

        # statistics panels
        self.ax_energy  = self.fig.add_subplot(gs_layout[1, 1])
        self.ax_fission = self.fig.add_subplot(gs_layout[2, 1])
        self.ax_active  = self.fig.add_subplot(gs_layout[3, 1])

        stat_cfg = [
            (self.ax_energy,  'Total Energy',  '#ff6644'),
            (self.ax_fission, 'Fission Rate',  '#ffcc00'),
            (self.ax_active,  'Fissile Cells',  '#44ff88'),
        ]
        self.stat_lines = []
        for ax, title, colour in stat_cfg:
            ax.set_facecolor('#08081a')
            ax.tick_params(colors='#888899', labelsize=6)
            for sp in ax.spines.values():
                sp.set_color('#222244')
            ax.set_title(title, color='#aaaacc', fontsize=9, pad=4)
            line, = ax.plot([], [], color=colour, linewidth=1.2, alpha=0.9)
            ax.set_xlim(0, 10)
            ax.set_ylim(0, 1)
            self.stat_lines.append(line)

        self.ax_active.set_xlabel('Step', color='#888899', fontsize=7)

        # isotope colour legend
        isotope_labels = [
            ('U235', ISOTOPES['U235'].color_rgb),
            ('U238', ISOTOPES['U238'].color_rgb),
            ('Pu239', ISOTOPES['Pu239'].color_rgb),
            ('Th232', ISOTOPES['Th232'].color_rgb),
            ('U233', ISOTOPES['U233'].color_rgb),
        ]
        material_labels = [
            ('Mod',   (0.15, 0.35, 0.70)),
            ('CRod',  (0.22, 0.22, 0.28)),
            ('Flash', (1.00, 0.95, 0.55)),
        ]
        lx = 0.04
        for i, (name, c) in enumerate(isotope_labels):
            self.fig.text(lx + i * 0.065, 0.015, f'■ {name}',
                          color=c, fontsize=6.5, fontfamily='monospace', va='bottom')
        ox = lx + len(isotope_labels) * 0.065 + 0.01
        for i, (name, c) in enumerate(material_labels):
            self.fig.text(ox + i * 0.055, 0.015, f'■ {name}',
                          color=c, fontsize=6.5, fontfamily='monospace', va='bottom')

        # controls help
        self.fig.text(
            0.55, 0.015,
            'LClick: Fission | RClick: Rod | Space: Pause | '
            'R: Reset | ↑↓: Rod Rows | M: Mode | F: 5 Fissions',
            ha='center', va='bottom', color='#555577',
            fontsize=7, fontfamily='monospace',
        )

        # connect events
        self.fig.canvas.mpl_connect('button_press_event', self._on_click)
        self.fig.canvas.mpl_connect('key_press_event',    self._on_key)

    # ----------------------------------------------------------
    # Event handlers
    # ----------------------------------------------------------
    def _on_click(self, event):
        if event.inaxes != self.ax_main or event.xdata is None:
            return
        y, x = int(round(event.ydata)), int(round(event.xdata))
        if event.button == 1:
            self.sim.trigger_fission(x, y)
        elif event.button == 3:
            self.sim.place_control_rod(x, y)

    def _on_key(self, event):
        if event.key == ' ':
            self.paused = not self.paused
        elif event.key == 'r':
            self.sim.reset()
            self.control_rod_rows.clear()
            self.next_rod_row = 5
        elif event.key == 'up':
            row = self.next_rod_row % self.sim.grid_size
            self.sim.insert_control_rod_row(row)
            self.control_rod_rows.append(row)
            self.next_rod_row += max(3, self.sim.grid_size // 12)
        elif event.key == 'down':
            if self.control_rod_rows:
                row = self.control_rod_rows.pop()
                self.sim.withdraw_control_rod_row(row)
        elif event.key == 'm':
            self.display_mode = (
                'temperature' if self.display_mode == 'energy' else 'energy'
            )
        elif event.key == 'f':
            for _ in range(5):
                x = np.random.randint(0, self.sim.grid_size)
                y = np.random.randint(0, self.sim.grid_size)
                self.sim.trigger_fission(x, y)

    # ----------------------------------------------------------
    # Animation frame
    # ----------------------------------------------------------
    def _animate(self, _frame):
        if not self.paused:
            self.sim.update()

        # render main panel
        if self.display_mode == 'temperature':
            self.im.set_array(self.sim.render_temperature())
        else:
            self.im.set_array(self.sim.render_grid())

        # update statistics lines
        histories = [
            self.sim.energy_history,
            self.sim.fission_rate_history,
            self.sim.active_cells_history,
        ]
        for hist, line in zip(histories, self.stat_lines):
            if len(hist) > 1:
                data  = list(hist)
                steps = list(range(len(data)))
                line.set_data(steps, data)
                ax = line.axes
                ax.set_xlim(0, max(10, len(steps)))
                ymax = max(data) if data else 1
                ax.set_ylim(0, max(1, ymax * 1.15))

        # status bar
        mode_str = 'TEMP' if self.display_mode == 'temperature' else 'ENERGY'
        meltdown_warn = '  ⚠ MELTDOWN' if self.sim.meltdown else ''
        state_icon = '⏸ PAUSED' if self.paused else '▶ RUNNING'
        status = (
            f'Step {self.sim.step_count:4d} │ '
            f'Fissions {self.sim.total_fissions:5d} │ '
            f'Fusions {self.sim.total_fusions:4d} │ '
            f'Breeds {self.sim.total_breeds:4d} │ '
            f'AvgT {np.mean(self.sim.temperature):5.2f} │ '
            f'Mode {mode_str} │ {state_icon}{meltdown_warn}'
        )
        self.title_text.set_text(status)
        if self.sim.meltdown:
            self.title_text.set_color('#ff4444')
        elif self.paused:
            self.title_text.set_color('#8888cc')
        else:
            self.title_text.set_color('#ddddff')

        return [self.im, self.title_text] + self.stat_lines

    # ----------------------------------------------------------
    # Run
    # ----------------------------------------------------------
    def run(self, interval=70):
        """Start the animation loop (runs indefinitely)."""
        self.ani = animation.FuncAnimation(
            self.fig, self._animate, frames=None,
            interval=interval, blit=False, cache_frame_data=False,
        )
        plt.show()


# ============================================================
# MAIN
# ============================================================

if __name__ == '__main__':
    print('=' * 62)
    print('   NUCLEAR CHAIN REACTION SIMULATOR')
    print('=' * 62)
    print()
    print('  Isotopes  : U235  U238  Pu239  Th232  U233 (bred)')
    print('  Processes : Fission · Fusion · Decay · Breeding')
    print('  Materials : Moderator (graphite) · Control Rods (boron)')
    print()
    print('  Controls:')
    print('    Left Click  — Trigger fission')
    print('    Right Click — Toggle control rod')
    print('    Space       — Pause / Resume')
    print('    R           — Reset simulation')
    print('    Up Arrow    — Insert control rod row')
    print('    Down Arrow  — Withdraw control rod row')
    print('    M           — Toggle energy / temperature view')
    print('    F           — Trigger 5 random fissions')
    print()
    print('=' * 62)

    sim = NuclearSimulation(
        grid_size=50,
        initial_fissions=3,
        neutron_delay=2,
        energy_decay=0.92,
        max_energy=8.0,
        fissile_density=0.45,
        moderator_density=0.05,
        control_rod_density=0.02,
        temperature_coefficient=-0.003,
        meltdown_threshold=7.5,
    )

    viz = SimulationVisualizer(sim)
    viz.run(interval=70)