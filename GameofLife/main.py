import sys, json, numpy as np
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QLabel,
    QFileDialog, QComboBox, QSpinBox, QCheckBox, QHBoxLayout
)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, FFMpegWriter
import sounddevice as sd
from scipy.ndimage import uniform_filter, label
from scipy.io.wavfile import write

# ----------------------------
# GAME OF LIFE LOGIC
# ----------------------------
class GameOfLife:
    def __init__(self, shape=(30,30), density=0.3):
        self.rows, self.cols = shape
        self.grid = np.random.rand(self.rows, self.cols) < density
        self.age = np.zeros_like(self.grid, dtype=int)

    def step(self):
        new_grid = np.zeros_like(self.grid)
        for i in range(self.rows):
            for j in range(self.cols):
                total = np.sum(self.grid[max(i-1,0):i+2, max(j-1,0):j+2]) - self.grid[i,j]
                if self.grid[i,j]:
                    if total == 2 or total == 3:
                        new_grid[i,j] = 1
                        self.age[i,j] += 1
                    else:
                        new_grid[i,j] = 0
                        self.age[i,j] = 0
                else:
                    if total == 3:
                        new_grid[i,j] = 1
                        self.age[i,j] = 1
        self.grid = new_grid
        return self.grid, self.age

# ----------------------------
# AUDIO GENERATION
# ----------------------------
def generate_audio(grid, ages, rate, duration, base_freq, freq_range, harmonics):
    t = np.linspace(0, duration, int(rate*duration), endpoint=False)
    signal_left = np.zeros_like(t)
    signal_right = np.zeros_like(t)
    rows, cols = grid.shape
    max_age = max(1, np.max(ages))
    labeled, num_features = label(grid)
    for i in range(rows):
        for j in range(cols):
            if grid[i,j]:
                cluster = labeled[i,j]
                cluster_size = np.sum(labeled==cluster)
                freq = base_freq + (ages[i,j]/max_age)*freq_range + cluster_size*10
                amp = 0.2*(ages[i,j]/max_age)
                pan = j/cols
                cell_signal = np.zeros_like(t)
                for h in harmonics:
                    cell_signal += amp*np.sin(2*np.pi*freq*h*t)
                signal_left += cell_signal*(1-pan)
                signal_right += cell_signal*pan
    max_val = max(np.max(np.abs(signal_left)), np.max(np.abs(signal_right)), 1e-6)
    signal_left /= max_val
    signal_right /= max_val
    return np.stack([signal_left, signal_right], axis=-1)

