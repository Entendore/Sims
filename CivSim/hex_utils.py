# hex_utils.py
"""
Hex-grid math: neighbors, distance, coordinate conversion, grid generation, rings.
"""
import math

HEX_DIRS = [(+1, 0), (+1, -1), (0, -1), (-1, 0), (-1, +1), (0, +1)]


def hex_neighbors(q, r):
    return [(q + dq, r + dr) for dq, dr in HEX_DIRS]


def hex_distance(q1, r1, q2, r2):
    return (abs(q1 - q2) + abs(q1 + r1 - q2 - r2) + abs(r1 - r2)) // 2


def hex_to_pixel(q, r, size=1.0):
    x = size * 3.0 / 2.0 * q
    y = size * math.sqrt(3) * (r + q / 2.0)
    return x, y


def pixel_to_hex(x, y, size=1.0):
    q = (2.0 / 3.0 * x) / size
    r = (-1.0 / 3.0 * x + math.sqrt(3) / 3.0 * y) / size
    s = -q - r
    rq, rr, rs = round(q), round(r), round(s)
    dq, dr, ds = abs(rq - q), abs(rr - r), abs(rs - s)
    if dq > dr and dq > ds:
        rq = -rr - rs
    elif dr > ds:
        rr = -rq - rs
    return int(rq), int(rr)


def generate_hex_grid(radius):
    return {
        (q, r)
        for q in range(-radius, radius + 1)
        for r in range(-radius, radius + 1)
        if -radius <= q + r <= radius
    }


def hex_ring(center_q, center_r, radius):
    if radius == 0:
        return [(center_q, center_r)]
    results = []
    q, r = center_q - radius, center_r + radius
    for i in range(6):
        for _ in range(radius):
            results.append((q, r))
            dq, dr = HEX_DIRS[i]
            q += dq
            r += dr
    return results


def hexes_in_range(center_q, center_r, radius):
    results = []
    for dq in range(-radius, radius + 1):
        for dr in range(max(-radius, -dq - radius), min(radius, -dq + radius) + 1):
            results.append((center_q + dq, center_r + dr))
    return results