import sys
import random
import math
from collections import defaultdict
from PySide6.QtCore import Qt, QTimer, QRectF, QPointF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QKeyEvent, QPolygonF
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout, 
                               QVBoxLayout, QPushButton, QLabel, QGroupBox, QScrollArea)

# ============================================================
# CONFIGURATION
# ============================================================
SCREEN_WIDTH = 1400
SCREEN_HEIGHT = 900
SIM_WIDTH = 920
SIM_HEIGHT = 660
PANEL_X = SIM_WIDTH + 10
PANEL_WIDTH = SCREEN_WIDTH - PANEL_X - 5
CHART_Y = SIM_HEIGHT + 5
CHART_HEIGHT = SCREEN_HEIGHT - CHART_Y - 5
CHART_X = 10
CHART_WIDTH = SIM_WIDTH - 20

POPULATION_SIZE = 500
INITIAL_INFECTED = 5
INITIAL_STRAINS = 2
MAX_STRAINS = 150

BASE_INFECTION_RADIUS = 14
BASE_INFECTION_PROB = 0.03
RECOVERY_TIME_BASE = 400
PERSON_RADIUS = 3
BASE_SPEED = 1.0
MORTALITY_RATE = 0.02
WANING_IMMUNITY_TIME = 2500

SOCIAL_DIST_RADIUS = 30
SOCIAL_DIST_FORCE = 0.05
VACCINATE_PCT = 0.10

SPATIAL_CELL = 32
FPS = 60
CHART_HISTORY_LEN = 600

# Colors (RGB)
C_BG = (12, 12, 22)
C_SIM_BG = (8, 8, 18)
C_SUSCEPTIBLE = (90, 140, 230)
C_RECOVERED = (45, 200, 45)
C_VACCINATED = (0, 210, 210)
C_DEAD = (110, 110, 110)
C_TEXT = (215, 215, 215)
C_DIM_TEXT = (140, 140, 160)
C_PANEL_BG = (20, 20, 35)
C_GRAPH_BG = (25, 25, 42)
C_GRID = (45, 45, 62)
C_BORDER = (70, 70, 95)
C_BTN = (50, 50, 75)
C_BTN_HOVER = (70, 70, 100)
C_BTN_ACTIVE = (35, 110, 35)
C_BTN_TEXT = (215, 215, 215)
C_ACCENT = (255, 90, 90)
C_ACCENT2 = (255, 180, 80)
C_QUARANTINE_ZONE = (180, 40, 40)
C_TRAVEL_ZONE = (40, 40, 180)

def to_qcolor(rgb, alpha=255):
    return QColor(rgb[0], rgb[1], rgb[2], alpha)

# ============================================================
# STRAIN SYSTEM
# ============================================================
class Strain:
    _next_id = 1

    def __init__(self, transmissibility=None, mutation_rate=None,
                 severity=None, parent_id=None, color=None):
        self.id = Strain._next_id
        Strain._next_id += 1
        self.transmissibility = (transmissibility if transmissibility is not None else 0.02 + random.random() * 0.03)
        self.mutation_rate = (mutation_rate if mutation_rate is not None else 0.001 + random.random() * 0.006)
        self.severity = (severity if severity is not None else 0.7 + random.random() * 0.6)
        self.parent_id = parent_id
        self.color = color if color else self._gen_color()
        self.generation = 0
        self.birth_step = 0
        self.total_infected = 0

    @classmethod
    def reset(cls):
        cls._next_id = 1

    def _gen_color(self):
        hue = (self.id * 0.618033988749895) % 1.0
        h = hue * 6.0
        c = 0.82
        x = c * (1.0 - abs(h % 2.0 - 1.0))
        if h < 1:   r, g, b = c, x, 0
        elif h < 2: r, g, b = x, c, 0
        elif h < 3: r, g, b = 0, c, x
        elif h < 4: r, g, b = 0, x, c
        elif h < 5: r, g, b = x, 0, c
        else:       r, g, b = c, 0, x
        v = 0.95
        return (min(255, int((r + v - c) * 255)),
                min(255, int((g + v - c) * 255)),
                min(255, int((b + v - c) * 255)))

    def mutate(self, global_mut_mult, step):
        nt = max(0.005, min(0.12, self.transmissibility * (1.0 + random.gauss(0, 0.12))))
        nm = max(0.0, min(0.04, self.mutation_rate * (1.0 + random.gauss(0, 0.2)) * global_mut_mult))
        ns = max(0.4, min(2.2, self.severity * (1.0 + random.gauss(0, 0.10))))
        child = Strain(transmissibility=nt, mutation_rate=nm, severity=ns, parent_id=self.id)
        child.generation = self.generation + 1
        child.birth_step = step
        pr, pg, pb = self.color
        child.color = (
            max(30, min(255, pr + random.randint(-35, 35))),
            max(30, min(255, pg + random.randint(-35, 35))),
            max(30, min(255, pb + random.randint(-35, 35))),
        )
        return child

