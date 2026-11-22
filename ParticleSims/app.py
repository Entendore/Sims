import sys
import random
import math
from collections import deque
from PySide6.QtCore import Qt, QTimer, QRectF, QPointF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QRadialGradient, QPixmap, QFont, QKeyEvent, QMouseEvent
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, 
                               QPushButton, QCheckBox, QLabel, QButtonGroup, QComboBox, QSizePolicy)

# ═══════════════════════════════════════════════════════════════
#  CONFIGURATION
# ═══════════════════════════════════════════════════════════════
SIM_W, SIM_H = 800, 600
PANEL_W       = 260
FPS           = 60
INIT_PER_TYPE = 25
MAX_PARTICLES = 600

FRICTION   = 0.95
MAX_SPEED  = 5.5
TRAIL_LEN  = 15
R_MAX      = 130
FORCE_MULT = 0.45
BETA       = 0.3

TYPE_NAMES  = ["Red", "Green", "Blue", "Yellow"]
TYPE_COLORS = {
    "Red":    (235, 75,  75),
    "Green":  (75,  235, 110),
    "Blue":   (75,  110, 235),
    "Yellow": (235, 235, 75),
}
P_RADIUS = 3

# UI colour palette
BG_COLOR       = QColor(8,   8,  18)
PANEL_BG_COLOR = QColor(16,  16,  30)
PANEL_LN_COLOR = QColor(40,  40,  70)
TXT_COLOR      = QColor(190, 190, 210)
TXT_DIM_COLOR  = QColor(110, 110, 140)
TXT_BR_COLOR   = QColor(240, 240, 255)
ACCENT_COLOR   = QColor(255, 220,  80)

# ═══════════════════════════════════════════════════════════════
#  INTERACTION MATRIX
# ═══════════════════════════════════════════════════════════════
def gen_interactions():
    m = {}
    for a in TYPE_NAMES:
        for b in TYPE_NAMES:
            if a == b:
                m[(a, b)] = round(random.uniform(-0.5, 0.15), 2)
            else:
                m[(a, b)] = round(random.uniform(-1.0, 1.0), 2)
    return m

def force_func(d, attraction, rmax):
    rmin = BETA * rmax
    if d < rmin:
        return d / rmin - 1.0
    elif d < rmax:
        return attraction * (1.0 - (d - rmin) / (rmax - rmin))
    return 0.0

# ═══════════════════════════════════════════════════════════════
#  PARTICLE
# ═══════════════════════════════════════════════════════════════
class Particle:
    __slots__ = ('x', 'y', 'vx', 'vy', 'ptype', 'color', 'trail')

    def __init__(self, x, y, ptype):
        self.x, self.y = float(x), float(y)
        self.vx = random.uniform(-0.5, 0.5)
        self.vy = random.uniform(-0.5, 0.5)
        self.ptype  = ptype
        self.color  = TYPE_COLORS[ptype]
        self.trail  = deque(maxlen=TRAIL_LEN)

    def update(self, particles, interactions, mouse_force, sim_w, sim_h):
        self.trail.append((self.x, self.y))

        fx = fy = 0.0
        for o in particles:
            if o is self:
                continue
            dx, dy = o.x - self.x, o.y - self.y
            d2 = dx * dx + dy * dy
            if 0 < d2 < R_MAX * R_MAX:
                dist = math.sqrt(d2)
                f = force_func(dist, interactions.get((self.ptype, o.ptype), 0), R_MAX)
                fx += (dx / dist) * f
                fy += (dy / dist) * f

        self.vx += fx * FORCE_MULT
        self.vy += fy * FORCE_MULT

        if mouse_force is not None:
            mx, my, mode = mouse_force
            dx, dy = mx - self.x, my - self.y
            dist = math.hypot(dx, dy)
            if 0 < dist < 200:
                s = 2.0 / max(dist * 0.08, 0.3)
                sign = 1 if mode == "attract" else -1
                self.vx += sign * (dx / dist) * s
                self.vy += sign * (dy / dist) * s

        self.vx *= FRICTION
        self.vy *= FRICTION
        spd = math.hypot(self.vx, self.vy)
        if spd > MAX_SPEED:
            r = MAX_SPEED / spd
            self.vx *= r
            self.vy *= r

        self.x += self.vx
        self.y += self.vy

        if self.x < 0:       self.x = 0;       self.vx =  abs(self.vx) * 0.5
        elif self.x > sim_w: self.x = sim_w;   self.vx = -abs(self.vx) * 0.5
        if self.y < 0:       self.y = 0;       self.vy =  abs(self.vy) * 0.5
        elif self.y > sim_h: self.y = sim_h;   self.vy = -abs(self.vy) * 0.5


