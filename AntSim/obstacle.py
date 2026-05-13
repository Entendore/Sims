import random
import math
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QPolygonF
from config import GW, GH, BLACK, DARK_GRAY
from utils import dist

class Obstacle:
    def __init__(self, circular=False, x=None, y=None, style="rock"):
        self.circular = circular
        self.style = style
        self.is_water = style == "water"
        self.is_tree = style == "tree"

        if style == "tree":
            self.color = (30 + random.randint(-10, 10), 80 + random.randint(-20, 20), 20 + random.randint(-10, 10))
        elif style == "water":
            self.color = (45, 120, 195)
        else:
            self.color = (random.randint(100, 140),) * 3

        if circular:
            self.radius = random.randint(20, 45) if style != "water" else 22
            self.x = x if x else random.randint(self.radius + 10, GW - self.radius - 10)
            self.y = y if y else random.randint(self.radius + 10, GH - self.radius - 10)
            self.width = self.radius * 2
            self.height = self.radius * 2
        else:
            self.width = random.randint(40, 110)
            self.height = random.randint(30, 90)
            self.x = x if x else random.randint(self.width // 2 + 10, GW - self.width // 2 - 10)
            self.y = y if y else random.randint(self.height // 2 + 10, GH - self.height // 2 - 10)
            self.radius = 0
            self.points = [
                QPointF(self.x - self.width // 2, self.y - self.height // 2),
                QPointF(self.x + self.width // 2, self.y - self.height // 2),
                QPointF(self.x + self.width // 2, self.y + self.height // 2),
                QPointF(self.x - self.width // 2, self.y + self.height // 2),
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

    def draw(self, painter: QPainter):
        if self.style == "water":
            self._draw_water(painter)
        elif self.style == "tree":
            self._draw_tree(painter)
        else:
            self._draw_rock(painter)

    def _draw_water(self, painter: QPainter):
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(*self.color))
        painter.drawEllipse(QPointF(self.x, self.y), self.radius, self.radius)

    def _draw_tree(self, painter: QPainter):
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(15, 50, 10))
        painter.drawEllipse(QPointF(self.x + 3, self.y + 3), self.radius, self.radius)
        painter.setBrush(QColor(*self.color))
        painter.drawEllipse(QPointF(self.x, self.y), self.radius, self.radius)
        painter.setBrush(QColor(100, 70, 30))
        r = max(2, self.radius // 5)
        painter.drawEllipse(QPointF(self.x, self.y), r, r)

    def _draw_rock(self, painter: QPainter):
        if self.circular:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(*self.color))
            painter.drawEllipse(QPointF(self.x, self.y), self.radius, self.radius)
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor(*BLACK), 2))
            painter.drawEllipse(QPointF(self.x, self.y), self.radius, self.radius)
        else:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(*self.color))
            painter.drawPolygon(QPolygonF(self.points))
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor(*BLACK), 2))
            painter.drawPolygon(QPolygonF(self.points))