# gui.py
"""
PySide6 GUI: Interactive hex map with overlays, zoom/pan, charts, log filtering,
save/load, recording (real-time and from-start), and keyboard shortcuts.
"""
import math
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
    QSlider, QTextEdit, QLabel, QSplitter, QTableWidget, QTableWidgetItem,
    QHeaderView, QCheckBox, QComboBox, QFileDialog, QGroupBox, QToolTip,
    QMessageBox, QInputDialog, QProgressDialog,
)
from PySide6.QtCore import Qt, QTimer, QPointF, QThread, Signal, QObject
from PySide6.QtGui import QPolygonF, QColor, QBrush, QPen, QFont, QPainter, QKeyEvent

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt

from config import CONFIG, history_log, active_disasters, cultural_map, categorize_log
from hex_utils import hex_to_pixel, pixel_to_hex
from data import TERRAINS, RESOURCES
from civilization import Civilization
from recorder import VideoRecorder


# ======================================================================
# Background worker for "Record from Start" so the GUI doesn't freeze
# ======================================================================
class _ExportWorker(QObject):
    """Runs the headless simulation recording in a background thread."""
    finished = Signal(bool)
    error = Signal(str)

    def __init__(self, filename, fps, max_turns, map_radius, num_civs):
        super().__init__()
        self.filename = filename
        self.fps = fps
        self.max_turns = max_turns
        self.map_radius = map_radius
        self.num_civs = num_civs

    def run(self):
        try:
            success = VideoRecorder.export_from_start(
                filename=self.filename,
                fps=self.fps,
                max_turns=self.max_turns,
                map_radius=self.map_radius,
                num_civs=self.num_civs,
            )
            self.finished.emit(success)
        except Exception as e:
            self.error.emit(str(e))