# ═══════════════════════════════════════════════════════════════
#  PRE-RENDERED GLOW QPIXMAPS
# ═══════════════════════════════════════════════════════════════
def make_glow_pixmap(color_tuple, radius=18, peak_alpha=30):
    size = radius * 2
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    
    gradient = QRadialGradient(QPointF(radius, radius), radius)
    c = QColor(color_tuple[0], color_tuple[1], color_tuple[2], peak_alpha)
    gradient.setColorAt(0, c)
    gradient.setColorAt(1, QColor(color_tuple[0], color_tuple[1], color_tuple[2], 0))
    
    painter.setBrush(QBrush(gradient))
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(0, 0, size, size)
    painter.end()
    return pixmap


# ═══════════════════════════════════════════════════════════════
#  INTERACTION MATRIX WIDGET
# ═══════════════════════════════════════════════════════════════
class MatrixWidget(QWidget):
    def __init__(self, interactions, parent=None):
        super().__init__(parent)
        self.interactions = interactions
        self.setFixedSize(140, 140)

    def update_interactions(self, interactions):
        self.interactions = interactions
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        font = QFont("Segoe UI", 7)
        painter.setFont(font)

        cell = 26
        x0, y0 = 20, 20

        # Headers
        for j, name in enumerate(TYPE_NAMES):
            painter.setBrush(QColor(*TYPE_COLORS[name]))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(x0 + cell * (j + 1) + cell // 2, y0 + 6), 4, 4)
            
        for i, name in enumerate(TYPE_NAMES):
            painter.setBrush(QColor(*TYPE_COLORS[name]))
            painter.drawEllipse(QPointF(x0 + 6, y0 + cell * (i + 1) + cell // 2), 4, 4)

        # Cells
        for i, t1 in enumerate(TYPE_NAMES):
            for j, t2 in enumerate(TYPE_NAMES):
                val = self.interactions.get((t1, t2), 0)
                cx = x0 + cell * (j + 1)
                cy = y0 + cell * (i + 1)
                rect = QRectF(cx, cy, cell - 2, cell - 2)
                
                mag = min(abs(val), 1.0)
                if val >= 0:
                    c = QColor(int(30 + 40*mag), int(50 + 160*mag), int(30 + 40*mag))
                else:
                    c = QColor(int(50 + 160*mag), int(30 + 40*mag), int(30 + 40*mag))
                
                painter.setBrush(c)
                painter.setPen(Qt.NoPen)
                painter.drawRoundedRect(rect, 3.0, 3.0)
                
                painter.setPen(QColor(210, 210, 210))
                painter.drawText(rect, Qt.AlignCenter, f"{val:+.1f}")
        
        painter.end()


# ═══════════════════════════════════════════════════════════════
#  SIMULATION CANVAS
# ═══════════════════════════════════════════════════════════════
class SimWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(SIM_W, SIM_H)
        self.setMouseTracking(True)
        
        self.interactions = gen_interactions()
        self.particles = []
        self.selected_type = "Red"
        self.mouse_mode = "spawn"
        self.show_trails = True
        self.show_glow = True
        self.show_links = False
        self.paused = False
        
        self.mouse_pos = None
        self.lmb_down = False
        self.rmb_down = False
        self.mouse_force = None
        self.spawn_acc = 0.0
        
        self.glow_cache = {name: make_glow_pixmap(TYPE_COLORS[name]) for name in TYPE_NAMES}
        self.spawn_initial()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(int(1000 / FPS))

    def spawn_initial(self):
        self.particles.clear()
        for t in TYPE_NAMES:
            for _ in range(INIT_PER_TYPE):
                self.particles.append(Particle(
                    random.uniform(20, SIM_W - 20),
                    random.uniform(20, SIM_H - 20), t))

    def tick(self):
        # Physics Update
        if not self.paused:
            for p in self.particles:
                p.update(self.particles, self.interactions, self.mouse_force, SIM_W, SIM_H)

        # Continuous Spawn Logic
        if self.mouse_pos and self.mouse_pos.x() < SIM_W:
            if self.rmb_down:
                self.mouse_force = (self.mouse_pos.x(), self.mouse_pos.y(), "repel")
            elif self.lmb_down and self.mouse_mode == "attract":
                self.mouse_force = (self.mouse_pos.x(), self.mouse_pos.y(), "attract")
            elif self.lmb_down and self.mouse_mode == "repel":
                self.mouse_force = (self.mouse_pos.x(), self.mouse_pos.y(), "repel")
            elif self.lmb_down and self.mouse_mode == "spawn":
                self.mouse_force = None
                self.spawn_acc += (1000 / FPS)
                while self.spawn_acc > 60 and len(self.particles) < MAX_PARTICLES:
                    self.spawn_acc -= 60
                    self.particles.append(Particle(
                        self.mouse_pos.x() + random.uniform(-10, 10),
                        self.mouse_pos.y() + random.uniform(-10, 10),
                        self.selected_type))
            else:
                self.mouse_force = None
        else:
            self.mouse_force = None
            self.spawn_acc = 0.0

        self.update() # Trigger repaint

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Background
        painter.fillRect(0, 0, SIM_W, SIM_H, BG_COLOR)

        # Links
        if self.show_links and len(self.particles) <= 250:
            for i in range(len(self.particles)):
                p = self.particles[i]
                for j in range(i + 1, len(self.particles)):
                    o = self.particles[j]
                    dx, dy = o.x - p.x, o.y - p.y
                    d2 = dx * dx + dy * dy
                    if d2 < 4096:
                        val = self.interactions.get((p.ptype, o.ptype), 0)
                        if val > 0:
                            dist = math.sqrt(d2)
                            f = max(0.0, min(1.0, val * (1 - dist / 64)))
                            c = QColor((p.color[0] + o.color[0]) // 2,
                                       (p.color[1] + o.color[1]) // 2,
                                       (p.color[2] + o.color[2]) // 2)
                            c.setAlpha(int(f * 127))
                            painter.setPen(QPen(c, 1))
                            painter.drawLine(QPointF(p.x, p.y), QPointF(o.x, o.y))

        # Particles
        for p in self.particles:
            # Trail
            if self.show_trails and len(p.trail) > 1:
                pts = list(p.trail)
                n = len(pts)
                for k in range(n - 1):
                    fac = (k + 1) / n * 0.4
                    c = QColor(int(p.color[0] * fac), int(p.color[1] * fac), int(p.color[2] * fac))
                    painter.setPen(QPen(c, 1))
                    painter.drawLine(QPointF(pts[k][0], pts[k][1]), QPointF(pts[k+1][0], pts[k+1][1]))

            # Glow
            if self.show_glow:
                gs = self.glow_cache[p.ptype]
                painter.drawPixmap(gs.rect(), gs, gs.rect(), QPointF(p.x - gs.width()/2, p.y - gs.height()/2))

            # Dot
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(*p.color))
            painter.drawEllipse(QPointF(p.x, p.y), P_RADIUS, P_RADIUS)
            
            # Bright center highlight
            bright = QColor(min(255, p.color[0] + 80), min(255, p.color[1] + 80), min(255, p.color[2] + 80))
            painter.setBrush(bright)
            painter.drawEllipse(QPointF(p.x, p.y), 1, 1)

        # Cursor Indicator
        if self.mouse_pos and self.mouse_pos.x() < SIM_W:
            if self.mouse_force is not None:
                mc = QColor(80, 255, 120) if self.mouse_force[2] == "attract" else QColor(255, 80, 80)
                painter.setPen(QPen(mc, 1))
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(self.mouse_pos, 20, 20)
                painter.drawEllipse(self.mouse_pos, 5, 5)
            elif self.mouse_mode == "spawn":
                painter.setPen(QPen(QColor(*TYPE_COLORS[self.selected_type]), 1))
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(self.mouse_pos, 14, 14)

        painter.end()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.lmb_down = True
            if event.position().x() < SIM_W and self.mouse_mode == "spawn" and len(self.particles) < MAX_PARTICLES:
                for _ in range(5):
                    self.particles.append(Particle(
                        event.position().x() + random.uniform(-12, 12),
                        event.position().y() + random.uniform(-12, 12),
                        self.selected_type))
        elif event.button() == Qt.RightButton:
            self.rmb_down = True

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.lmb_down = False
            self.spawn_acc = 0.0
        elif event.button() == Qt.RightButton:
            self.rmb_down = False

    def mouseMoveEvent(self, event: QMouseEvent):
        self.mouse_pos = event.position()


# ═══════════════════════════════════════════════════════════════
#  CONTROL PANEL
# ═══════════════════════════════════════════════════════════════
class ControlPanel(QWidget):
    def __init__(self, sim_widget: SimWidget, parent=None):
        super().__init__(parent)
        self.sim = sim_widget
        self.setFixedSize(PANEL_W, SIM_H)
        self.setStyleSheet(f"""
            QWidget {{ background-color: {PANEL_BG_COLOR.name()}; color: {TXT_COLOR.name()}; }}
            QPushButton {{ 
                background-color: #282841; 
                border: 1px solid #282846; 
                border-radius: 4px; 
                padding: 5px; 
                color: {TXT_COLOR.name()};
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #373755; }}
            QPushButton:checked {{ background-color: #2D6E37; color: white; }}
            QCheckBox {{ spacing: 5px; }}
            QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 3px; border: 1px solid #444466; background: #1E1E30; }}
            QCheckBox::indicator:checked {{ background: #2D6E37; border: 1px solid #44FF66; }}
            QComboBox {{ background-color: #282841; border: 1px solid #282846; border-radius: 4px; padding: 5px; }}
            QComboBox::drop-down {{ border: none; }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Title
        title = QLabel("✨ Particle Life")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title.setStyleSheet(f"color: {ACCENT_COLOR.name()}; border: none;")
        layout.addWidget(title)

        # Stats
        self.stats_label = QLabel("FPS: 0 | Particles: 0")
        self.stats_label.setStyleSheet(f"color: {TXT_DIM_COLOR.name()}; border: none;")
        layout.addWidget(self.stats_label)
        
        self.counts_label = QLabel("")
        self.counts_label.setStyleSheet(f"color: {TXT_COLOR.name()}; border: none;")
        layout.addWidget(self.counts_label)

        # Select Type
        layout.addWidget(self.create_section_label("Select Type"))
        type_layout = QHBoxLayout()
        self.type_btn_group = QButtonGroup(self)
        for i, name in enumerate(TYPE_NAMES):
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setStyleSheet(f"""
                QPushButton {{ background-color: #282841; color: rgb{TYPE_COLORS[name]}; border: 1px solid #282846; }}
                QPushButton:checked {{ background-color: #2D6E37; color: white; border: 1px solid #44FF66; }}
            """)
            self.type_btn_group.addButton(btn, i)
            type_layout.addWidget(btn)
            if i == 0: btn.setChecked(True)
        self.type_btn_group.idClicked.connect(self.on_type_changed)
        layout.addLayout(type_layout)

        # Mouse Mode
        layout.addWidget(self.create_section_label("Mouse Mode"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Spawn", "Attract", "Repel"])
        self.mode_combo.currentTextChanged.connect(self.on_mode_changed)
        layout.addWidget(self.mode_combo)

        # Display
        layout.addWidget(self.create_section_label("Display"))
        disp_layout = QHBoxLayout()
        self.trail_cb = QCheckBox("Trails")
        self.trail_cb.setChecked(True)
        self.glow_cb = QCheckBox("Glow")
        self.glow_cb.setChecked(True)
        self.link_cb = QCheckBox("Links")
        
        self.trail_cb.toggled.connect(lambda v: setattr(self.sim, 'show_trails', v))
        self.glow_cb.toggled.connect(lambda v: setattr(self.sim, 'show_glow', v))
        self.link_cb.toggled.connect(lambda v: setattr(self.sim, 'show_links', v))

        disp_layout.addWidget(self.trail_cb)
        disp_layout.addWidget(self.glow_cb)
        disp_layout.addWidget(self.link_cb)
        layout.addLayout(disp_layout)

        # Actions
        layout.addWidget(self.create_section_label("Actions"))
        act_grid = QHBoxLayout()
        self.rand_btn = QPushButton("Randomize")
        self.reset_btn = QPushButton("Reset")
        self.clear_btn = QPushButton("Clear")
        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setCheckable(True)

        self.rand_btn.clicked.connect(self.on_randomize)
        self.reset_btn.clicked.connect(self.on_reset)
        self.clear_btn.clicked.connect(lambda: self.sim.particles.clear())
        self.pause_btn.toggled.connect(self.on_pause_toggled)

        act_grid.addWidget(self.rand_btn)
        act_grid.addWidget(self.reset_btn)
        act_grid.addWidget(self.clear_btn)
        act_grid.addWidget(self.pause_btn)
        layout.addLayout(act_grid)

        # Matrix
        layout.addWidget(self.create_section_label("Interaction Matrix"))
        self.matrix_widget = MatrixWidget(self.sim.interactions)
        layout.addWidget(self.matrix_widget, alignment=Qt.AlignCenter)

        # Help
        help_text = QLabel("LClick: spawn/attract/repel\nRClick: quick repel\nSpace:Pause  T:Trails  G:Glow\n1-4:Type  R:Random  C:Clear")
        help_text.setStyleSheet(f"color: {TXT_DIM_COLOR.name()}; font-size: 11px; border: none;")
        layout.addWidget(help_text)

        # FPS Timer
        self.fps_timer = QTimer(self)
        self.fps_timer.timeout.connect(self.update_stats)
        self.fps_timer.start(500)
        self.frame_count = 0

    def create_section_label(self, text):
        lbl = QLabel(text)
        lbl.setFont(QFont("Segoe UI", 10, QFont.Bold))
        lbl.setStyleSheet(f"color: {TXT_COLOR.name()}; border: none; margin-top: 5px;")
        return lbl

    def update_stats(self):
        fps = 1000.0 / (self.sim.timer.interval() + 0.001) # Approximate
        self.stats_label.setText(f"FPS: ~{fps:.0f} | Particles: {len(self.sim.particles)}")
        
        counts = {t: 0 for t in TYPE_NAMES}
        for p in self.sim.particles:
            counts[p.ptype] += 1
            
        text = "  ".join([f"<font color='rgb{TYPE_COLORS[t]}'>{t[0]}:{counts[t]}</font>" for t in TYPE_NAMES])
        self.counts_label.setText(text)

    def on_type_changed(self, id):
        self.sim.selected_type = TYPE_NAMES[id]

    def on_mode_changed(self, text):
        self.sim.mouse_mode = text.lower()

    def on_randomize(self):
        self.sim.interactions = gen_interactions()
        self.matrix_widget.update_interactions(self.sim.interactions)

    def on_reset(self):
        self.on_randomize()
        self.sim.spawn_initial()

    def on_pause_toggled(self, checked):
        self.sim.paused = checked
        self.pause_btn.setText("Resume" if checked else "Pause")

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        if key == Qt.Key_Space:
            self.pause_btn.toggle()
        elif key == Qt.Key_T:
            self.trail_cb.toggle()
        elif key == Qt.Key_G:
            self.glow_cb.toggle()
        elif key == Qt.Key_L:
            self.link_cb.toggle()
        elif key == Qt.Key_R:
            self.on_randomize()
        elif key == Qt.Key_C:
            self.sim.particles.clear()
        elif key == Qt.Key_X:
            self.on_reset()
        elif key in (Qt.Key_1, Qt.Key_2, Qt.Key_3, Qt.Key_4):
            idx = key - Qt.Key_1
            btn = self.type_btn_group.button(idx)
            if btn: btn.setChecked(True)


# ═══════════════════════════════════════════════════════════════
#  MAIN WINDOW
# ═══════════════════════════════════════════════════════════════
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("✨ Particle Life Simulation")
        self.setStyleSheet(f"background-color: {BG_COLOR.name()};")

        central = QWidget()
        self.setCentralWidget(central)
        
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.sim_widget = SimWidget()
        self.control_panel = ControlPanel(self.sim_widget)

        layout.addWidget(self.sim_widget)
        
        # Separator
        sep = QWidget()
        sep.setFixedWidth(2)
        sep.setStyleSheet(f"background-color: {PANEL_LN_COLOR.name()};")
        layout.addWidget(sep)
        
        layout.addWidget(self.control_panel)

        self.setFixedSize(SIM_W + PANEL_W + 2, SIM_H)

    def keyPressEvent(self, event: QKeyEvent):
        # Forward key presses to the control panel to handle shortcuts
        self.control_panel.keyPressEvent(event)
        super().keyPressEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())