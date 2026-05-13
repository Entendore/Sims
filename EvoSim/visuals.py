# visuals.py
import numpy as np
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QImage, QPainter, QMouseEvent
from PySide6.QtCore import Qt, QRectF, Signal
from config import GRID_SIZE, NUM_SPECIES, apply_bloom

SPECIES_COLORS = np.array([
    [1.00, 0.38, 0.28], [0.22, 0.92, 0.68], [1.00, 0.76, 0.18], [0.68, 0.42, 1.00],
    [1.00, 0.52, 0.68], [0.38, 0.95, 0.88],
], dtype=np.float32)
STAGE_GLOW = np.array([0.0, 0.60, 0.85, 1.25, 0.38], dtype=np.float32)

class CAGridWidget(QWidget):
    mouse_pressed = Signal(int, int, Qt.MouseButton)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 400)
        self.img_data = np.zeros((GRID_SIZE, GRID_SIZE, 3), dtype=np.uint8)

    def update_grid(self, S, env):
        img = render_base_image(S, env)
        self.img_data = (np.clip(img, 0, 1) * 255).astype(np.uint8)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, False)
        h, w, ch = self.img_data.shape
        qimg = QImage(self.img_data.data, w, h, ch * w, QImage.Format_RGB888)
        painter.drawImage(QRectF(0, 0, self.width(), self.height()), qimg)
        painter.end()

    def mousePressEvent(self, event: QMouseEvent):
        cell_w, cell_h = self.width() / GRID_SIZE, self.height() / GRID_SIZE
        gx = int(event.position().x() / cell_w)
        gy = int(event.position().y() / cell_h)
        if 0 <= gx < GRID_SIZE and 0 <= gy < GRID_SIZE:
            self.mouse_pressed.emit(gx, gy, event.button())

def render_base_image(S, env):
    img = np.zeros((GRID_SIZE, GRID_SIZE, 3), dtype=np.float32)
    img[:, :, 0] += env.zone_energy_map * 0.025
    img[:, :, 1] += env.zone_energy_map * 0.018
    img[:, :, 2] += env.zone_energy_map * 0.050

    fading = (~S['alive']) & (S['fade'] > 0)
    if fading.any():
        for c in range(3): img[fading, c] = S['fade'][fading] * 0.09

    if S['show_zones']:
        for zx in range(env.num_zones_x + 1):
            xi = min(zx * env.num_zones_x, GRID_SIZE - 1)
            img[xi, :] = np.maximum(img[xi, :], 0.14)
        for zy in range(env.num_zones_y + 1):
            yi = min(zy * env.num_zones_y, GRID_SIZE - 1)
            img[:, yi] = np.maximum(img[:, yi], 0.14)

    if S['disaster_flash'] > 0:
        flash = S['disaster_flash'] / 8.0 * 0.22
        img[:, :, 0] = np.maximum(img[:, :, 0], flash)
        img[:, :, 1] = np.maximum(img[:, :, 1], flash * 0.3)

    for sp in range(NUM_SPECIES):
        colour = SPECIES_COLORS[sp % len(SPECIES_COLORS)]
        sp_mask = (S['species'] == sp)
        for stg_val in (1, 2, 3, 4):
            cell_mask = sp_mask & (S['stage'] == stg_val) & S['alive']
            if not cell_mask.any(): continue
            glow = STAGE_GLOW[stg_val]
            e = S['energy'][cell_mask]
            bri = glow * (0.5 + 0.5 * e)
            for c in range(3): img[cell_mask, c] = np.clip(colour[c] * bri, 0, 1)

    return apply_bloom(img, threshold=0.35, strength=0.40, passes=3)