# ======================================================================
# Hex Map Widget
# ======================================================================
class HexMapScene(QWidget):
    """Custom widget to draw the hex map with zoom, pan, overlays, and tooltips."""

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.base_size = CONFIG["hex_size"] * 20
        self.zoom = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0
        self._dragging = False
        self._last_pos = None
        self.selected = None
        self.highlight_civ = None

        # Overlays
        self.show_resources = True
        self.show_armies = False
        self.show_culture = False
        self.show_diplomacy = False
        self.show_rivers = True

        self.setMinimumSize(600, 600)
        self.setMouseTracking(True)

    @property
    def hex_size(self):
        return self.base_size * self.zoom

    def _create_hex_polygon(self, cx, cy):
        points = []
        for i in range(6):
            angle_rad = math.pi / 180 * (60 * i)
            points.append(QPointF(
                cx + self.hex_size * math.cos(angle_rad),
                cy + self.hex_size * math.sin(angle_rad)
            ))
        return QPolygonF(points)

    def _center_offset(self):
        return self.width() / 2 + self.pan_x, self.height() / 2 + self.pan_y

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#1a1a2e"))

        offset_x, offset_y = self._center_offset()
        hs = self.hex_size

        # 1. Terrain
        for h, t in self.engine.terrain.items():
            px, py = hex_to_pixel(*h, hs)
            cx, cy = px + offset_x, py + offset_y
            poly = self._create_hex_polygon(cx, cy)
            painter.setBrush(QBrush(QColor(TERRAINS[t]["color"])))
            painter.setPen(QPen(QColor("#333333"), 1))
            painter.drawPolygon(poly)
            # Terrain symbol
            painter.setPen(QPen(QColor(0, 0, 0, 160)))
            painter.setFont(QFont("Segoe UI Emoji", max(5, int(8 * self.zoom))))
            painter.drawText(poly.boundingRect(), Qt.AlignCenter, TERRAINS[t]["symbol"])

        # 2. Rivers
        if self.show_rivers:
            painter.setPen(QPen(QColor("#4a90e2"), max(1, int(2 * self.zoom))))
            for h in self.engine.rivers:
                px, py = hex_to_pixel(*h, hs)
                cx, cy = px + offset_x, py + offset_y
                painter.setFont(QFont("Segoe UI Emoji", max(4, int(7 * self.zoom))))
                painter.drawText(QPointF(cx - 4 * self.zoom, cy + 4 * self.zoom), "〰")

        # 3. Resources Overlay
        if self.show_resources:
            for h, rname in self.engine.resources.items():
                px, py = hex_to_pixel(*h, hs)
                cx, cy = px + offset_x, py + offset_y
                res = RESOURCES[rname]
                painter.setPen(QPen(QColor(res["color"]), 1))
                painter.setFont(QFont("Segoe UI Emoji", max(4, int(7 * self.zoom))))
                painter.drawText(QPointF(cx - 4 * self.zoom, cy - 4 * self.zoom), res["symbol"])

        # 4. Territory Overlay
        for civ in self.engine.alive_civs:
            color = QColor(civ.color)
            is_hl = (self.highlight_civ == civ.name)
            color.setAlpha(160 if is_hl else 80)
            pen_w = 3 if is_hl else 2
            pen_c = QColor("white") if is_hl else QColor("black")
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(pen_c, pen_w))
            for h in civ.hexes:
                px, py = hex_to_pixel(*h, hs)
                cx, cy = px + offset_x, py + offset_y
                painter.drawPolygon(self._create_hex_polygon(cx, cy))

        # 5. Culture Overlay
        if self.show_culture:
            for h, cdata in cultural_map.items():
                if not cdata:
                    continue
                dominant = max(cdata, key=cdata.get)
                civ = next((c for c in self.engine.alive_civs if c.name == dominant), None)
                if civ:
                    px, py = hex_to_pixel(*h, hs)
                    cx, cy = px + offset_x, py + offset_y
                    c_color = QColor(civ.color)
                    c_color.setAlpha(40)
                    painter.setBrush(QBrush(c_color))
                    painter.setPen(Qt.NoPen)
                    painter.drawPolygon(self._create_hex_polygon(cx, cy))

        # 6. Diplomacy Borders
        if self.show_diplomacy:
            for civ in self.engine.alive_civs:
                for ally_name in civ.allies:
                    ally = next((c for c in self.engine.alive_civs if c.name == ally_name), None)
                    if ally and civ.name < ally.name:
                        p1 = hex_to_pixel(*civ.capital, hs)
                        p2 = hex_to_pixel(*ally.capital, hs)
                        painter.setPen(QPen(QColor("#00ff00"), 2, Qt.DashLine))
                        painter.drawLine(QPointF(p1[0] + offset_x, p1[1] + offset_y),
                                         QPointF(p2[0] + offset_x, p2[1] + offset_y))
                for enemy_name in civ.enemies:
                    enemy = next((c for c in self.engine.alive_civs if c.name == enemy_name), None)
                    if enemy and civ.name < enemy.name:
                        p1 = hex_to_pixel(*civ.capital, hs)
                        p2 = hex_to_pixel(*enemy.capital, hs)
                        painter.setPen(QPen(QColor("#ff0000"), 2, Qt.DotLine))
                        painter.drawLine(QPointF(p1[0] + offset_x, p1[1] + offset_y),
                                         QPointF(p2[0] + offset_x, p2[1] + offset_y))

        # 7. Armies Overlay
        if self.show_armies:
            for civ in self.engine.alive_civs:
                for h, army in civ.armies.items():
                    if army > 0 and h in civ.hexes:
                        px, py = hex_to_pixel(*h, hs)
                        cx, cy = px + offset_x, py + offset_y
                        painter.setPen(QPen(QColor("white"), 1))
                        painter.setFont(QFont("Arial", max(5, int(8 * self.zoom)), QFont.Bold))
                        painter.drawText(QPointF(cx - 8 * self.zoom, cy + 10 * self.zoom), f"⚔{army}")

        # 8. Capitals & Golden Age
        for civ in self.engine.alive_civs:
            if civ.capital in civ.hexes:
                px, py = hex_to_pixel(*civ.capital, hs)
                cx, cy = px + offset_x, py + offset_y
                painter.setPen(QPen(QColor("white"), 2))
                painter.setFont(QFont("Segoe UI Emoji", max(8, int(14 * self.zoom)), QFont.Bold))
                star = "🌟" if civ.in_golden_age else "⭐"
                painter.drawText(QPointF(cx - 8 * self.zoom, cy + 8 * self.zoom), star)

        # 9. Disasters
        icons = {"flood": "🌊", "drought": "🔥", "plague": "☣️",
                 "volcano": "🌋", "earthquake": "💥", "blizzard": "❄️"}
        for h, (dt, _) in active_disasters.items():
            px, py = hex_to_pixel(*h, hs)
            cx, cy = px + offset_x, py + offset_y
            painter.setPen(QPen(QColor("white"), 1))
            painter.setFont(QFont("Segoe UI Emoji", max(6, int(12 * self.zoom))))
            painter.drawText(QPointF(cx - 8 * self.zoom, cy - 8 * self.zoom), icons.get(dt, "⚠️"))

        # 10. Selected Hex Highlight
        if self.selected:
            px, py = hex_to_pixel(*self.selected, hs)
            cx, cy = px + offset_x, py + offset_y
            poly = self._create_hex_polygon(cx, cy)
            painter.setBrush(QBrush(QColor(255, 255, 255, 60)))
            painter.setPen(QPen(QColor("white"), 3))
            painter.drawPolygon(poly)

        painter.end()

    def wheelEvent(self, event):
        factor = 1.1 if event.angleDelta().y() > 0 else 0.9
        self.zoom = max(0.3, min(5.0, self.zoom * factor))
        self.update()

    def mousePressEvent(self, event):
        if event.button() in (Qt.RightButton, Qt.MiddleButton):
            self._dragging = True
            self._last_pos = event.position()
        elif event.button() == Qt.LeftButton:
            ox, oy = self._center_offset()
            x, y = event.position().x() - ox, event.position().y() - oy
            self.selected = pixel_to_hex(x, y, self.hex_size)
            self.update()
            parent = self.parent()
            while parent and not isinstance(parent, CivSimWindow):
                parent = parent.parent()
            if parent:
                parent.update_hex_info(self.selected)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging and self._last_pos:
            delta = event.position() - self._last_pos
            self.pan_x += delta.x()
            self.pan_y += delta.y()
            self._last_pos = event.position()
            self.update()
        else:
            ox, oy = self._center_offset()
            x, y = event.position().x() - ox, event.position().y() - oy
            h = pixel_to_hex(x, y, self.hex_size)
            if h in self.engine.terrain:
                info = self.engine.get_hex_info(h)
                tip = f"{info['terrain'].title()} ({h[0]},{h[1]})"
                if info['owner']:
                    tip += f"\n{info['owner']}"
                if info['resource']:
                    tip += f"\n{info['resource'].title()}"
                if info['army'] > 0:
                    tip += f"\nArmy: {info['army']}"
                QToolTip.showText(event.globalPosition().toPoint(), tip, self)
            else:
                QToolTip.hideText()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() in (Qt.RightButton, Qt.MiddleButton):
            self._dragging = False
        super().mouseReleaseEvent(event)


