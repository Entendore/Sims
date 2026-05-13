import random
import math
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPainter, QPen, QBrush, QColor
from config import SPOT_SIZE, MAX_FOOD, GW, GH, BLACK, DARK_RED
from utils import dist

class FeedingSpot:
    def __init__(self, x=None, y=None):
        self.x = x if x else random.randint(SPOT_SIZE + 10, GW - SPOT_SIZE - 10)
        self.y = y if y else random.randint(SPOT_SIZE + 10, GH - SPOT_SIZE - 10)
        self.food_amount = MAX_FOOD
        self.initial_food = MAX_FOOD
        self.regen_rate = 0.01
        self.pulse = random.uniform(0, math.pi * 2)

    def update(self, day_f):
        if self.food_amount < self.initial_food:
            self.food_amount = min(self.initial_food, self.food_amount + self.regen_rate * day_f)
        self.pulse = (self.pulse + 0.06) % (2 * math.pi)

    def valid(self, obs):
        return not any(o.collides_with(self.x, self.y, SPOT_SIZE) for o in obs)

    def draw(self, painter: QPainter):
        ratio = self.food_amount / self.initial_food
        glow_r = SPOT_SIZE + 6 + math.sin(self.pulse) * 3
        
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 210, 40, 35))
        painter.drawEllipse(QPointF(self.x, self.y), glow_r, glow_r)

        if ratio > 0.5: cr, cg = int(255 * (1 - (ratio - 0.5) * 2)), 255
        else: cr, cg = 255, int(255 * ratio * 2)
        
        painter.setBrush(QColor(cr, cg, 0))
        painter.drawEllipse(QPointF(self.x, self.y), SPOT_SIZE, SPOT_SIZE)
        
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(*BLACK), 1))
        painter.drawEllipse(QPointF(self.x, self.y), SPOT_SIZE, SPOT_SIZE)

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(*DARK_RED))
        for a in range(0, 360, 60):
            lx = self.x + math.cos(math.radians(a)) * SPOT_SIZE * 0.5
            ly = self.y + math.sin(math.radians(a)) * SPOT_SIZE * 0.5
            painter.drawEllipse(QPointF(lx, ly), 2, 2)