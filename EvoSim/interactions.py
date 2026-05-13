# interactions.py
import numpy as np
from config import GRID_SIZE, BRUSH_RADIUS, NUM_SPECIES
from state import init_state

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
    elif k == 'z':
        S['show_zones'] = not S['show_zones']
    elif k in ('+', '='):
        S['volume'] = min(1.0, S['volume'] + 0.1)
    elif k == '-':
        S['volume'] = max(0.0, S['volume'] - 0.1)
    elif k == 's':
        n = np.random.randint(10, 40)
        xs = np.random.randint(0, GRID_SIZE, n)
        ys = np.random.randint(0, GRID_SIZE, n)
        S['alive'][xs, ys] = True
        S['energy'][xs, ys] = 0.4
        S['stage'][xs, ys] = 1
        S['age'][xs, ys] = 0
        S['species'][xs, ys] = np.random.randint(0, NUM_SPECIES, n).astype(np.int8)

def setup_interactions(fig, S, ax1):
    fig.canvas.mpl_connect('button_press_event', lambda event: on_click(event, S, ax1))
    fig.canvas.mpl_connect('key_press_event', lambda event: on_key(event, S))