# ======================================================================
# Main Window
# ======================================================================
class CivSimWindow(QMainWindow):
    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        self.setWindowTitle("CivSim — Advanced Civilization Simulator")
        self.setGeometry(50, 50, 1600, 900)
        self.setStyleSheet("""
            QMainWindow { background-color: #1a1a2e; color: #e0e0e0; }
            QWidget { background-color: #16213e; color: #e0e0e0; }
            QPushButton { background-color: #0f3460; padding: 6px; font-weight: bold; border-radius: 3px; }
            QPushButton:hover { background-color: #1a4a8a; }
            QSlider::groove:horizontal { background: #0f3460; height: 6px; }
            QSlider::handle:horizontal { background: #e94560; width: 14px; margin: -4px 0; border-radius: 7px; }
            QTableWidget { gridline-color: #333; background-color: #0f3460; }
            QHeaderView::section { background-color: #0f3460; padding: 4px; border: 1px solid #333; }
            QCheckBox { spacing: 5px; }
            QComboBox { background-color: #0f3460; padding: 4px; border-radius: 3px; }
        """)

        # Recording state
        self.recorder = None
        self._export_thread = None
        self._export_worker = None
        self._export_progress = None

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        # LEFT — map
        self.map_widget = HexMapScene(engine)
        splitter.addWidget(self.map_widget)

        # RIGHT — controls
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_panel.setMaximumWidth(650)
        splitter.addWidget(right_panel)

        # --- Controls ---
        ctrl_group = QGroupBox("Simulation")
        ctrl_layout = QHBoxLayout(ctrl_group)
        self.btn_pause = QPushButton("⏯ Pause")
        self.btn_pause.clicked.connect(self.toggle_pause)
        ctrl_layout.addWidget(self.btn_pause)
        self.btn_restart = QPushButton("🔄 New")
        self.btn_restart.clicked.connect(self.restart_sim)
        ctrl_layout.addWidget(self.btn_restart)
        self.btn_save = QPushButton("💾 Save")
        self.btn_save.clicked.connect(self.save_sim)
        ctrl_layout.addWidget(self.btn_save)
        self.btn_load = QPushButton("📂 Load")
        self.btn_load.clicked.connect(self.load_sim)
        ctrl_layout.addWidget(self.btn_load)
        self.slider_speed = QSlider(Qt.Horizontal)
        self.slider_speed.setRange(50, 2000)
        self.slider_speed.setValue(CONFIG["timer_interval"])
        ctrl_layout.addWidget(QLabel("Speed:"))
        ctrl_layout.addWidget(self.slider_speed)
        self.lbl_speed = QLabel(f"{CONFIG['timer_interval']}ms")
        ctrl_layout.addWidget(self.lbl_speed)
        self.slider_speed.valueChanged.connect(self._update_timer_speed)
        right_layout.addWidget(ctrl_group)

        # --- Overlays & Recording ---
        overlay_group = QGroupBox("Map Overlays & Recording")
        overlay_layout = QHBoxLayout(overlay_group)
        self.chk_res = QCheckBox("Resources")
        self.chk_res.setChecked(True)
        self.chk_res.toggled.connect(lambda v: (setattr(self.map_widget, 'show_resources', v), self.map_widget.update()))
        overlay_layout.addWidget(self.chk_res)
        self.chk_army = QCheckBox("Armies")
        self.chk_army.toggled.connect(lambda v: (setattr(self.map_widget, 'show_armies', v), self.map_widget.update()))
        overlay_layout.addWidget(self.chk_army)
        self.chk_culture = QCheckBox("Culture")
        self.chk_culture.toggled.connect(lambda v: (setattr(self.map_widget, 'show_culture', v), self.map_widget.update()))
        overlay_layout.addWidget(self.chk_culture)
        self.chk_diplo = QCheckBox("Diplomacy")
        self.chk_diplo.toggled.connect(lambda v: (setattr(self.map_widget, 'show_diplomacy', v), self.map_widget.update()))
        overlay_layout.addWidget(self.chk_diplo)
        self.chk_rivers = QCheckBox("Rivers")
        self.chk_rivers.setChecked(True)
        self.chk_rivers.toggled.connect(lambda v: (setattr(self.map_widget, 'show_rivers', v), self.map_widget.update()))
        overlay_layout.addWidget(self.chk_rivers)
        overlay_layout.addStretch()
        right_layout.addWidget(overlay_group)

        # --- Recording Buttons ---
        rec_group = QGroupBox("Video Recording")
        rec_layout = QHBoxLayout(rec_group)
        
        self.btn_record = QPushButton("⏺ Record MP4")
        self.btn_record.setCheckable(True)
        self.btn_record.toggled.connect(self.toggle_recording)
        rec_layout.addWidget(self.btn_record)
        
        self.btn_rec_start = QPushButton("🎬 Record from Start")
        self.btn_rec_start.clicked.connect(self.record_from_start)
        rec_layout.addWidget(self.btn_rec_start)
        
        right_layout.addWidget(rec_group)

        # --- Turn & hex info ---
        info_layout = QHBoxLayout()
        self.lbl_turn = QLabel("Turn: 0")
        self.lbl_turn.setStyleSheet("font-size: 16px; font-weight: bold; color: #e94560;")
        info_layout.addWidget(self.lbl_turn)
        self.lbl_hex_info = QLabel("Click hex for info")
        self.lbl_hex_info.setStyleSheet("font-size: 12px; color: #a0a0a0;")
        self.lbl_hex_info.setWordWrap(True)
        info_layout.addWidget(self.lbl_hex_info, stretch=1)
        right_layout.addLayout(info_layout)

        # --- Stats table ---
        self.table_civs = QTableWidget()
        self.table_civs.setColumnCount(9)
        self.table_civs.setHorizontalHeaderLabels(
            ["Civ", "Pop", "Mil", "Eco", "Cul", "Stab", "Hex", "Strategy", "Great Person"])
        self.table_civs.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_civs.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_civs.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_civs.clicked.connect(self.on_table_click)
        right_layout.addWidget(self.table_civs)

        # --- Charts ---
        self.fig, ((self.ax_pop, self.ax_terr), (self.ax_mil, self.ax_eco)) = \
            plt.subplots(2, 2, figsize=(6, 4), facecolor="#16213e")
        self.chart_canvas = FigureCanvas(self.fig)
        right_layout.addWidget(self.chart_canvas)

        # --- Log ---
        log_group = QGroupBox("Event Log")
        log_layout = QVBoxLayout(log_group)
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filter:"))
        self.combo_log_filter = QComboBox()
        self.combo_log_filter.addItems(
            ["All", "War", "Tech", "Diplomacy", "Disaster", "Wonder",
             "Golden Age", "Great Person"])
        filter_layout.addWidget(self.combo_log_filter)
        log_layout.addLayout(filter_layout)
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setStyleSheet(
            "background-color: #0f3460; color: #cccccc; "
            "font-family: monospace; font-size: 11px;")
        log_layout.addWidget(self.txt_log)
        right_layout.addWidget(log_group)

        # Timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.simulation_step)
        self.timer.start(CONFIG["timer_interval"])

    # ------------------------------------------------------------------
    # Keyboard shortcuts
    # ------------------------------------------------------------------
    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Space:
            self.toggle_pause()
        elif event.key() in (Qt.Key_Plus, Qt.Key_Equal):
            self.slider_speed.setValue(self.slider_speed.value() - 50)
        elif event.key() == Qt.Key_Minus:
            self.slider_speed.setValue(self.slider_speed.value() + 50)
        elif event.key() == Qt.Key_S and event.modifiers() & Qt.ControlModifier:
            self.save_sim()
        elif event.key() == Qt.Key_L and event.modifiers() & Qt.ControlModifier:
            self.load_sim()
        super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # Simulation controls
    # ------------------------------------------------------------------
    def toggle_pause(self):
        import config
        config.paused = not config.paused
        self.btn_pause.setText("⏯ Play" if config.paused else "⏯ Pause")

    def _update_timer_speed(self, value):
        self.timer.setInterval(value)
        self.lbl_speed.setText(f"{value}ms")

    def restart_sim(self):
        from engine import SimEngine
        import config
        config.paused = False
        config.history_log.clear()
        config.active_disasters.clear()
        config.cultural_map.clear()
        Civilization._cid = 0
        self.engine = SimEngine()
        self.map_widget.engine = self.engine
        self.map_widget.selected = None
        self.map_widget.highlight_civ = None
        self.update_ui()

    def save_sim(self):
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save Game", "civsim_save.pkl", "Save (*.pkl)")
        if filename:
            self.engine.save(filename)

    def load_sim(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, "Load Game", "", "Save (*.pkl)")
        if filename:
            from engine import SimEngine
            self.engine = SimEngine.load(filename)
            self.map_widget.engine = self.engine
            self.map_widget.selected = None
            self.map_widget.highlight_civ = None
            self.update_ui()

    # ------------------------------------------------------------------
    # Real-time recording (captures GUI widget frames)
    # ------------------------------------------------------------------
    def toggle_recording(self, checked):
        if checked:
            if not VideoRecorder.check_available():
                QMessageBox.warning(self, "Missing Dependency",
                                    "Video export requires imageio[ffmpeg].\n"
                                    "Install with: pip install imageio[ffmpeg]")
                self.btn_record.setChecked(False)
                return
            filename, _ = QFileDialog.getSaveFileName(
                self, "Save Video", "civsim_realtime.mp4", "Video (*.mp4)")
            if filename:
                self.recorder = VideoRecorder(filename)
                self.recorder.start()
                self.btn_record.setText("⏹ Stop Rec")
                self.btn_record.setStyleSheet("background-color: #8b0000;")
            else:
                self.btn_record.setChecked(False)
        else:
            if self.recorder:
                success = self.recorder.stop_and_save()
                if success:
                    QMessageBox.information(
                        self, "Video Saved",
                        f"Saved {self.recorder.frame_count} frames "
                        f"to {self.recorder.filename}")
                self.recorder = None
            self.btn_record.setText("⏺ Record MP4")
            self.btn_record.setStyleSheet("")

    # ------------------------------------------------------------------
    # Record from start (headless offscreen in background thread)
    # ------------------------------------------------------------------
    def record_from_start(self):
        """Spawn a background thread that runs a fresh sim from turn 1 and exports to MP4."""
        if not VideoRecorder.check_available():
            QMessageBox.warning(self, "Missing Dependency",
                                "Video export requires imageio[ffmpeg].\n"
                                "Install with: pip install imageio[ffmpeg]")
            return

        filename, _ = QFileDialog.getSaveFileName(
            self, "Save Video (From Start)", "civsim_from_start.mp4", "Video (*.mp4)")
        if not filename:
            return

        # Ask for max turns
        turns, ok = QInputDialog.getInt(
            self, "Record from Start", "Max turns to record:",
            value=CONFIG["max_turns"], min=10, max=10000, step=100)
        if not ok:
            return

        # Set up progress dialog
        self._export_progress = QProgressDialog(
            "Recording simulation from start…", "Cancel", 0, 0, self)
        self._export_progress.setWindowModality(Qt.WindowModal)
        self._export_progress.setMinimumDuration(0)
        self._export_progress.setAutoClose(True)
        self._export_progress.setAutoReset(True)
        self._export_progress.setLabelText(
            f"Running headless simulation ({turns} turns)…\n"
            "Progress is printed to the console.")
        self.btn_rec_start.setEnabled(False)

        # Create worker and thread
        self._export_thread = QThread()
        self._export_worker = _ExportWorker(
            filename=filename,
            fps=CONFIG["recording_fps"],
            max_turns=turns,
            map_radius=CONFIG["map_radius"],
            num_civs=CONFIG["num_initial_civs"],
        )
        self._export_worker.moveToThread(self._export_thread)
        self._export_thread.started.connect(self._export_worker.run)
        self._export_worker.finished.connect(self._on_export_finished)
        self._export_worker.error.connect(self._on_export_error)
        self._export_worker.finished.connect(self._export_thread.quit)
        self._export_worker.finished.connect(self._export_worker.deleteLater)
        self._export_thread.finished.connect(self._export_thread.deleteLater)

        # Handle cancel
        self._export_progress.canceled.connect(self._on_export_canceled)

        self._export_thread.start()

    def _on_export_finished(self, success):
        self.btn_rec_start.setEnabled(True)
        if self._export_progress:
            self._export_progress.close()
            self._export_progress = None
        if success:
            QMessageBox.information(self, "Recording Complete",
                                    "Video from start has been saved successfully!\n"
                                    "Check the console for details.")
        else:
            QMessageBox.warning(self, "Recording Failed",
                                "Failed to save the video.\n"
                                "Check the console for error details.")

    def _on_export_error(self, err_msg):
        self.btn_rec_start.setEnabled(True)
        if self._export_progress:
            self._export_progress.close()
            self._export_progress = None
        QMessageBox.critical(self, "Export Error", f"An error occurred:\n{err_msg}")

    def _on_export_canceled(self):
        # Note: truly canceling a running QThread gracefully requires a flag.
        # For simplicity, we just disable the UI. The thread will finish on its own.
        if self._export_progress:
            self._export_progress.setLabelText("Canceling… (thread will finish current run)")
        self.btn_rec_start.setEnabled(True)

    # ------------------------------------------------------------------
    # Table & hex interactions
    # ------------------------------------------------------------------
    def on_table_click(self, index):
        alive = sorted(self.engine.alive_civs, key=lambda x: x.power, reverse=True)
        if 0 <= index.row() < len(alive):
            self.map_widget.highlight_civ = alive[index.row()].name
            self.map_widget.update()

    def update_hex_info(self, hex_coord):
        info = self.engine.get_hex_info(hex_coord)
        text = f"📍({info['coord'][0]},{info['coord'][1]}) {info['terrain'].title()}"
        if info['is_river']:
            text += " 〰River"
        if info['resource']:
            text += f" | {info['resource'].title()}"
        if info['owner']:
            text += f" | 👑 {info['owner']}"
            if info.get('is_capital'):
                text += " (Capital)"
        if info['army'] > 0:
            text += f" | ⚔️ {info['army_owner']}: {info['army']}"
        if info['disaster']:
            text += f" | ☣️ {info['disaster'][0].title()}"
        self.lbl_hex_info.setText(text)

    # ------------------------------------------------------------------
    # Main simulation loop
    # ------------------------------------------------------------------
    def simulation_step(self):
        import config
        if not self.engine.victor and not config.paused:
            self.engine.step()
        # Capture frame for real-time video recording
        if self.recorder and self.recorder.recording:
            self.recorder.capture_widget(self.map_widget)
        self.update_ui()

    # ------------------------------------------------------------------
    # UI update
    # ------------------------------------------------------------------
    def update_ui(self):
        # Turn
        if self.engine.victor:
            self.lbl_turn.setText(
                f"🏆 {self.engine.victor.name} WINS! ({self.engine.victory_type})")
        else:
            self.lbl_turn.setText(
                f"Turn: {self.engine.turn} | Alive: {len(self.engine.alive_civs)}")
        self.map_widget.update()

        # Table
        alive = sorted(self.engine.alive_civs, key=lambda x: x.power, reverse=True)
        self.table_civs.setRowCount(len(alive))
        for i, c in enumerate(alive):
            era_s = c.era[:3].title()
            ga = "🌟" if c.in_golden_age else ""
            gp = c.great_person_name or ""
            items = [
                QTableWidgetItem(f"{c.name} [{era_s}]{ga}"),
                QTableWidgetItem(str(c.population)),
                QTableWidgetItem(f"{c.military:.2f}"),
                QTableWidgetItem(f"{c.economy:.2f}"),
                QTableWidgetItem(f"{c.culture:.2f}"),
                QTableWidgetItem(f"{c.stability:.2f}"),
                QTableWidgetItem(str(len(c.hexes))),
                QTableWidgetItem(c.strategy_name.title()),
                QTableWidgetItem(gp),
            ]
            items[0].setForeground(QColor(c.color))
            for j, item in enumerate(items):
                self.table_civs.setItem(i, j, item)

        # Log
        cur_filter = self.combo_log_filter.currentText().lower()
        filtered = []
        for msg in list(history_log)[-20:]:
            cat = categorize_log(msg)
            if cur_filter == "all" or cat == cur_filter:
                filtered.append(msg)
        self.txt_log.setHtml("<br>".join(filtered))
        self.txt_log.verticalScrollBar().setValue(
            self.txt_log.verticalScrollBar().maximum())

        # Charts (every 3 turns for perf)
        if self.engine.turn % 3 == 0 or self.engine.victor:
            self._update_charts(alive)

    def _update_charts(self, alive):
        for ax in [self.ax_pop, self.ax_terr, self.ax_mil, self.ax_eco]:
            ax.clear()
            ax.set_facecolor("#16213e")
            ax.tick_params(colors="white", labelsize=6)
            for spine in ax.spines.values():
                spine.set_color("#333")
        if not alive:
            self.chart_canvas.draw()
            return
        for c in alive:
            h = c.stats_history
            if h["population"]:
                self.ax_pop.plot(h["population"], color=c.color, linewidth=1, label=c.name)
                self.ax_terr.plot(h["territory"], color=c.color, linewidth=1, label=c.name)
                self.ax_mil.plot(h["military"], color=c.color, linewidth=1, label=c.name)
                self.ax_eco.plot(h["economy"], color=c.color, linewidth=1, label=c.name)
        self.ax_pop.set_title("Population", color="white", fontsize=8)
        self.ax_terr.set_title("Territory", color="white", fontsize=8)
        self.ax_mil.set_title("Military", color="white", fontsize=8)
        self.ax_eco.set_title("Economy", color="white", fontsize=8)
        self.ax_pop.legend(fontsize=5, loc="upper left",
                           facecolor="#16213e", edgecolor="#333", labelcolor="white")
        self.fig.tight_layout()
        self.chart_canvas.draw()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    def closeEvent(self, event):
        # Stop real-time recording if active
        if self.recorder and self.recorder.recording:
            self.recorder.cancel()
            self.recorder = None
        # Wait for background export thread
        if self._export_thread and self._export_thread.isRunning():
            self._export_thread.quit()
            self._export_thread.wait(3000)
        event.accept()