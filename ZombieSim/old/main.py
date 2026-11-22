import kivy
from kivy.app import App
from kivy.uix.widget import Widget
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.graphics import Color, Ellipse
from kivy.clock import Clock
import threading
import time
import random
import numpy as np

# For Matplotlib integration
from kivy.garden.matplotlib.backend_kivyagg import FigureCanvasKivyAgg
import matplotlib.pyplot as plt

# --- Simulation Model (Unchanged from the Tkinter version) ---
# This class handles the logic and is now made thread-safe.

class OutbreakSimulation:
    """Manages the state and logic of the zombie outbreak simulation."""
    def __init__(self, num_cities=20, grid_size=100, transmission_rate=0.3, removal_rate=0.05):
        self.grid_size = grid_size
        self.transmission_rate = transmission_rate
        self.removal_rate = removal_rate
        self.day = 0
        self.is_over = False
        self.lock = threading.Lock()  # Lock for thread-safe access

        self.cities = []
        for _ in range(num_cities):
            x = random.randint(10, grid_size - 10)
            y = random.randint(10, grid_size - 10)
            population = random.randint(5000, 500000)
            self.cities.append(City(x, y, population))

        patient_zero = random.choice(self.cities)
        with self.lock:
            patient_zero.infected = 1
            patient_zero.susceptible -= 1

        self.history_s = []
        self.history_i = []
        self.history_r = []

    def step(self):
        """Advances the simulation by one day."""
        with self.lock:
            if self.is_over:
                return

            self.day += 1
            new_infections = {}

            for city in self.cities:
                city.update(self.transmission_rate, self.removal_rate)

            for source_city in self.cities:
                if source_city.infected > 0:
                    for target_city in self.cities:
                        if source_city != target_city and target_city.susceptible > 0:
                            distance = np.sqrt((source_city.x - target_city.x)**2 + (source_city.y - target_city.y)**2)
                            if distance < 20 and random.random() < (source_city.infected / source_city.population) * 0.1:
                                num_to_infect = min(int(source_city.infected * 0.01), target_city.susceptible)
                                if num_to_infect > 0:
                                    if target_city not in new_infections:
                                        new_infections[target_city] = 0
                                    new_infections[target_city] += num_to_infect

            for city, num in new_infections.items():
                city.infected += num
                city.susceptible -= num

            total_s = sum(c.susceptible for c in self.cities)
            total_i = sum(c.infected for c in self.cities)
            total_r = sum(c.removed for c in self.cities)

            self.history_s.append(total_s)
            self.history_i.append(total_i)
            self.history_r.append(total_r)

            if total_i < 1:
                self.is_over = True

class City:
    """Represents a single city in the simulation."""
    def __init__(self, x, y, population):
        self.x = x
        self.y = y
        self.population = population
        self.susceptible = population
        self.infected = 0
        self.removed = 0

    def update(self, transmission_rate, removal_rate):
        if self.infected == 0:
            return
        new_infected = (self.susceptible * self.infected / self.population) * transmission_rate
        new_removed = self.infected * removal_rate
        new_infected = min(new_infected, self.susceptible)
        new_removed = min(new_removed, self.infected)
        self.susceptible -= new_infected
        self.infected += new_infected - new_removed
        self.removed += new_removed

# --- Kivy GUI Components ---

class MapWidget(Widget):
    """A custom widget to draw the infection map."""
    def __init__(self, simulation, **kwargs):
        super().__init__(**kwargs)
        self.simulation = simulation

    def draw_cities(self):
        """Clears and redraws all cities on the canvas."""
        self.canvas.clear()
        with self.simulation.lock:
            for city in self.simulation.cities:
                infection_ratio = city.infected / city.population if city.population > 0 else 0
                
                if infection_ratio < 0.05: color = (0.17, 0.8, 0.44, 1)  # Green
                elif infection_ratio < 0.25: color = (0.95, 0.77, 0.06, 1) # Yellow
                elif infection_ratio < 0.5: color = (0.9, 0.49, 0.13, 1)  # Orange
                else: color = (0.75, 0.22, 0.17, 1) # Red

                size = 5 + (city.population / 500000) * 25
                x, y = city.x * 5, city.y * 5

                with self.canvas:
                    Color(*color)
                    Ellipse(pos=(x - size, self.height - y - size), size=(size * 2, size * 2))

