import pygame
import random
import math
import numpy as np
from collections import deque, defaultdict
import sys

pygame.init()

# ===================== CONSTANTS =====================
WIDTH, HEIGHT = 1200, 750
PANEL_W = 280
GW = WIDTH - PANEL_W   # Game area width
GH = HEIGHT             # Game area height

PHERO_RES = 4           # Pheromone grid resolution (lower = faster)
PW = GW // PHERO_RES    # Pheromone grid width
PH = GH // PHERO_RES    # Pheromone grid height

ANT_COUNT = 60
SPOT_COUNT = 6
OBSTACLE_COUNT = 8
PREDATOR_COUNT = 2

ANT_SIZE = 5
SPOT_SIZE = 20
NEST_SIZE = 35
ANT_SPEED = 2
DETECT_RANGE = 80
COLLECT_RATE = 0.5
MAX_FOOD = 15
PHERO_EVAP = 0.995

SCOUT, WORKER, SOLDIER = 0, 1, 2
FOOD_P, DANGER_P = 0, 1

# Colors
WHITE      = (255, 255, 255)
BLACK      = (0, 0, 0)
BROWN      = (139, 69, 19)
GREEN      = (34, 139, 34)
RED        = (255, 0, 0)
YELLOW     = (255, 255, 0)
BLUE       = (0, 0, 255)
GRAY       = (128, 128, 128)
PURPLE     = (128, 0, 128)
ORANGE     = (255, 165, 0)
DARK_RED   = (139, 0, 0)
CYAN       = (0, 200, 200)
DARK_GRAY  = (64, 64, 64)
LIGHT_GRAY = (192, 192, 192)
NEST_INNER = (210, 180, 140)
PANEL_BG   = (30, 30, 40)
PANEL_TEXT  = (200, 200, 210)
PANEL_ACC  = (70, 170, 70)
RAIN_CLR   = (100, 149, 237)

# Fonts
FONT_SM    = pygame.font.SysFont("consolas", 14)
FONT_MD    = pygame.font.SysFont("consolas", 18)
FONT_LG    = pygame.font.SysFont("consolas", 24)
FONT_TITLE = pygame.font.SysFont("consolas", 28, bold=True)

# Surfaces
screen       = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Advanced Ant Colony Simulation — MDP & MCTS")
clock        = pygame.time.Clock()
game_surf    = pygame.Surface((GW, GH))
panel_surf   = pygame.Surface((PANEL_W, HEIGHT))
night_surf   = pygame.Surface((GW, GH), pygame.SRCALPHA)


# ===================== HELPERS =====================
def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def dist(x1, y1, x2, y2):
    return math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)

def p2g(x, y):
    """Pixel coords to pheromone grid coords."""
    return int(x / PHERO_RES), int(y / PHERO_RES)


