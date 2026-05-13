# map_gen.py
"""
Procedural terrain, river, and resource generation.
"""
import random
from hex_utils import hex_distance, hex_neighbors, generate_hex_grid
from data import TERRAINS, RESOURCE_CHANCES


def generate_terrain(radius):
    terrain = {}
    grid = list(generate_hex_grid(radius))
    elev_seeds = [(random.choice(grid), random.uniform(-1, 1)) for _ in range(max(5, radius))]
    moist_seeds = [(random.choice(grid), random.uniform(-1, 1)) for _ in range(max(5, radius))]
    for h in grid:
        e_num = sum(v / (hex_distance(*h, *s) + 1) ** 2 for s, v in elev_seeds)
        e_den = sum(1.0 / (hex_distance(*h, *s) + 1) ** 2 for s, _ in elev_seeds)
        e = e_num / e_den if e_den else 0
        m_num = sum(v / (hex_distance(*h, *s) + 1) ** 2 for s, v in moist_seeds)
        m_den = sum(1.0 / (hex_distance(*h, *s) + 1) ** 2 for s, _ in moist_seeds)
        m = m_num / m_den if m_den else 0
        if e > 0.6:
            terrain[h] = "mountain"
        elif e > 0.45:
            terrain[h] = "hills"
        elif e < -0.5:
            terrain[h] = "water"
        elif e < -0.3:
            terrain[h] = "coast"
        elif m > 0.4:
            terrain[h] = "jungle"
        elif m > 0.2:
            terrain[h] = "forest"
        elif m > 0.0:
            terrain[h] = "plains"
        elif m > -0.2:
            terrain[h] = "desert"
        else:
            terrain[h] = "tundra"
        if terrain[h] == "mountain" and random.random() < 0.15:
            terrain[h] = "volcano"
        elif terrain[h] in ("plains", "forest") and random.random() < 0.03:
            terrain[h] = "swamp"
    return terrain


def generate_rivers(terrain):
    """Generate river hexes flowing from high elevation to water."""
    rivers = set()
    mountains = [h for h, t in terrain.items() if t in ("mountain", "hills", "volcano")]
    water_hexes = {h for h, t in terrain.items() if t in ("water", "coast")}
    if not mountains or not water_hexes:
        return rivers
    num_rivers = random.randint(3, max(3, len(mountains) // 3))
    starts = random.sample(mountains, min(len(mountains), num_rivers))
    for start in starts:
        current = start
        visited = {current}
        for _ in range(25):
            nbrs = [n for n in hex_neighbors(*current) if n in terrain and n not in visited]
            if not nbrs:
                break
            nbrs.sort(key=lambda n: min(hex_distance(*n, *w) for w in water_hexes))
            pick = min(2, len(nbrs) - 1)
            next_hex = nbrs[random.randint(0, max(0, pick))]
            if terrain[next_hex] not in ("mountain", "volcano"):
                rivers.add(next_hex)
            visited.add(next_hex)
            current = next_hex
            if terrain[current] in ("water", "coast"):
                break
    return rivers


def generate_resources(terrain):
    resources = {}
    for h, t in terrain.items():
        for res, ch in RESOURCE_CHANCES.get(t, {}).items():
            if random.random() < ch:
                resources[h] = res
                break
    return resources