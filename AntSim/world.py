import random
import math
import numpy as np
from config import (NEST_SIZE, SPOT_SIZE, PH, PW, GW, GH, 
                    PREDATOR_COUNT, ANT_COUNT, 
                    SCOUT, WORKER, SOLDIER, MAX_FOOD)
from utils import dist
from obstacle import Obstacle
from food import FeedingSpot
from predator import Predator
from ant import Ant
from colony import Colony
from PySide6.QtGui import QImage

def _river_y(x):
    return GH * 0.33 + math.sin(x * 0.007) * 70 + math.sin(x * 0.003) * 40

def _river_y_arr(x):
    return GH * 0.33 + np.sin(x * 0.007) * 70 + np.sin(x * 0.003) * 40

def _generate_terrain():
    scale = 2
    sw, sh = GW // scale, GH // scale
    yc, xc = np.mgrid[0:sh, 0:sw]
    xf = xc.astype(np.float32) * scale
    yf = yc.astype(np.float32) * scale
    cx, cy = GW / 2.0, GH / 2.0

    noise = (np.sin(xf * 0.013) * 10 + np.cos(yf * 0.017) * 8 +
             np.sin((xf + yf) * 0.009) * 6 + np.sin(xf * 0.041) * 3 + np.cos(yf * 0.037) * 3)

    r = 108.0 + noise * 0.4
    g = 168.0 + noise
    b = 88.0 + noise * 0.25

    # Biome tints
    fd = np.sqrt((xf - GW * 0.18)**2 + (yf - GH * 0.18)**2)
    ff = np.clip(1 - fd / 280, 0, 1) * ((xf < GW * 0.42) & (yf < GH * 0.48))
    r -= ff * 45; g -= ff * 15; b -= ff * 40

    rd = np.sqrt((xf - GW * 0.82)**2 + (yf - GH * 0.78)**2)
    rf = np.clip(1 - rd / 320, 0, 1) * ((xf > GW * 0.58) & (yf > GH * 0.52))
    r += rf * 30; g -= rf * 30; b -= rf * 40

    md = np.sqrt((xf - GW * 0.2)**2 + (yf - GH * 0.78)**2)
    mf = np.clip(1 - md / 300, 0, 1)
    g += mf * 35; r += mf * 15; b += mf * 5

    md2 = np.sqrt((xf - GW * 0.82)**2 + (yf - GH * 0.22)**2)
    mf2 = np.clip(1 - md2 / 250, 0, 1)
    g += mf2 * 25; r += mf2 * 10

    nd = np.sqrt((xf - cx)**2 + (yf - cy)**2)
    cf = np.clip(1 - nd / 130, 0, 1)**0.7
    r = r * (1 - cf) + 175 * cf; g = g * (1 - cf) + 210 * cf; b = b * (1 - cf) + 135 * cf

    # River
    rc = _river_y_arr(xf)
    rdist = np.abs(yf - rc)
    rm = rdist < 22
    re = (rdist >= 22) & (rdist < 32)
    bl = np.clip(1 - (rdist[re] - 22) / 10, 0, 1)
    r[rm] = 42; g[rm] = 115; b[rm] = 190
    r[re] = r[re] * (1 - bl) + 42 * bl; g[re] = g[re] * (1 - bl) + 115 * bl; b[re] = b[re] * (1 - bl) + 190 * bl

    rng = np.random.RandomState(42)
    nt = rng.randint(-5, 6, (sh, sw, 3)).astype(np.int16)
    rgb = np.clip(np.stack([r, g, b], axis=2).astype(np.int16) + nt, 0, 255).astype(np.uint8)
    
    # Fix: Use positional arguments for np.repeat
    terrain = np.repeat(np.repeat(rgb, scale, axis=0), scale, axis=1)[:GH, :GW]
    
    # QImage needs row-major contiguous array
    return np.ascontiguousarray(terrain)

