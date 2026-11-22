import random
import math
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPainter, QPen, QBrush, QColor
from config import GW, GH, ANT_SIZE, DARK_RED, YELLOW, BLACK, RED, ORANGE, GREEN, DARK_GRAY, PHERO_RES, PW, PH, DANGER_P, SOLDIER
from utils import dist, p2g
import numpy as np

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
        events = []
        if self.cooldown > 0: self.cooldown -= 1
        self.stamina = min(self.max_stamina, self.stamina + 0.3)

        if random.random() < 0.02:
            self.angle += random.uniform(-math.pi / 4, math.pi / 4)

        ally = min((p for p in predators if p is not self),
                   key=lambda p: dist(self.x, self.y, p.x, p.y), default=None)
        ally_d = dist(self.x, self.y, ally.x, ally.y) if ally else 999

        target = None
        md = self.detect_range if self.stamina > 20 else self.detect_range * 0.5
        for a in ants:
            d = dist(self.x, self.y, a.x, a.y)
            if d < md and not a.has_food:
                md = d; target = a

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
                        events.append("blocked")
                    else:
                        killed.append(a)
                        self.kills += 1
                    if len(killed) >= self.attack_power: break
            for a in killed:
                if a in ants: ants.remove(a)
            if killed:
                self.cooldown = 60
                self._danger(phero, self.x, self.y, 10)
                events.append("attacked")
        return events

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

    def draw(self, painter: QPainter):
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(*DARK_RED))
        painter.drawEllipse(QPointF(self.x, self.y), self.size, self.size)

        for s in (-0.5, 0.5):
            ex = self.x + math.cos(self.angle + s) * self.size * 0.5
            ey = self.y + math.sin(self.angle + s) * self.size * 0.5
            painter.setBrush(QColor(*YELLOW))
            painter.drawEllipse(QPointF(ex, ey), 3, 3)
            painter.setBrush(QColor(*BLACK))
            painter.drawEllipse(QPointF(ex, ey), 1, 1)

        mx = self.x + math.cos(self.angle) * self.size * 0.7
        my = self.y + math.sin(self.angle) * self.size * 0.7
        painter.setBrush(QColor(*BLACK))
        painter.drawEllipse(QPointF(mx, my), 4, 4)

        # Stamina bar
        bw = self.size * 2
        bx, by = self.x - bw / 2, self.y - self.size - 8
        r = self.stamina / self.max_stamina
        painter.setBrush(QColor(*DARK_GRAY))
        painter.drawRect(QPointF(bx, by), bw, 3)
        c = RED if r < 0.3 else ORANGE if r < 0.6 else GREEN
        painter.setBrush(QColor(*c))
        painter.drawRect(QPointF(bx, by), bw * r, 3)