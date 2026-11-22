import random
import numpy as np
from config import (OBSTACLE_COUNT, SPOT_COUNT, PREDATOR_COUNT, ANT_COUNT, 
                   NEST_SIZE, SPOT_SIZE, PH, PW, GW, GH, SCOUT, WORKER, SOLDIER)
from utils import dist
from obstacle import Obstacle
from food import FeedingSpot
from predator import Predator
from ant import Ant
from colony import Colony

def init_world():
    nest_x, nest_y = GW // 2, GH // 2
    colony = Colony(nest_x, nest_y)

    obs = []
    for _ in range(OBSTACLE_COUNT):
        for _ in range(50):
            o = Obstacle(circular=random.random() < 0.3)
            if dist(o.x, o.y, nest_x, nest_y) > NEST_SIZE + max(o.width, o.height) / 2 + 30:
                obs.append(o); break

    spots = []
    for _ in range(SPOT_COUNT):
        for _ in range(50):
            s = FeedingSpot()
            if s.valid(obs) and dist(s.x, s.y, nest_x, nest_y) > NEST_SIZE + SPOT_SIZE + 20:
                spots.append(s); break

    preds = [Predator() for _ in range(PREDATOR_COUNT)]

    ants = []
    for _ in range(ANT_COUNT):
        r = random.random()
        t = SCOUT if r < 0.35 else (WORKER if r < 0.7 else SOLDIER)
        ants.append(Ant(nest_x, nest_y, t))

    phero = np.zeros((PH, PW, 2), dtype=np.float32)
    return colony, obs, spots, preds, ants, phero