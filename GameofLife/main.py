import sys, numpy as np
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QComboBox, QCheckBox, QFileDialog
)
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtCore import Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, FFMpegWriter
import sounddevice as sd
from scipy.ndimage import label
from scipy.io.wavfile import write

# ----------------------------
# HIGH-DPI FIX
# ----------------------------
QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

# ----------------------------
# CELLULAR AUTOMATA CLASS
# ----------------------------
class CellularAutomata:
    def __init__(self, shape=(50,50), birth=[3], survive=[2,3], name="Custom"):
        self.rows, self.cols = shape
        self.birth = birth
        self.survive = survive
        self.name = name
        self.grid = np.random.randint(0,2,(self.rows,self.cols),dtype=int)
        self.age = np.zeros((self.rows,self.cols), dtype=int)

    def step(self):
        new_grid = np.zeros_like(self.grid)
        new_age = np.zeros_like(self.age)
        for i in range(self.rows):
            for j in range(self.cols):
                total = np.sum(self.grid[max(i-1,0):i+2, max(j-1,0):j+2]) - self.grid[i,j]
                if self.grid[i,j]:
                    if total in self.survive:
                        new_grid[i,j] = 1
                        new_age[i,j] = self.age[i,j]+1
                else:
                    if total in self.birth:
                        new_grid[i,j] = 1
                        new_age[i,j] = 1
        self.grid = new_grid
        self.age = new_age
        return self.grid, self.age

# ----------------------------
# CLUSTER-SPECIFIC AUDIO
# ----------------------------
def generate_audio_cluster_advanced(grid, ages, rate, duration, base_freq, default_freq_range,
                                    default_harmonics, default_waveform='sine'):
    t = np.linspace(0, duration, int(rate*duration), endpoint=False)
    signal_left = np.zeros_like(t)
    signal_right = np.zeros_like(t)
    labeled, num_features = label(grid>0)
    max_age = max(1, np.max(ages))
    rows, cols = grid.shape

    # Cluster parameters
    waveform_types = ['sine','square','saw','triangle']
    cluster_waveforms = {}
    cluster_freq_ranges = {}
    cluster_harmonics = {}
    for c in range(1,num_features+1):
        cluster_waveforms[c] = waveform_types[(c-1) % len(waveform_types)]
        cluster_freq_ranges[c] = default_freq_range*(0.8 + 0.1*c)
        cluster_harmonics[c] = [h*(1+c%3) for h in default_harmonics]

    def waveform_func(freq, t, type):
        if type=='sine': return np.sin(2*np.pi*freq*t)
        elif type=='square': return np.sign(np.sin(2*np.pi*freq*t))
        elif type=='saw': return 2*(t*freq - np.floor(t*freq + 0.5))
        elif type=='triangle': return 2*np.abs(2*(t*freq - np.floor(t*freq + 0.5)))-1
        return np.sin(2*np.pi*freq*t)

    for i in range(rows):
        for j in range(cols):
            if grid[i,j]:
                cluster = labeled[i,j]
                waveform = cluster_waveforms.get(cluster, default_waveform)
                freq_range = cluster_freq_ranges.get(cluster, default_freq_range)
                harmonics = cluster_harmonics.get(cluster, default_harmonics)

                cluster_size = np.sum(labeled==cluster)
                freq = base_freq + (ages[i,j]/max_age)*freq_range + cluster_size*10
                amp = 0.2*(ages[i,j]/max_age)
                pan = j/cols
                cell_signal = np.zeros_like(t)
                for h in harmonics:
                    cell_signal += amp*waveform_func(freq*h, t, waveform)
                signal_left += cell_signal*(1-pan)
                signal_right += cell_signal*pan

    max_val = max(np.max(np.abs(signal_left)), np.max(np.abs(signal_right)), 1e-6)
    signal_left /= max_val
    signal_right /= max_val
    return np.stack([signal_left, signal_right], axis=-1)

