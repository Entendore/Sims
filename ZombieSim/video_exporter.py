"""
Z-POC: MP4 video export for YouTube.

Streams frames directly to disk via imageio + ffmpeg so memory
usage stays constant regardless of video length.

Requirements:
    pip install imageio[ffmpeg]
"""

import numpy as np

from PySide6.QtCore import Qt, QRect, QTimer
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont, QImage, QPen
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QProgressBar, QFileDialog, QMessageBox,
    QCheckBox,
)

from constants import YOUTUBE_WIDTH, YOUTUBE_HEIGHT, YOUTUBE_FPS


class VideoExporter:
    """Capture Qt widgets and write them straight to an MP4 file."""

    def __init__(self, filepath,
                 target_width=YOUTUBE_WIDTH,
                 target_height=YOUTUBE_HEIGHT,
                 fps=YOUTUBE_FPS):
        self.filepath = filepath
        self.target_width = target_width
        self.target_height = target_height
        self.fps = fps
        self.writer = None
        self.frame_count = 0
        self.is_recording = False

    def start(self, title_text="", subtitle_text=""):
        import imageio
        self.writer = imageio.get_writer(
            self.filepath, fps=self.fps,
            codec="libx264",
            output_params=["-pix_fmt", "yuv420p"],
        )
        self.is_recording = True
        self.frame_count = 0
        if title_text:
            self._write_title_card(title_text, subtitle_text)

    def stop(self):
        self.is_recording = False
        if self.writer is not None:
            self.writer.close()
            self.writer = None
        return self.frame_count

    def stop_with_end_card(self, stats_text="", duration=4):
        if self.writer is not None and self.is_recording:
            self._write_end_card(stats_text, duration)
        return self.stop()

    def capture_frame(self, widget):
        if not self.is_recording or self.writer is None:
            return
        pixmap = widget.grab()
        scaled = pixmap.scaled(
            self.target_width, self.target_height,
            Qt.KeepAspectRatio, Qt.SmoothTransformation,
        )
        canvas = QPixmap(self.target_width, self.target_height)
        canvas.fill(QColor(20, 22, 28))
        x = (self.target_width - scaled.width()) // 2
        y = (self.target_height - scaled.height()) // 2
        p = QPainter(canvas)
        p.drawPixmap(x, y, scaled)
        p.end()

        arr = self._pixmap_to_array(canvas)
        self.writer.append_data(arr)
        self.frame_count += 1

    def _write_title_card(self, title, subtitle="", duration=3):
        pm = QPixmap(self.target_width, self.target_height)
        pm.fill(QColor(14, 16, 22))
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor(242, 56, 56, 80), 2))
        m = 80
        p.drawLine(m, m, self.target_width - m, m)
        p.drawLine(m, self.target_height - m, self.target_width - m, self.target_height - m)

        p.setFont(QFont("Arial", 52, QFont.Bold))
        p.setPen(QColor(242, 56, 56))
        p.drawText(QRect(0, self.target_height // 2 - 80, self.target_width, 100), Qt.AlignCenter, title)

        if subtitle:
            p.setFont(QFont("Arial", 26))
            p.setPen(QColor(200, 200, 200))
            p.drawText(QRect(0, self.target_height // 2 + 30, self.target_width, 60), Qt.AlignCenter, subtitle)

        p.setFont(QFont("Arial", 14))
        p.setPen(QColor(100, 100, 100))
        p.drawText(QRect(0, self.target_height - m - 30, self.target_width, 30), Qt.AlignCenter, "Z-POC Command Center Simulation")
        p.end()

        arr = self._pixmap_to_array(pm)
        for _ in range(int(self.fps * duration)):
            self.writer.append_data(arr)
            self.frame_count += 1

    def _write_end_card(self, stats_text="", duration=4):
        pm = QPixmap(self.target_width, self.target_height)
        pm.fill(QColor(14, 16, 22))
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)

        p.setFont(QFont("Arial", 40, QFont.Bold))
        p.setPen(QColor(242, 56, 56))
        p.drawText(QRect(0, self.target_height // 2 - 120, self.target_width, 80), Qt.AlignCenter, "OUTBREAK CONCLUDED")

        if stats_text:
            p.setFont(QFont("Arial", 20))
            p.setPen(QColor(200, 200, 200))
            p.drawText(QRect(0, self.target_height // 2 - 20, self.target_width, 120), Qt.AlignCenter, stats_text)

        p.setFont(QFont("Arial", 14))
        p.setPen(QColor(80, 80, 80))
        p.drawText(QRect(0, self.target_height - 100, self.target_width, 30), Qt.AlignCenter, "Thanks for watching")
        p.end()

        arr = self._pixmap_to_array(pm)
        for _ in range(int(self.fps * duration)):
            self.writer.append_data(arr)
            self.frame_count += 1

    def _pixmap_to_array(self, pixmap):
        image = pixmap.toImage().convertToFormat(QImage.Format_RGB888)
        w = image.width()
        h = image.height()
        bpl = image.bytesPerLine()
        ptr = image.constBits()
        ptr.setsize(h * bpl)
        if bpl == w * 3:
            return np.frombuffer(ptr, dtype=np.uint8).reshape((h, w, 3)).copy()
        raw = np.frombuffer(ptr, dtype=np.uint8).reshape((h, bpl))
        return raw[:, : w * 3].reshape((h, w, 3)).copy()

    @staticmethod
    def is_available():
        try:
            import imageio
            return True
        except ImportError:
            return False


class RenderVideoDialog(QDialog):
    """Non-modal dialog that renders the simulation to MP4 until the outbreak ends."""

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.exporter = None
        self.render_timer = None
        self.is_rendering = False
        self.frames_per_day = 3
        self._day_sub_frame = 0

        self.setWindowTitle("🎬  Render YouTube Video")
        self.setMinimumWidth(440)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        def _row(label_text, widget):
            row = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setFixedWidth(130)
            row.addWidget(lbl)
            row.addWidget(widget)
            return row

        self.combo_res = QComboBox()
        self.combo_res.addItems(["1280×720  (720p)", "1920×1080 (1080p)", "3840×2160 (4K)"])
        self.combo_res.setCurrentIndex(1)
        layout.addLayout(_row("Resolution:", self.combo_res))

        self.combo_fps = QComboBox()
        self.combo_fps.addItems(["24", "30", "60"])
        self.combo_fps.setCurrentIndex(1)
        layout.addLayout(_row("Frame Rate:", self.combo_fps))

        # Replaced Max Sim Days with Playback Speed (Frames per Day)
        self.combo_speed = QComboBox()
        self.combo_speed.addItems([
            "Slow (10 f/day)", "Normal (5 f/day)", 
            "Fast (2 f/day)", "Very Fast (1 f/day)"
        ])
        self.combo_speed.setCurrentIndex(1)
        layout.addLayout(_row("Playback Speed:", self.combo_speed))

        self.chk_cards = QCheckBox("Include title & end cards")
        self.chk_cards.setChecked(True)
        layout.addWidget(self.chk_cards)

        # Use progress bar in busy mode since we don't know the total days
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        layout.addWidget(self.progress)

        self.lbl_status = QLabel("Configure settings and click Start Render.\nRender will continue until the outbreak ends.")
        self.lbl_status.setWordWrap(True)
        layout.addWidget(self.lbl_status)

        btn_row = QHBoxLayout()
        self.btn_start = QPushButton("🎬  Start Render")
        self.btn_start.setStyleSheet("background-color:#218c38; color:white; padding:8px;")
        self.btn_start.clicked.connect(self._start_render)
        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self._on_close)
        btn_row.addWidget(self.btn_start)
        btn_row.addWidget(self.btn_close)
        layout.addLayout(btn_row)

    def _resolution(self):
        txt = self.combo_res.currentText()
        if "720p" in txt: return 1280, 720
        if "4K" in txt: return 3840, 2160
        return 1920, 1080

    def _get_frames_per_day(self):
        txt = self.combo_speed.currentText()
        if "10" in txt: return 10
        if "5" in txt: return 5
        if "2" in txt: return 2
        return 1

    def _start_render(self):
        if not VideoExporter.is_available():
            QMessageBox.critical(self, "Missing Dependency", "Video export requires imageio with ffmpeg.\n\nInstall with:\n  pip install \"imageio[ffmpeg]\"")
            return

        filepath, _ = QFileDialog.getSaveFileName(self, "Save Video", "zpoc_outbreak_full.mp4", "MP4 Video (*.mp4)")
        if not filepath: return

        self.main_window.is_running = False
        self.main_window._reset_sim()

        fps = int(self.combo_fps.currentText())
        w, h = self._resolution()
        self.frames_per_day = self._get_frames_per_day()

        self.exporter = VideoExporter(filepath, w, h, fps)
        try:
            if self.chk_cards.isChecked():
                self.exporter.start(title_text="Z-POC: ZOMBIE PATHOGEN OUTBREAK", subtitle_text="Pathogen Spread Simulation")
            else:
                self.exporter.start()
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Could not start writer:\n{exc}")
            return

        self.main_window.showNormal()
        self.main_window.raise_()
        self.main_window.tabs.setCurrentIndex(0)

        self.is_rendering = True
        self._day_sub_frame = 0
        self.btn_start.setEnabled(False)
        self.lbl_status.setText("Rendering – waiting for outbreak to end...")

        # Set progress bar to busy mode (0, 0)
        self.progress.setRange(0, 0)
        self.progress.setValue(0)

        self.render_timer = QTimer(self)
        self.render_timer.timeout.connect(self._render_step)
        self.render_timer.start(1)

    def _render_step(self):
        if not self.is_rendering: return
        sim = self.main_window.simulation

        self.exporter.capture_frame(self.main_window.centralWidget())
        self._day_sub_frame += 1

        if self._day_sub_frame >= self.frames_per_day:
            self._day_sub_frame = 0
            sim.step()
            self.main_window._update_ui()

        total_i = int(sum(c.infected for c in sim.cities))
        self.lbl_status.setText(
            f"Day {sim.day}  |  Frames: {self.exporter.frame_count}  |  "
            f"Currently Infected: {total_i:,}"
        )

        # ONLY stop when the outbreak naturally concludes
        if sim.is_over:
            self._finish_render()

    def _finish_render(self):
        self.is_rendering = False
        if self.render_timer:
            self.render_timer.stop()
            self.render_timer = None

        self.main_window._update_ui()
        self.exporter.capture_frame(self.main_window.centralWidget())

        sim = self.main_window.simulation
        if self.chk_cards.isChecked():
            stats = f"Duration: {sim.day} days\nCasualties: {int(sum(c.removed for c in sim.cities)):,}\nCities Nuked: {sim.nuked_cities}"
            self.exporter.stop_with_end_card(stats)
        else:
            self.exporter.stop()

        # Restore progress bar
        self.progress.setRange(0, 100)
        self.progress.setValue(100)
        
        w, h = self._resolution()
        self.lbl_status.setText(f"✅  Outbreak Ended!\nSaved: {self.exporter.filepath}\nFrames: {self.exporter.frame_count}")
        QMessageBox.information(self, "Render Complete", f"YouTube video saved to:\n{self.exporter.filepath}\n\nResolution: {w}×{h}\nFrames: {self.exporter.frame_count}\nSim days: {sim.day}")
        self.btn_start.setEnabled(True)

    def _on_close(self):
        if self.is_rendering:
            ans = QMessageBox.question(self, "Cancel Render?", "Rendering is in progress. Stop and discard?", QMessageBox.Yes | QMessageBox.No)
            if ans == QMessageBox.Yes:
                self.is_rendering = False
                if self.render_timer: self.render_timer.stop()
                if self.exporter: self.exporter.stop()
                self.progress.setRange(0, 100)
                self.reject()
        else:
            self.accept()