"""
Z-POC: Main application window featuring Dashboard and Settings Tabs.
Automatically starts recording if setting is checked.
"""

import threading
import time
from datetime import datetime

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QPushButton, QLabel, QSlider, QProgressBar,
    QTextEdit, QMessageBox, QFileDialog, QTabWidget, QGroupBox,
    QCheckBox, QSpinBox, QDoubleSpinBox, QFormLayout
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont

from constants import DARK_STYLESHEET, YOUTUBE_FPS
from simulation import OutbreakSimulation
from map_widget import QMapWidget
from sir_graph import SIRGraphCanvas
from video_exporter import VideoExporter, RenderVideoDialog


class OutbreakMainWindow(QMainWindow):

    update_signal = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Z-POC: Zombie Pathogen Outbreak Command Center")
        self.resize(1200, 800)

        self.is_running = False
        self.sim_thread = None
        self.sim_speed = 0.05
        self._seen_events = set()

        # ── Live recording state ──
        self.live_exporter = None
        self.capture_timer = None

        self.setStyleSheet(DARK_STYLESHEET)

        self.simulation = OutbreakSimulation()
        self._build_ui()

        # Map pulse animation
        self.pulse_timer = QTimer()
        self.pulse_timer.timeout.connect(self.map_widget.update)
        self.pulse_timer.start(120)

        self.update_signal.connect(self._update_ui)
        self._update_ui()

    # ═══════════════════════════════════════════════════
    #  UI construction
    # ═══════════════════════════════════════════════════

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(5, 5, 5, 5)
        root.setSpacing(3)

        # ── Title ──
        lbl_title = QLabel("Z-POC : ZOMBIE PATHOGEN OUTBREAK COMMAND CENTER")
        lbl_title.setAlignment(Qt.AlignCenter)
        lbl_title.setStyleSheet("color:#f23838; font-size:16px; font-weight:bold;")
        lbl_title.setFixedHeight(32)
        root.addWidget(lbl_title)

        # ── Top Control Bar ──
        ctrl = QHBoxLayout()
        ctrl.setSpacing(5)

        self.btn_start = QPushButton("▶  Start Outbreak")
        self.btn_start.setStyleSheet("background-color:#218c38; color:white;")
        self.btn_start.clicked.connect(self._toggle_sim)

        self.btn_reset = QPushButton("↺  Reset")
        self.btn_reset.setStyleSheet("background-color:#851c1c; color:white;")
        self.btn_reset.clicked.connect(self._reset_sim)

        self.btn_record = QPushButton("⏺  Record")
        self.btn_record.setStyleSheet("background-color:#666; color:white;")
        self.btn_record.clicked.connect(self._toggle_live_record)
        self.btn_record.setToolTip("Toggle live recording")

        ctrl.addWidget(self.btn_start)
        ctrl.addWidget(self.btn_reset)
        ctrl.addStretch()
        ctrl.addWidget(self.btn_record)
        root.addLayout(ctrl)

        # ── Tabs: Dashboard & Settings ──
        self.tabs = QTabWidget()
        root.addWidget(self.tabs)

        # == TAB 1: Dashboard ==
        dash_widget = QWidget()
        dash_layout = QHBoxLayout(dash_widget)
        dash_layout.setSpacing(5)

        self.map_widget = QMapWidget(self.simulation)
        self.map_widget.city_selected.connect(self._on_city_selected)
        dash_layout.addWidget(self.map_widget, stretch=2)

        right = QVBoxLayout()
        right.setSpacing(3)

        self.graph_canvas = SIRGraphCanvas()
        right.addWidget(self.graph_canvas, stretch=1)

        stats = QGridLayout()
        stats.setSpacing(2)
        self.lbl_day  = self._stat_lbl("Day: 0", 15, True, "white")
        self.lbl_r0   = self._stat_lbl("R₀: 0.00", 13, False, "#e6b3e6")
        self.lbl_sus  = self._stat_lbl("Susceptible: 0", 12, False, "#4de680")
        self.lbl_inf  = self._stat_lbl("Infected: 0", 12, False, "#ff4d4d")
        self.lbl_rem  = self._stat_lbl("Casualties: 0", 12, False, "#e6e64d")
        self.lbl_cinf = self._stat_lbl("Cities Infected: 0/0", 12, False, "#ff994d")
        self.lbl_over = self._stat_lbl("Overrun: 0", 12, False, "#ff6633")
        self.lbl_vax  = self._stat_lbl("Vaccinated: 0", 12, False, "#4dcfff")
        for i, w in enumerate([self.lbl_day, self.lbl_r0, self.lbl_sus, self.lbl_inf, self.lbl_rem, self.lbl_cinf, self.lbl_over, self.lbl_vax]):
            stats.addWidget(w, i // 2, i % 2)
        right.addLayout(stats)

        prog_row = QHBoxLayout()
        lbl_prog = QLabel("Infection:")
        lbl_prog.setStyleSheet("color:#b3b3b3; font-size:10px;")
        lbl_prog.setFixedWidth(65)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.lbl_pct = QLabel("0.0%")
        self.lbl_pct.setStyleSheet("color:#ff8080; font-size:11px;")
        self.lbl_pct.setFixedWidth(50)
        prog_row.addWidget(lbl_prog)
        prog_row.addWidget(self.progress)
        prog_row.addWidget(self.lbl_pct)
        right.addLayout(prog_row)

        self.lbl_city = QLabel("Click a city on the map for details")
        self.lbl_city.setWordWrap(True)
        self.lbl_city.setStyleSheet("color:#b3ccff; font-size:11px; padding:2px;")
        self.lbl_city.setFixedHeight(50)
        right.addWidget(self.lbl_city)

        city_btns = QHBoxLayout()
        city_btns.setSpacing(3)
        self.btn_c_quar = QPushButton("Quarantine")
        self.btn_c_quar.setStyleSheet("background-color:#224d8c; font-size:10px;")
        self.btn_c_quar.setEnabled(False)
        self.btn_c_quar.clicked.connect(self._quarantine_selected)

        self.btn_c_vax = QPushButton("Vaccinate")
        self.btn_c_vax.setStyleSheet("background-color:#227385; font-size:10px;")
        self.btn_c_vax.setEnabled(False)
        self.btn_c_vax.clicked.connect(self._vaccinate_selected)

        self.btn_nuke = QPushButton("☢ NUKE")
        self.btn_nuke.setStyleSheet("background-color:#991a1a; font-size:10px;")
        self.btn_nuke.setEnabled(False)
        self.btn_nuke.clicked.connect(self._nuke_selected)

        city_btns.addWidget(self.btn_c_quar)
        city_btns.addWidget(self.btn_c_vax)
        city_btns.addWidget(self.btn_nuke)
        right.addLayout(city_btns)

        self.event_log = QTextEdit()
        self.event_log.setReadOnly(True)
        self.event_log.setFont(QFont("Consolas", 9))
        right.addWidget(self.event_log, stretch=1)

        dash_layout.addLayout(right, stretch=1)
        self.tabs.addTab(dash_widget, "📡 Dashboard")

        # == TAB 2: Settings ==
        settings_widget = QWidget()
        settings_layout = QVBoxLayout(settings_widget)
        
        # -- Simulation Parameters Group --
        param_group = QGroupBox("Simulation Parameters")
        param_form = QFormLayout()
        
        self.slider_trans = QSlider(Qt.Horizontal)
        self.slider_trans.setRange(5, 80)
        self.slider_trans.setValue(int(self.simulation.transmission_rate * 100))
        self.slider_trans.valueChanged.connect(lambda v: setattr(self.simulation, 'transmission_rate', v / 100.0))
        self.lbl_trans_val = QLabel(f"{self.simulation.transmission_rate:.2f}")
        self.slider_trans.valueChanged.connect(lambda v: self.lbl_trans_val.setText(f"{v/100.0:.2f}"))
        row_trans = QHBoxLayout()
        row_trans.addWidget(self.slider_trans)
        row_trans.addWidget(self.lbl_trans_val)
        param_form.addRow("Transmission Rate:", row_trans)

        self.slider_rem = QSlider(Qt.Horizontal)
        self.slider_rem.setRange(10, 200)
        self.slider_rem.setValue(int(self.simulation.removal_rate * 1000))
        self.slider_rem.valueChanged.connect(lambda v: setattr(self.simulation, 'removal_rate', v / 1000.0))
        self.lbl_rem_val = QLabel(f"{self.simulation.removal_rate:.3f}")
        self.slider_rem.valueChanged.connect(lambda v: self.lbl_rem_val.setText(f"{v/1000.0:.3f}"))
        row_rem = QHBoxLayout()
        row_rem.addWidget(self.slider_rem)
        row_rem.addWidget(self.lbl_rem_val)
        param_form.addRow("Removal Rate:", row_rem)

        self.slider_speed = QSlider(Qt.Horizontal)
        self.slider_speed.setRange(1, 50)
        self.slider_speed.setValue(int(self.sim_speed * 100))
        self.slider_speed.valueChanged.connect(self._set_speed)
        self.lbl_speed_val = QLabel(f"{self.sim_speed:.2f}s")
        self.slider_speed.valueChanged.connect(lambda v: self.lbl_speed_val.setText(f"{v/100.0:.2f}s"))
        row_speed = QHBoxLayout()
        row_speed.addWidget(self.slider_speed)
        row_speed.addWidget(self.lbl_speed_val)
        param_form.addRow("Sim Step Delay:", row_speed)

        self.chk_autostart = QCheckBox("Auto-Start on Launch")
        param_form.addRow("Convenience:", self.chk_autostart)

        param_group.setLayout(param_form)
        settings_layout.addWidget(param_group)

        # -- Auto-Pilot Group --
        auto_group = QGroupBox("Auto-Pilot (No Interaction Needed)")
        auto_form = QFormLayout()

        self.chk_auto_quar = QCheckBox("Auto-Quarantine Cities")
        self.chk_auto_quar.setChecked(self.simulation.auto_quarantine_enabled)
        self.chk_auto_quar.toggled.connect(lambda v: setattr(self.simulation, 'auto_quarantine_enabled', v))
        auto_form.addRow("Enable:", self.chk_auto_quar)

        self.spin_quar_thresh = QDoubleSpinBox()
        self.spin_quar_thresh.setRange(0.05, 0.90)
        self.spin_quar_thresh.setSingleStep(0.05)
        self.spin_quar_thresh.setValue(self.simulation.auto_quarantine_threshold)
        self.spin_quar_thresh.valueChanged.connect(lambda v: setattr(self.simulation, 'auto_quarantine_threshold', v))
        auto_form.addRow("Quarantine Threshold:", self.spin_quar_thresh)

        self.chk_auto_vax = QCheckBox("Auto-Vaccinate Cities")
        self.chk_auto_vax.setChecked(self.simulation.auto_vaccinate_enabled)
        self.chk_auto_vax.toggled.connect(lambda v: setattr(self.simulation, 'auto_vaccinate_enabled', v))
        auto_form.addRow("Enable:", self.chk_auto_vax)

        self.spin_vax_thresh = QDoubleSpinBox()
        self.spin_vax_thresh.setRange(0.01, 0.50)
        self.spin_vax_thresh.setSingleStep(0.01)
        self.spin_vax_thresh.setValue(self.simulation.auto_vaccinate_threshold)
        self.spin_vax_thresh.valueChanged.connect(lambda v: setattr(self.simulation, 'auto_vaccinate_threshold', v))
        auto_form.addRow("Vaccine Threshold:", self.spin_vax_thresh)

        auto_group.setLayout(auto_form)
        settings_layout.addWidget(auto_group)

        # -- Display Group --
        disp_group = QGroupBox("Display Settings")
        disp_form = QFormLayout()

        self.chk_labels = QCheckBox("Show All City Labels")
        self.chk_labels.setChecked(True)
        self.chk_labels.toggled.connect(lambda v: setattr(self.map_widget, 'show_labels', v))
        disp_form.addRow("Map Labels:", self.chk_labels)

        disp_group.setLayout(disp_form)
        settings_layout.addWidget(disp_group)

        # -- Video & Recording Group --
        vid_group = QGroupBox("Video & Recording")
        vid_form = QFormLayout()

        self.chk_auto_record = QCheckBox("Auto-Record on Sim Start")
        self.chk_auto_record.setToolTip("Automatically starts recording to a timestamped file when simulation starts.")
        vid_form.addRow("Live Record:", self.chk_auto_record)

        btn_render = QPushButton("🎬  Render Full Simulation to MP4")
        btn_render.setStyleSheet("background-color:#5c2d91; color:white; padding:8px;")
        btn_render.clicked.connect(self._open_render_dialog)
        vid_form.addRow("Offline Render:", btn_render)

        vid_group.setLayout(vid_form)
        settings_layout.addWidget(vid_group)

        settings_layout.addStretch()
        self.tabs.addTab(settings_widget, "⚙ Settings")

        # Execute Auto-Start if checked
        if self.chk_autostart.isChecked():
            self._toggle_sim()

    @staticmethod
    def _stat_lbl(text, size, bold, color):
        lbl = QLabel(text)
        weight = "bold" if bold else "normal"
        lbl.setStyleSheet(f"color:{color}; font-size:{size}px; font-weight:{weight};")
        return lbl

    def _set_speed(self, v):
        self.sim_speed = v / 100.0

    # ═══════════════════════════════════════════════════
    #  Simulation control
    # ═══════════════════════════════════════════════════

    def _toggle_sim(self):
        if not self.is_running:
            self.is_running = True
            self.btn_start.setText("⏸  Pause")
            self.btn_start.setStyleSheet("background-color:#8c6e21; color:white;")
            self.sim_thread = threading.Thread(target=self._sim_loop, daemon=True)
            self.sim_thread.start()
            
            # Auto-Record Functionality
            if self.chk_auto_record.isChecked() and self.live_exporter is None:
                self._start_auto_record()
        else:
            self.is_running = False
            self.btn_start.setText("▶  Resume")
            self.btn_start.setStyleSheet("background-color:#218c38; color:white;")

    def _sim_loop(self):
        while self.is_running and not self.simulation.is_over:
            self.simulation.step()
            self.update_signal.emit()
            time.sleep(self.sim_speed)
        if self.simulation.is_over:
            self.update_signal.emit()

    def _reset_sim(self):
        self.is_running = False
        if self.sim_thread and self.sim_thread.is_alive():
            self.sim_thread.join(timeout=1)

        # Stop recording if active
        if self.live_exporter is not None:
            self._stop_live_record(save_msg=False)

        trans = self.simulation.transmission_rate
        rem = self.simulation.removal_rate
        auto_q = self.simulation.auto_quarantine_enabled
        q_thresh = self.simulation.auto_quarantine_threshold
        auto_v = self.simulation.auto_vaccinate_enabled
        v_thresh = self.simulation.auto_vaccinate_threshold

        self.simulation = OutbreakSimulation(transmission_rate=trans, removal_rate=rem)
        
        self.simulation.auto_quarantine_enabled = auto_q
        self.simulation.auto_quarantine_threshold = q_thresh
        self.simulation.auto_vaccinate_enabled = auto_v
        self.simulation.auto_vaccinate_threshold = v_thresh

        self.map_widget.simulation = self.simulation
        self.map_widget.selected_city = None
        self.graph_canvas.reset()

        self.btn_start.setText("▶  Start Outbreak")
        self.btn_start.setStyleSheet("background-color:#218c38; color:white;")
        self.event_log.clear()
        self._seen_events.clear()
        self._update_ui()

    # ═══════════════════════════════════════════════════
    #  Strategic actions (Manual Overrides)
    # ═══════════════════════════════════════════════════

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
        if not city: return
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Critical)
        msg.setWindowTitle("⚠  CONFIRM NUCLEAR STRIKE  ⚠")
        msg.setText(f"NUKE {city.name}?")
        msg.setInformativeText(f"This will kill ALL {city.population:,} inhabitants!\nThis CANNOT be undone.")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.No)
        msg.setStyleSheet("background-color:#2a0a0a; color:white;")
        if msg.exec() == QMessageBox.Yes:
            self.simulation.nuke_city(city)
            self._update_ui()

    # ═══════════════════════════════════════════════════
    #  Video recording logic
    # ═══════════════════════════════════════════════════

    def _start_auto_record(self):
        """Starts recording automatically to a timestamped file."""
        if not VideoExporter.is_available():
            self.chk_auto_record.setChecked(False)
            return
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = f"zpoc_auto_{timestamp}.mp4"
        
        self.live_exporter = VideoExporter(filepath, fps=YOUTUBE_FPS)
        try:
            self.live_exporter.start(title_text="Z-POC: ZOMBIE PATHOGEN OUTBREAK", subtitle_text="Auto-Recorded Simulation")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Could not start auto-recording:\n{exc}")
            self.live_exporter = None
            self.chk_auto_record.setChecked(False)
            return

        self.btn_record.setText("⏹  Stop Recording")
        self.btn_record.setStyleSheet("background-color:#cc0000; color:white;")
        self.setWindowTitle("🔴 REC  —  Z-POC Command Center")

        self.capture_timer = QTimer(self)
        self.capture_timer.timeout.connect(self._capture_live_frame)
        self.capture_timer.start(int(1000 / YOUTUBE_FPS))

    def _toggle_live_record(self):
        if self.live_exporter is not None:
            self._stop_live_record(save_msg=True)
        else:
            if not VideoExporter.is_available():
                QMessageBox.critical(self, "Missing Dependency", "Video export requires imageio with ffmpeg.\n\nInstall with:\n  pip install \"imageio[ffmpeg]\"")
                return

            filepath, _ = QFileDialog.getSaveFileName(self, "Save Recording", "zpoc_live.mp4", "MP4 Video (*.mp4)")
            if not filepath: return

            self.live_exporter = VideoExporter(filepath, fps=YOUTUBE_FPS)
            try:
                self.live_exporter.start(title_text="Z-POC: ZOMBIE PATHOGEN OUTBREAK", subtitle_text="Live Simulation")
            except Exception as exc:
                QMessageBox.critical(self, "Error", f"Could not start recording:\n{exc}")
                self.live_exporter = None
                return

            self.btn_record.setText("⏹  Stop Recording")
            self.btn_record.setStyleSheet("background-color:#cc0000; color:white;")
            self.setWindowTitle("🔴 REC  —  Z-POC Command Center")

            self.capture_timer = QTimer(self)
            self.capture_timer.timeout.connect(self._capture_live_frame)
            self.capture_timer.start(int(1000 / YOUTUBE_FPS))

    def _stop_live_record(self, save_msg=True):
        self.capture_timer.stop()
        self.capture_timer = None
        sim = self.simulation
        stats = f"Duration: {sim.day} days\nCasualties: {int(sum(c.removed for c in sim.cities)):,}"
        self.live_exporter.stop_with_end_card(stats, duration=3)
        n = self.live_exporter.frame_count
        path = self.live_exporter.filepath
        self.live_exporter = None

        self.btn_record.setText("⏺  Record")
        self.btn_record.setStyleSheet("background-color:#666; color:white;")
        self.setWindowTitle("Z-POC: Zombie Pathogen Outbreak Command Center")
        
        if save_msg:
            QMessageBox.information(self, "Recording Saved", f"Video saved to:\n{path}\n\nFrames: {n}")

    def _capture_live_frame(self):
        if self.live_exporter and self.live_exporter.is_recording:
            self.live_exporter.capture_frame(self.centralWidget())

    def _open_render_dialog(self):
        dlg = RenderVideoDialog(self, self)
        dlg.show()

    # ═══════════════════════════════════════════════════
    #  UI refresh
    # ═══════════════════════════════════════════════════

    def _update_ui(self):
        self.map_widget.update()
        self.graph_canvas.update_plot(self.simulation)

        with self.simulation.lock:
            total_pop = sum(c.population for c in self.simulation.cities)
            total_s   = sum(c.susceptible for c in self.simulation.cities)
            total_i   = sum(c.infected for c in self.simulation.cities)
            total_r   = sum(c.removed for c in self.simulation.cities)
            overrun   = sum(1 for c in self.simulation.cities if c.infection_ratio > 0.5)
            infected  = sum(1 for c in self.simulation.cities if c.infected > 0)
            n_cities  = len(self.simulation.cities)
            day       = self.simulation.day
            r0        = self.simulation.effective_r0
            vax       = self.simulation.total_vaccinated
            events    = list(self.simulation.events)

        pct = (total_i / total_pop * 100) if total_pop > 0 else 0.0

        self.lbl_day.setText(f"Day: {day}")
        self.lbl_r0.setText(f"R₀: {r0:.2f}")
        self.lbl_sus.setText(f"Susceptible: {int(total_s):,}")
        self.lbl_inf.setText(f"Infected: {int(total_i):,}")
        self.lbl_rem.setText(f"Casualties: {int(total_r):,}")
        self.lbl_cinf.setText(f"Cities Infected: {infected}/{n_cities}")
        self.lbl_over.setText(f"Overrun: {overrun}")
        self.lbl_vax.setText(f"Vaccinated: {vax:,}")

        self.progress.setValue(int(pct))
        self.lbl_pct.setText(f"{pct:.1f}%")

        self._update_city_info()
        self._update_event_log(events)

    def _update_city_info(self):
        city = self.map_widget.selected_city
        if city and not city.is_nuked:
            q = "Yes" if city.is_quarantined else "No"
            self.lbl_city.setText(
                f"<b>{city.name}</b>  |  Pop: {city.population:,}<br>"
                f"S: {int(city.susceptible):,}  I: {int(city.infected):,}  "
                f"R: {int(city.removed):,}  "
                f"({city.infection_ratio*100:.1f}% infected)<br>"
                f"Quarantined: {q}  |  "
                f"Vaccinated: {city.vaccination_rate*100:.0f}%"
            )
            self.btn_c_quar.setEnabled(True)
            self.btn_c_vax.setEnabled(True)
            self.btn_nuke.setEnabled(True)
            self.btn_c_quar.setText("Release City" if city.is_quarantined else "Quarantine")
        elif city and city.is_nuked:
            self.lbl_city.setText(f"<b>{city.name}</b>  —  DESTROYED")
            self.btn_c_quar.setEnabled(False)
            self.btn_c_vax.setEnabled(False)
            self.btn_nuke.setEnabled(False)
        else:
            self.lbl_city.setText("Click a city on the map for details")
            self.btn_c_quar.setEnabled(False)
            self.btn_c_vax.setEnabled(False)
            self.btn_nuke.setEnabled(False)

    def _update_event_log(self, events):
        new = [e for e in events if e not in self._seen_events]
        if not new: return

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
            elif "[AUTO]" in e:
                html_parts.append(f'<span style="color:#bb86fc">{e}</span>')
            else:
                html_parts.append(f'<span style="color:#bbbbbb">{e}</span>')

        self.event_log.append("<br>".join(html_parts))
        scrollbar = self.event_log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())