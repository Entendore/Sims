import random
import math
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPainter, QPen, QBrush, QColor
from config import NEST_SIZE, BROWN, NEST_INNER, DARK_GRAY, BLACK, SCOUT, WORKER, SOLDIER
from ant import Ant

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

    def draw(self, painter: QPainter):
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(180, 140, 60, 25))
        painter.drawEllipse(QPointF(self.nx, self.ny), NEST_SIZE + 15, NEST_SIZE + 15)

        painter.setBrush(QColor(*BROWN))
        painter.drawEllipse(QPointF(self.nx, self.ny), NEST_SIZE, NEST_SIZE)
        painter.setBrush(QColor(*NEST_INNER))
        painter.drawEllipse(QPointF(self.nx, self.ny), NEST_SIZE - 5, NEST_SIZE - 5)
        
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(*DARK_GRAY), 2))
        painter.drawEllipse(QPointF(self.nx, self.ny), NEST_SIZE, NEST_SIZE)