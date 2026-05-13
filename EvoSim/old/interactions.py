# interactions.py
import numpy as np
from matplotlib.widgets import Slider, Button, CheckButtons
from Sims.EvoSim.old.config import GRID_SIZE, BRUSH_RADIUS, NUM_SPECIES
from Sims.EvoSim.old.state import init_state

def _apply_brush(S, x, y, alive_val):
    r = BRUSH_RADIUS
    for dx in range(-r, r + 1):
        for dy in range(-r, r + 1):
            nx, ny = x + dx, y + dy
            if 0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE and dx*dx + dy*dy <= r*r:
                S['alive'][nx, ny]  = alive_val
                if alive_val:
                    S['energy'][nx, ny] = 0.5
                    S['stage'][nx, ny]  = 1
                    S['age'][nx, ny]    = 0
                else:
                    S['stage'][nx, ny]  = 0
                    S['fade'][nx, ny]   = 0.5

def on_click(event, S, ax1):
    if event.inaxes is not ax1 or event.xdata is None:
        return
    gy, gx = int(round(event.ydata)), int(round(event.xdata))
    if not (0 <= gx < GRID_SIZE and 0 <= gy < GRID_SIZE):
        return
    if event.button == 1:
        _apply_brush(S, gx, gy, True)
    elif event.button == 3:
        _apply_brush(S, gx, gy, False)

def on_key(event, S):
    k = event.key
    if k == 'r':
        S.update(init_state())
    elif k == 'p':
        S['paused'] = not S['paused']
    elif k == 'd':
        cx, cy = np.random.randint(5, GRID_SIZE - 5, size=2)
        rad = 8
        yy, xx = np.ogrid[:GRID_SIZE, :GRID_SIZE]
        dm = ((xx - cx)**2 + (yy - cy)**2 < rad**2) & (np.random.rand(GRID_SIZE, GRID_SIZE) < 0.8)
        S['alive'][dm] = False; S['stage'][dm] = 0
        S['disaster_flash'] = 6
    elif k == 's':
        n = np.random.randint(10, 40)
        xs = np.random.randint(0, GRID_SIZE, n)
        ys = np.random.randint(0, GRID_SIZE, n)
        S['alive'][xs, ys] = True
        S['energy'][xs, ys] = 0.4
        S['stage'][xs, ys] = 1
        S['age'][xs, ys] = 0
        S['species'][xs, ys] = np.random.randint(0, NUM_SPECIES, n).astype(np.int8)

def setup_interactions(fig, S, ax1, recorder):
    # Mouse and Keyboard
    fig.canvas.mpl_connect('button_press_event', lambda event: on_click(event, S, ax1))
    fig.canvas.mpl_connect('key_press_event', lambda event: on_key(event, S))

    # --- Settings Tab (Widgets) ---
    # Background for the panel
    ax_panel_bg = fig.add_axes([0.74, 0.05, 0.24, 0.90])
    ax_panel_bg.set_title('Settings & Controls', color='#cccccc', fontsize=10)
    ax_panel_bg.set_xticks([]); ax_panel_bg.set_yticks([])
    ax_panel_bg.set_facecolor('#12121f')

    # Sliders
    ax_vol = fig.add_axes([0.78, 0.88, 0.16, 0.03])
    ax_mut = fig.add_axes([0.78, 0.82, 0.16, 0.03])
    
    s_vol = Slider(ax_vol, 'Volume', 0.0, 1.0, valinit=S['volume'], color='#4488ff')
    s_mut = Slider(ax_mut, 'Mutation', 0.0, 0.5, valinit=S['mutation_rate'], color='#44ff88')

    def update_vol(val): S['volume'] = val
    def update_mut(val): S['mutation_rate'] = val
    s_vol.on_changed(update_vol)
    s_mut.on_changed(update_mut)

    # Checkboxes
    ax_chk = fig.add_axes([0.77, 0.64, 0.14, 0.12])
    ax_chk.set_facecolor('#12121f')
    c_chk = CheckButtons(ax_chk, ['Sound On', 'Show Zones'], [S['sound_on'], S['show_zones']])
    
    def toggle_sound(label): S['sound_on'] = not S['sound_on']
    def toggle_zones(label): S['show_zones'] = not S['show_zones']
    c_chk.on_clicked(toggle_sound)
    c_chk.on_clicked(toggle_zones)

    # Buttons
    ax_rec = fig.add_axes([0.78, 0.54, 0.16, 0.06])
    ax_rst = fig.add_axes([0.78, 0.44, 0.16, 0.06])
    ax_dis = fig.add_axes([0.78, 0.34, 0.16, 0.06])
    ax_scat = fig.add_axes([0.78, 0.24, 0.16, 0.06])
    ax_pause = fig.add_axes([0.78, 0.14, 0.16, 0.06])

    b_rec = Button(ax_rec, 'Start Recording MP4', color='#331111', hovercolor='#662222')
    b_rst = Button(ax_rst, 'Reset Simulation', color='#112211', hovercolor='#226622')
    b_dis = Button(ax_dis, 'Trigger Disaster', color='#221111', hovercolor='#662222')
    b_scat = Button(ax_scat, 'Scatter Cells', color='#111122', hovercolor='#222266')
    b_pause = Button(ax_pause, 'Pause / Resume', color='#112211', hovercolor='#226622')

    def toggle_recording(event):
        if S['recording']:
            recorder.stop()
            S['recording'] = False
            b_rec.label.set_text('Start Recording MP4')
            ax_rec.set_facecolor('#331111')
        else:
            if recorder.start():
                S['recording'] = True
                b_rec.label.set_text('Stop Recording MP4')
                ax_rec.set_facecolor('#662222')
            else:
                print("Recording failed to start. Is `imageio` installed?")
                
    def reset_sim(event): S.update(init_state())
    def trigger_dis(event):
        cx, cy = np.random.randint(5, GRID_SIZE - 5, size=2)
        rad = 8
        yy, xx = np.ogrid[:GRID_SIZE, :GRID_SIZE]
        dm = ((xx - cx)**2 + (yy - cy)**2 < rad**2) & (np.random.rand(GRID_SIZE, GRID_SIZE) < 0.8)
        S['alive'][dm] = False; S['stage'][dm] = 0
        S['disaster_flash'] = 6
    def scatter(event): on_key(type('', (), {'key': 's'})(), S)
    def pause(event): S['paused'] = not S['paused']

    b_rec.on_clicked(toggle_recording)
    b_rst.on_clicked(reset_sim)
    b_dis.on_clicked(trigger_dis)
    b_scat.on_clicked(scatter)
    b_pause.on_clicked(pause)