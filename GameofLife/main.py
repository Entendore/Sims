import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, FFMpegWriter
import sounddevice as sd
from scipy.ndimage import uniform_filter, label
from scipy.io.wavfile import write

# ----------------------------
# CONFIG
# ----------------------------
config = {
    'grid_size': (50, 50),
    'init_density': 0.25,
    'frames': 300,
    'fps': 15,
    'visual_mode': 'age_color',  # 'binary' or 'age_color'
    'audio_rate': 44100,
    'audio_chunk_duration': 0.1,
    'base_freq': 220,
    'freq_range': 1000,
    'harmonics': [1, 2, 3],
    'output_video': 'game_of_life_final.mp4',
    'output_audio': 'game_of_life_audio.wav'
}

# ----------------------------
# GAME OF LIFE CLASS
# ----------------------------
class GameOfLife:
    def __init__(self, shape, density=0.2):
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
    
    # Label clusters for waveform/harmonic mapping
    labeled, num_features = label(grid)
    
    for i in range(rows):
        for j in range(cols):
            if grid[i, j]:
                cluster = labeled[i, j]
                cluster_size = np.sum(labeled == cluster)
                
                # Frequency: age + cluster size
                freq = base_freq + (ages[i,j]/max_age)*freq_range + cluster_size*10
                amp = 0.2 * (ages[i,j]/max_age)
                pan = j / cols  # stereo panning
                
                # Harmonics based on cluster size
                cell_signal = np.zeros_like(t)
                for h in harmonics:
                    cell_signal += amp * np.sin(2*np.pi*freq*h*t)
                
                signal_left += cell_signal * (1-pan)
                signal_right += cell_signal * pan
    
    # Normalize
    max_val = max(np.max(np.abs(signal_left)), np.max(np.abs(signal_right)), 1e-6)
    signal_left /= max_val
    signal_right /= max_val
    stereo_signal = np.stack([signal_left, signal_right], axis=-1)
    return stereo_signal

# ----------------------------
# VISUALIZATION AND EXPORT
# ----------------------------
def visualize_and_export(game, config):
    fig, ax = plt.subplots(figsize=(6,6))
    
    # Initial frame
    grid, age = game.step()
    if config['visual_mode'] == 'binary':
        img = ax.imshow(grid, cmap='Greys', interpolation='nearest')
    else:
        img = ax.imshow(age, cmap='viridis', interpolation='nearest')
    ax.set_title("Game of Life")
    
    audio_frames = []

    def update(frame):
        grid, age = game.step()
        if config['visual_mode'] == 'binary':
            img.set_data(grid)
        else:
            img.set_data(age)
        
        # Generate audio for this frame
        chunk = generate_audio(grid, age, config['audio_rate'], config['audio_chunk_duration'],
                               config['base_freq'], config['freq_range'], config['harmonics'])
        audio_frames.append(chunk)
        return [img]

    writer = FFMpegWriter(fps=config['fps'], metadata=dict(artist='GameOfLife'), bitrate=1800)
    with writer.saving(fig, config['output_video'], dpi=100):
        for frame in range(config['frames']):
            update(frame)
            writer.grab_frame()
    
    # Combine audio frames
    full_audio = np.concatenate(audio_frames, axis=0)
    write(config['output_audio'], config['audio_rate'], (full_audio*32767).astype(np.int16))
    print(f"Exported video to {config['output_video']} and audio to {config['output_audio']}")

# ----------------------------
# MAIN
# ----------------------------
if __name__ == "__main__":
    game = GameOfLife(config['grid_size'], config['init_density'])
    visualize_and_export(game, config)
