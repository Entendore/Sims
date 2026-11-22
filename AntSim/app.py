import sys
import random
import time
import numpy as np
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtCore import Qt, QTimer, QPointF, QRectF
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QPixmap, QImage, QFont
from config import *
from utils import dist
from world import init_world

try:
    import cv2
    CV2_OK = True
except ImportError:
    CV2_OK = False

class Particle:
    def __init__(self, x, y, color, life=25):
        self.x = x; self.y = y
        self.vx = random.uniform(-1.2, 1.2)
        self.vy = random.uniform(-2.0, 0.2)
        self.color = color; self.life = life; self.max_life = life
    def update(self):
        self.x += self.vx; self.y += self.vy; self.vy += 0.06; self.life -= 1
    def dead(self): return self.life <= 0

class SimWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(WIDTH, HEIGHT)
        self.setFocusPolicy(Qt.StrongFocus)

        self.init_sim()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_sim)
        self.timer.start(16) # ~60fps

    def init_sim(self):
        print("Generating world...")
        (self.colony, self.obstacles, self.feeding_spots, 
         self.predators, self.ants, self.pheromone_map, self.terrain_qimg) = init_world()
        print("World ready.")
        
        self.terrain_pixmap = QPixmap.fromImage(self.terrain_qimg)
        self.particles = []
        self.paused = False
        self.show_phero = 0
        self.frame_count = 0
        self.day_length = 1800
        
        self.is_raining = False
        self.rain_timer = 0
        self.rain_drops = [(random.randint(0, GW), random.randint(0, GH)) for _ in range(180)]

        self.recording = False
        self.video_writer = None
        self.last_capture = 0.0
        self.capture_interval = 1.0 / RECORD_FPS

    def start_recording(self):
        if not CV2_OK:
            print("cv2 not installed — run: pip install opencv-python"); return
        fname = f"ant_sim_{time.strftime('%Y%m%d_%H%M%S')}.mp4"
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        self.video_writer = cv2.VideoWriter(fname, fourcc, RECORD_FPS, (WIDTH, HEIGHT))
        self.recording = True; self.last_capture = 0.0
        print(f"● Recording → {fname}")

    def stop_recording(self):
        if self.video_writer:
            self.video_writer.release(); self.video_writer = None
        self.recording = False
        print("■ Recording saved")

    def capture_frame(self):
        now = time.time()
        if now - self.last_capture < self.capture_interval: return
        self.last_capture = now
        # QWidget.grab() renders the widget to a QPixmap
        qimg = self.grab().toImage().convertToFormat(QImage.Format_RGB888)
        ptr = qimg.bits()
        ptr.setsize(qimg.height() * qimg.width() * 3)
        arr = np.frombuffer(ptr, np.uint8).reshape((qimg.height(), qimg.width(), 3))
        arr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        self.video_writer.write(arr)

    def update_sim(self):
        if self.paused:
            self.update() # Still render, just don't step physics
            return

        # Day/Night
        day_t = (self.frame_count % self.day_length) / self.day_length
        if day_t < 0.25:     day_f = 1.0
        elif day_t < 0.5:    day_f = 1.0 - (day_t - 0.25) * 4 * 0.5
        elif day_t < 0.75:   day_f = 0.5
        else:                day_f = 0.5 + (day_t - 0.75) * 4 * 0.5

        # Rain
        if not self.is_raining and random.random() < 0.001:
            self.is_raining = True; self.rain_timer = random.randint(120, 300)
            self.rain_drops = [(random.randint(0, GW), random.randint(0, GH)) for _ in range(180)]
        elif self.is_raining:
            self.rain_timer -= 1
            if self.rain_timer <= 0: self.is_raining = False

        # Physics
        self.pheromone_map *= (PHERO_EVAP - (0.01 if self.is_raining else 0.0))
        self.colony.update()
        for s in self.feeding_spots: s.update(day_f)

        dead_ants = []
        for a in self.ants:
            fd, evts = a.update(self.feeding_spots, self.colony.nx, self.colony.ny,
                                self.pheromone_map, self.obstacles, self.predators, day_f, self.is_raining)
            if fd > 0:
                self.colony.deposit(fd)
                for _ in range(6): self.particles.append(Particle(self.colony.nx, self.colony.ny, (80, 255, 80), 22))
            for ev in evts:
                if ev == "collected":
                    for _ in range(4): self.particles.append(Particle(a.x, a.y, (255, 210, 40), 18))
            if a.is_dead(): dead_ants.append(a)

        for a in dead_ants:
            self.ants.remove(a); self.colony.ants_lost += 1
            for _ in range(5): self.particles.append(Particle(a.x, a.y, (180, 180, 180), 15))

        for i, a1 in enumerate(self.ants):
            for a2 in self.ants[max(0, i - 5):i + 5]:
                if a1 is not a2 and dist(a1.x, a1.y, a2.x, a2.y) < 10:
                    a1.communicate(a2, self.feeding_spots)
                    a2.communicate(a1, self.feeding_spots)

        for p in self.predators:
            pe = p.update(self.ants, self.pheromone_map, self.predators)
            if "attacked" in pe:
                for _ in range(8): self.particles.append(Particle(p.x, p.y, (255, 40, 40), 16))

        if self.colony.can_spawn() and len(self.ants) < 150:
            self.ants.append(self.colony.spawn())

        for pt in self.particles: pt.update()
        self.particles = [pt for pt in self.particles if not pt.dead()]

        self.frame_count += 1

        if self.recording: self.capture_frame()
        self.update() # Trigger paintEvent

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.drawPixmap(0, 0, self.terrain_pixmap)

        # Pheromones
        if self.show_phero:
            phero_r = np.zeros((PW, PH, 3), dtype=np.uint8)
            if self.show_phero in (1, 3):
                phero_r[:, :, 1] = np.clip(self.pheromone_map[:, :, FOOD_P].T * 18, 0, 160).astype(np.uint8)
            if self.show_phero in (2, 3):
                phero_r[:, :, 0] = np.clip(self.pheromone_map[:, :, DANGER_P].T * 18, 0, 160).astype(np.uint8)
            
            # Must copy to keep numpy array reference intact for QImage lifetime
            phero_r = np.ascontiguousarray(phero_r)
            phero_qimg = QImage(phero_r.data, PW, PH, 3 * PW, QImage.Format_RGB888).copy()
            phero_pixmap = QPixmap.fromImage(phero_qimg).scaled(GW, GH, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            painter.setOpacity(0.5)
            painter.drawPixmap(0, 0, phero_pixmap)
            painter.setOpacity(1.0)

        for o in self.obstacles: o.draw(painter)
        for s in self.feeding_spots: s.draw(painter)
        self.colony.draw(painter)
        for p in self.predators: p.draw(painter)
        for a in self.ants: a.draw(painter)

        # Particles
        painter.setPen(Qt.NoPen)
        for pt in self.particles:
            a_alpha = max(0.05, pt.life / pt.max_life)
            c = tuple(int(v * a_alpha) for v in pt.color)
            painter.setBrush(QColor(*c))
            r = max(1, int(2.5 * a_alpha))
            painter.drawEllipse(QPointF(pt.x, pt.y), r, r)

        # Night Overlay
        day_t = (self.frame_count % self.day_length) / self.day_length
        if day_t < 0.25: day_f = 1.0
        elif day_t < 0.5: day_f = 1.0 - (day_t - 0.25) * 4 * 0.5
        elif day_t < 0.75: day_f = 0.5
        else: day_f = 0.5 + (day_t - 0.75) * 4 * 0.5

        if day_f < 1.0:
            alpha = int((1 - day_f) * 150)
            painter.fillRect(0, 0, GW, GH, QColor(10, 10, 50, alpha))

        # Rain
        if self.is_raining:
            painter.setPen(QPen(QColor(*RAIN_CLR), 1))
            for i in range(len(self.rain_drops)):
                rx, ry = self.rain_drops[i]
                painter.drawLine(QPointF(rx, ry), QPointF(rx - 1, ry + 5))
                self.rain_drops[i] = (rx - 1, ry + 8)
                if ry > GH: self.rain_drops[i] = (random.randint(0, GW), 0)
                if rx < 0: self.rain_drops[i] = (GW, self.rain_drops[i][1])

        # HUD
        painter.fillRect(0, 0, 230, 105, QColor(0, 0, 0, 140))
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(FONT_MD)
        
        time_str = "Day" if day_t < 0.5 else "Night"
        rain_str = " | RAIN" if self.is_raining else ""
        rec_str = " | ● REC" if self.recording else ""
        
        painter.drawText(10, 20, f"Time: {time_str}{rain_str}{rec_str}")
        painter.drawText(10, 40, f"Colony Food: {self.colony.food_storage:.1f}")
        painter.drawText(10, 60, f"Ants: {len(self.ants)} | Lost: {self.colony.ants_lost}")
        painter.drawText(10, 80, f"Carrying: {sum(1 for a in self.ants if a.has_food)}")
        painter.setFont(FONT_SM)
        painter.drawText(10, 100, f"[P] Phero [M] Record [SPACE] Pause [R] Reset")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Space:
            self.paused = not self.paused
        elif event.key() == Qt.Key_P:
            self.show_phero = (self.show_phero + 1) % 4
        elif event.key() == Qt.Key_M:
            if self.recording: self.stop_recording()
            else: self.start_recording()
        elif event.key() == Qt.Key_R:
            if self.recording: self.stop_recording()
            self.init_sim()
        elif event.key() == Qt.Key_Escape:
            if self.recording: self.stop_recording()
            self.close()