def init_world():
    nest_x, nest_y = GW // 2, GH // 2
    colony = Colony(nest_x, nest_y)

    obs = []
    crossing_xs = [GW * 0.25, GW * 0.55, GW * 0.80]
    crossing_hw = 28

    # River
    x = 15
    while x < GW - 15:
        near_ford = any(abs(x - cx) < crossing_hw for cx in crossing_xs)
        if not near_ford:
            ry = int(_river_y(x))
            o = Obstacle(circular=True, x=int(x), y=ry, style="water")
            o.radius = 22; o.width = 44; o.height = 44
            if dist(o.x, o.y, nest_x, nest_y) > NEST_SIZE + o.radius + 40: obs.append(o)
        x += 34

    # Forest
    for _ in range(10):
        for _ in range(40):
            tx = random.randint(40, int(GW * 0.38)); ty = random.randint(40, int(GH * 0.42))
            o = Obstacle(circular=True, x=tx, y=ty, style="tree")
            if dist(o.x, o.y, nest_x, nest_y) > NEST_SIZE + o.radius + 35:
                if not any(dist(o.x, o.y, e.x, e.y) < 30 for e in obs): obs.append(o); break

    # Rocks
    for _ in range(7):
        for _ in range(40):
            rx = random.randint(int(GW * 0.62), GW - 50); ry = random.randint(int(GH * 0.55), GH - 50)
            o = Obstacle(circular=False, x=rx, y=ry, style="rock")
            if dist(o.x, o.y, nest_x, nest_y) > NEST_SIZE + max(o.width, o.height) / 2 + 35:
                if not any(dist(o.x, o.y, e.x, e.y) < 45 for e in obs): obs.append(o); break

    # Scattered
    for _ in range(6):
        for _ in range(40):
            o = Obstacle(circular=random.random() < 0.4, style="rock")
            if dist(o.x, o.y, nest_x, nest_y) > NEST_SIZE + max(o.width, o.height) / 2 + 40:
                if not any(dist(o.x, o.y, e.x, e.y) < 40 for e in obs): obs.append(o); break

    # Food
    zone_configs = [
        (GW * 0.15, GH * 0.13, 70, 2, 1.0), (GW * 0.85, GH * 0.15, 60, 1, 0.8),
        (GW * 0.50, GH * 0.08, 50, 1, 0.7), (GW * 0.14, GH * 0.75, 80, 2, 1.2),
        (GW * 0.50, GH * 0.88, 60, 1, 1.0), (GW * 0.82, GH * 0.72, 65, 1, 0.8),
        (GW * 0.36, GH * 0.56, 50, 1, 1.0), (GW * 0.66, GH * 0.50, 50, 1, 1.0),
    ]
    spots = []
    for cx, cy, spread, count, fmult in zone_configs:
        for _ in range(count):
            for _ in range(60):
                sx = int(cx + random.randint(-int(spread), int(spread)))
                sy = int(cy + random.randint(-int(spread), int(spread)))
                sx = max(SPOT_SIZE + 5, min(GW - SPOT_SIZE - 5, sx))
                sy = max(SPOT_SIZE + 5, min(GH - SPOT_SIZE - 5, sy))
                s = FeedingSpot(sx, sy)
                s.initial_food = MAX_FOOD * fmult; s.food_amount = s.initial_food
                if s.valid(obs) and dist(s.x, s.y, nest_x, nest_y) > NEST_SIZE + SPOT_SIZE + 25:
                    spots.append(s); break

    # Predators
    pred_homes = [(GW * 0.25, GH * 0.45), (GW * 0.72, GH * 0.28), (GW * 0.90, GH * 0.60)]
    preds = []
    for i in range(PREDATOR_COUNT):
        tx, ty = pred_homes[i % len(pred_homes)]
        p = Predator(int(tx), int(ty))
        p.territory = (int(tx), int(ty)); p.territory_r = 180
        preds.append(p)

    # Ants
    ants = []
    for _ in range(ANT_COUNT):
        r = random.random()
        t = SCOUT if r < 0.30 else (WORKER if r < 0.70 else SOLDIER)
        ants.append(Ant(nest_x, nest_y, t))

    phero = np.zeros((PH, PW, 2), dtype=np.float32)
    terrain_data = _generate_terrain()

    # Construct QImage
    terrain_qimg = QImage(terrain_data.data, GW, GH, 3 * GW, QImage.Format_RGB888).copy()
    
    return colony, obs, spots, preds, ants, phero, terrain_qimg