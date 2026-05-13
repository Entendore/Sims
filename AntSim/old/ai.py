import random
import math
from collections import defaultdict
from config import SCOUT, WORKER, SOLDIER, FOOD_P, PW, PH, GW, GH
from utils import dist, p2g

class MDPDecisionMaker:
    def __init__(self, ant_type):
        self.ant_type = ant_type
        self.q = defaultdict(lambda: defaultdict(float))
        self.lr = 0.1
        self.gamma = 0.9
        self.eps = {SCOUT: 0.35, WORKER: 0.10, SOLDIER: 0.15}[ant_type]
        self.eps_decay = 0.9999
        self.eps_min = 0.05

    def state_key(self, ant, spots, nx, ny, phero, preds):
        has_food = ant.has_food
        fleeing = ant.state == "fleeing"
        food_near = any(s.food_amount > 0 and dist(ant.x, ant.y, s.x, s.y) < ant.detect_range for s in spots)
        danger = 0
        for p in preds:
            d = dist(ant.x, ant.y, p.x, p.y)
            if d < 80: danger = min(2, int(d / 40) + 1)
        gx, gy = p2g(ant.x, ant.y)
        phero_strong = False
        for dx in range(-4, 5):
            for dy in range(-4, 5):
                ax, ay = gx + dx, gy + dy
                if 0 <= ax < PW and 0 <= ay < PH and phero[ay, ax, FOOD_P] > 1.5:
                    phero_strong = True; break
            if phero_strong: break
        near_nest = dist(ant.x, ant.y, nx, ny) < 100
        return (has_food, fleeing, food_near, danger, phero_strong, near_nest)

    def actions(self, ant):
        if ant.state == "fleeing": return ["flee", "hide", "confront"]
        if ant.has_food: return ["return_to_nest", "follow_pheromone", "explore"]
        return ["search_food", "follow_pheromone", "explore", "patrol"]

    def reward(self, ant, act, info):
        r = 0
        if act == "return_to_nest" and ant.has_food: r += 5
        elif act == "search_food" and info.get("found_food"): r += 10
        elif act == "follow_pheromone" and info.get("found_trail"): r += 3
        elif act == "flee" and info.get("avoided_danger"): r += 8
        elif act == "confront" and ant.ant_type == SOLDIER and info.get("protected"): r += 15
        elif act == "explore" and info.get("found_new"): r += 4
        if info.get("in_danger"): r -= 10
        if info.get("followed_danger"): r -= 8
        return r

    def choose(self, state, acts):
        if random.random() < self.eps: return random.choice(acts)
        return max(acts, key=lambda a: self.q[state][a])

    def update(self, s, a, r, s2, acts2):
        mx = max((self.q[s2][a2] for a2 in acts2), default=0)
        self.q[s][a] += self.lr * (r + self.gamma * mx - self.q[s][a])
        self.eps = max(self.eps_min, self.eps * self.eps_decay)


class MCTSAgent:
    def __init__(self, ant, sims=15):
        self.ant = ant
        self.sims = sims

    class Node:
        __slots__ = ['pos', 'parent', 'action', 'children', 'visits', 'value', 'terminal']
        def __init__(self, pos, parent=None, action=None):
            self.pos = pos; self.parent = parent; self.action = action
            self.children = []; self.visits = 0; self.value = 0; self.terminal = False

    def _eval(self, pos, target, phero):
        x, y = pos; score = 0
        if target.get("position"):
            tx, ty = target["position"]
            score += 100 / (1 + dist(x, y, tx, ty))
        gx, gy = p2g(x, y)
        if 0 <= gx < PW and 0 <= gy < PH:
            score += phero[gy, gx, FOOD_P] * 5
        for o in target.get("obstacles", []):
            d = o.distance_to(x, y)
            if d < 20: score -= (20 - d) * 2
        return score

    def _sim_step(self, pos, angle, obs, steps=5):
        x, y = pos
        for _ in range(steps):
            nx2 = x + math.cos(angle) * self.ant.speed
            ny2 = y + math.sin(angle) * self.ant.speed
            if nx2 < 0 or nx2 > GW or ny2 < 0 or ny2 > GH: break
            if any(o.collides_with(nx2, ny2) for o in obs): break
            x, y = nx2, ny2
        return (x, y)

    def search(self, target, obs, phero):
        if not target or not target.get("position"): return None
        root = self.Node((self.ant.x, self.ant.y))
        angles = [i * math.pi / 4 for i in range(8)]
        for _ in range(self.sims):
            node = root
            while node.children and not node.terminal:
                tot = sum(c.visits for c in node.children) or 1
                node = max(node.children,
                           key=lambda c: float('inf') if c.visits == 0
                           else c.value / c.visits + math.sqrt(2 * math.log(tot) / c.visits))
            if not node.terminal:
                for a in angles:
                    np_ = self._sim_step(node.pos, a, obs, 3)
                    ch = self.Node(np_, node, a)
                    x, y = np_
                    if x < 0 or x > GW or y < 0 or y > GH: ch.terminal = True
                    elif any(o.collides_with(x, y) for o in obs): ch.terminal = True
                    node.children.append(ch)
                node = random.choice(node.children) if node.children else node
            result = self._eval(node.pos, target, phero)
            while node:
                node.visits += 1; node.value += result; node = node.parent
        if root.children:
            return max(root.children, key=lambda c: c.value / max(1, c.visits)).action
        return None