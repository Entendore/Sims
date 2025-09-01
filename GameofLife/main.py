import sys, numpy as np, json
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QCheckBox, QFileDialog
)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, FFMpegWriter
import sounddevice as sd
from scipy.ndimage import label
from scipy.io.wavfile import write

# ----------------------------
# CELLULAR AUTOMATA CLASS
# ----------------------------
class CellularAutomata:
    def __init__(self, shape=(30,30), density=0.25, birth=[3], survive=[2,3]):
        self.rows, self.cols = shape
        self.birth = birth
        self.survive = survive
        self.grid = np.random.rand(self.rows,self.cols)<density
        self.age = np.zeros_like(self.grid, dtype=int)

    def step(self):
        new_grid = np.zeros_like(self.grid)
        new_age = np.zeros_like(self.age)
        for i in range(self.rows):
            for j in range(self.cols):
                total = np.sum(self.grid[max(i-1,0):i+2, max(j-1,0):j+2]) - self.grid[i,j]
                if self.grid[i,j]:
                    if total in self.survive:
                        new_grid[i,j]=1
                        new_age[i,j]=self.age[i,j]+1
                else:
                    if total in self.birth:
                        new_grid[i,j]=1
                        new_age[i,j]=1
        self.grid=new_grid
        self.age=new_age
        return self.grid,self.age

# ----------------------------
# AUDIO GENERATION
# ----------------------------
def generate_audio(grid, ages, rate, duration, base_freq, freq_range, harmonics):
    t = np.linspace(0,duration,int(rate*duration),endpoint=False)
    signal_left = np.zeros_like(t)
    signal_right = np.zeros_like(t)
    labeled, num_features = label(grid>0)
    max_age = max(1,np.max(ages))
    rows,cols=grid.shape
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
    signal_left/=max_val
    signal_right/=max_val
    return np.stack([signal_left,signal_right],axis=-1)

# ----------------------------
# QT6 GUI
# ----------------------------
class CAStudio(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cellular Automata Studio")
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # Default config
        self.config = {
            "grid_size":[30,30], "init_density":0.25, "frames":300, "fps":15,
            "visual_mode":"cluster", "audio_rate":44100, "audio_chunk_duration":0.05,
            "base_freq":220, "freq_range":1000, "harmonics":[1,2,3],
            "birth":[3], "survive":[2,3]
        }
        self.ca = CellularAutomata(tuple(self.config['grid_size']),
                                   self.config['init_density'],
                                   self.config['birth'], self.config['survive'])

        # Dynamic Rule Editor
        rule_layout = QHBoxLayout()
        self.birth_input = QLineEdit("3")
        self.survive_input = QLineEdit("2,3")
        rule_layout.addWidget(QLabel("Birth (B):"))
        rule_layout.addWidget(self.birth_input)
        rule_layout.addWidget(QLabel("Survive (S):"))
        rule_layout.addWidget(self.survive_input)
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
        self.img = self.ax.imshow(self.ca.age, cmap='tab20', interpolation='nearest')
        self.ax.set_title("Cellular Automata")
        self.anim = None

    # ----------------------------
    # Simulation
    # ----------------------------
    def update_rule(self):
        try:
            birth = [int(x) for x in self.birth_input.text().split(',')]
            survive = [int(x) for x in self.survive_input.text().split(',')]
            self.ca.birth=birth
            self.ca.survive=survive
        except:
            print("Invalid rule input")

    def start_simulation(self):
        self.update_rule()
        self.anim = FuncAnimation(self.figure, self.update_frame,
                                  frames=self.config['frames'],
                                  interval=1000/self.config['fps'], blit=True)
        self.canvas.draw()

    def pause_simulation(self):
        if self.anim: self.anim.event_source.stop()

    def update_frame(self, frame):
        grid, age = self.ca.step()
        # Cluster-based coloring
        labeled, num_features = label(grid>0)
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
    # Export
    # ----------------------------
    def export_video_audio(self):
        video_file, _ = QFileDialog.getSaveFileName(self,"Save Video","","MP4 Files (*.mp4)")
        audio_file, _ = QFileDialog.getSaveFileName(self,"Save Audio","","WAV Files (*.wav)")
        if video_file and audio_file:
            self.update_rule()
            audio_frames=[]
            fig, ax = plt.subplots(figsize=(6,6))
            img=ax.imshow(self.ca.age, cmap='tab20', interpolation='nearest')
            writer = FFMpegWriter(fps=self.config['fps'], bitrate=1800)
            with writer.saving(fig, video_file, dpi=100):
                for f in range(self.config['frames']):
                    grid, age=self.ca.step()
                    labeled,_ = label(grid>0)
                    img.set_data(labeled)
                    writer.grab_frame()
                    chunk = generate_audio(grid, age, self.config['audio_rate'],
                                           self.config['audio_chunk_duration'],
                                           self.config['base_freq'],
                                           self.config['freq_range'],
                                           self.config['harmonics'])
                    audio_frames.append(chunk)
            full_audio=np.concatenate(audio_frames,axis=0)
            write(audio_file, self.config['audio_rate'], (full_audio*32767).astype(np.int16))
            print(f"Exported video: {video_file}, audio: {audio_file}")

    def export_audio_only(self):
        audio_file,_=QFileDialog.getSaveFileName(self,"Save Audio","","WAV Files (*.wav)")
        if audio_file:
            self.update_rule()
            audio_frames=[]
            for f in range(self.config['frames']):
                grid, age=self.ca.step()
                chunk=generate_audio(grid, age, self.config['audio_rate'],
                                     self.config['audio_chunk_duration'],
                                     self.config['base_freq'],
                                     self.config['freq_range'],
                                     self.config['harmonics'])
                audio_frames.append(chunk)
            full_audio=np.concatenate(audio_frames,axis=0)
            write(audio_file, self.config['audio_rate'], (full_audio*32767).astype(np.int16))
            print(f"Exported audio: {audio_file}")

# ----------------------------
# RUN APP
# ----------------------------
if __name__=="__main__":
    app = QApplication(sys.argv)
    window = CAStudio()
    window.show()
    sys.exit(app.exec())
