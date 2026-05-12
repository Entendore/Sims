"""
Z-POC: Zombie Pathogen Outbreak Command Center (PySide6 Version)
================================================================
Requirements:
  pip install PySide6 numpy matplotlib
"""

import sys
import threading
import time
import random
import math
import numpy as np

import matplotlib
matplotlib.use('QtAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvasQTAgg

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QPushButton, QLabel, QSlider, QProgressBar,
    QTextEdit, QMessageBox, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QTimer, QRectF, QPointF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QRadialGradient


# ═══════════════════════════════════════════════════════
#  City name pool for thematic immersion
# ═══════════════════════════════════════════════════════
CITY_NAMES = [
    "Haven", "Blackwood", "Cresthill", "Duskfield", "Ironhaven",
    "Millford", "Northgate", "Oakhaven", "Redmoor", "Silverdale",
    "Thornwall", "Ashford", "Brierwood", "Copperwell", "Dawnfield",
    "Eastport", "Fairhaven", "Glenwood", "Hartfield", "Jadecove",
    "Kingsford", "Lakewatch", "Mistwood", "Newhaven", "Pinecrest",
    "Ravensholm", "Stonebridge", "Twilight", "Umberland", "Wraithmoor",
    "Yorkshire", "Zephyr", "Amberdale", "Brookhaven", "Cinderpeak",
    "Driftwood", "Emberfall", "Frosthollow", "Grimstone", "Hollowdale",
]


# ═══════════════════════════════════════════════════════
#  Simulation Model
# ═══════════════════════════════════════════════════════

class City:
    """Represents a single city with SIR compartments and strategic state."""

    def __init__(self, x, y, population, name="Unknown"):
        self.x = x
        self.y = y
        self.population = population
        self.susceptible = float(population)
        self.infected = 0.0
        self.removed = 0.0
        self.name = name
        self.is_quarantined = False
        self.is_nuked = False
        self.vaccination_rate = 0.0
        self.infection_day = None
        self.connections = []          # neighbouring cities
        self.daily_new = 0             # new infections today (for graphing)

    def update(self, transmission_rate, removal_rate):
        if self.infected == 0 or self.is_nuked:
            self.daily_new = 0
            return

        effective_trans = transmission_rate * (1.0 - self.vaccination_rate)
        if self.is_quarantined:
            effective_trans *= 0.3      # quarantine reduces local spread

        new_inf = min(
            (self.susceptible * self.infected / self.population) * effective_trans,
            self.susceptible,
        )
        new_rem = min(self.infected * removal_rate, self.infected)

        self.susceptible -= new_inf
        self.infected += new_inf - new_rem
        self.removed += new_rem
        self.daily_new = new_inf

    @property
    def infection_ratio(self):
        return self.infected / self.population if self.population > 0 else 0.0


class OutbreakSimulation:
    """Core simulation engine – thread-safe with RLock."""

    def __init__(self, num_cities=20, grid_size=100,
                 transmission_rate=0.3, removal_rate=0.05):
        self.grid_size = grid_size
        self.transmission_rate = transmission_rate
        self.removal_rate = removal_rate
        self.day = 0
        self.is_over = False
        self.lock = threading.RLock()       # re-entrant – avoids deadlocks
        self.events = []
        self.quarantine_active = False
        self.total_vaccinated = 0
        self.nuked_cities = 0

        # --- build cities ---
        self.cities = []
        used = random.sample(CITY_NAMES, min(num_cities, len(CITY_NAMES)))
        for i in range(num_cities):
            x = random.randint(10, grid_size - 10)
            y = random.randint(10, grid_size - 10)
            pop = random.randint(5000, 500000)
            name = used[i] if i < len(used) else f"City-{i+1}"
            self.cities.append(City(x, y, pop, name))

        # --- build road network (nearby cities are connected) ---
        for i, c1 in enumerate(self.cities):
            for j, c2 in enumerate(self.cities):
                if i < j:
                    d = math.hypot(c1.x - c2.x, c1.y - c2.y)
                    if d < 30:
                        c1.connections.append(c2)
                        c2.connections.append(c1)

        # --- patient zero ---
        p0 = random.choice(self.cities)
        with self.lock:
            p0.infected = 1
            p0.susceptible -= 1
            p0.infection_day = 0
            self.events.append(
                f"Day 0: Patient Zero identified in {p0.name}!"
            )

        self.history_s = []
        self.history_i = []
        self.history_r = []
        self.history_new = []

    # --------------------------------------------------
    def step(self):
        with self.lock:
            if self.is_over:
                return
            self.day += 1

            # local SIR dynamics
            for city in self.cities:
                city.update(self.transmission_rate, self.removal_rate)

            # inter-city spread
            incoming = {}
            for src in self.cities:
                if src.infected <= 0 or src.is_quarantined or src.is_nuked:
                    continue
                for tgt in self.cities:
                    if src is tgt or tgt.susceptible <= 0 or tgt.is_nuked:
                        continue
                    if self.quarantine_active and tgt.is_quarantined:
                        continue

                    dist = math.hypot(src.x - tgt.x, src.y - tgt.y)
                    connected = tgt in src.connections

                    if connected and dist < 30:
                        chance = (src.infected / src.population) * 0.15
                        if not self.quarantine_active:
                            chance *= 1.5
                    elif dist < 20:
                        chance = (src.infected / src.population) * 0.08
                    else:
                        continue

                    if random.random() < chance:
                        n = min(int(src.infected * 0.01), int(tgt.susceptible))
                        if n > 0:
                            incoming.setdefault(tgt, 0)
                            incoming[tgt] += n

            daily_new = 0
            for city, n in incoming.items():
                if city.infection_day is None and n > 0:
                    city.infection_day = self.day
                    self.events.append(
                        f"Day {self.day}: OUTBREAK in {city.name}! "
                        f"({int(n)} cases)"
                    )
                city.infected += n
                city.susceptible -= n
                daily_new += n

            total_s = sum(c.susceptible for c in self.cities)
            total_i = sum(c.infected for c in self.cities)
            total_r = sum(c.removed for c in self.cities)

            self.history_s.append(total_s)
            self.history_i.append(total_i)
            self.history_r.append(total_r)
            self.history_new.append(daily_new)

            # --- milestone / alert events ---
            overrun = sum(1 for c in self.cities if c.infection_ratio > 0.5)
            infected_c = sum(1 for c in self.cities if c.infected > 0)

            if self.day == 10:
                self.events.append(
                    f"Day {self.day}: {infected_c} cities affected – "
                    f"situation critical."
                )
            if self.day == 30:
                self.events.append(
                    f"Day {self.day}: Crisis enters second month."
                )
            if self.day % 25 == 0 and overrun > 0:
                self.events.append(
                    f"Day {self.day}: {overrun} cities overrun "
                    f"(>50% infected)"
                )
            if daily_new > 50000:
                self.events.append(
                    f"Day {self.day}: CATASTROPHIC SURGE – "
                    f"{int(daily_new):,} new infections!"
                )

            if total_i < 1:
                self.is_over = True
                self.events.append(
                    f"Day {self.day}: Outbreak ended. "
                    f"Total casualties: {int(total_r):,}"
                )

            # cap event log to prevent memory bloat
            if len(self.events) > 500:
                self.events = self.events[-300:]

    # --- strategic actions --------------------------------
    def vaccinate_city(self, city, pct=0.1):
        with self.lock:
            if city.is_nuked:
                return
            n = int(city.susceptible * pct)
            if n > 0:
                city.susceptible -= n
                city.removed += n
                city.vaccination_rate = min(city.vaccination_rate + pct, 1.0)
                self.total_vaccinated += n
                self.events.append(
                    f"Day {self.day}: Vaccinated {n:,} in "
                    f"{city.name} ({pct*100:.0f}%)"
                )

    def toggle_city_quarantine(self, city):
        with self.lock:
            if city.is_nuked:
                return
            city.is_quarantined = not city.is_quarantined
            tag = "QUARANTINED" if city.is_quarantined else "released from quarantine"
            self.events.append(f"Day {self.day}: {city.name} {tag}")

    def nuke_city(self, city):
        with self.lock:
            if city.is_nuked:
                return
            lost = int(city.susceptible + city.infected)
            city.susceptible = 0
            city.infected = 0
            city.removed = city.population
            city.is_nuked = True
            city.is_quarantined = False
            self.nuked_cities += 1
            self.events.append(
                f"Day {self.day}: ☢ {city.name} NUKED! "
                f"{lost:,} lives lost."
            )

    @property
    def effective_r0(self):
        """R_eff = (β / γ) × (S / N)"""
        total_pop = sum(c.population for c in self.cities)
        total_s = sum(c.susceptible for c in self.cities)
        if total_pop > 0 and self.removal_rate > 0:
            return (self.transmission_rate / self.removal_rate) * (total_s / total_pop)
        return 0.0


# ═══════════════════════════════════════════════════════
#  Map Widget
# ═══════════════════════════════════════════════════════

class QMapWidget(QWidget):
    """Custom widget that draws the interactive infection map."""

    city_selected = Signal(object)

    def __init__(self, simulation, parent=None):
        super().__init__(parent)
        self.simulation = simulation
        self.selected_city = None
        self.city_positions = {}     # name → (sx, sy, radius)
        self.setMinimumSize(450, 450)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def _to_screen(self, city):
        """Grid coords → pixel coords inside the widget."""
        if self.width() < 1 or self.height() < 1:
            return 0, 0
        sx = (city.x / self.simulation.grid_size) * self.width()
        # Qt Y axis is inverted compared to standard math coords
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

                # Nuked city
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

                # Color ramp
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

                # Pulsing radius for active infections
                r = base_r
                if city.infected > 0:
                    pulse = math.sin(time.time() * 3.5 + city.x * 0.4) * 2.5
                    r = base_r + max(pulse, 0)

                self.city_positions[city.name] = (sx, sy, r)

                # Infection glow
                if ratio > 0.08:
                    a = min(ratio * 115, 90)
                    grad = QRadialGradient(QPointF(sx, sy), r * 1.6)
                    grad.setColorAt(0, QColor(255, 0, 0, a))
                    grad.setColorAt(1, QColor(255, 0, 0, 0))
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(QBrush(grad))
                    painter.drawEllipse(QPointF(sx, sy), r * 1.6, r * 1.6)

                # Quarantine ring
                if city.is_quarantined:
                    painter.setPen(QPen(QColor(51, 153, 255, 190), 2))
                    painter.setBrush(Qt.NoBrush)
                    painter.drawEllipse(QPointF(sx, sy), r + 5, r + 5)

                # City dot
                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(clr))
                painter.drawEllipse(QPointF(sx, sy), r, r)

                # Vaccination arc indicator
                if city.vaccination_rate > 0:
                    painter.setBrush(QBrush(QColor(77, 204, 255, 115)))
                    vr = r * min(city.vaccination_rate, 1.0)
                    painter.drawEllipse(QPointF(sx, sy), vr, vr)

                # Selection highlight
                if self.selected_city and self.selected_city.name == city.name:
                    painter.setPen(QPen(QColor(255, 255, 255, 230), 2))
                    painter.setBrush(Qt.NoBrush)
                    painter.drawEllipse(QPointF(sx, sy), r + 4, r + 4)

            # Name label for selected city
            if self.selected_city and not self.selected_city.is_nuked:
                c = self.selected_city
                if c.name in self.city_positions:
                    sx, sy, r = self.city_positions[c.name]
                    painter.setPen(QPen(QColor(255, 255, 255, 235)))
                    painter.setFont(QFont("Arial", 10))
                    text_rect = painter.fontMetrics().boundingRect(c.name)
                    painter.drawText(int(sx - text_rect.width()/2), int(sy - r - 8), c.name)

        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            best, best_d = None, float('inf')
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


