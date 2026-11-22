# visuals.py
import numpy as np
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QImage, QPainter, QMouseEvent, QPolygonF
from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from config import GRID_SIZE, NUM_SPECIES, ZONE_SIZE, apply_bloom

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
        self._last_cell = (-1, -1)
        self._held_button = Qt.NoButton
        self.setMouseTracking(False)

    def update_grid(self, S, env):
        img = render_base_image(S, env)
        self.img_data = (np.clip(img, 0, 1) * 255).astype(np.uint8)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, False)
        h, w, ch = self.img_data.shape
        # Use .copy() to ensure QImage data stays valid
        qimg = QImage(self.img_data.copy().tobytes(), w, h, ch * w, QImage.Format_RGB888)
        painter.drawImage(QRectF(0, 0, self.width(), self.height()), qimg)
        painter.end()

    def mousePressEvent(self, event: QMouseEvent):
        self._held_button = event.button()
        gx, gy = self._pos_to_cell(event)
        self._last_cell = (gx, gy)
        if 0 <= gx < GRID_SIZE and 0 <= gy < GRID_SIZE:
            self.mouse_pressed.emit(gx, gy, event.button())

    def mouseMoveEvent(self, event: QMouseEvent):
        """Support continuous painting while dragging."""
        if event.buttons() & Qt.LeftButton:
            button = Qt.LeftButton
        elif event.buttons() & Qt.RightButton:
            button = Qt.RightButton
        else:
            return
        gx, gy = self._pos_to_cell(event)
        if (gx, gy) != self._last_cell and 0 <= gx < GRID_SIZE and 0 <= gy < GRID_SIZE:
            self._last_cell = (gx, gy)
            self.mouse_pressed.emit(gx, gy, button)

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._held_button = Qt.NoButton
        self._last_cell = (-1, -1)

    def _pos_to_cell(self, event):
        cell_w = self.width() / GRID_SIZE
        cell_h = self.height() / GRID_SIZE
        gx = int(event.position().x() / cell_w)
        gy = int(event.position().y() / cell_h)
        return gx, gy


class PopGraphWidget(QWidget):
    """Mini population graph shown in the settings panel."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(80)
        self.setMaximumHeight(120)
        self._data = None

    def set_data(self, pop_history, species_hist):
        self._data = (list(pop_history), [list(h) for h in species_hist])
        self.update()

    def paintEvent(self, event):
        from PySide6.QtGui import QColor, QPen, QBrush
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor(30, 30, 46))
        p.setPen(QPen(QColor(60, 64, 90), 1))
        p.drawRect(0, 0, w - 1, h - 1)

        if not self._data or len(self._data[0]) < 2:
            p.setPen(QColor(100, 100, 120))
            p.drawText(QRectF(0, 0, w, h), Qt.AlignCenter, "Waiting for data…")
            p.end()
            return

        pop, sp_data = self._data
        n = len(pop)
        if n < 2:
            p.end()
            return
        max_val = max(max(pop), 1)
        colors = [
            QColor(255, 97, 71), QColor(56, 235, 173),
            QColor(255, 194, 46), QColor(173, 107, 255),
        ]

        # Draw species lines
        for sp in range(NUM_SPECIES):
            sd = sp_data[sp] if sp < len(sp_data) else []
            if len(sd) < 2:
                continue
            polygon = QPolygonF()
            for i, v in enumerate(sd):
                x = 2 + (i / (n - 1)) * (w - 4)
                y = h - 2 - (v / max_val) * (h - 4)
                polygon.append(QPointF(x, y))
            p.setPen(QPen(colors[sp % len(colors)], 1.5))
            p.drawPolyline(polygon)

        # Draw total population line
        polygon = QPolygonF()
        for i, v in enumerate(pop):
            x = 2 + (i / (n - 1)) * (w - 4)
            y = h - 2 - (v / max_val) * (h - 4)
            polygon.append(QPointF(x, y))
        p.setPen(QPen(QColor(205, 214, 244), 2))
        p.drawPolyline(polygon)

        # Legend
        p.setFont(p.font())
        p.setPen(QColor(140, 140, 160))
        p.drawText(4, 12, f"max: {max_val}")

        p.end()


def render_base_image(S, env):
    img = np.zeros((GRID_SIZE, GRID_SIZE, 3), dtype=np.float32)

    # Background: faint energy map
    img[:, :, 0] += env.zone_energy_map * 0.025
    img[:, :, 1] += env.zone_energy_map * 0.018
    img[:, :, 2] += env.zone_energy_map * 0.050

    # Energy heatmap overlay
    if S['show_energy']:
        e_norm = S['energy'] * S['alive'].astype(np.float32)
        img[:, :, 0] += e_norm * 0.08
        img[:, :, 1] += e_norm * 0.20
        img[:, :, 2] += e_norm * 0.04

    # Fading cells
    fading = (~S['alive']) & (S['fade'] > 0)
    if fading.any():
        for c in range(3):
            img[fading, c] = S['fade'][fading] * 0.09

    # Zone grid lines (BUG FIX: was using num_zones_x instead of ZONE_SIZE)
    if S['show_zones']:
        for zx in range(env.num_zones_x + 1):
            xi = min(zx * ZONE_SIZE, GRID_SIZE - 1)
            img[xi, :] = np.maximum(img[xi, :], 0.14)
        for zy in range(env.num_zones_y + 1):
            yi = min(zy * ZONE_SIZE, GRID_SIZE - 1)
            img[:, yi] = np.maximum(img[:, yi], 0.14)

    # Disaster flash
    if S['disaster_flash'] > 0:
        flash = S['disaster_flash'] / 8.0 * 0.22
        img[:, :, 0] = np.maximum(img[:, :, 0], flash)
        img[:, :, 1] = np.maximum(img[:, :, 1], flash * 0.3)

    # Species cells
    for sp in range(NUM_SPECIES):
        colour = SPECIES_COLORS[sp % len(SPECIES_COLORS)]
        sp_mask = (S['species'] == sp)
        for stg_val in (1, 2, 3, 4):
            cell_mask = sp_mask & (S['stage'] == stg_val) & S['alive']
            if not cell_mask.any():
                continue
            glow = STAGE_GLOW[stg_val]
            e = S['energy'][cell_mask]
            bri = glow * (0.5 + 0.5 * e)
            for c in range(3):
                img[cell_mask, c] = np.clip(colour[c] * bri, 0, 1)

    # Bloom (configurable)
    if S.get('bloom_on', True):
        bloom_str = S.get('bloom_strength', 0.40)
        return apply_bloom(img, threshold=0.35, strength=bloom_str, passes=3)
    return img