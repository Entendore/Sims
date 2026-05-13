import math
from config import PHERO_RES

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def dist(x1, y1, x2, y2):
    return math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)

def p2g(x, y):
    return int(x / PHERO_RES), int(y / PHERO_RES)