# ═══════════════════════════════════════════════════════
#  Main Application Window
# ═══════════════════════════════════════════════════════

class OutbreakMainWindow(QMainWindow):

    update_signal = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Z-POC: Zombie Pathogen Outbreak Command Center")
        self.resize(1200, 800)
        self.is_running = False
        self.sim_thread = None
        self.sim_speed = 0.05
        self._graph_tick = 0
        self._seen_events = set()

        # Apply global dark theme
        self.setStyleSheet("""
            QMainWindow, QWidget { background-color: #14161c; color: #cccccc; }
            QLabel { color: #cccccc; }
            QPushButton { padding: 5px; border: 1px solid #333; border-radius: 3px; background-color: #222; color: white; }
            QPushButton:disabled { background-color: #111; color: #555; }
            QSlider::groove:horizontal { height: 6px; background: #333; border-radius: 3px; }
            QSlider::handle:horizontal { background: #888; width: 12px; margin: -4px 0; border-radius: 6px; }
            QProgressBar { text-align: center; border: 1px solid #333; border-radius: 3px; background-color: #111; color: white; }
            QProgressBar::chunk { background-color: #cc3333; }
            QTextEdit { border: 1px solid #333; background-color: #0d0e12; color: #aaa; }
        """)

        # Core Simulation
        self.simulation = OutbreakSimulation()

        # Central Widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(5, 5, 5, 5)
        root_layout.setSpacing(3)

        # ─── Title ───
        lbl_title = QLabel('Z-POC : ZOMBIE PATHOGEN OUTBREAK COMMAND CENTER')
        lbl_title.setAlignment(Qt.AlignCenter)
        lbl_title.setStyleSheet("color: #f23838; font-size: 16px; font-weight: bold;")
        lbl_title.setFixedHeight(32)
        root_layout.addWidget(lbl_title)

        # ─── Control Buttons ───
        ctrl_layout = QHBoxLayout()
        ctrl_layout.setSpacing(5)

        self.btn_start = QPushButton('▶  Start Outbreak')
        self.btn_start.setStyleSheet("background-color: #218c38; color: white;")
        self.btn_start.clicked.connect(self._toggle_sim)

        self.btn_reset = QPushButton('↺  Reset')
        self.btn_reset.setStyleSheet("background-color: #851c1c; color: white;")
        self.btn_reset.clicked.connect(self._reset_sim)

        self.btn_quarantine = QPushButton('Travel Ban')
        self.btn_quarantine.setCheckable(True)
        self.btn_quarantine.setStyleSheet("background-color: #224085; color: white;")
        self.btn_quarantine.clicked.connect(self._toggle_quarantine)

        self.btn_vaccinate = QPushButton('Mass Vaccinate')
        self.btn_vaccinate.setStyleSheet("background-color: #226985; color: white;")
        self.btn_vaccinate.clicked.connect(self._mass_vaccinate)

        ctrl_layout.addWidget(self.btn_start)
        ctrl_layout.addWidget(self.btn_reset)
        ctrl_layout.addWidget(self.btn_quarantine)
        ctrl_layout.addWidget(self.btn_vaccinate)
        root_layout.addLayout(ctrl_layout)

        # ─── Parameter Sliders ───
        params_layout = QHBoxLayout()
        params_layout.setSpacing(3)

        # Helper for float sliders
        def create_slider(text, min_val, max_val, val, step, callback):
            layout = QHBoxLayout()
            lbl = QLabel(text)
            lbl.setStyleSheet("color: #b3b3b3; font-size: 11px;")
            slider = QSlider(Qt.Horizontal)
            slider.setRange(int(min_val/step), int(max_val/step))
            slider.setValue(int(val/step))
            slider.valueChanged.connect(lambda v: callback(v * step))
            layout.addWidget(lbl)
            layout.addWidget(slider)
            return layout

        l1 = create_slider('Transmission:', 0.05, 0.80, 0.3, 0.01, self._set_trans)
        l2 = create_slider('Removal:', 0.01, 0.20, 0.05, 0.005, self._set_rem)
        l3 = create_slider('Speed:', 0.01, 0.50, 0.05, 0.01, self._set_speed)
        
        params_layout.addLayout(l1)
        params_layout.addLayout(l2)
        params_layout.addLayout(l3)
        root_layout.addLayout(params_layout)

        # ─── Main Display ───
        main_layout = QHBoxLayout()
        main_layout.setSpacing(5)

        # Map (left)
        self.map_widget = QMapWidget(self.simulation)
        self.map_widget.city_selected.connect(self._on_city_selected)
        main_layout.addWidget(self.map_widget, stretch=2)

        # Right panel
        right_layout = QVBoxLayout()
        right_layout.setSpacing(3)

        # SIR Graph
        self.fig, self.ax = plt.subplots(figsize=(5, 3), facecolor='#14161c')
        self.fig_canvas = FigureCanvasQTAgg(self.fig)
        self.fig_canvas.setMinimumHeight(200)
        right_layout.addWidget(self.fig_canvas, stretch=1)

        # Statistics grid
        stats_layout = QGridLayout()
        stats_layout.setSpacing(2)
        
        self.lbl_day  = self._create_stat_label('Day: 0', 15, True, 'white')
        self.lbl_r0   = self._create_stat_label('R₀: 0.00', 13, False, '#e6b3e6')
        self.lbl_sus  = self._create_stat_label('Susceptible: 0', 12, False, '#4de680')
        self.lbl_inf  = self._create_stat_label('Infected: 0', 12, False, '#ff4d4d')
        self.lbl_rem  = self._create_stat_label('Casualties: 0', 12, False, '#e6e64d')
        self.lbl_cinf = self._create_stat_label('Cities Infected: 0/0', 12, False, '#ff994d')
        self.lbl_over = self._create_stat_label('Overrun: 0', 12, False, '#ff6633')
        self.lbl_vax  = self._create_stat_label('Vaccinated: 0', 12, False, '#4dcfff')
        
        stats_layout.addWidget(self.lbl_day, 0, 0)
        stats_layout.addWidget(self.lbl_r0, 0, 1)
        stats_layout.addWidget(self.lbl_sus, 1, 0)
        stats_layout.addWidget(self.lbl_inf, 1, 1)
        stats_layout.addWidget(self.lbl_rem, 2, 0)
        stats_layout.addWidget(self.lbl_cinf, 2, 1)
        stats_layout.addWidget(self.lbl_over, 3, 0)
        stats_layout.addWidget(self.lbl_vax, 3, 1)
        right_layout.addLayout(stats_layout)

        # Infection progress bar
        prog_layout = QHBoxLayout()
        lbl_prog = QLabel('Infection:')
        lbl_prog.setStyleSheet("color: #b3b3b3; font-size: 10px;")
        lbl_prog.setFixedWidth(65)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.lbl_pct = QLabel('0.0%')
        self.lbl_pct.setStyleSheet("color: #ff8080; font-size: 11px;")
        self.lbl_pct.setFixedWidth(50)
        prog_layout.addWidget(lbl_prog)
        prog_layout.addWidget(self.progress)
        prog_layout.addWidget(self.lbl_pct)
        right_layout.addLayout(prog_layout)

        # City detail + actions
        self.lbl_city = QLabel('Click a city on the map for details')
        self.lbl_city.setWordWrap(True)
        self.lbl_city.setStyleSheet("color: #b3ccff; font-size: 11px; padding: 2px;")
        self.lbl_city.setFixedHeight(50)
        right_layout.addWidget(self.lbl_city)

        city_btns_layout = QHBoxLayout()
        city_btns_layout.setSpacing(3)
        
        self.btn_c_quar = QPushButton('Quarantine')
        self.btn_c_quar.setStyleSheet("background-color: #224d8c; font-size: 10px;")
        self.btn_c_quar.setEnabled(False)
        self.btn_c_quar.clicked.connect(self._quarantine_selected)

        self.btn_c_vax = QPushButton('Vaccinate')
        self.btn_c_vax.setStyleSheet("background-color: #227385; font-size: 10px;")
        self.btn_c_vax.setEnabled(False)
        self.btn_c_vax.clicked.connect(self._vaccinate_selected)

        self.btn_nuke = QPushButton('☢ NUKE')
        self.btn_nuke.setStyleSheet("background-color: #991a1a; font-size: 10px;")
        self.btn_nuke.setEnabled(False)
        self.btn_nuke.clicked.connect(self._nuke_selected)

        city_btns_layout.addWidget(self.btn_c_quar)
        city_btns_layout.addWidget(self.btn_c_vax)
        city_btns_layout.addWidget(self.btn_nuke)
        right_layout.addLayout(city_btns_layout)

        # Event Log
        self.event_log = QTextEdit()
        self.event_log.setReadOnly(True)
        self.event_log.setFont(QFont("Consolas", 9))
        right_layout.addWidget(self.event_log, stretch=1)

        main_layout.addLayout(right_layout, stretch=1)
        root_layout.addLayout(main_layout)

        # Animation timer for map pulsing
        self.pulse_timer = QTimer()
        self.pulse_timer.timeout.connect(self.map_widget.update)
        self.pulse_timer.start(120)

        # Connect cross-thread signal
        self.update_signal.connect(self._update_ui)

        self._update_ui() # First draw

    def _create_stat_label(self, text, size, bold, color):
        lbl = QLabel(text)
        weight = "bold" if bold else "normal"
        lbl.setStyleSheet(f"color: {color}; font-size: {size}px; font-weight: {weight};")
        return lbl

    # ─── Slider Callbacks ───────────────────────────
    def _set_trans(self, v):
        self.simulation.transmission_rate = v

    def _set_rem(self, v):
        self.simulation.removal_rate = v

    def _set_speed(self, v):
        self.sim_speed = v

    # ─── Simulation Control ─────────────────────────
    def _toggle_sim(self):
        if not self.is_running:
            self.is_running = True
            self.btn_start.setText('⏸  Pause')
            self.btn_start.setStyleSheet("background-color: #8c6e21; color: white;")
            self.sim_thread = threading.Thread(target=self._sim_loop, daemon=True)
            self.sim_thread.start()
        else:
            self.is_running = False
            self.btn_start.setText('▶  Resume')
            self.btn_start.setStyleSheet("background-color: #218c38; color: white;")

    def _sim_loop(self):
        while self.is_running and not self.simulation.is_over:
            self.simulation.step()
            self.update_signal.emit() # Thread safe UI update trigger
            time.sleep(self.sim_speed)
        if self.simulation.is_over:
            self.update_signal.emit()

    def _reset_sim(self):
        self.is_running = False
        if self.sim_thread and self.sim_thread.is_alive():
            self.sim_thread.join(timeout=1)
            
        trans = self.simulation.transmission_rate
        rem = self.simulation.removal_rate
        self.simulation = OutbreakSimulation(transmission_rate=trans, removal_rate=rem)
        
        self.map_widget.simulation = self.simulation
        self.map_widget.selected_city = None
        self.btn_start.setText('▶  Start Outbreak')
        self.btn_start.setStyleSheet("background-color: #218c38; color: white;")
        self.btn_quarantine.setChecked(False)
        self.btn_quarantine.setText('Travel Ban')
        self.event_log.clear()
        self._seen_events.clear()
        self._graph_tick = 0
        self._update_ui()

    # ─── Strategic Actions ──────────────────────────
    def _toggle_quarantine(self):
        on = self.btn_quarantine.isChecked()
        self.simulation.quarantine_active = on
        self.btn_quarantine.setText('Travel Ban: ON' if on else 'Travel Ban')
        with self.simulation.lock:
            self.simulation.events.append(
                f"Day {self.simulation.day}: Global travel ban "
                f"{'ACTIVATED' if on else 'LIFTED'}"
            )

    def _mass_vaccinate(self):
        for city in self.simulation.cities:
            if city.infection_ratio < 0.5 and not city.is_nuked:
                self.simulation.vaccinate_city(city, 0.05)
        self._update_ui()

    def _on_city_selected(self, city):
        self.btn_c_quar.setEnabled(True)
        self.btn_c_vax.setEnabled(True)
        self.btn_nuke.setEnabled(True)
        self._update_city_info()

    def _quarantine_selected(self):
        c = self.map_widget.selected_city
        if c:
            self.simulation.toggle_city_quarantine(c)
            self._update_ui()

    def _vaccinate_selected(self):
        c = self.map_widget.selected_city
        if c:
            self.simulation.vaccinate_city(c, 0.15)
            self._update_ui()

    def _nuke_selected(self):
        city = self.map_widget.selected_city
        if not city:
            return

        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Critical)
        msg.setWindowTitle("⚠  CONFIRM NUCLEAR STRIKE  ⚠")
        msg.setText(f"NUKE {city.name}?")
        msg.setInformativeText(
            f"This will kill ALL {city.population:,} inhabitants!\n"
            f"This CANNOT be undone."
        )
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.No)
        msg.setStyleSheet("background-color: #2a0a0a; color: white;")
        
        if msg.exec() == QMessageBox.Yes:
            self.simulation.nuke_city(city)
            self._update_ui()

    # ─── UI Refresh ─────────────────────────────────
    def _update_ui(self):
        # Map
        self.map_widget.update()

        # Graph (throttled)
        self._graph_tick += 1
        if self._graph_tick % 3 == 0 or not self.is_running:
            self.ax.clear()
            if self.simulation.history_s:
                days = range(len(self.simulation.history_s))
                self.ax.fill_between(days, self.simulation.history_s, alpha=0.12, color='cyan')
                self.ax.fill_between(days, self.simulation.history_r, alpha=0.12, color='yellow')
                self.ax.plot(days, self.simulation.history_s, 'c-', label='Susceptible', linewidth=1.5)
                self.ax.plot(days, self.simulation.history_i, 'm-', label='Infected', linewidth=2)
                self.ax.plot(days, self.simulation.history_r, 'y-', label='Removed', linewidth=1.5)
                if self.simulation.history_new:
                    self.ax.bar(days, self.simulation.history_new, alpha=0.18, color='red', label='New Cases')
            
            self.ax.set_title("SIR Model", color='white', fontsize=10)
            self.ax.set_xlabel("Days", color='white', fontsize=8)
            self.ax.set_ylabel("Population", color='white', fontsize=8)
            self.ax.legend(fontsize=7, loc='right', facecolor='#2c3e50', edgecolor='#555', labelcolor='white')
            self.ax.grid(True, linestyle='--', alpha=0.18)
            self.ax.set_facecolor('#12141a')
            self.ax.tick_params(colors='white', labelsize=7)
            for spine in self.ax.spines.values():
                spine.set_edgecolor('#333')
            self.fig.tight_layout()
            self.fig_canvas.draw()

        # Stats
        with self.simulation.lock:
            total_pop = sum(c.population for c in self.simulation.cities)
            total_s   = sum(c.susceptible for c in self.simulation.cities)
            total_i   = sum(c.infected    for c in self.simulation.cities)
            total_r   = sum(c.removed     for c in self.simulation.cities)
            overrun   = sum(1 for c in self.simulation.cities if c.infection_ratio > 0.5)
            infected  = sum(1 for c in self.simulation.cities if c.infected > 0)
            n_cities  = len(self.simulation.cities)
            day       = self.simulation.day
            r0        = self.simulation.effective_r0
            vax       = self.simulation.total_vaccinated
            events    = list(self.simulation.events)

        pct = (total_i / total_pop * 100) if total_pop > 0 else 0.0

        self.lbl_day.setText(f'Day: {day}')
        self.lbl_r0.setText(f'R₀: {r0:.2f}')
        self.lbl_sus.setText(f'Susceptible: {int(total_s):,}')
        self.lbl_inf.setText(f'Infected: {int(total_i):,}')
        self.lbl_rem.setText(f'Casualties: {int(total_r):,}')
        self.lbl_cinf.setText(f'Cities Infected: {infected}/{n_cities}')
        self.lbl_over.setText(f'Overrun: {overrun}')
        self.lbl_vax.setText(f'Vaccinated: {vax:,}')

        self.progress.setValue(int(pct))
        self.lbl_pct.setText(f'{pct:.1f}%')

        self._update_city_info()
        self._update_event_log(events)

    def _update_city_info(self):
        city = self.map_widget.selected_city
        if city and not city.is_nuked:
            q_tag = "Yes" if city.is_quarantined else "No"
            self.lbl_city.setText(
                f'<b>{city.name}</b>  |  Pop: {city.population:,}<br>'
                f'S: {int(city.susceptible):,}  I: {int(city.infected):,}  '
                f'R: {int(city.removed):,}  '
                f'({city.infection_ratio*100:.1f}% infected)<br>'
                f'Quarantined: {q_tag}  |  '
                f'Vaccinated: {city.vaccination_rate*100:.0f}%'
            )
            self.btn_c_quar.setEnabled(True)
            self.btn_c_vax.setEnabled(True)
            self.btn_nuke.setEnabled(True)
            self.btn_c_quar.setText('Release City' if city.is_quarantined else 'Quarantine')
        elif city and city.is_nuked:
            self.lbl_city.setText(f'<b>{city.name}</b>  —  DESTROYED')
            self.btn_c_quar.setEnabled(False)
            self.btn_c_vax.setEnabled(False)
            self.btn_nuke.setEnabled(False)
        else:
            self.lbl_city.setText('Click a city on the map for details')
            self.btn_c_quar.setEnabled(False)
            self.btn_c_vax.setEnabled(False)
            self.btn_nuke.setEnabled(False)

    def _update_event_log(self, events):
        new = [e for e in events if e not in self._seen_events]
        if not new:
            return
        
        self._seen_events.update(new)
        html_parts = []
        for e in new:
            if "Patient Zero" in e:
                html_parts.append(f'<span style="color:#ff4444"><b>{e}</b></span>')
            elif "OUTBREAK" in e:
                html_parts.append(f'<span style="color:#ff8844">{e}</span>')
            elif "CATASTROPHIC" in e:
                html_parts.append(f'<span style="color:#ff0000"><b>{e}</b></span>')
            elif "NUKED" in e:
                html_parts.append(f'<span style="color:#ff6600"><b>{e}</b></span>')
            elif "ended" in e:
                html_parts.append(f'<span style="color:#44ff44"><b>{e}</b></span>')
            elif "QUARANTINED" in e:
                html_parts.append(f'<span style="color:#4488ff">{e}</span>')
            elif "Vaccinated" in e:
                html_parts.append(f'<span style="color:#44ddff">{e}</span>')
            elif "overrun" in e.lower():
                html_parts.append(f'<span style="color:#ff6644">{e}</span>')
            else:
                html_parts.append(f'<span style="color:#bbbbbb">{e}</span>')
        
        self.event_log.append("<br>".join(html_parts))
        # Auto scroll to bottom
        scrollbar = self.event_log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = OutbreakMainWindow()
    window.show()
    sys.exit(app.exec())