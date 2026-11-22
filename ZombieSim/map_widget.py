"""
Z-POC: Interactive infection map widget.
Displays all city names simultaneously by default. Scales automatically to grid size.
"""

import math
import time

from PySide6.QtWidgets import QWidget, QSizePolicy
from PySide6.QtCore import Qt, Signal, QPointF
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QRadialGradient
)


class QMapWidget(QWidget):
    """Custom widget that draws the interactive infection map."""

    city_selected = Signal(object)

    def __init__(self, simulation, parent=None):
        super().__init__(parent)
        self.simulation = simulation
        self.selected_city = None
        self.city_positions = {}
        self.show_labels = True
        self.setMinimumSize(450, 450)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def _to_screen(self, city):
        if self.width() < 1 or self.height() < 1:
            return 0, 0
        sx = (city.x / self.simulation.grid_size) * self.width()
        sy = (1.0 - (city.y / self.simulation.grid_size)) * self.height()
        return sx, sy

    def paintEvent(self, event):
        if self.width() < 2 or self.height() < 2:
            return

        self.city_positions = {}
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        # Background
        painter.fillRect(self.rect(), QColor(20, 23, 30))

        # Grid
        pen = QPen(QColor(38, 41, 51), 0.5)
        painter.setPen(pen)
        for i in range(1, 10):
            gx = (i / 10) * self.width()
            painter.drawLine(int(gx), 0, int(gx), self.height())
            gy = (i / 10) * self.height()
            painter.drawLine(0, int(gy), self.width(), int(gy))

        with self.simulation.lock:
            # Road connections
            drawn = set()
            for city in self.simulation.cities:
                x1, y1 = self._to_screen(city)
                for conn in city.connections:
                    pair = tuple(sorted((id(city), id(conn))))
                    if pair in drawn:
                        continue
                    drawn.add(pair)
                    x2, y2 = self._to_screen(conn)

                    if city.infected > 0 and conn.infected > 0:
                        color = QColor(190, 30, 30, 140)
                    elif city.infected > 0 or conn.infected > 0:
                        color = QColor(215, 128, 25, 90)
                    else:
                        color = QColor(56, 82, 107, 50)

                    painter.setPen(QPen(color, 1.5))
                    painter.drawLine(int(x1), int(y1), int(x2), int(y2))

            # Cities
            for city in self.simulation.cities:
                sx, sy = self._to_screen(city)
                base_r = 7 + (city.population / 500000) * 16

                if city.is_nuked:
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(QBrush(QColor(90, 90, 90, 60)))
                    painter.drawEllipse(QPointF(sx, sy), base_r, base_r)
                    painter.setPen(QPen(QColor(255, 64, 0, 216), 2))
                    d = base_r * 0.6
                    painter.drawLine(int(sx - d), int(sy - d), int(sx + d), int(sy + d))
                    painter.drawLine(int(sx - d), int(sy + d), int(sx + d), int(sy - d))
                    self.city_positions[city.name] = (sx, sy, base_r)
                    continue

                ratio = city.infection_ratio

                if ratio < 0.01:
                    clr = QColor(43, 204, 112)
                elif ratio < 0.05:
                    clr = QColor(102, 217, 77)
                elif ratio < 0.15:
                    clr = QColor(191, 217, 38)
                elif ratio < 0.25:
                    clr = QColor(242, 196, 15)
                elif ratio < 0.50:
                    clr = QColor(230, 125, 33)
                else:
                    clr = QColor(191, 56, 43)

                r = base_r
                if city.infected > 0:
                    pulse = math.sin(time.time() * 3.5 + city.x * 0.4) * 2.5
                    r = base_r + max(pulse, 0)

                self.city_positions[city.name] = (sx, sy, r)

                if ratio > 0.08:
                    a = min(ratio * 115, 90)
                    grad = QRadialGradient(QPointF(sx, sy), r * 1.6)
                    grad.setColorAt(0, QColor(255, 0, 0, a))
                    grad.setColorAt(1, QColor(255, 0, 0, 0))
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(QBrush(grad))
                    painter.drawEllipse(QPointF(sx, sy), r * 1.6, r * 1.6)

                if city.is_quarantined:
                    painter.setPen(QPen(QColor(51, 153, 255, 190), 2))
                    painter.setBrush(Qt.NoBrush)
                    painter.drawEllipse(QPointF(sx, sy), r + 5, r + 5)

                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(clr))
                painter.drawEllipse(QPointF(sx, sy), r, r)

                if city.vaccination_rate > 0:
                    painter.setBrush(QBrush(QColor(77, 204, 255, 115)))
                    vr = r * min(city.vaccination_rate, 1.0)
                    painter.drawEllipse(QPointF(sx, sy), vr, vr)

                if self.selected_city and self.selected_city.name == city.name:
                    painter.setPen(QPen(QColor(255, 255, 255, 230), 2))
                    painter.setBrush(Qt.NoBrush)
                    painter.drawEllipse(QPointF(sx, sy), r + 4, r + 4)

            # ── Labels for ALL cities ──
            if self.show_labels:
                for city in self.simulation.cities:
                    if city.name in self.city_positions:
                        sx, sy, r = self.city_positions[city.name]
                        
                        if city.is_nuked:
                            painter.setPen(QPen(QColor(255, 64, 0, 150)))
                            painter.setFont(QFont("Arial", 7, QFont.StrikeOut))
                        elif city.infection_ratio > 0.25:
                            painter.setPen(QPen(QColor(255, 100, 100, 220)))
                            painter.setFont(QFont("Arial", 8, QFont.Bold))
                        elif city.is_quarantined:
                            painter.setPen(QPen(QColor(100, 150, 255, 220)))
                            painter.setFont(QFont("Arial", 8))
                        else:
                            painter.setPen(QPen(QColor(220, 220, 220, 180)))
                            painter.setFont(QFont("Arial", 8))
                            
                        text_rect = painter.fontMetrics().boundingRect(city.name)
                        painter.drawText(
                            int(sx - text_rect.width() / 2), int(sy - r - 6), city.name
                        )

        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            best, best_d = None, float("inf")
            for name, (cx, cy, cr) in self.city_positions.items():
                d = math.hypot(event.position().x() - cx, event.position().y() - cy)
                if d < cr + 15 and d < best_d:
                    best_d = d
                    best = name
            if best:
                with self.simulation.lock:
                    for city in self.simulation.cities:
                        if city.name == best:
                            self.selected_city = city
                            self.city_selected.emit(city)
                            break
                self.update()
                return
        super().mousePressEvent(event)