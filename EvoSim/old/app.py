# main.py
from matplotlib.animation import FuncAnimation
import matplotlib.pyplot as plt  # <-- THIS WAS MISSING
import numpy as np

from Sims.EvoSim.old.config import MAX_STEPS, FPS
from Sims.EvoSim.old.environment import Environment
from Sims.EvoSim.old.state import S, update_stats
from Sims.EvoSim.old.simulation import step
from Sims.EvoSim.old.events import step_events
from Sims.EvoSim.old.audio import AudioEngine, get_active_notes
from Sims.EvoSim.old.visuals import Visualizer
from Sims.EvoSim.old.interactions import setup_interactions

# --- MP4 Recorder Class ---
class Recorder:
    def __init__(self):
        self.writer = None

    def start(self, filename='simulation.mp4'):
        try:
            import imageio
            self.writer = imageio.get_writer(filename, fps=FPS, quality=8)
            print(f"Recording started: {filename}")
            return True
        except ImportError:
            print("MP4 recording requires `imageio` and `imageio-ffmpeg`.")
            print("Install via: pip install imageio imageio-ffmpeg")
            return False
        except Exception as e:
            print(f"Failed to start recording: {e}")
            return False

    def capture_frame(self, fig):
        if self.writer:
            try:
                fig.canvas.draw()
                # Convert matplotlib canvas to RGB array
                img = np.frombuffer(fig.canvas.buffer_rgba(), dtype=np.uint8)
                img = img.reshape(fig.canvas.get_width_height()[::-1] + (4,))[:, :, :3] # Drop alpha
                self.writer.append_data(img)
            except Exception as e:
                print(f"Error capturing frame: {e}")

    def stop(self):
        if self.writer:
            self.writer.close()
            self.writer = None
            print("Recording stopped. File saved.")

# Initialize components
env = Environment()
audio_engine = AudioEngine()
vis = Visualizer()
recorder = Recorder()

# Wire up interactions and widgets
setup_interactions(vis.get_fig(), S, vis.get_ax1(), recorder)

def update(frame_num):
    if S['paused']:
        if S['recording']:
            recorder.capture_frame(vis.get_fig())
        return [vis.im, vis.pop_line, vis.info_text, vis.div_line, vis.energy_line] + vis.species_lines

    S['generation'] += 1

    # Core simulation steps
    step(S, env.zone_energy_map, env.zone_harshness_map)
    step_events(S, env)
    total_pop, sp_pops, diversity, avg_e = update_stats(S)

    # Audio mapping and synthesis
    notes = get_active_notes(S, env.note_map)
    audio_engine.synthesize(notes, S['volume'], S['sound_on'])

    # Update matplotlib visuals
    vis.render_grid(S, env)
    vis.update_plots(S, total_pop, sp_pops, diversity, avg_e)

    # MP4 Recording
    if S['recording']:
        recorder.capture_frame(vis.get_fig())

    return [vis.im, vis.pop_line, vis.info_text, vis.div_line, vis.energy_line] + vis.species_lines

if __name__ == '__main__':
    audio_engine.start()
    
    anim = FuncAnimation(vis.get_fig(), update, frames=MAX_STEPS,
                         interval=1000 / FPS, blit=False, repeat=True)
    
    plt.show() # Now plt is defined!
    
    # Cleanup on window close
    audio_engine.stop()
    if S['recording']:
        recorder.stop()