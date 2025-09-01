import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import sounddevice as sd

# ----------------------------
# CONFIG
# ----------------------------
config = {
    'grid_size': (40, 40),
    'init_density': 0.25,
    'frames': 200,
    'fps': 10,
    'visual_mode': 'age_color',  # options: 'binary', 'age_color'
    'audio_rate': 44100,
    'audio_chunk_duration': 0.1,  # seconds per step
    'base_freq': 200,             # Hz
    'freq_range': 1200,           # Hz
}

# ----------------------------
# GAME OF LIFE
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
# AUDIO MAPPING
# ----------------------------
def generate_audio_chunk(ages, rate, duration, base_freq, freq_range):
    """Generate an audio chunk based on cell ages using FFT mapping."""
    t = np.linspace(0, duration, int(rate*duration), endpoint=False)
    
    # Flatten the ages to map to frequency bins
    flat_ages = ages.flatten()
    max_age = max(1, np.max(flat_ages))
    
    # Map ages to frequencies
    freqs = base_freq + (flat_ages / max_age) * freq_range
    
    # Map ages to amplitudes
    amplitudes = (flat_ages / max_age) * 0.3
    
    # Sum sine waves for each cell
    signal = np.zeros_like(t)
    for f, a in zip(freqs, amplitudes):
        signal += a * np.sin(2 * np.pi * f * t)
    
    # Normalize to prevent clipping
    signal /= np.max(np.abs(signal)) + 1e-6
    return signal

# ----------------------------
# VISUALIZATION
# ----------------------------
def visualize_game(game, config):
    fig, ax = plt.subplots()
    grid, age = game.step()
    
    if config['visual_mode'] == 'binary':
        img = ax.imshow(grid, cmap='Greys', interpolation='nearest')
    else:
        img = ax.imshow(age, cmap='viridis', interpolation='nearest')

    # Audio stream for real-time playback
    def update(frame):
        grid, age = game.step()
        if config['visual_mode'] == 'binary':
            img.set_data(grid)
        else:
            img.set_data(age)
        
        # Generate audio chunk and play
        chunk = generate_audio_chunk(age, config['audio_rate'],
                                     config['audio_chunk_duration'],
                                     config['base_freq'],
                                     config['freq_range'])
        sd.play(chunk, config['audio_rate'], blocking=False)
        return [img]

    anim = FuncAnimation(fig, update, frames=config['frames'],
                         interval=1000/config['fps'], blit=True)
    plt.show()

# ----------------------------
# MAIN
# ----------------------------
if __name__ == "__main__":
    game = GameOfLife(config['grid_size'], config['init_density'])
    visualize_game(game, config)
