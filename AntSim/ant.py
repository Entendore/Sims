import random
import math
from collections import deque
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPainter, QPen, QBrush, QColor
from config import (SCOUT, WORKER, SOLDIER, FOOD_P, DANGER_P, ANT_SIZE, NEST_SIZE,
                    DETECT_RANGE, ANT_SPEED, SPOT_SIZE, COLLECT_RATE, PW, PH, GW, GH,
                    BLACK, RED, ORANGE, PURPLE, GREEN, YELLOW, CYAN, PHERO_RES)
from utils import dist, p2g
from ai import MDPDecisionMaker, MCTSAgent

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
        events = []

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

        if self.mcts_cd > 0: self.mcts_cd -= 1

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
                if self.mcts_angle is not None: self.angle = self.mcts_angle
                else: self.angle = math.atan2(cs.y - self.y, cs.x - self.x)
                self.state = "foraging"
            else:
                self.mcts_angle = None
                if self.action == "follow_pheromone":
                    pd, pv = self._sense(phero, FOOD_P)
                    if pv > 1.0 and pd is not None: self.angle = pd; self.state = "following_pheromone"
                    else: self.angle += random.uniform(-self.wander, self.wander); self.state = "exploring"
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
            if self.mcts_angle is not None: self.angle = self.mcts_angle
            else: self.angle = math.atan2(ny - self.y, nx - self.x)
            self.state = "returning"
            self._deposit_path(phero)

        if self.target and not self.has_food:
            if dist(self.x, self.y, self.target.x, self.target.y) < SPOT_SIZE:
                amt = min(COLLECT_RATE * self.collect_eff, self.target.food_amount)
                self.target.food_amount -= amt
                self.food_carrying = amt; self.has_food = True
                self.returning = True; self.target = None
                self._emit_food(phero, 1.5 * self.collect_eff)
                events.append("collected")

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

        return food_returned, events

    def is_dead(self): return self.age >= self.max_age

    def communicate(self, other, spots):
        for s in spots:
            if s.food_amount > 0:
                loc = (s.x, s.y)
                if loc not in other.known_food: other.known_food.append(loc)
        if len(other.known_food) > 5: other.known_food = other.known_food[-5:]

    def draw(self, painter: QPainter):
        c = ORANGE if self.has_food else self.color
        ix, iy = self.x, self.y
        bx = self.x - math.cos(self.angle) * self.size * 0.6
        by = self.y - math.sin(self.angle) * self.size * 0.6
        hx = self.x + math.cos(self.angle) * self.size * 0.6
        hy = self.y + math.sin(self.angle) * self.size * 0.6

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(*c))
        painter.drawEllipse(QPointF(bx, by), self.size, self.size)
        painter.drawEllipse(QPointF(ix, iy), self.size - 1, self.size - 1)
        painter.drawEllipse(QPointF(hx, hy), self.size - 2, self.size - 2)

        painter.setPen(QPen(QColor(*c), 1))
        for s in (-0.4, 0.4):
            ax = hx + math.cos(self.angle + s) * self.size * 1.8
            ay = hy + math.sin(self.angle + s) * self.size * 1.8
            painter.drawLine(QPointF(hx, hy), QPointF(ax, ay))

        painter.setBrush(Qt.NoBrush)
        if self.state == "fleeing":
            painter.setPen(QPen(QColor(*RED), 2))
            painter.drawEllipse(QPointF(ix, iy), self.size + 3, self.size + 3)
        elif self.state == "foraging":
            painter.setPen(QPen(QColor(*GREEN), 2))
            painter.drawEllipse(QPointF(ix, iy), self.size + 3, self.size + 3)
        elif self.state == "returning":
            painter.setPen(QPen(QColor(*YELLOW), 2))
            painter.drawEllipse(QPointF(ix, iy), self.size + 3, self.size + 3)