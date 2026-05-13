# main.py
from matplotlib.animation import FuncAnimation
import matplotlib.pyplot as plt

from config import MAX_STEPS, FPS
from environment import Environment
from state import S, update_stats
from simulation import step
from events import step_events
from audio import AudioEngine, get_active_notes
from visuals import Visualizer
from interactions import setup_interactions

# Initialize components
env = Environment()
audio_engine = AudioEngine()
vis = Visualizer()

# Wire up interactions
setup_interactions(vis.get_fig(), S, vis.get_ax1())

def update(frame_num):
    if S['paused']:
        return [vis.im, vis.pop_line, vis.info_text, vis.div_line, vis.energy_line] + vis.species_lines

    S['generation'] += 1

    # Core simulation steps
    step(S, env.zone_energy_map, env.zone_harshness_map)
    step_events(S, env)
    total_pop, sp_pops, diversity, avg_e = update_stats(S)

    # Audio mapping and synthesis
    notes = get_active_notes(S, env.note_map)
    audio_engine.synthesize(notes, S['volume'])

    # Update matplotlib visuals
    vis.render_grid(S, env)
    vis.update_plots(S, total_pop, sp_pops, diversity, avg_e)

    return [vis.im, vis.pop_line, vis.info_text, vis.div_line, vis.energy_line] + vis.species_lines

if __name__ == '__main__':
    audio_engine.start()
    
    anim = FuncAnimation(vis.get_fig(), update, frames=MAX_STEPS,
                         interval=1000 / FPS, blit=False, repeat=True)
    plt.show()
    
    audio_engine.stop()