# ============================================================
# SPATIAL HASH
# ============================================================
class SpatialHash:
    def __init__(self, cell_size):
        self.cs = cell_size
        self.grid = defaultdict(list)

    def clear(self):
        self.grid.clear()

    def insert(self, person):
        key = (int(person.x // self.cs), int(person.y // self.cs))
        self.grid[key].append(person)

    def query(self, x, y, radius):
        out = []
        cs = self.cs
        x0 = int((x - radius) // cs)
        x1 = int((x + radius) // cs)
        y0 = int((y - radius) // cs)
        y1 = int((y + radius) // cs)
        for cx in range(x0, x1 + 1):
            for cy in range(y0, y1 + 1):
                bucket = self.grid.get((cx, cy))
                if bucket:
                    out.extend(bucket)
        return out

# ============================================================
# PERSON
# ============================================================
class Person:
    __slots__ = ('x', 'y', 'vx', 'vy', 'status', 'strain',
                 'inf_timer', 'imm_timer', 'strain_immunity',
                 'alive', 'home_x', 'home_y')

    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.vx = random.uniform(-BASE_SPEED, BASE_SPEED)
        self.vy = random.uniform(-BASE_SPEED, BASE_SPEED)
        self.status = "susceptible"
        self.strain = None
        self.inf_timer = 0
        self.imm_timer = 0
        self.strain_immunity = set()
        self.alive = True
        self.home_x = x
        self.home_y = y

    def move(self, quarantine, speed_mult):
        if not self.alive:
            return
        if quarantine and self.status == "infected":
            if random.random() < 0.92:
                return
        self.x += self.vx * speed_mult
        self.y += self.vy * speed_mult
        r = PERSON_RADIUS
        if self.x < r:      self.x = r;            self.vx = abs(self.vx)
        if self.x > SIM_WIDTH - r:  self.x = SIM_WIDTH - r; self.vx = -abs(self.vx)
        if self.y < r:      self.y = r;            self.vy = abs(self.vy)
        if self.y > SIM_HEIGHT - r: self.y = SIM_HEIGHT - r; self.vy = -abs(self.vy)
        self.vx += random.gauss(0, 0.04) * speed_mult
        self.vy += random.gauss(0, 0.04) * speed_mult
        spd = math.hypot(self.vx, self.vy)
        mx = BASE_SPEED * speed_mult * 2.2
        if spd > mx:
            self.vx = self.vx / spd * mx
            self.vy = self.vy / spd * mx

    def infect(self, strain):
        if self.status == "susceptible" and strain.id not in self.strain_immunity:
            self.status = "infected"
            self.strain = strain
            self.inf_timer = 0
            strain.total_infected += 1
            return True
        return False

    def vaccinate(self):
        if self.status == "susceptible":
            self.status = "vaccinated"
            self.strain_immunity.add(-1)
            return True
        return False

    def update(self, mortality, waning):
        if self.status == "infected":
            self.inf_timer += 1
            rec = int(RECOVERY_TIME_BASE * self.strain.severity)
            if self.inf_timer >= rec:
                if random.random() < mortality:
                    self.status = "dead"
                    self.alive = False
                    self.strain = None
                else:
                    self.status = "recovered"
                    self.strain_immunity.add(self.strain.id)
                    self.imm_timer = 0
                    self.strain = None
        elif self.status == "recovered":
            if waning:
                self.imm_timer += 1
                if self.imm_timer >= WANING_IMMUNITY_TIME:
                    self.status = "susceptible"
                    self.strain_immunity.clear()
                    self.imm_timer = 0

    def color(self):
        if self.status == "susceptible":  return C_SUSCEPTIBLE
        if self.status == "infected":     return self.strain.color if self.strain else C_ACCENT
        if self.status == "recovered":    return C_RECOVERED
        if self.status == "vaccinated":   return C_VACCINATED
        if self.status == "dead":         return C_DEAD
        return C_TEXT

# ============================================================
# SIMULATION ENGINE
# ============================================================
class SimulationEngine:
    def __init__(self):
        self.sh = SpatialHash(SPATIAL_CELL)
        self.step = 0
        self.speed = 1.0
        self.inf_radius = BASE_INFECTION_RADIUS
        self.global_trans = 1.0
        self.global_mut = 1.0
        self.mortality = MORTALITY_RATE
        self.waning = False
        self.soc_dist = False
        self.quarantine = False
        self.travel = False
        self.show_radius = False
        self.peak_infected = 0
        self.peak_step = 0
        self.total_ever_infected = 0

        self.strains = []
        self.population = []
        self.chart_hist = []
        self.strain_hist = defaultdict(list)
        self.reset()

    def reset(self):
        Strain.reset()
        self.strains.clear()
        self.step = 0
        self.chart_hist.clear()
        self.strain_hist.clear()
        self.peak_infected = 0
        self.peak_step = 0
        self.total_ever_infected = INITIAL_INFECTED

        for _ in range(INITIAL_STRAINS):
            s = Strain(transmissibility=0.02 + random.random() * 0.03,
                       mutation_rate=0.002 + random.random() * 0.005,
                       severity=0.75 + random.random() * 0.5)
            s.birth_step = 0
            self.strains.append(s)

        self.population = [
            Person(random.randint(PERSON_RADIUS + 5, SIM_WIDTH - PERSON_RADIUS - 5),
                   random.randint(PERSON_RADIUS + 5, SIM_HEIGHT - PERSON_RADIUS - 5))
            for _ in range(POPULATION_SIZE)
        ]
        for idx in random.sample(range(POPULATION_SIZE), INITIAL_INFECTED):
            self.population[idx].infect(random.choice(self.strains))

        self.soc_dist = False
        self.quarantine = False
        self.waning = False
        self.travel = False
        self.show_radius = False

    def update(self):
        self.step += 1
        self.sh.clear()
        for p in self.population:
            if p.alive:
                self.sh.insert(p)

        for p in self.population:
            if not p.alive: continue
            p.move(self.quarantine, self.speed)

            if self.soc_dist and p.status != "infected":
                near = self.sh.query(p.x, p.y, SOCIAL_DIST_RADIUS)
                rx = ry = 0.0
                for o in near:
                    if o is p or not o.alive: continue
                    dx = p.x - o.x
                    dy = p.y - o.y
                    d2 = dx * dx + dy * dy
                    if 0 < d2 < SOCIAL_DIST_RADIUS ** 2:
                        d = math.sqrt(d2)
                        f = SOCIAL_DIST_FORCE / d
                        rx += dx * f
                        ry += dy * f
                p.vx += rx
                p.vy += ry

            if self.travel:
                m = 45
                ft = 0.35
                if p.x < m:         p.vx += ft
                if p.x > SIM_WIDTH - m:  p.vx -= ft
                if p.y < m:         p.vy += ft
                if p.y > SIM_HEIGHT - m: p.vy -= ft

        radius = self.inf_radius
        radius_sq = radius * radius
        new_infections = []
        
        for p in self.population:
            if p.status != "infected" or not p.alive or not p.strain: continue
            near = self.sh.query(p.x, p.y, radius)
            for o in near:
                if o.status != "susceptible" or not o.alive: continue
                dx = p.x - o.x
                dy = p.y - o.y
                d2 = dx * dx + dy * dy
                if d2 < radius_sq:
                    dist = math.sqrt(d2) if d2 > 0 else 0.1
                    prob = (p.strain.transmissibility * self.global_trans * (1.0 - dist / radius))
                    if random.random() < prob:
                        if (random.random() < p.strain.mutation_rate * self.global_mut
                                and len(self.strains) < MAX_STRAINS):
                            ns = p.strain.mutate(self.global_mut, self.step)
                            self.strains.append(ns)
                            new_infections.append((o, ns))
                        else:
                            new_infections.append((o, p.strain))

        for person, strain in new_infections:
            if person.status == "susceptible":
                person.infect(strain)
                self.total_ever_infected += 1

        for p in self.population:
            p.update(self.mortality, self.waning)

        self._record()

    def _record(self):
        s = i = r = v = d = 0
        sc = defaultdict(int)
        for p in self.population:
            if p.status == "susceptible":  s += 1
            elif p.status == "infected":   i += 1; sc[p.strain.id] += 1 if p.strain else 0
            elif p.status == "recovered":  r += 1
            elif p.status == "vaccinated": v += 1
            elif p.status == "dead":       d += 1
        self.chart_hist.append((s, i, r, v, d))
        if len(self.chart_hist) > CHART_HISTORY_LEN:
            self.chart_hist.pop(0)
        if i > self.peak_infected:
            self.peak_infected = i
            self.peak_step = self.step
        for st in self.strains:
            sid = st.id
            self.strain_hist[sid].append(sc.get(sid, 0))
            if len(self.strain_hist[sid]) > CHART_HISTORY_LEN:
                self.strain_hist[sid].pop(0)

    def counts(self):
        s = i = r = v = d = 0
        sc = defaultdict(int)
        for p in self.population:
            if p.status == "susceptible":  s += 1
            elif p.status == "infected":   i += 1; sc[p.strain.id] += 1 if p.strain else 0
            elif p.status == "recovered":  r += 1
            elif p.status == "vaccinated": v += 1
            elif p.status == "dead":       d += 1
        return s, i, r, v, d, sc

    def vaccinate_10(self):
        sus = [p for p in self.population if p.status == "susceptible"]
        n = max(1, int(len(sus) * VACCINATE_PCT))
        for p in random.sample(sus, min(n, len(sus))):
            p.vaccinate()

    def add_strain(self):
        ns = Strain(transmissibility=0.02 + random.random() * 0.06,
                    mutation_rate=0.001 + random.random() * 0.008,
                    severity=0.5 + random.random() * 0.9)
        ns.birth_step = self.step
        self.strains.append(ns)
        sus = [p for p in self.population if p.status == "susceptible"]
        if sus:
            random.choice(sus).infect(ns)


# ============================================================
# QT CUSTOM WIDGETS
# ============================================================
class SimWidget(QWidget):
    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        self.setFixedSize(SIM_WIDTH, SIM_HEIGHT)
        self.setMouseTracking(True)
        self.setStyleSheet(f"background-color: {to_qcolor(C_SIM_BG).name()}; border: 2px solid {to_qcolor(C_BORDER).name()};")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        
        # Background
        painter.fillRect(self.rect(), to_qcolor(C_SIM_BG))

        # Travel restriction zones
        if self.engine.travel:
            m = 45
            painter.setPen(Qt.NoPen)
            painter.setBrush(to_qcolor(C_TRAVEL_ZONE, 35))
            painter.drawRect(0, 0, m, SIM_HEIGHT)
            painter.drawRect(SIM_WIDTH - m, 0, m, SIM_HEIGHT)
            painter.drawRect(0, 0, SIM_WIDTH, m)
            painter.drawRect(0, SIM_HEIGHT - m, SIM_WIDTH, m)

        # Quarantine visual
        if self.engine.quarantine:
            painter.setPen(Qt.NoPen)
            painter.setBrush(to_qcolor(C_QUARANTINE_ZONE, 25))
            for p in self.engine.population:
                if p.status == "infected" and p.alive:
                    painter.drawEllipse(QPointF(p.x, p.y), 20, 20)

        # Show infection radius
        if self.engine.show_radius:
            painter.setPen(Qt.NoPen)
            for p in self.engine.population:
                if p.status == "infected" and p.alive and p.strain:
                    painter.setBrush(to_qcolor(p.strain.color, 20))
                    painter.drawEllipse(QPointF(p.x, p.y), self.engine.inf_radius, self.engine.inf_radius)

        # Draw People
        for p in self.engine.population:
            if not p.alive:
                painter.setPen(QPen(to_qcolor(C_DEAD), 1))
                painter.drawLine(int(p.x - 2), int(p.y - 2), int(p.x + 2), int(p.y + 2))
                painter.drawLine(int(p.x - 2), int(p.y + 2), int(p.x + 2), int(p.y - 2))
            else:
                c = p.color()
                painter.setPen(Qt.NoPen)
                painter.setBrush(to_qcolor(c))
                painter.drawEllipse(QPointF(p.x, p.y), PERSON_RADIUS, PERSON_RADIUS)
                if p.status == "infected":
                    glow = QColor(min(255, c[0] + 30), min(255, c[1] + 30), min(255, c[2] + 30))
                    painter.setPen(QPen(glow, 1))
                    painter.setBrush(Qt.NoBrush)
                    painter.drawEllipse(QPointF(p.x, p.y), PERSON_RADIUS + 2, PERSON_RADIUS + 2)
        painter.end()

    def mousePressEvent(self, event):
        mx, my = event.position().x(), event.position().y()
        best = None
        bd = 25.0
        for p in self.engine.population:
            if not p.alive: continue
            d = math.hypot(p.x - mx, p.y - my)
            if d < bd:
                best = p
                bd = d
        if best:
            if event.button() == Qt.LeftButton and best.status == "susceptible":
                if self.engine.strains:
                    best.infect(random.choice(self.engine.strains))
                    self.engine.total_ever_infected += 1
            elif event.button() == Qt.RightButton:
                best.vaccinate()


class ChartWidget(QWidget):
    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        self.setFixedSize(CHART_WIDTH, CHART_HEIGHT + 25)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        
        cr = QRectF(CHART_X, CHART_Y, CHART_WIDTH, CHART_HEIGHT)
        painter.fillRect(cr, to_qcolor(C_GRAPH_BG))

        # Grid
        painter.setPen(QPen(to_qcolor(C_GRID), 1))
        for i in range(1, 4):
            y = cr.top() + i * cr.height() / 4
            painter.drawLine(QPointF(cr.left(), y), QPointF(cr.right(), y))
        for i in range(1, 8):
            x = cr.left() + i * cr.width() / 8
            painter.drawLine(QPointF(x, cr.top()), QPointF(x, cr.bottom()))

        painter.setPen(QPen(to_qcolor(C_TEXT), 2))
        painter.drawLine(QPointF(cr.left(), cr.bottom()), QPointF(cr.right(), cr.bottom()))
        painter.drawLine(QPointF(cr.left(), cr.top()), QPointF(cr.left(), cr.bottom()))

        if len(self.engine.chart_hist) >= 2:
            lines = [
                ("S", C_SUSCEPTIBLE, 0),
                ("I", C_ACCENT, 1),
                ("R", C_RECOVERED, 2),
                ("V", C_VACCINATED, 3),
                ("D", C_DEAD, 4),
            ]
            for _, col, idx in lines:
                poly = QPolygonF()
                for i, rec in enumerate(self.engine.chart_hist):
                    x = cr.left() + (i / CHART_HISTORY_LEN) * cr.width()
                    y = cr.bottom() - (rec[idx] / POPULATION_SIZE) * cr.height()
                    poly.append(QPointF(x, y))
                painter.setPen(QPen(to_qcolor(col), 2))
                painter.drawPolyline(poly)

            # Peak marker
            if self.engine.peak_step > 0:
                px = cr.left() + (min(self.engine.peak_step, CHART_HISTORY_LEN) / CHART_HISTORY_LEN) * cr.width()
                if cr.left() < px < cr.right():
                    painter.setPen(QPen(to_qcolor(C_ACCENT), 1))
                    painter.drawLine(QPointF(px, cr.top()), QPointF(px, cr.bottom()))

        # Legend
        s, i_c, r, v, d, _ = self.engine.counts()
        lx = cr.right() - 170
        items = [("Susceptible", C_SUSCEPTIBLE, s),
                 ("Infected", C_ACCENT, i_c),
                 ("Recovered", C_RECOVERED, r),
                 ("Vaccinated", C_VACCINATED, v),
                 ("Dead", C_DEAD, d)]
                 
        font = QFont("Consolas", 8)
        painter.setFont(font)
        for j, (nm, cl, ct) in enumerate(items):
            ly = cr.top() + 6 + j * 17
            painter.fillRect(QRectF(lx, ly, 10, 10), to_qcolor(cl))
            painter.setPen(to_qcolor(C_TEXT))
            painter.drawText(QPointF(lx + 14, ly + 10), f"{nm}: {ct}")

        # Y-axis labels
        painter.setPen(to_qcolor(C_DIM_TEXT))
        for i in range(5):
            val = int(POPULATION_SIZE * (4 - i) / 4)
            y = cr.top() + i * cr.height() / 4
            painter.drawText(QPointF(cr.left() - 35, y + 4), str(val))

        # Title
        font.setPointSize(9)
        painter.setFont(font)
        painter.setPen(to_qcolor(C_TEXT))
        painter.drawText(QPointF(cr.left() + 5, cr.top() - 5), "Epidemic Curve")

        # Peak text
        font.setPointSize(7)
        painter.setFont(font)
        painter.setPen(to_qcolor(C_ACCENT))
        painter.drawText(QPointF(cr.left() + 5, cr.bottom() + 12), 
                         f"Peak: {self.engine.peak_infected} @ step {self.engine.peak_step}")
        painter.end()


# ============================================================
# MAIN WINDOW
# ============================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Virus Mutation & Outbreak Simulator")
        self.setStyleSheet(f"background-color: {to_qcolor(C_BG).name()}; color: {to_qcolor(C_TEXT).name()};")
        self.setFixedSize(SCREEN_WIDTH, SCREEN_HEIGHT)

        self.engine = SimulationEngine()
        self.is_paused = False

        # Central Widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        # Left Side (Sim + Chart)
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        
        self.sim_widget = SimWidget(self.engine)
        self.chart_widget = ChartWidget(self.engine)
        left_layout.addWidget(self.sim_widget)
        left_layout.addWidget(self.chart_widget)

        # Right Side (Controls)
        right_panel = QWidget()
        right_panel.setFixedWidth(PANEL_WIDTH)
        right_panel.setStyleSheet(f"background-color: {to_qcolor(C_PANEL_BG).name()}; border-left: 2px solid {to_qcolor(C_BORDER).name()};")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(5, 5, 5, 5)

        self._build_ui(right_layout)

        main_layout.addWidget(left_widget)
        main_layout.addWidget(right_panel)

        # Timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_sim)
        self.timer.start(int(1000 / FPS))

    def _build_ui(self, layout):
        # Header
        title_lbl = QLabel("Virus Simulator")
        title_lbl.setStyleSheet(f"color: {to_qcolor(C_ACCENT).name()}; font-size: 18px; font-weight: bold;")
        layout.addWidget(title_lbl)

        # Stats Group
        stats_group = QGroupBox("Statistics")
        stats_group.setStyleSheet(f"QGroupBox {{ border: 1px solid {to_qcolor(C_BORDER).name()}; margin-top:10px; }} QGroupBox::title {{ color: {to_qcolor(C_TEXT).name()}; }}")
        stats_layout = QVBoxLayout()
        self.lbl_step = QLabel("Step: 0")
        self.lbl_sus = QLabel("Susceptible: 0")
        self.lbl_inf = QLabel("Infected: 0")
        self.lbl_rec = QLabel("Recovered: 0")
        self.lbl_vac = QLabel("Vaccinated: 0")
        self.lbl_dead = QLabel("Dead: 0")
        self.lbl_peak = QLabel("Peak: 0")
        self.lbl_total = QLabel("Total ever infected: 0")

        for lbl in [self.lbl_step, self.lbl_sus, self.lbl_inf, self.lbl_rec, self.lbl_vac, self.lbl_dead, self.lbl_peak, self.lbl_total]:
            lbl.setStyleSheet("font-size: 11px;")
            stats_layout.addWidget(lbl)
        
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)

        # Params Group
        params_group = QGroupBox("Parameters")
        params_group.setStyleSheet(f"QGroupBox {{ border: 1px solid {to_qcolor(C_BORDER).name()}; margin-top:10px; }} QGroupBox::title {{ color: {to_qcolor(C_ACCENT2).name()}; }}")
        params_layout = QVBoxLayout()
        self.lbl_speed = QLabel(f"Speed: {self.engine.speed:.1f}x")
        self.lbl_radius = QLabel(f"Inf Radius: {self.engine.inf_radius}")
        self.lbl_trans = QLabel(f"Transmissibility: {self.engine.global_trans:.2f}")
        self.lbl_mut = QLabel(f"Mutation Mult: {self.engine.global_mut:.2f}")
        self.lbl_mort = QLabel(f"Mortality: {self.engine.mortality:.3f}")
        self.lbl_strains = QLabel(f"Strains: {len(self.engine.strains)}/{MAX_STRAINS}")
        
        for lbl in [self.lbl_speed, self.lbl_radius, self.lbl_trans, self.lbl_mut, self.lbl_mort, self.lbl_strains]:
            lbl.setStyleSheet("font-size: 10px;")
            params_layout.addWidget(lbl)

        params_group.setLayout(params_layout)
        layout.addWidget(params_group)

        # Buttons
        btn_layout = QVBoxLayout()
        self.btns = {}
        
        def create_btn(text, key, callback, checkable=False):
            btn = QPushButton(text)
            btn.setCheckable(checkable)
            btn.setChecked(False)
            btn.setStyleSheet(f"QPushButton {{ background-color: {to_qcolor(C_BTN).name()}; border: 1px solid {to_qcolor(C_BORDER).name()}; padding: 5px; color: {to_qcolor(C_BTN_TEXT).name()} }} QPushButton:hover {{ background-color: {to_qcolor(C_BTN_HOVER).name()} }} QPushButton:checked {{ background-color: {to_qcolor(C_BTN_ACTIVE).name()} }}")
            btn.clicked.connect(callback)
            btn_layout.addWidget(btn)
            self.btns[key] = btn

        create_btn("Soc. Distancing [S]", "sd", self._toggle_sd, True)
        create_btn("Quarantine [Q]", "q", self._toggle_q, True)
        create_btn("Waning Imm. [W]", "w", self._toggle_w, True)
        create_btn("Travel Rest. [T]", "t", self._toggle_t, True)
        create_btn("Vaccinate 10% [V]", "v", self.engine.vaccinate_10)
        create_btn("New Strain [N]", "n", self.engine.add_strain)
        create_btn("Mortality Toggle [M]", "m", self._toggle_mortality, True)
        create_btn("Show Radius [G]", "g", self._toggle_radius, True)
        create_btn("Pause [SPACE]", "pause", self._toggle_pause, True)
        create_btn("Reset [R]", "r", self._reset)

        layout.addLayout(btn_layout)
        
        # Spacer
        layout.addStretch()

        # Help
        help_text = QLabel("Click L=infect  R=vaccinate  |  ESC=quit\nArrow keys: speed & radius\n+/- transmissibility  [/] mutation")
        help_text.setStyleSheet(f"color: {to_qcolor(C_DIM_TEXT).name()}; font-size: 9px;")
        layout.addWidget(help_text)

    # Callbacks
    def _toggle_sd(self):
        self.engine.soc_dist = not self.engine.soc_dist
        self.btns["sd"].setChecked(self.engine.soc_dist)

    def _toggle_q(self):
        self.engine.quarantine = not self.engine.quarantine
        self.btns["q"].setChecked(self.engine.quarantine)

    def _toggle_w(self):
        self.engine.waning = not self.engine.waning
        self.btns["w"].setChecked(self.engine.waning)

    def _toggle_t(self):
        self.engine.travel = not self.engine.travel
        self.btns["t"].setChecked(self.engine.travel)

    def _toggle_mortality(self):
        if self.engine.mortality > 0: 
            self.engine.mortality = 0.0
        else: 
            self.engine.mortality = MORTALITY_RATE
        self.btns["m"].setChecked(self.engine.mortality > 0)

    def _toggle_radius(self):
        self.engine.show_radius = not self.engine.show_radius
        self.btns["g"].setChecked(self.engine.show_radius)

    def _toggle_pause(self):
        self.is_paused = not self.is_paused
        self.btns["pause"].setChecked(self.is_paused)

    def _reset(self):
        self.engine.reset()
        self.is_paused = False
        self.btns["pause"].setChecked(False)
        for k in ["sd", "q", "w", "t", "g", "m"]:
            self.btns[k].setChecked(False)

    def update_sim(self):
        if not self.is_paused:
            self.engine.update()
        
        # Update Stats
        s, i_c, r, v, d, sc = self.engine.counts()
        self.lbl_step.setText(f"Step: {self.engine.step}")
        self.lbl_sus.setText(f"Susceptible: {s}")
        self.lbl_inf.setText(f"Infected: {i_c}")
        self.lbl_rec.setText(f"Recovered: {r}")
        self.lbl_vac.setText(f"Vaccinated: {v}")
        self.lbl_dead.setText(f"Dead: {d}")
        self.lbl_peak.setText(f"Peak: {self.engine.peak_infected} (step {self.engine.peak_step})")
        self.lbl_total.setText(f"Total ever infected: {self.engine.total_ever_infected}")

        # Update Params
        self.lbl_speed.setText(f"Speed: {self.engine.speed:.1f}x")
        self.lbl_radius.setText(f"Inf Radius: {self.engine.inf_radius}")
        self.lbl_trans.setText(f"Transmissibility: {self.engine.global_trans:.2f}")
        self.lbl_mut.setText(f"Mutation Mult: {self.engine.global_mut:.2f}")
        self.lbl_mort.setText(f"Mortality: {self.engine.mortality:.3f}")
        self.lbl_strains.setText(f"Strains: {len(self.engine.strains)}/{MAX_STRAINS}")

        # Repaint custom widgets
        self.sim_widget.update()
        self.chart_widget.update()

    def keyPressEvent(self, event):
        k = event.key()
        if k == Qt.Key_Escape:
            self.close()
        elif k == Qt.Key_Space:
            self._toggle_pause()
        elif k == Qt.Key_Up:
            self.engine.speed = min(5.0, self.engine.speed + 0.5)
        elif k == Qt.Key_Down:
            self.engine.speed = max(0.5, self.engine.speed - 0.5)
        elif k == Qt.Key_Right:
            self.engine.inf_radius = min(50, self.engine.inf_radius + 2)
        elif k == Qt.Key_Left:
            self.engine.inf_radius = max(5, self.engine.inf_radius - 2)
        elif k == Qt.Key_V:
            self.engine.vaccinate_10()
        elif k == Qt.Key_S:
            self._toggle_sd()
        elif k == Qt.Key_Q:
            self._toggle_q()
        elif k == Qt.Key_W:
            self._toggle_w()
        elif k == Qt.Key_T:
            self._toggle_t()
        elif k == Qt.Key_R:
            self._reset()
        elif k == Qt.Key_N:
            self.engine.add_strain()
        elif k == Qt.Key_G:
            self._toggle_radius()
        elif k == Qt.Key_M:
            self._toggle_mortality()
        elif k in (Qt.Key_Plus, Qt.Key_Equals):
            self.engine.global_trans = min(3.0, self.engine.global_trans + 0.1)
        elif k == Qt.Key_Minus:
            self.engine.global_trans = max(0.1, self.engine.global_trans - 0.1)
        elif k == Qt.Key_BracketRight:
            self.engine.global_mut = min(5.0, self.engine.global_mut + 0.5)
        elif k == Qt.Key_BracketLeft:
            self.engine.global_mut = max(0.0, self.engine.global_mut - 0.5)
        else:
            super().keyPressEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())