# ----------------------------
# PRESETS
# ----------------------------
PRESETS = {
    "Conway":{"birth":[3],"survive":[2,3],"waveform":"sine"},
    "HighLife":{"birth":[3,6],"survive":[2,3],"waveform":"saw"},
    "Seeds":{"birth":[2],"survive":[],"waveform":"square"},
    "Brian":{"birth":[2],"survive":[],"waveform":"triangle"}
}

# ----------------------------
# GUI
# ----------------------------
class CAStudio(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Advanced Cellular Automata Studio")
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # Initialize CA
        preset = PRESETS["Conway"]
        self.ca = CellularAutomata(name="Conway", birth=preset["birth"], survive=preset["survive"])
        self.current_waveform = preset["waveform"]

        # Preset selector
        self.rule_combo = QComboBox()
        self.rule_combo.addItems(PRESETS.keys())
        self.rule_combo.currentTextChanged.connect(self.load_preset)
        self.layout.addWidget(QLabel("Select Rule Preset:"))
        self.layout.addWidget(self.rule_combo)

        # Rule editor
        rule_layout = QHBoxLayout()
        self.birth_input = QLineEdit(",".join(map(str,self.ca.birth)))
        self.survive_input = QLineEdit(",".join(map(str,self.ca.survive)))
        self.waveform_combo = QComboBox()
        self.waveform_combo.addItems(['sine','square','saw','triangle'])
        self.waveform_combo.setCurrentText(self.current_waveform)
        rule_layout.addWidget(QLabel("Birth (B):"))
        rule_layout.addWidget(self.birth_input)
        rule_layout.addWidget(QLabel("Survive (S):"))
        rule_layout.addWidget(self.survive_input)
        rule_layout.addWidget(QLabel("Waveform:"))
        rule_layout.addWidget(self.waveform_combo)
        self.layout.addLayout(rule_layout)

        # Controls
        control_layout = QHBoxLayout()
        self.start_btn = QPushButton("Start")
        self.start_btn.clicked.connect(self.start_simulation)
        self.pause_btn = QPushButton("Pause")
        self.pause_btn.clicked.connect(self.pause_simulation)
        self.audio_checkbox = QCheckBox("Enable Audio")
        self.audio_checkbox.setChecked(True)
        control_layout.addWidget(self.start_btn)
        control_layout.addWidget(self.pause_btn)
        control_layout.addWidget(self.audio_checkbox)
        self.layout.addLayout(control_layout)

        # Export buttons
        export_layout = QHBoxLayout()
        self.export_video_btn = QPushButton("Export Video + Audio")
        self.export_video_btn.clicked.connect(self.export_video_audio)
        self.export_audio_btn = QPushButton("Export Audio Only")
        self.export_audio_btn.clicked.connect(self.export_audio_only)
        export_layout.addWidget(self.export_video_btn)
        export_layout.addWidget(self.export_audio_btn)
        self.layout.addLayout(export_layout)

        # Visualization
        self.figure, self.ax = plt.subplots(figsize=(6,6))
        self.canvas = FigureCanvas(self.figure)
        self.layout.addWidget(self.canvas)
        self.img = self.ax.imshow(self.ca.age, cmap='tab20', vmin=0, vmax=10, interpolation='nearest')
        self.ax.set_title("Cellular Automata (Age/Cluster)")
        self.anim = None

        # Simulation config
        self.config_frames = 300
        self.config_fps = 15
        self.config_audio_rate = 44100
        self.config_audio_chunk = 0.05
        self.config_base_freq = 220
        self.config_freq_range = 1000
        self.config_harmonics = [1,2,3]

    # ----------------------------
    # Preset loader
    # ----------------------------
    def load_preset(self, name):
        preset = PRESETS[name]
        self.ca.birth = preset["birth"]
        self.ca.survive = preset["survive"]
        self.birth_input.setText(",".join(map(str,preset["birth"])))
        self.survive_input.setText(",".join(map(str,preset["survive"])))
        self.waveform_combo.setCurrentText(preset["waveform"])
        self.current_waveform = preset["waveform"]
        self.ca.name = name

    # ----------------------------
    # Update rule
    # ----------------------------
    def update_rule(self):
        try:
            birth = [int(x) for x in self.birth_input.text().split(',') if x]
            survive = [int(x) for x in self.survive_input.text().split(',') if x]
            waveform = self.waveform_combo.currentText()
            self.ca.birth = birth
            self.ca.survive = survive
            self.current_waveform = waveform
        except:
            print("Invalid input")

    # ----------------------------
    # Simulation
    # ----------------------------
    def start_simulation(self):
        self.update_rule()
        self.anim = FuncAnimation(self.figure, self.update_frame,
                                  frames=self.config_frames,
                                  interval=1000/self.config_fps, blit=False)
        self.canvas.draw()

    def pause_simulation(self):
        if self.anim: self.anim.event_source.stop()

    def update_frame(self, frame):
        grid, age = self.ca.step()
        labeled,_ = label(grid>0)
        # Display clusters with age mapping
        self.img.set_data(age + labeled*2)  # combine age + cluster for color variation
        self.img.set_clim(vmin=0, vmax=max(10,np.max(age+labeled*2)))
        if self.audio_checkbox.isChecked():
            chunk = generate_audio_cluster_advanced(
                grid, age,
                self.config_audio_rate,
                self.config_audio_chunk,
                self.config_base_freq,
                self.config_freq_range,
                self.config_harmonics,
                self.current_waveform
            )
            sd.play(chunk, self.config_audio_rate, blocking=False)
        self.canvas.draw()
        return [self.img]

    # ----------------------------
    # Export
    # ----------------------------
    def export_video_audio(self):
        video_file,_ = QFileDialog.getSaveFileName(self,"Save Video","","MP4 Files (*.mp4)")
        audio_file,_ = QFileDialog.getSaveFileName(self,"Save Audio","","WAV Files (*.wav)")
        if video_file and audio_file:
            self.update_rule()
            audio_frames=[]
            fig, ax = plt.subplots(figsize=(6,6))
            img=ax.imshow(self.ca.age, cmap='tab20', vmin=0, vmax=10, interpolation='nearest')
            writer = FFMpegWriter(fps=self.config_fps, bitrate=1800)
            with writer.saving(fig, video_file, dpi=100):
                for f in range(self.config_frames):
                    grid, age = self.ca.step()
                    labeled,_ = label(grid>0)
                    img.set_data(age + labeled*2)
                    img.set_clim(vmin=0, vmax=max(10,np.max(age+labeled*2)))
                    writer.grab_frame()
                    chunk = generate_audio_cluster_advanced(
                        grid, age,
                        self.config_audio_rate,
                        self.config_audio_chunk,
                        self.config_base_freq,
                        self.config_freq_range,
                        self.config_harmonics,
                        self.current_waveform
                    )
                    audio_frames.append(chunk)
            full_audio = np.concatenate(audio_frames, axis=0)
            write(audio_file, self.config_audio_rate, (full_audio*32767).astype(np.int16))
            print(f"Exported video: {video_file}, audio: {audio_file}")

    def export_audio_only(self):
        audio_file,_ = QFileDialog.getSaveFileName(self,"Save Audio","","WAV Files (*.wav)")
        if audio_file:
            self.update_rule()
            audio_frames=[]
            for f in range(self.config_frames):
                grid, age = self.ca.step()
                chunk = generate_audio_cluster_advanced(
                    grid, age,
                    self.config_audio_rate,
                    self.config_audio_chunk,
                    self.config_base_freq,
                    self.config_freq_range,
                    self.config_harmonics,
                    self.current_waveform
                )
                audio_frames.append(chunk)
            full_audio = np.concatenate(audio_frames, axis=0)
            write(audio_file, self.config_audio_rate, (full_audio*32767).astype(np.int16))
            print(f"Exported audio: {audio_file}")

# ----------------------------
# Run App
# ----------------------------
if __name__=="__main__":
    app = QApplication(sys.argv)
    window = CAStudio()
    window.show()
    sys.exit(app.exec())