# ----------------------------
# QT6 INTERFACE
# ----------------------------
class GameOfLifeApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Generative Audio-Visual Game of Life")
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # Default config
        self.config = {
            "grid_size":[30,30], "init_density":0.25, "frames":300, "fps":15,
            "visual_mode":"age_color", "audio_rate":44100, "audio_chunk_duration":0.05,
            "base_freq":220, "freq_range":1000, "harmonics":[1,2,3]
        }

        self.game = GameOfLife(tuple(self.config['grid_size']), self.config['init_density'])

        # Top controls
        top_layout = QHBoxLayout()
        self.load_btn = QPushButton("Load Config")
        self.load_btn.clicked.connect(self.load_config)
        top_layout.addWidget(self.load_btn)

        self.start_btn = QPushButton("Start")
        self.start_btn.clicked.connect(self.start_simulation)
        top_layout.addWidget(self.start_btn)

        self.pause_btn = QPushButton("Pause")
        self.pause_btn.clicked.connect(self.pause_simulation)
        top_layout.addWidget(self.pause_btn)

        self.audio_checkbox = QCheckBox("Enable Audio")
        self.audio_checkbox.setChecked(True)
        top_layout.addWidget(self.audio_checkbox)

        self.layout.addLayout(top_layout)

        # Visual mode
        self.visual_mode_combo = QComboBox()
        self.visual_mode_combo.addItems(["binary","age_color","cluster_color"])
        self.visual_mode_combo.setCurrentText(self.config['visual_mode'])
        self.layout.addWidget(QLabel("Visualization Mode:"))
        self.layout.addWidget(self.visual_mode_combo)

        # Matplotlib figure
        self.figure, self.ax = plt.subplots(figsize=(6,6))
        self.canvas = FigureCanvas(self.figure)
        self.layout.addWidget(self.canvas)
        self.img = self.ax.imshow(self.game.age, cmap='viridis', interpolation='nearest')
        self.ax.set_title("Game of Life")

        # Animation
        self.anim = None
        self.running = False

        # Export buttons
        export_layout = QHBoxLayout()
        self.export_video_btn = QPushButton("Export Video + Audio")
        self.export_video_btn.clicked.connect(self.export_video_audio)
        export_layout.addWidget(self.export_video_btn)
        self.export_audio_btn = QPushButton("Export Audio Only")
        self.export_audio_btn.clicked.connect(self.export_audio_only)
        export_layout.addWidget(self.export_audio_btn)
        self.layout.addLayout(export_layout)

    # ----------------------------
    # CONFIG LOADING
    # ----------------------------
    def load_config(self):
        file_name,_ = QFileDialog.getOpenFileName(self,"Open Config","","JSON Files (*.json)")
        if file_name:
            with open(file_name,'r') as f:
                self.config = json.load(f)
            self.game = GameOfLife(tuple(self.config['grid_size']), self.config['init_density'])
            self.visual_mode_combo.setCurrentText(self.config.get('visual_mode','age_color'))
            print(f"Config loaded: {file_name}")

    # ----------------------------
    # SIMULATION CONTROLS
    # ----------------------------
    def start_simulation(self):
        if self.anim: self.anim.event_source.stop()
        self.running = True
        self.anim = FuncAnimation(self.figure, self.update_frame, frames=self.config['frames'],
                                  interval=1000/self.config['fps'], blit=True)
        self.canvas.draw()

    def pause_simulation(self):
        self.running = False
        if self.anim: self.anim.event_source.stop()

    def update_frame(self, frame):
        grid, age = self.game.step()
        visual_mode = self.visual_mode_combo.currentText()
        if visual_mode == 'binary':
            self.img.set_data(grid)
        elif visual_mode == 'age_color':
            self.img.set_data(age)
        else: # cluster_color
            labeled, _ = label(grid)
            self.img.set_data(labeled)
        if self.audio_checkbox.isChecked():
            chunk = generate_audio(grid, age, self.config['audio_rate'],
                                   self.config['audio_chunk_duration'],
                                   self.config['base_freq'],
                                   self.config['freq_range'],
                                   self.config['harmonics'])
            sd.play(chunk, self.config['audio_rate'], blocking=False)
        return [self.img]

    # ----------------------------
    # EXPORT FUNCTIONS
    # ----------------------------
    def export_video_audio(self):
        video_file, _ = QFileDialog.getSaveFileName(self,"Save Video","","MP4 Files (*.mp4)")
        audio_file, _ = QFileDialog.getSaveFileName(self,"Save Audio","","WAV Files (*.wav)")
        if video_file and audio_file:
            audio_frames = []
            fig, ax = plt.subplots(figsize=(6,6))
            img = ax.imshow(self.game.age, cmap='viridis', interpolation='nearest')
            ax.set_title("Game of Life")
            writer = FFMpegWriter(fps=self.config['fps'], metadata=dict(artist='GameOfLife'), bitrate=1800)
            with writer.saving(fig, video_file, dpi=100):
                for f in range(self.config['frames']):
                    grid, age = self.game.step()
                    visual_mode = self.visual_mode_combo.currentText()
                    if visual_mode == 'binary': img.set_data(grid)
                    elif visual_mode == 'age_color': img.set_data(age)
                    else: img.set_data(label(grid)[0])
                    writer.grab_frame()
                    chunk = generate_audio(grid, age, self.config['audio_rate'],
                                           self.config['audio_chunk_duration'],
                                           self.config['base_freq'],
                                           self.config['freq_range'],
                                           self.config['harmonics'])
                    audio_frames.append(chunk)
            full_audio = np.concatenate(audio_frames, axis=0)
            write(audio_file, self.config['audio_rate'], (full_audio*32767).astype(np.int16))
            print(f"Exported video: {video_file}, audio: {audio_file}")

    def export_audio_only(self):
        audio_file, _ = QFileDialog.getSaveFileName(self,"Save Audio","","WAV Files (*.wav)")
        if audio_file:
            audio_frames = []
            for f in range(self.config['frames']):
                grid, age = self.game.step()
                chunk = generate_audio(grid, age, self.config['audio_rate'],
                                       self.config['audio_chunk_duration'],
                                       self.config['base_freq'],
                                       self.config['freq_range'],
                                       self.config['harmonics'])
                audio_frames.append(chunk)
            full_audio = np.concatenate(audio_frames, axis=0)
            write(audio_file, self.config['audio_rate'], (full_audio*32767).astype(np.int16))
            print(f"Exported audio: {audio_file}")

# ----------------------------
# RUN APP
# ----------------------------
if __name__=="__main__":
    app = QApplication(sys.argv)
    window = GameOfLifeApp()
    window.show()
    sys.exit(app.exec())