# ===================== OBSTACLE =====================
class Obstacle:
    def __init__(self, circular=False, x=None, y=None):
        self.circular = circular
        self.color = (random.randint(100, 140),) * 3
        if circular:
            self.radius = random.randint(25, 55)
            self.x = x if x else random.randint(self.radius + 10, GW - self.radius - 10)
            self.y = y if y else random.randint(self.radius + 10, GH - self.radius - 10)
            self.width = self.radius * 2
            self.height = self.radius * 2
        else:
            self.width = random.randint(40, 120)
            self.height = random.randint(40, 120)
            self.x = x if x else random.randint(self.width // 2 + 10, GW - self.width // 2 - 10)
            self.y = y if y else random.randint(self.height // 2 + 10, GH - self.height // 2 - 10)
            self.radius = 0
            self.points = [
                (self.x - self.width // 2, self.y - self.height // 2),
                (self.x + self.width // 2, self.y - self.height // 2),
                (self.x + self.width // 2, self.y + self.height // 2),
                (self.x - self.width // 2, self.y + self.height // 2),
            ]

    def collides_with(self, x, y, buf=5):
        if self.circular:
            return dist(self.x, self.y, x, y) < self.radius + buf
        return (self.x - self.width / 2 - buf <= x <= self.x + self.width / 2 + buf and
                self.y - self.height / 2 - buf <= y <= self.y + self.height / 2 + buf)

    def distance_to(self, x, y):
        if self.circular:
            return max(0, dist(self.x, self.y, x, y) - self.radius)
        dx = max(self.x - self.width / 2 - x, 0, x - (self.x + self.width / 2))
        dy = max(self.y - self.height / 2 - y, 0, y - (self.y + self.height / 2))
        return math.sqrt(dx * dx + dy * dy)

    def draw(self, surf):
        if self.circular:
            pygame.draw.circle(surf, self.color, (int(self.x), int(self.y)), self.radius)
            pygame.draw.circle(surf, BLACK, (int(self.x), int(self.y)), self.radius, 2)
            for a in range(0, 360, 45):
                ex = self.x + math.cos(math.radians(a)) * self.radius * 0.7
                ey = self.y + math.sin(math.radians(a)) * self.radius * 0.7
                pygame.draw.line(surf, DARK_GRAY, (int(self.x), int(self.y)), (int(ex), int(ey)), 1)
        else:
            pygame.draw.polygon(surf, self.color, self.points)
            pygame.draw.polygon(surf, BLACK, self.points, 2)
            for row in range(int(self.y - self.height / 2) + 8, int(self.y + self.height / 2), 12):
                pygame.draw.line(surf, DARK_GRAY,
                                 (int(self.x - self.width / 2), row),
                                 (int(self.x + self.width / 2), row), 1)


# ===================== PREDATOR =====================
class Predator:
    def __init__(self, x=None, y=None):
        self.x = x if x else random.randint(60, GW - 60)
        self.y = y if y else random.randint(60, GH - 60)
        self.size = 15
        self.speed = 1.2
        self.angle = random.uniform(0, 2 * math.pi)
        self.detect_range = 120
        self.cooldown = 0
        self.attack_power = 3
        self.stamina = 100.0
        self.max_stamina = 100.0
        self.territory = (self.x, self.y)
        self.territory_r = 200
        self.kills = 0

    def update(self, ants, phero, predators):
        if self.cooldown > 0:
            self.cooldown -= 1
        self.stamina = min(self.max_stamina, self.stamina + 0.3)

        if random.random() < 0.02:
            self.angle += random.uniform(-math.pi / 4, math.pi / 4)

        # Pack hunting: move toward nearby ally
        ally = min((p for p in predators if p is not self),
                   key=lambda p: dist(self.x, self.y, p.x, p.y), default=None)
        ally_d = dist(self.x, self.y, ally.x, ally.y) if ally else 999

        target = None
        md = self.detect_range if self.stamina > 20 else self.detect_range * 0.5
        for a in ants:
            d = dist(self.x, self.y, a.x, a.y)
            if d < md and not a.has_food:
                md = d
                target = a

        if target and self.stamina > 10:
            ta = math.atan2(target.y - self.y, target.x - self.x)
            diff = ta - self.angle
            while diff > math.pi:  diff -= 2 * math.pi
            while diff < -math.pi: diff += 2 * math.pi
            self.angle += diff * 0.15
            self.stamina -= 0.2
        elif ally and ally_d < 150:
            ta = math.atan2(ally.y - self.y, ally.x - self.x)
            self.angle = self.angle * 0.7 + ta * 0.3
        else:
            td = dist(self.x, self.y, *self.territory)
            if td > self.territory_r:
                ta = math.atan2(self.territory[1] - self.y, self.territory[0] - self.x)
                self.angle = self.angle * 0.9 + ta * 0.1
            self.angle += random.uniform(-0.05, 0.05)

        spd = self.speed * (0.5 if self.stamina < 20 else 1.0)
        self.x += math.cos(self.angle) * spd
        self.y += math.sin(self.angle) * spd

        if self.x < self.size:           self.x = self.size;           self.angle = math.pi - self.angle
        elif self.x > GW - self.size:    self.x = GW - self.size;      self.angle = math.pi - self.angle
        if self.y < self.size:           self.y = self.size;           self.angle = -self.angle
        elif self.y > GH - self.size:    self.y = GH - self.size;      self.angle = -self.angle

        if self.cooldown <= 0:
            killed = []
            for a in ants:
                if dist(self.x, self.y, a.x, a.y) < self.size + ANT_SIZE + 5:
                    if a.ant_type == SOLDIER and random.random() < 0.5:
                        self.stamina -= 15
                        self._danger(phero, a.x, a.y, 6)
                    else:
                        killed.append(a)
                        self.kills += 1
                    if len(killed) >= self.attack_power:
                        break
            for a in killed:
                if a in ants: ants.remove(a)
            if killed:
                self.cooldown = 60
                self._danger(phero, self.x, self.y, 10)

    def _danger(self, phero, x, y, radius):
        gx, gy = p2g(x, y)
        rg = radius // PHERO_RES + 1
        for dx in range(-rg, rg + 1):
            for dy in range(-rg, rg + 1):
                nx, ny = gx + dx, gy + dy
                if 0 <= nx < PW and 0 <= ny < PH:
                    d = math.sqrt(dx * dx + dy * dy)
                    if d < rg:
                        phero[ny, nx, DANGER_P] += 2.0 * (1 - d / rg)

    def draw(self, surf):
        pygame.draw.circle(surf, DARK_RED, (int(self.x), int(self.y)), self.size)
        for s in (-0.5, 0.5):
            ex = self.x + math.cos(self.angle + s) * self.size * 0.5
            ey = self.y + math.sin(self.angle + s) * self.size * 0.5
            pygame.draw.circle(surf, YELLOW, (int(ex), int(ey)), 3)
            pygame.draw.circle(surf, BLACK, (int(ex), int(ey)), 1)
        mx = self.x + math.cos(self.angle) * self.size * 0.7
        my = self.y + math.sin(self.angle) * self.size * 0.7
        pygame.draw.circle(surf, BLACK, (int(mx), int(my)), 4)
        # Stamina bar
        bw = self.size * 2
        bx, by = self.x - bw / 2, self.y - self.size - 8
        r = self.stamina / self.max_stamina
        pygame.draw.rect(surf, DARK_GRAY, (int(bx), int(by), int(bw), 3))
        c = RED if r < 0.3 else ORANGE if r < 0.6 else GREEN
        pygame.draw.rect(surf, c, (int(bx), int(by), int(bw * r), 3))


# ===================== MDP =====================
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


# ===================== MCTS =====================
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


# ===================== ANT =====================
class Ant:
    _id = 0

    def __init__(self, nx, ny, ant_type=WORKER):
        Ant._id += 1
        self.id = Ant._id
        self.x = nx + random.randint(-NEST_SIZE, NEST_SIZE)
        self.y = ny + random.randint(-NEST_SIZE, NEST_SIZE)
        self.angle = random.uniform(0, 2 * math.pi)
        self.has_food = False
        self.food_carrying = 0.0
        self.target = None
        self.returning = False
        self.path = deque(maxlen=25)
        self.ant_type = ant_type
        self.state = "exploring"
        self.flee_timer = 0
        self.age = 0
        self.max_age = random.randint(3600, 7200)

        cfg = {
            SCOUT:   dict(w=0.5, dr=DETECT_RANGE * 1.5, sp=ANT_SPEED * 1.2,
                          col=PURPLE, sz=ANT_SIZE, br=0.3, ce=0.7, ps=0.5, ms=15),
            WORKER:  dict(w=0.3, dr=DETECT_RANGE,       sp=ANT_SPEED,
                          col=BLACK, sz=ANT_SIZE, br=0.6, ce=1.0, ps=0.8, ms=20),
            SOLDIER: dict(w=0.2, dr=DETECT_RANGE * 0.8, sp=ANT_SPEED * 0.8,
                          col=RED,   sz=ANT_SIZE + 2, br=0.9, ce=0.5, ps=0.3, ms=10),
        }[ant_type]
        self.wander     = cfg["w"]
        self.detect_range = cfg["dr"]
        self.speed      = cfg["sp"]
        self.color      = cfg["col"]
        self.size       = cfg["sz"]
        self.bravery    = cfg["br"]
        self.collect_eff = cfg["ce"]
        self.phero_str  = cfg["ps"]

        self.mdp        = MDPDecisionMaker(ant_type)
        self.mcts       = MCTSAgent(self, sims=cfg["ms"])
        self.dec_cd     = 0
        self.action     = "explore"
        self.mcts_cd    = 0
        self.mcts_angle = None
        self.known_food = []

    def _sense(self, phero, channel, radius=5):
        gx, gy = p2g(self.x, self.y)
        best_dir, best_val = None, 0.5
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if dx == 0 and dy == 0: continue
                ax, ay = gx + dx, gy + dy
                if 0 <= ax < PW and 0 <= ay < PH:
                    v = phero[ay, ax, channel]
                    if v > best_val:
                        best_val = v
                        best_dir = math.atan2(dy * PHERO_RES, dx * PHERO_RES)
        return best_dir, best_val

    def _avoid(self, obs):
        closest = min(obs, key=lambda o: o.distance_to(self.x, self.y), default=None)
        if closest:
            md = closest.distance_to(self.x, self.y)
            if md < 30:
                dx, dy = self.x - closest.x, self.y - closest.y
                if dx == 0 and dy == 0: dx, dy = random.uniform(-1, 1), random.uniform(-1, 1)
                return math.atan2(dy, dx), (30 - md) / 30
        return self.angle, 0

    def _emit_food(self, phero, strength, radius=2):
        gx, gy = p2g(self.x, self.y)
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                ax, ay = gx + dx, gy + dy
                if 0 <= ax < PW and 0 <= ay < PH:
                    d = math.sqrt(dx * dx + dy * dy)
                    if d < radius:
                        phero[ay, ax, FOOD_P] += strength * (1 - d / radius)

    def _deposit_path(self, phero):
        for px, py in self.path:
            gx, gy = p2g(px, py)
            if 0 <= gx < PW and 0 <= gy < PH:
                phero[gy, gx, FOOD_P] += self.phero_str * 0.5

    def update(self, spots, nx, ny, phero, obs, preds, day_f, rain_f):
        self.age += 1
        self.path.append((int(self.x), int(self.y)))

        if self.flee_timer > 0:
            self.flee_timer -= 1
            if self.flee_timer <= 0: self.state = "exploring"

        if self.state != "fleeing":
            dd, dv = self._sense(phero, DANGER_P, 8)
            if dv > 2.0 and random.random() > self.bravery:
                self.state = "fleeing"; self.flee_timer = 120
                if dd is not None: self.angle = dd

        if self.dec_cd <= 0:
            sk = self.mdp.state_key(self, spots, nx, ny, phero, preds)
            acts = self.mdp.actions(self)
            self.action = self.mdp.choose(sk, acts)
            info = {
                "found_food": any(s.food_amount > 0 and dist(self.x, self.y, s.x, s.y) < 30 for s in spots),
                "in_danger": any(dist(self.x, self.y, p.x, p.y) < 50 for p in preds),
                "found_trail": self._sense(phero, FOOD_P)[1] > 1.5,
                "avoided_danger": not any(dist(self.x, self.y, p.x, p.y) < 50 for p in preds) and self.state == "fleeing",
                "protected": self.ant_type == SOLDIER and any(dist(self.x, self.y, p.x, p.y) < 80 for p in preds),
                "found_new": random.random() < 0.1,
                "followed_danger": False,
            }
            rw = self.mdp.reward(self, self.action, info)
            sk2 = self.mdp.state_key(self, spots, nx, ny, phero, preds)
            self.mdp.update(sk, self.action, rw, sk2, self.mdp.actions(self))
            self.dec_cd = 15
        else:
            self.dec_cd -= 1

        if self.mcts_cd > 0:
            self.mcts_cd -= 1

        if self.action == "flee":
            self.state = "fleeing"
            p = min(preds, key=lambda p: dist(self.x, self.y, p.x, p.y), default=None)
            if p: self.angle = math.atan2(self.y - p.y, self.x - p.x)
        elif self.action == "hide":
            self.state = "fleeing"
            o = min(obs, key=lambda o: o.distance_to(self.x, self.y), default=None)
            if o: self.angle = math.atan2(o.y - self.y, o.x - self.x)
        elif self.action == "confront" and self.ant_type == SOLDIER:
            p = min(preds, key=lambda p: dist(self.x, self.y, p.x, p.y), default=None)
            if p and dist(self.x, self.y, p.x, p.y) < 100:
                self.angle = math.atan2(p.y - self.y, p.x - self.x)

        food_returned = 0
        if self.has_food and dist(self.x, self.y, nx, ny) < NEST_SIZE:
            food_returned = self.food_carrying
            self.has_food = False; self.food_carrying = 0
            self.returning = False
            self.angle = random.uniform(0, 2 * math.pi)
            self.state = "exploring"

        if not self.has_food and not self.returning and self.state != "fleeing":
            cs = None; md = self.detect_range
            for s in spots:
                if s.food_amount > 0:
                    d = dist(self.x, self.y, s.x, s.y)
                    if d < md: md = d; cs = s
            if not cs:
                for fx, fy in self.known_food:
                    d = dist(self.x, self.y, fx, fy)
                    if d < md:
                        for s in spots:
                            if s.food_amount > 0 and dist(fx, fy, s.x, s.y) < SPOT_SIZE:
                                md = d; cs = s; break

            if cs:
                self.target = cs
                if self.action in ("search_food", "follow_pheromone") and self.mcts_cd <= 0:
                    ti = {"type": "food", "position": (cs.x, cs.y), "obstacles": obs}
                    ma = self.mcts.search(ti, obs, phero)
                    self.mcts_angle = ma; self.mcts_cd = 10
                if self.mcts_angle is not None:
                    self.angle = self.mcts_angle
                else:
                    self.angle = math.atan2(cs.y - self.y, cs.x - self.x)
                self.state = "foraging"
            else:
                self.mcts_angle = None
                if self.action == "follow_pheromone":
                    pd, pv = self._sense(phero, FOOD_P)
                    if pv > 1.0 and pd is not None:
                        self.angle = pd; self.state = "following_pheromone"
                    else:
                        self.angle += random.uniform(-self.wander, self.wander)
                        self.state = "exploring"
                elif self.action == "patrol":
                    if random.random() < 0.1: self.angle = random.uniform(0, 2 * math.pi)
                    self.state = "patrolling"
                else:
                    self.angle += random.uniform(-self.wander, self.wander)
                    self.state = "exploring"

        elif self.returning:
            if self.action == "return_to_nest" and self.mcts_cd <= 0:
                ti = {"type": "nest", "position": (nx, ny), "obstacles": obs}
                ma = self.mcts.search(ti, obs, phero)
                self.mcts_angle = ma; self.mcts_cd = 10
            if self.mcts_angle is not None:
                self.angle = self.mcts_angle
            else:
                self.angle = math.atan2(ny - self.y, nx - self.x)
            self.state = "returning"
            self._deposit_path(phero)

        if self.target and not self.has_food:
            if dist(self.x, self.y, self.target.x, self.target.y) < SPOT_SIZE:
                amt = min(COLLECT_RATE * self.collect_eff, self.target.food_amount)
                self.target.food_amount -= amt
                self.food_carrying = amt; self.has_food = True
                self.returning = True; self.target = None
                self._emit_food(phero, 1.5 * self.collect_eff)

        aa, ab = self._avoid(obs)
        if ab > 0: self.angle = self.angle * (1 - ab) + aa * ab

        if self.ant_type == SOLDIER and self.state == "fleeing" and random.random() < 0.05:
            self.flee_timer = max(0, self.flee_timer - 30)

        spd = self.speed * (0.7 + 0.3 * day_f) * (0.8 if rain_f else 1.0) * (1.5 if self.state == "fleeing" else 1.0)
        self.x += math.cos(self.angle) * spd
        self.y += math.sin(self.angle) * spd

        if self.x < 0:   self.x = 0;   self.angle = math.pi - self.angle
        elif self.x > GW: self.x = GW;  self.angle = math.pi - self.angle
        if self.y < 0:   self.y = 0;   self.angle = -self.angle
        elif self.y > GH: self.y = GH;  self.angle = -self.angle

        for o in obs:
            if o.collides_with(self.x, self.y, 0):
                dx, dy = self.x - o.x, self.y - o.y
                d = math.sqrt(dx * dx + dy * dy) or 0.1
                buf = (o.radius if o.circular else max(o.width, o.height) / 2) + 5
                self.x = o.x + dx / d * buf
                self.y = o.y + dy / d * buf

        return food_returned

    def is_dead(self):
        return self.age >= self.max_age

    def communicate(self, other, spots):
        for s in spots:
            if s.food_amount > 0:
                loc = (s.x, s.y)
                if loc not in other.known_food:
                    other.known_food.append(loc)
        if len(other.known_food) > 5:
            other.known_food = other.known_food[-5:]

    def draw(self, surf, selected=False):
        c = ORANGE if self.has_food else self.color
        ix, iy = int(self.x), int(self.y)
        bx = self.x - math.cos(self.angle) * self.size * 0.6
        by = self.y - math.sin(self.angle) * self.size * 0.6
        hx = self.x + math.cos(self.angle) * self.size * 0.6
        hy = self.y + math.sin(self.angle) * self.size * 0.6
        pygame.draw.circle(surf, c, (int(bx), int(by)), self.size)       
        pygame.draw.circle(surf, c, (ix, iy), self.size - 1)             
        pygame.draw.circle(surf, c, (int(hx), int(hy)), self.size - 2)   
        for s in (-0.4, 0.4):
            ax = hx + math.cos(self.angle + s) * self.size * 1.8
            ay = hy + math.sin(self.angle + s) * self.size * 1.8
            pygame.draw.line(surf, c, (int(hx), int(hy)), (int(ax), int(ay)), 1)
        if self.state == "fleeing":
            pygame.draw.circle(surf, RED, (ix, iy), self.size + 3, 2)
        elif self.state == "foraging":
            pygame.draw.circle(surf, GREEN, (ix, iy), self.size + 3, 2)
        elif self.state == "returning":
            pygame.draw.circle(surf, YELLOW, (ix, iy), self.size + 3, 2)
        if self.ant_type == SCOUT:
            pygame.draw.circle(surf, PURPLE, (ix, iy), self.size + 1, 1)
        elif self.ant_type == SOLDIER:
            pygame.draw.circle(surf, RED, (ix, iy), self.size + 2, 1)
        if selected:
            pygame.draw.circle(surf, CYAN, (ix, iy), self.size + 6, 2)


# ===================== FEEDING SPOT =====================
class FeedingSpot:
    def __init__(self, x=None, y=None):
        self.x = x if x else random.randint(SPOT_SIZE + 10, GW - SPOT_SIZE - 10)
        self.y = y if y else random.randint(SPOT_SIZE + 10, GH - SPOT_SIZE - 10)
        self.food_amount = MAX_FOOD
        self.initial_food = MAX_FOOD
        self.regen_rate = 0.01

    def update(self, day_f):
        if self.food_amount < self.initial_food:
            self.food_amount = min(self.initial_food, self.food_amount + self.regen_rate * day_f)

    def valid(self, obs):
        return not any(o.collides_with(self.x, self.y, SPOT_SIZE) for o in obs)

    def draw(self, surf):
        r = self.food_amount / self.initial_food
        if r > 0.5: cr, cg = int(255 * (1 - (r - 0.5) * 2)), 255
        else: cr, cg = 255, int(255 * r * 2)
        pygame.draw.circle(surf, (cr, cg, 0), (int(self.x), int(self.y)), SPOT_SIZE)
        pygame.draw.circle(surf, BLACK, (int(self.x), int(self.y)), SPOT_SIZE, 1)
        for a in range(0, 360, 60):
            lx = self.x + math.cos(math.radians(a)) * SPOT_SIZE * 0.5
            ly = self.y + math.sin(math.radians(a)) * SPOT_SIZE * 0.5
            pygame.draw.circle(surf, DARK_RED, (int(lx), int(ly)), 2)
        t = FONT_SM.render(f"{self.food_amount:.1f}", True, BLACK)
        surf.blit(t, (self.x - t.get_width() // 2, self.y - t.get_height() // 2))


# ===================== COLONY =====================
class Colony:
    def __init__(self, nx, ny):
        self.nx, self.ny = nx, ny
        self.food_storage = 0.0
        self.total_collected = 0.0
        self.ants_lost = 0
        self.ants_born = 0
        self.spawn_cost = 10
        self.spawn_cd = 0
        self.spawn_interval = 120

    def deposit(self, amt):
        self.food_storage += amt
        self.total_collected += amt

    def can_spawn(self):
        return self.food_storage >= self.spawn_cost and self.spawn_cd <= 0

    def spawn(self):
        self.food_storage -= self.spawn_cost
        self.spawn_cd = self.spawn_interval
        self.ants_born += 1
        r = random.random()
        t = SCOUT if r < 0.25 else (WORKER if r < 0.7 else SOLDIER)
        return Ant(self.nx, self.ny, t)

    def update(self):
        if self.spawn_cd > 0: self.spawn_cd -= 1

    def draw(self, surf):
        pygame.draw.circle(surf, BROWN, (int(self.nx), int(self.ny)), NEST_SIZE)
        pygame.draw.circle(surf, NEST_INNER, (int(self.nx), int(self.ny)), NEST_SIZE - 5)
        pygame.draw.circle(surf, DARK_GRAY, (int(self.nx), int(self.ny)), NEST_SIZE, 2)
        t = FONT_MD.render(f"{self.food_storage:.0f}", True, BLACK)
        surf.blit(t, (self.nx - t.get_width() // 2, self.ny - t.get_height() // 2))


# ===================== INITIALIZATION =====================
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

colony, obstacles, feeding_spots, predators, ants, pheromone_map = init_world()

# ===================== MAIN LOOP =====================
running = True
paused = False
show_food_phero = False
show_danger_phero = False
speed_mult = 1
selected_ant = None
frame_count = 0
day_length = 1800  # 30 seconds at 60fps

# Rain
is_raining = False
rain_timer = 0
rain_duration = 300
rain_drops = [(random.randint(0, GW), random.randint(0, GH)) for _ in range(150)]

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE: paused = not paused
            elif event.key == pygame.K_p: show_food_phero = not show_food_phero; show_danger_phero = False
            elif event.key == pygame.K_d: show_danger_phero = not show_danger_phero; show_food_phero = False
            elif event.key == pygame.K_UP: speed_mult = min(5, speed_mult + 1)
            elif event.key == pygame.K_DOWN: speed_mult = max(1, speed_mult - 1)
            elif event.key == pygame.K_r:
                colony, obstacles, feeding_spots, predators, ants, pheromone_map = init_world()
                selected_ant = None; frame_count = 0
        elif event.type == pygame.MOUSEBUTTONDOWN:
            mx, my = event.pos
            if mx < GW:
                selected_ant = None
                for a in ants:
                    if dist(a.x, a.y, mx, my) < 15:
                        selected_ant = a; break

    # Day/Night Cycle
    day_t = (frame_count % day_length) / day_length
    if day_t < 0.25: day_f = 1.0
    elif day_t < 0.5: day_f = 1.0 - (day_t - 0.25) * 4 * 0.5
    elif day_t < 0.75: day_f = 0.5
    else: day_f = 0.5 + (day_t - 0.75) * 4 * 0.5

    # Rain
    if not is_raining:
        if random.random() < 0.001:
            is_raining = True
            rain_timer = random.randint(120, rain_duration)
            rain_drops = [(random.randint(0, GW), random.randint(0, GH)) for _ in range(150)]
    else:
        rain_timer -= 1
        if rain_timer <= 0: is_raining = False

    if not paused:
        for _ in range(speed_mult):
            # Evaporate & Diffuse
            pheromone_map *= (PHERO_EVAP - (0.01 if is_raining else 0.0))
            
            colony.update()
            for s in feeding_spots: s.update(day_f)

            # Ant updates
            ants_to_remove = []
            for a in ants:
                fd = a.update(feeding_spots, colony.nx, colony.ny, pheromone_map, obstacles, predators, day_f, is_raining)
                if fd > 0: colony.deposit(fd)
                if a.is_dead(): ants_to_remove.append(a)

            for a in ants_to_remove:
                ants.remove(a)
                colony.ants_lost += 1
                if a is selected_ant: selected_ant = None

            # Ant communication
            for i, a1 in enumerate(ants):
                for a2 in ants[max(0, i-5):i+5]:
                    if a1 is not a2 and dist(a1.x, a1.y, a2.x, a2.y) < 10:
                        a1.communicate(a2, feeding_spots)
                        a2.communicate(a1, feeding_spots)

            # Predators
            for p in predators:
                p.update(ants, pheromone_map, predators)

            # Colony spawn
            if colony.can_spawn() and len(ants) < 150:
                ants.append(colony.spawn())

            frame_count += 1

    # ===================== RENDERING =====================
    # Background
    bg_g = int(180 * day_f + 40)
    bg_b = int(220 * day_f + 30)
    game_surf.fill((min(255, 140 + int(60*day_f)), min(255, bg_g), min(255, bg_b)))

    # Pheromones
    if show_food_phero or show_danger_phero:
        phero_r = np.zeros((PW, PH, 3), dtype=np.uint8)
        if show_food_phero:
            phero_r[:, :, 1] = np.clip(pheromone_map[:, :, FOOD_P].T * 20, 0, 255).astype(np.uint8)
        if show_danger_phero:
            phero_r[:, :, 0] = np.clip(pheromone_map[:, :, DANGER_P].T * 20, 0, 255).astype(np.uint8)
        ps = pygame.surfarray.make_surface(phero_r)
        scaled_p = pygame.transform.scale(ps, (GW, GH))
        scaled_p.set_alpha(150)
        game_surf.blit(scaled_p, (0, 0))

    for o in obstacles: o.draw(game_surf)
    for s in feeding_spots: s.draw(game_surf)
    colony.draw(game_surf)
    for p in predators: p.draw(game_surf)
    for a in ants: a.draw(game_surf, a is selected_ant)

    # Night overlay
    if day_f < 1.0:
        night_surf.fill((10, 10, 50, int((1 - day_f) * 150)))
        game_surf.blit(night_surf, (0, 0))

    # Rain
    if is_raining:
        for i in range(len(rain_drops)):
            rx, ry = rain_drops[i]
            pygame.draw.line(game_surf, RAIN_CLR, (rx, ry), (rx - 1, ry + 5), 1)
            rain_drops[i] = (rx - 1, ry + 8)
            if ry > GH: rain_drops[i] = (random.randint(0, GW), 0)
            if rx < 0: rain_drops[i] = (GW, rain_drops[i][1])

    screen.blit(game_surf, (0, 0))

    # ===================== PANEL =====================
    panel_surf.fill(PANEL_BG)
    y = 15
    
    def draw_text(txt, col=PANEL_TEXT, font=FONT_MD):
        s = font.render(txt, True, col)
        panel_surf.blit(s, (15, y))
        y += s.get_height() + 5
        
    # Replacing the broken draw_text pattern with a simple return value approach:
    def draw_text(txt, col=PANEL_TEXT, font=FONT_MD, y_pos=0):
        s = font.render(txt, True, col)
        panel_surf.blit(s, (15, y_pos))
        return y_pos + s.get_height() + 5

    y = draw_text("ANT COLONY SIM", PANEL_ACC, FONT_TITLE, y)
    y = draw_text("─" * 20, DARK_GRAY, FONT_MD, y)
    
    # Time / Weather
    time_str = "Day" if day_t < 0.5 else "Night"
    rain_str = " | RAIN" if is_raining else ""
    y = draw_text(f"Time: {time_str}{rain_str}", CYAN if is_raining else YELLOW, FONT_MD, y)
    y = draw_text(f"Speed: {speed_mult}x  FPS: {int(clock.get_fps())}", PANEL_TEXT, FONT_MD, y)
    y = draw_text("─" * 20, DARK_GRAY, FONT_MD, y)

    y = draw_text(f"Colony Food: {colony.food_storage:.1f}", ORANGE, FONT_MD, y)
    y = draw_text(f"Total Collected: {colony.total_collected:.1f}", GREEN, FONT_MD, y)
    y = draw_text(f"Ants: {len(ants)} | Lost: {colony.ants_lost}", WHITE, FONT_MD, y)
    y = draw_text(f"Scouts: {sum(1 for a in ants if a.ant_type==SCOUT)}", PURPLE, FONT_MD, y)
    y = draw_text(f"Workers: {sum(1 for a in ants if a.ant_type==WORKER)}", LIGHT_GRAY, FONT_MD, y)
    y = draw_text(f"Soldiers: {sum(1 for a in ants if a.ant_type==SOLDIER)}", RED, FONT_MD, y)
    y = draw_text(f"Carrying Food: {sum(1 for a in ants if a.has_food)}", ORANGE, FONT_MD, y)
    y = draw_text(f"Fleeing: {sum(1 for a in ants if a.state=='fleeing')}", YELLOW, FONT_MD, y)
    y = draw_text("─" * 20, DARK_GRAY, FONT_MD, y)

    # Legend
    y = draw_text("LEGEND", PANEL_ACC, FONT_LG, y)
    items = [
        (PURPLE, "Scout"), (BLACK, "Worker"), (RED, "Soldier"),
        (ORANGE, "Carrying Food"), (DARK_RED, "Predator"),
        (GREEN, "Foraging"), (YELLOW, "Returning"), (RED, "Fleeing")
    ]
    for c, t in items:
        pygame.draw.circle(panel_surf, c, (25, y + 8), 6)
        s = FONT_SM.render(t, True, PANEL_TEXT)
        panel_surf.blit(s, (40, y))
        y += 20

    y = draw_text("─" * 20, DARK_GRAY, FONT_MD, y)
    y = draw_text("CONTROLS", PANEL_ACC, FONT_LG, y)
    ctrls = [
        "SPACE - Pause/Resume",
        "P - Food Pheromones",
        "D - Danger Pheromones",
        "UP/DOWN - Speed",
        "R - Reset",
        "CLICK - Select Ant"
    ]
    for c in ctrls:
        y = draw_text(c, LIGHT_GRAY, FONT_SM, y)

    # Selected Ant Info
    if selected_ant:
        y = draw_text("─" * 20, DARK_GRAY, FONT_MD, y)
        y = draw_text("SELECTED ANT", CYAN, FONT_LG, y)
        a = selected_ant
        types = ["Scout", "Worker", "Soldier"]
        y = draw_text(f"Type: {types[a.ant_type]}", a.color, FONT_MD, y)
        y = draw_text(f"State: {a.state}", PANEL_TEXT, FONT_SM, y)
        y = draw_text(f"Action: {a.action}", PANEL_TEXT, FONT_SM, y)
        y = draw_text(f"Has Food: {a.has_food}", PANEL_TEXT, FONT_SM, y)
        y = draw_text(f"Age: {a.age}/{a.max_age}", PANEL_TEXT, FONT_SM, y)
        y = draw_text(f"Epsilon: {a.mdp.eps:.3f}", PANEL_TEXT, FONT_SM, y)

    screen.blit(panel_surf, (GW, 0))
    pygame.display.flip()
    clock.tick(60)

pygame.quit()
sys.exit()