class OutbreakApp(App):
    """The main Kivy application."""
    def build(self):
        self.title = "Z-POC: Zombie Pathogen Outbreak Command Center"
        self.is_running = False
        self.simulation_thread = None

        # Main layout
        root = BoxLayout(orientation='vertical', padding=10, spacing=10)

        # --- Control Panel ---
        control_panel = BoxLayout(size_hint_y=None, height=50, spacing=10)
        self.start_button = Button(text='Start Outbreak')
        self.start_button.bind(on_press=self.toggle_simulation)
        self.reset_button = Button(text='Reset Simulation')
        self.reset_button.bind(on_press=self.reset_simulation)
        self.status_label = Label(text='Status: Ready', halign='left')
        control_panel.add_widget(self.start_button)
        control_panel.add_widget(self.reset_button)
        control_panel.add_widget(self.status_label)
        root.add_widget(control_panel)

        # --- Main Display Area ---
        main_display = BoxLayout(spacing=10)

        # --- Map Widget (Left) ---
        self.simulation = OutbreakSimulation()
        self.map_widget = MapWidget(self.simulation)
        main_display.add_widget(self.map_widget)

        # --- Right Panel ---
        right_panel = BoxLayout(orientation='vertical', spacing=10)

        # --- SIR Graph (Top Right) ---
        self.fig, self.sir_ax = plt.subplots(figsize=(5, 4), facecolor='#2c3e50')
        self.sir_canvas = FigureCanvasKivyAgg(self.fig)
        right_panel.add_widget(self.sir_canvas)

        # --- Statistics (Bottom Right) ---
        stats_panel = BoxLayout(orientation='vertical', size_hint_y=None, height=150, spacing=5)
        self.day_label = Label(text='Day: 0', font_size='20sp', bold=True)
        self.infected_label = Label(text='Total Infected: 0')
        self.casualties_label = Label(text='Total Casualties: 0')
        self.cities_overrun_label = Label(text='Cities Overrun: 0')
        stats_panel.add_widget(self.day_label)
        stats_panel.add_widget(self.infected_label)
        stats_panel.add_widget(self.casualties_label)
        stats_panel.add_widget(self.cities_overrun_label)
        right_panel.add_widget(stats_panel)

        main_display.add_widget(right_panel)
        root.add_widget(main_display)

        # Initial draw
        self.update_ui(None)
        return root

    def toggle_simulation(self, instance):
        """Starts or pauses the simulation thread."""
        if not self.is_running:
            self.is_running = True
            self.start_button.text = 'Pause Outbreak'
            self.status_label.text = 'Status: ACTIVE'
            self.simulation_thread = threading.Thread(target=self.run_simulation_loop, daemon=True)
            self.simulation_thread.start()
        else:
            self.is_running = False
            self.start_button.text = 'Resume Outbreak'
            self.status_label.text = 'Status: PAUSED'

    def run_simulation_loop(self):
        """The target for the simulation thread."""
        while self.is_running and not self.simulation.is_over:
            self.simulation.step()
            Clock.schedule_once(self.update_ui)
            time.sleep(0.05) # Control simulation speed

        if self.simulation.is_over:
            Clock.schedule_once(self.end_simulation)

    def end_simulation(self, dt):
        """Called when the simulation naturally ends."""
        self.is_running = False
        self.start_button.text = 'Start Outbreak'
        self.status_label.text = 'Status: Outbreak Ended'

    def reset_simulation(self, instance):
        """Resets the entire application state."""
        self.is_running = False
        if self.simulation_thread and self.simulation_thread.is_alive():
            self.simulation_thread.join(timeout=1)
        
        self.simulation = OutbreakSimulation()
        self.map_widget.simulation = self.simulation
        self.start_button.text = 'Start Outbreak'
        self.status_label.text = 'Status: Ready'
        self.update_ui(None)

    def update_ui(self, dt):
        """Updates all UI elements. Called from the main Kivy thread."""
        # Update Map
        self.map_widget.draw_cities()

        # Update Graph
        self.sir_ax.clear()
        days = range(len(self.simulation.history_s))
        self.sir_ax.plot(days, self.simulation.history_s, 'c-', label='Susceptible', linewidth=2)
        self.sir_ax.plot(days, self.simulation.history_i, 'm-', label='Infected (Zombies)', linewidth=2)
        self.sir_ax.plot(days, self.simulation.history_r, 'y-', label='Removed (Casualties)', linewidth=2)
        self.sir_ax.set_title("SIR Model Over Time")
        self.sir_ax.set_xlabel("Days")
        self.sir_ax.set_ylabel("Population")
        self.sir_ax.legend()
        self.sir_ax.grid(True, linestyle='--', alpha=0.6)
        self.sir_ax.set_facecolor('#34495e')
        self.sir_canvas.draw()

        # Update Stats
        with self.simulation.lock:
            total_infected = sum(c.infected for c in self.simulation.cities)
            total_casualties = sum(c.removed for c in self.simulation.cities)
            cities_overrun = sum(1 for c in self.simulation.cities if (c.infected / c.population) > 0.5)
            day = self.simulation.day

        self.day_label.text = f'Day: {day}'
        self.infected_label.text = f'Total Infected: {int(total_infected):,}'
        self.casualties_label.text = f'Total Casualties: {int(total_casualties):,}'
        self.cities_overrun_label.text = f'Cities Overrun: {cities_overrun}'

if __name__ == '__main__':
    OutbreakApp().run()