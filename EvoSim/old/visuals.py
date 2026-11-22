# visuals.py
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from Sims.EvoSim.old.config import GRID_SIZE, NUM_SPECIES

SPECIES_COLORS = np.array([
    [1.00, 0.25, 0.20],   # red
    [0.20, 0.85, 0.35],   # green
    [0.30, 0.55, 1.00],   # blue
    [1.00, 0.80, 0.15],   # gold
    [0.85, 0.30, 0.85],   # magenta
    [0.15, 0.90, 0.90],   # cyan
], dtype=np.float32)

STAGE_GLOW = np.array([0.0, 0.65, 0.95, 1.30, 0.35], dtype=np.float32)

class Visualizer:
    def __init__(self):
        plt.style.use('dark_background')
        self.fig = plt.figure(figsize=(18, 9))
        self.fig.patch.set_facecolor('#080810')
        
        # Leave space on the right for the settings panel
        self.fig.subplots_adjust(left=0.05, right=0.72, top=0.95, bottom=0.05)

        gs = gridspec.GridSpec(2, 2, width_ratios=[2.5, 1], height_ratios=[2.5, 1],
                               hspace=0.30, wspace=0.25, left=0.05, right=0.72, top=0.95, bottom=0.05)

        self.ax1 = self.fig.add_subplot(gs[0, 0])
        self.im  = self.ax1.imshow(np.zeros((GRID_SIZE, GRID_SIZE, 3)),
                                   interpolation='nearest', aspect='equal', origin='upper')
        self.ax1.set_title('Evolutionary Cellular Automata', fontsize=12, color='#cccccc', pad=8)
        self.ax1.set_xticks([]); self.ax1.set_yticks([])

        self.ax2 = self.fig.add_subplot(gs[1, 0])
        self.pop_line, = self.ax2.plot([], [], 'w-', lw=1.3, alpha=0.85, label='Total')
        self.species_lines = []
        for sp in range(NUM_SPECIES):
            c = SPECIES_COLORS[sp % len(SPECIES_COLORS)]
            ln, = self.ax2.plot([], [], '-', lw=0.9, color=c, label=f'Sp {sp}', alpha=0.85)
            self.species_lines.append(ln)
        self.ax2.legend(loc='upper left', fontsize=7, ncol=NUM_SPECIES + 1, framealpha=0.25)
        self.ax2.set_xlabel('Frame', fontsize=8, color='#888')
        self.ax2.set_ylabel('Population', fontsize=8, color='#888')
        self.ax2.set_title('Population Dynamics', fontsize=10, color='#cccccc')
        self.ax2.tick_params(colors='#555', labelsize=7)
        self.ax2.set_facecolor('#0a0a12')

        self.ax3 = self.fig.add_subplot(gs[0, 1])
        self.ax3.axis('off')
        self.info_text = self.ax3.text(0.05, 0.97, '', transform=self.ax3.transAxes, fontsize=7.5,
                                       verticalalignment='top', fontfamily='monospace',
                                       color='#cccccc', linespacing=1.35)

        self.ax4 = self.fig.add_subplot(gs[1, 1])
        self.div_line,    = self.ax4.plot([], [], '-', color='#ff88ff', lw=1, label='Shannon H′')
        self.energy_line, = self.ax4.plot([], [], '-', color='#88ff88', lw=1, label='Avg Energy')
        self.ax4.legend(loc='upper left', fontsize=7, framealpha=0.25)
        self.ax4.set_xlabel('Frame', fontsize=8, color='#888')
        self.ax4.set_title('Diversity & Energy', fontsize=10, color='#cccccc')
        self.ax4.tick_params(colors='#555', labelsize=7)
        self.ax4.set_facecolor('#0a0a12')

    def render_grid(self, S, env):
        img = np.zeros((GRID_SIZE, GRID_SIZE, 3), dtype=np.float32)

        fading = (~S['alive']) & (S['fade'] > 0)
        if fading.any():
            for c in range(3):
                img[fading, c] = S['fade'][fading] * 0.07

        if S['show_zones']:
            for zx in range(env.num_zones_x + 1):
                xi = min(zx * env.num_zones_x, GRID_SIZE - 1)
                img[xi, :] = np.maximum(img[xi, :], 0.12)
            for zy in range(env.num_zones_y + 1):
                yi = min(zy * env.num_zones_y, GRID_SIZE - 1)
                img[:, yi] = np.maximum(img[:, yi], 0.12)

        if S['disaster_flash'] > 0:
            flash_alpha = S['disaster_flash'] / 6.0 * 0.15
            img[:, :, 0] = np.maximum(img[:, :, 0], flash_alpha)

        for sp in range(NUM_SPECIES):
            colour = SPECIES_COLORS[sp % len(SPECIES_COLORS)]
            sp_mask = (S['species'] == sp)

            for stg_val in (1, 2, 3, 4):
                cell_mask = sp_mask & (S['stage'] == stg_val) & S['alive']
                if not cell_mask.any():
                    continue
                glow = STAGE_GLOW[stg_val]
                e    = S['energy'][cell_mask]
                bri  = glow * (0.5 + 0.5 * e)
                for c in range(3):
                    img[cell_mask, c] = np.clip(colour[c] * bri, 0, 1)

        self.im.set_data(np.clip(img, 0, 1))

    def update_plots(self, S, total_pop, sp_pops, diversity, avg_e):
        pd = list(S['pop_history'])
        self.pop_line.set_data(range(len(pd)), pd)
        self.ax2.set_xlim(0, max(1, len(pd)))
        self.ax2.set_ylim(0, max(10, max(pd) * 1.15) if pd else 10)

        for sp in range(NUM_SPECIES):
            sd_ = list(S['species_hist'][sp])
            self.species_lines[sp].set_data(range(len(sd_)), sd_)

        dd = list(S['diversity_hist'])
        ed = list(S['energy_hist'])
        self.div_line.set_data(range(len(dd)), dd)
        self.energy_line.set_data(range(len(ed)), ed)
        self.ax4.set_xlim(0, max(1, len(dd)))
        y_max = max(1.0, max(max(dd, default=0.5), max(ed, default=0.5)) * 1.2)
        self.ax4.set_ylim(0, y_max)

        active_sp = sum(1 for p in sp_pops if p > 0)
        rec_status = "🔴 REC" if S['recording'] else "OFF"
        lines = [
            "══════ EVOLUTIONARY CA ══════", "",
            f"  Generation   {S['generation']:>6}",
            f"  Population   {total_pop:>6}",
            f"  Species      {active_sp}/{NUM_SPECIES}",
            f"  Shannon H′   {diversity:>6.3f}",
            f"  Avg Energy   {avg_e:>6.3f}",
            f"  Recording    {rec_status}", "",
            "── Species ──────────────────",
        ]
        for sp in range(NUM_SPECIES):
            bar = '█' * min(25, sp_pops[sp] // max(1, total_pop // 25 + 1))
            lines.append(f"  Sp{sp} {sp_pops[sp]:>5}  {bar}")
        lines += [
            "", "── Controls (Right Panel) ──",
        ]
        self.info_text.set_text('\n'.join(lines))

    def get_fig(self):
        return self.fig

    def get_ax1(self):
        return self.ax1