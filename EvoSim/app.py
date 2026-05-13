# app.py
import sys
import numpy as np
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QHBoxLayout
from PySide6.QtCore import QTimer
from config import FPS
from environment import Environment
from state import S, update_stats
from simulation import step, step_events
from audio import AudioEngine, get_active_notes
from visuals import CAGridWidget
from interactions import SettingsPanel, Recorder

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Evolutionary Cellular Automata - PySide6")
        self.resize(1100, 750)
        central_widget = QWidget(); self.setCentralWidget(central_widget)
        layout = QHBoxLayout(central_widget)

        self.env = Environment()
        self.audio_engine = AudioEngine()
        self.grid_widget = CAGridWidget()
        self.recorder = Recorder()
        self.settings_panel = SettingsPanel(S, self.recorder, self.grid_widget)

        layout.addWidget(self.grid_widget, 3)
        layout.addWidget(self.settings_panel, 1)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_step)
        self.timer.start(int(1000 / FPS))

    def update_step(self):
        if S['paused']:
            if S['recording']:
                audio_buf = self.audio_engine.get_current_buffer() if S['sound_on'] else None
                self.recorder.capture_frame(S, self.env, audio_buf)
            return

        S['generation'] += 1
        step(S, self.env.zone_energy_map, self.env.zone_harshness_map)
        step_events(S, self.env)
        total_pop, sp_pops, diversity, avg_e = update_stats(S)

        notes = get_active_notes(S, self.env.note_map)
        self.audio_engine.synthesize(notes, S['volume'], S['sound_on'])

        self.grid_widget.update_grid(S, self.env)
        self.settings_panel.update_stats_display(total_pop, sp_pops, diversity, avg_e, S['generation'])

        if S['recording']:
            audio_buf = self.audio_engine.get_current_buffer() if S['sound_on'] else None
            self.recorder.capture_frame(S, self.env, audio_buf)

    def closeEvent(self, event):
        self.timer.stop(); self.audio_engine.stop()
        if S['recording']: self.recorder.stop()
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyleSheet("""
        QWidget { background-color: #1e1e2e; color: #cdd6f4; font-size: 14px; }
        QGroupBox { border: 1px solid #45475a; border-radius: 5px; margin-top: 10px; padding-top: 15px; }
        QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px; }
        QPushButton { background-color: #313244; border: 1px solid #45475a; border-radius: 4px; padding: 5px; }
        QPushButton:hover { background-color: #45475a; }
        QSlider::groove:horizontal { height: 6px; background: #313244; border-radius: 3px; }
        QSlider::handle:horizontal { width: 10px; margin: -2px 0; background: #89b4fa; border-radius: 5px; }
        QCheckBox::indicator { width: 16px; height: 16px; }
        QComboBox { background-color: #313244; border: 1px solid #45475a; border-radius: 4px; padding: 4px; }
        QComboBox::drop-down { border: none; }
    """)
    window = MainWindow(); window.show()
    window.audio_engine.start()
    sys.exit(app.exec())