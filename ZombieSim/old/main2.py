"""
Z-POC: Zombie Pathogen Outbreak Command Center
================================================
Requirements:
  pip install kivy numpy matplotlib
  garden install matplotlib   (or: pip install kivy-garden.matplotlib)
"""

import kivy
from kivy.app import App
from kivy.uix.widget import Widget
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.slider import Slider
from kivy.uix.scrollview import ScrollView
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.popup import Popup
from kivy.uix.progressbar import ProgressBar
from kivy.graphics import Color, Ellipse, Line, Rectangle
from kivy.core.text import Label as CoreLabel
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import sp
import threading
import time
import random
import math
import numpy as np

try:
    from kivy.garden.matplotlib.backend_kivyagg import FigureCanvasKivyAgg
except ImportError:
    from kivy_garden.matplotlib import FigureCanvasKivyAgg

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


# ═══════════════════════════════════════════════════════
#  City name pool for thematic immersion
# ═══════════════════════════════════════════════════════
CITY_NAMES = [
    "Haven", "Blackwood", "Cresthill", "Duskfield", "Ironhaven",
    "Millford", "Northgate", "Oakhaven", "Redmoor", "Silverdale",
    "Thornwall", "Ashford", "Brierwood", "Copperwell", "Dawnfield",
    "Eastport", "Fairhaven", "Glenwood", "Hartfield", "Jadecove",
    "Kingsford", "Lakewatch", "Mistwood", "Newhaven", "Pinecrest",
    "Ravensholm", "Stonebridge", "Twilight", "Umberland", "Wraithmoor",
    "Yorkshire", "Zephyr", "Amberdale", "Brookhaven", "Cinderpeak",
    "Driftwood", "Emberfall", "Frosthollow", "Grimstone", "Hollowdale",
]


# ═══════════════════════════════════════════════════════
#  Simulation Model
# ═══════════════════════════════════════════════════════

class City:
    """Represents a single city with SIR compartments and strategic state."""

    def __init__(self, x, y, population, name="Unknown"):
        self.x = x
        self.y = y
        self.population = population
        self.susceptible = float(population)
        self.infected = 0.0
        self.removed = 0.0
        self.name = name
        self.is_quarantined = False
        self.is_nuked = False
        self.vaccination_rate = 0.0
        self.infection_day = None
        self.connections = []          # neighbouring cities
        self.daily_new = 0             # new infections today (for graphing)

    def update(self, transmission_rate, removal_rate):
        if self.infected == 0 or self.is_nuked:
            self.daily_new = 0
            return

        effective_trans = transmission_rate * (1.0 - self.vaccination_rate)
        if self.is_quarantined:
            effective_trans *= 0.3      # quarantine reduces local spread

        new_inf = min(
            (self.susceptible * self.infected / self.population) * effective_trans,
            self.susceptible,
        )
        new_rem = min(self.infected * removal_rate, self.infected)

        self.susceptible -= new_inf
        self.infected += new_inf - new_rem
        self.removed += new_rem
        self.daily_new = new_inf

    @property
    def infection_ratio(self):
        return self.infected / self.population if self.population > 0 else 0.0


class OutbreakSimulation:
    """Core simulation engine – thread-safe with RLock."""

    def __init__(self, num_cities=20, grid_size=100,
                 transmission_rate=0.3, removal_rate=0.05):
        self.grid_size = grid_size
        self.transmission_rate = transmission_rate
        self.removal_rate = removal_rate
        self.day = 0
        self.is_over = False
        self.lock = threading.RLock()       # re-entrant – avoids deadlocks
        self.events = []
        self.quarantine_active = False
        self.total_vaccinated = 0
        self.nuked_cities = 0

        # --- build cities ---
        self.cities = []
        used = random.sample(CITY_NAMES, min(num_cities, len(CITY_NAMES)))
        for i in range(num_cities):
            x = random.randint(10, grid_size - 10)
            y = random.randint(10, grid_size - 10)
            pop = random.randint(5000, 500000)
            name = used[i] if i < len(used) else f"City-{i+1}"
            self.cities.append(City(x, y, pop, name))

        # --- build road network (nearby cities are connected) ---
        for i, c1 in enumerate(self.cities):
            for j, c2 in enumerate(self.cities):
                if i < j:
                    d = math.hypot(c1.x - c2.x, c1.y - c2.y)
                    if d < 30:
                        c1.connections.append(c2)
                        c2.connections.append(c1)

        # --- patient zero ---
        p0 = random.choice(self.cities)
        with self.lock:
            p0.infected = 1
            p0.susceptible -= 1
            p0.infection_day = 0
            self.events.append(
                f"Day 0: Patient Zero identified in {p0.name}!"
            )

        self.history_s = []
        self.history_i = []
        self.history_r = []
        self.history_new = []

    # --------------------------------------------------
    def step(self):
        with self.lock:
            if self.is_over:
                return
            self.day += 1

            # local SIR dynamics
            for city in self.cities:
                city.update(self.transmission_rate, self.removal_rate)

            # inter-city spread
            incoming = {}
            for src in self.cities:
                if src.infected <= 0 or src.is_quarantined or src.is_nuked:
                    continue
                for tgt in self.cities:
                    if src is tgt or tgt.susceptible <= 0 or tgt.is_nuked:
                        continue
                    if self.quarantine_active and tgt.is_quarantined:
                        continue

                    dist = math.hypot(src.x - tgt.x, src.y - tgt.y)
                    connected = tgt in src.connections

                    if connected and dist < 30:
                        chance = (src.infected / src.population) * 0.15
                        if not self.quarantine_active:
                            chance *= 1.5
                    elif dist < 20:
                        chance = (src.infected / src.population) * 0.08
                    else:
                        continue

                    if random.random() < chance:
                        n = min(int(src.infected * 0.01), int(tgt.susceptible))
                        if n > 0:
                            incoming.setdefault(tgt, 0)
                            incoming[tgt] += n

            daily_new = 0
            for city, n in incoming.items():
                if city.infection_day is None and n > 0:
                    city.infection_day = self.day
                    self.events.append(
                        f"Day {self.day}: OUTBREAK in {city.name}! "
                        f"({int(n)} cases)"
                    )
                city.infected += n
                city.susceptible -= n
                daily_new += n

            total_s = sum(c.susceptible for c in self.cities)
            total_i = sum(c.infected for c in self.cities)
            total_r = sum(c.removed for c in self.cities)

            self.history_s.append(total_s)
            self.history_i.append(total_i)
            self.history_r.append(total_r)
            self.history_new.append(daily_new)

            # --- milestone / alert events ---
            overrun = sum(1 for c in self.cities if c.infection_ratio > 0.5)
            infected_c = sum(1 for c in self.cities if c.infected > 0)

            if self.day == 10:
                self.events.append(
                    f"Day {self.day}: {infected_c} cities affected – "
                    f"situation critical."
                )
            if self.day == 30:
                self.events.append(
                    f"Day {self.day}: Crisis enters second month."
                )
            if self.day % 25 == 0 and overrun > 0:
                self.events.append(
                    f"Day {self.day}: {overrun} cities overrun "
                    f"(>50% infected)"
                )
            if daily_new > 50000:
                self.events.append(
                    f"Day {self.day}: CATASTROPHIC SURGE – "
                    f"{int(daily_new):,} new infections!"
                )

            if total_i < 1:
                self.is_over = True
                self.events.append(
                    f"Day {self.day}: Outbreak ended. "
                    f"Total casualties: {int(total_r):,}"
                )

            # cap event log to prevent memory bloat
            if len(self.events) > 500:
                self.events = self.events[-300:]

    # --- strategic actions --------------------------------
    def vaccinate_city(self, city, pct=0.1):
        with self.lock:
            if city.is_nuked:
                return
            n = int(city.susceptible * pct)
            if n > 0:
                city.susceptible -= n
                city.removed += n
                city.vaccination_rate = min(city.vaccination_rate + pct, 1.0)
                self.total_vaccinated += n
                self.events.append(
                    f"Day {self.day}: Vaccinated {n:,} in "
                    f"{city.name} ({pct*100:.0f}%)"
                )

    def toggle_city_quarantine(self, city):
        with self.lock:
            if city.is_nuked:
                return
            city.is_quarantined = not city.is_quarantined
            tag = "QUARANTINED" if city.is_quarantined else "released from quarantine"
            self.events.append(f"Day {self.day}: {city.name} {tag}")

    def nuke_city(self, city):
        with self.lock:
            if city.is_nuked:
                return
            lost = int(city.susceptible + city.infected)
            city.susceptible = 0
            city.infected = 0
            city.removed = city.population
            city.is_nuked = True
            city.is_quarantined = False
            self.nuked_cities += 1
            self.events.append(
                f"Day {self.day}: ☢ {city.name} NUKED! "
                f"{lost:,} lives lost."
            )

    @property
    def effective_r0(self):
        """R_eff = (β / γ) × (S / N)"""
        total_pop = sum(c.population for c in self.cities)
        total_s = sum(c.susceptible for c in self.cities)
        if total_pop > 0 and self.removal_rate > 0:
            return (self.transmission_rate / self.removal_rate) * (total_s / total_pop)
        return 0.0


# ═══════════════════════════════════════════════════════
#  Map Widget
# ═══════════════════════════════════════════════════════

class MapWidget(Widget):
    """Custom widget that draws the interactive infection map."""

    def __init__(self, simulation, **kwargs):
        super().__init__(**kwargs)
        self.simulation = simulation
        self.selected_city = None
        self.city_positions = {}     # name → (sx, sy, radius)
        self._label_cache = {}       # name → texture
        self.bind(size=self._request_redraw, pos=self._request_redraw)

    def _request_redraw(self, *_):
        self.draw_cities()

    def _to_screen(self, city):
        """Grid coords → pixel coords inside the widget."""
        if self.width < 1 or self.height < 1:
            return self.x, self.y
        sx = (city.x / self.simulation.grid_size) * self.width + self.x
        sy = self.height - (city.y / self.simulation.grid_size) * self.height + self.y
        return sx, sy

    def _get_name_texture(self, name):
        if name not in self._label_cache:
            lbl = CoreLabel(text=name, font_size=10, color=(255, 255, 255, 255))
            lbl.refresh()
            self._label_cache[name] = lbl.texture
        return self._label_cache[name]

    # --------------------------------------------------
    def draw_cities(self):
        if self.width < 2 or self.height < 2:
            return

        self.canvas.clear()
        self.city_positions = {}

        # ---- background & grid ----
        with self.canvas:
            Color(0.08, 0.09, 0.12, 1)
            Rectangle(pos=self.pos, size=self.size)
            Color(0.15, 0.16, 0.20, 0.6)
            for i in range(1, 10):
                gx = self.x + (i / 10) * self.width
                Line(points=[gx, self.y, gx, self.y + self.height], width=0.5)
                gy = self.y + (i / 10) * self.height
                Line(points=[self.x, gy, self.x + self.width, gy], width=0.5)

        with self.simulation.lock:
            # ---- road connections ----
            drawn = set()
            for city in self.simulation.cities:
                x1, y1 = self._to_screen(city)
                for conn in city.connections:
                    pair = tuple(sorted((id(city), id(conn))))
                    if pair in drawn:
                        continue
                    drawn.add(pair)
                    x2, y2 = self._to_screen(conn)
                    with self.canvas:
                        if city.infected > 0 and conn.infected > 0:
                            Color(0.75, 0.12, 0.12, 0.55)
                        elif city.infected > 0 or conn.infected > 0:
                            Color(0.85, 0.50, 0.10, 0.35)
                        else:
                            Color(0.22, 0.32, 0.42, 0.20)
                        Line(points=[x1, y1, x2, y2], width=1)

            # ---- cities ----
            for city in self.simulation.cities:
                sx, sy = self._to_screen(city)
                base_r = 7 + (city.population / 500000) * 16

                # nuked city
                if city.is_nuked:
                    with self.canvas:
                        Color(0.35, 0.35, 0.35, 0.25)
                        Ellipse(pos=(sx - base_r, sy - base_r),
                                size=(base_r * 2, base_r * 2))
                        Color(1, 0.25, 0, 0.85)
                        d = base_r * 0.6
                        Line(points=[sx - d, sy - d, sx + d, sy + d], width=2)
                        Line(points=[sx - d, sy + d, sx + d, sy - d], width=2)
                    self.city_positions[city.name] = (sx, sy, base_r)
                    continue

                ratio = city.infection_ratio

                # colour ramp
                if ratio < 0.01:
                    clr = (0.17, 0.80, 0.44, 1)
                elif ratio < 0.05:
                    clr = (0.40, 0.85, 0.30, 1)
                elif ratio < 0.15:
                    clr = (0.75, 0.85, 0.15, 1)
                elif ratio < 0.25:
                    clr = (0.95, 0.77, 0.06, 1)
                elif ratio < 0.50:
                    clr = (0.90, 0.49, 0.13, 1)
                else:
                    clr = (0.75, 0.22, 0.17, 1)

                # pulsing radius for active infections
                r = base_r
                if city.infected > 0:
                    pulse = math.sin(time.time() * 3.5 + city.x * 0.4) * 2.5
                    r = base_r + max(pulse, 0)

                self.city_positions[city.name] = (sx, sy, r)

                with self.canvas:
                    # infection glow
                    if ratio > 0.08:
                        a = min(ratio * 0.45, 0.35)
                        Color(1, 0, 0, a)
                        Ellipse(pos=(sx - r * 1.6, sy - r * 1.6),
                                size=(r * 3.2, r * 3.2))

                    # quarantine ring
                    if city.is_quarantined:
                        Color(0.20, 0.60, 1.0, 0.75)
                        Line(circle=(sx, sy, r + 5), width=2)

                    # city dot
                    Color(*clr)
                    Ellipse(pos=(sx - r, sy - r), size=(r * 2, r * 2))

                    # vaccination arc indicator
                    if city.vaccination_rate > 0:
                        Color(0.30, 0.80, 1.0, 0.45)
                        vr = r * min(city.vaccination_rate, 1.0)
                        Ellipse(pos=(sx - vr, sy - vr), size=(vr * 2, vr * 2))

                    # selection highlight
                    if (self.selected_city
                            and self.selected_city.name == city.name):
                        Color(1, 1, 1, 0.90)
                        Line(circle=(sx, sy, r + 4), width=2)

            # ---- name label for selected city ----
            if self.selected_city and not self.selected_city.is_nuked:
                c = self.selected_city
                if c.name in self.city_positions:
                    sx, sy, r = self.city_positions[c.name]
                    tex = self._get_name_texture(c.name)
                    if tex:
                        with self.canvas:
                            Color(1, 1, 1, 0.92)
                            Rectangle(
                                texture=tex,
                                pos=(sx - tex.size[0] / 2, sy + r + 4),
                                size=tex.size,
                            )

    # --------------------------------------------------
    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return False

        best, best_d = None, float('inf')
        for name, (cx, cy, cr) in self.city_positions.items():
            d = math.hypot(touch.pos[0] - cx, touch.pos[1] - cy)
            if d < cr + 15 and d < best_d:
                best_d = d
                best = name

        if best:
            with self.simulation.lock:
                for city in self.simulation.cities:
                    if city.name == best:
                        self.selected_city = city
                        break
            self.draw_cities()
            return True
        return False


# ═══════════════════════════════════════════════════════
#  Event Log
# ═══════════════════════════════════════════════════════

class EventLog(ScrollView):
    """Scrollable, colour-coded event log."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._label = Label(
            text='[color=44ff44][b]--- System Online ---[/b][/color]',
            markup=True, font_size='11sp',
            halign='left', valign='top',
            size_hint_y=None,
        )
        self._label.bind(texture_size=self._label.setter('size'))
        self.add_widget(self._label)
        self._seen = set()

    def update(self, events):
        new = [e for e in events if e not in self._seen]
        if not new:
            return
        self._seen.update(new)
        parts = []
        for e in new:
            if "Patient Zero" in e:
                parts.append(f'[color=ff4444][b]{e}[/b][/color]')
            elif "OUTBREAK" in e:
                parts.append(f'[color=ff8844]{e}[/color]')
            elif "CATASTROPHIC" in e:
                parts.append(f'[color=ff0000][b]{e}[/b][/color]')
            elif "NUKED" in e:
                parts.append(f'[color=ff6600][b]{e}[/b][/color]')
            elif "ended" in e:
                parts.append(f'[color=44ff44][b]{e}[/b][/color]')
            elif "QUARANTINED" in e:
                parts.append(f'[color=4488ff]{e}[/color]')
            elif "Vaccinated" in e:
                parts.append(f'[color=44ddff]{e}[/color]')
            elif "overrun" in e.lower():
                parts.append(f'[color=ff6644]{e}[/color]')
            else:
                parts.append(f'[color=bbbbbb]{e}[/color]')
        self._label.text += '\n' + '\n'.join(parts)
        self.scroll_y = 0

    def clear(self):
        self._seen.clear()
        self._label.text = '[color=44ff44][b]--- System Reset ---[/b][/color]'


# ═══════════════════════════════════════════════════════
#  Main Application
# ═══════════════════════════════════════════════════════

class OutbreakApp(App):

    def build(self):
        Window.clearcolor = (0.08, 0.09, 0.12, 1)
        self.title = "Z-POC: Zombie Pathogen Outbreak Command Center"
        self.is_running = False
        self.sim_thread = None
        self.sim_speed = 0.05
        self._graph_tick = 0

        root = BoxLayout(orientation='vertical', padding=5, spacing=3)

        # ─── Title ───
        root.add_widget(Label(
            text='Z-POC : ZOMBIE PATHOGEN OUTBREAK COMMAND CENTER',
            font_size='16sp', bold=True,
            color=(0.95, 0.22, 0.22, 1),
            size_hint_y=None, height=32,
        ))

        # ─── Control Buttons ───
        ctrl = BoxLayout(size_hint_y=None, height=42, spacing=5)
        self.btn_start = Button(
            text='▶  Start Outbreak',
            background_color=(0.13, 0.52, 0.13, 1),
        )
        self.btn_start.bind(on_press=self._toggle_sim)
        self.btn_reset = Button(
            text='↺  Reset', background_color=(0.52, 0.13, 0.13, 1),
        )
        self.btn_reset.bind(on_press=self._reset_sim)
        self.btn_quarantine = ToggleButton(
            text='Travel Ban', background_color=(0.13, 0.25, 0.52, 1),
        )
        self.btn_quarantine.bind(on_press=self._toggle_quarantine)
        self.btn_vaccinate = Button(
            text='Mass Vaccinate', background_color=(0.13, 0.42, 0.52, 1),
        )
        self.btn_vaccinate.bind(on_press=self._mass_vaccinate)
        for w in (self.btn_start, self.btn_reset,
                  self.btn_quarantine, self.btn_vaccinate):
            ctrl.add_widget(w)
        root.add_widget(ctrl)

        # ─── Parameter Sliders ───
        params = GridLayout(cols=6, size_hint_y=None, height=38, spacing=3)
        params.add_widget(Label(
            text='Transmission:', font_size='11sp', color=(0.7, 0.7, 0.7, 1),
        ))
        self.sl_trans = Slider(min=0.05, max=0.8, value=0.3, step=0.01)
        self.sl_trans.bind(
            value=lambda _, v: setattr(self.simulation, 'transmission_rate', v)
        )
        params.add_widget(self.sl_trans)
        params.add_widget(Label(
            text='Removal:', font_size='11sp', color=(0.7, 0.7, 0.7, 1),
        ))
        self.sl_rem = Slider(min=0.01, max=0.20, value=0.05, step=0.005)
        self.sl_rem.bind(
            value=lambda _, v: setattr(self.simulation, 'removal_rate', v)
        )
        params.add_widget(self.sl_rem)
        params.add_widget(Label(
            text='Speed:', font_size='11sp', color=(0.7, 0.7, 0.7, 1),
        ))
        self.sl_speed = Slider(min=0.01, max=0.50, value=0.05, step=0.01)
        self.sl_speed.bind(value=lambda _, v: setattr(self, 'sim_speed', v))
        params.add_widget(self.sl_speed)
        root.add_widget(params)

        # ─── Main Display ───
        main = BoxLayout(spacing=5)

        # map (left)
        self.simulation = OutbreakSimulation()
        self.map_widget = MapWidget(self.simulation)
        main.add_widget(self.map_widget)

        # right panel
        right = BoxLayout(orientation='vertical', spacing=3)

        # SIR graph
        self.fig, self.ax = plt.subplots(
            figsize=(5, 3), facecolor='#14161c',
        )
        self.fig_canvas = FigureCanvasKivyAgg(self.fig)
        right.add_widget(self.fig_canvas)

        # statistics grid
        stats = GridLayout(cols=2, size_hint_y=None, height=130, spacing=2)
        self.lbl_day  = Label(text='Day: 0',   font_size='15sp', bold=True, color=(1,1,1,1))
        self.lbl_r0   = Label(text='R₀: 0.00', font_size='13sp', color=(0.9,0.7,0.9,1))
        self.lbl_sus  = Label(text='Susceptible: 0', font_size='12sp', color=(0.3,0.9,0.5,1))
        self.lbl_inf  = Label(text='Infected: 0',     font_size='12sp', color=(1,0.3,0.3,1))
        self.lbl_rem  = Label(text='Casualties: 0',    font_size='12sp', color=(0.9,0.9,0.3,1))
        self.lbl_cinf = Label(text='Cities Infected: 0/0', font_size='12sp', color=(1,0.6,0.3,1))
        self.lbl_over = Label(text='Overrun: 0',        font_size='12sp', color=(1,0.4,0.2,1))
        self.lbl_vax  = Label(text='Vaccinated: 0',     font_size='12sp', color=(0.3,0.8,1,1))
        for w in (self.lbl_day, self.lbl_r0, self.lbl_sus, self.lbl_inf,
                  self.lbl_rem, self.lbl_cinf, self.lbl_over, self.lbl_vax):
            stats.add_widget(w)
        right.add_widget(stats)

        # infection progress bar
        prog = BoxLayout(size_hint_y=None, height=28, spacing=5)
        prog.add_widget(Label(
            text='Infection:', font_size='10sp',
            color=(0.7, 0.7, 0.7, 1), size_hint_x=None, width=65,
        ))
        self.progress = ProgressBar(max=100, value=0)
        prog.add_widget(self.progress)
        self.lbl_pct = Label(
            text='0.0%', font_size='11sp',
            color=(1, 0.5, 0.5, 1), size_hint_x=None, width=50,
        )
        prog.add_widget(self.lbl_pct)
        right.add_widget(prog)

        # city detail + actions
        city_panel = BoxLayout(orientation='vertical',
                               size_hint_y=None, height=95, spacing=2)
        self.lbl_city = Label(
            text='Click a city on the map for details',
            font_size='11sp', color=(0.7, 0.8, 1, 1),
            halign='left', valign='top', size_hint_y=None, height=50,
        )
        self.lbl_city.bind(texture_size=self.lbl_city.setter('size'))
        city_panel.add_widget(self.lbl_city)

        city_btns = BoxLayout(size_hint_y=None, height=32, spacing=3)
        self.btn_c_quar = Button(
            text='Quarantine', font_size='10sp',
            background_color=(0.13, 0.30, 0.55, 1), disabled=True,
        )
        self.btn_c_quar.bind(on_press=self._quarantine_selected)
        self.btn_c_vax = Button(
            text='Vaccinate', font_size='10sp',
            background_color=(0.13, 0.45, 0.50, 1), disabled=True,
        )
        self.btn_c_vax.bind(on_press=self._vaccinate_selected)
        self.btn_nuke = Button(
            text='☢ NUKE', font_size='10sp',
            background_color=(0.60, 0.10, 0.10, 1), disabled=True,
        )
        self.btn_nuke.bind(on_press=self._nuke_selected)
        city_btns.add_widget(self.btn_c_quar)
        city_btns.add_widget(self.btn_c_vax)
        city_btns.add_widget(self.btn_nuke)
        city_panel.add_widget(city_btns)
        right.add_widget(city_panel)

        # event log
        self.event_log = EventLog(size_hint_y=0.25)
        right.add_widget(self.event_log)

        main.add_widget(right)
        root.add_widget(main)

        # first draw
        self._update_ui(None)
        Clock.schedule_interval(self._pulse, 0.12)
        return root

    # ─── animation pulse ─────────────────────────────
    def _pulse(self, _dt):
        if self.is_running:
            self.map_widget.draw_cities()

    # ─── simulation control ──────────────────────────
    def _toggle_sim(self, _inst):
        if not self.is_running:
            self.is_running = True
            self.btn_start.text = '⏸  Pause'
            self.btn_start.background_color = (0.55, 0.40, 0.10, 1)
            self.sim_thread = threading.Thread(
                target=self._sim_loop, daemon=True,
            )
            self.sim_thread.start()
        else:
            self.is_running = False
            self.btn_start.text = '▶  Resume'
            self.btn_start.background_color = (0.13, 0.52, 0.13, 1)

    def _sim_loop(self):
        while self.is_running and not self.simulation.is_over:
            self.simulation.step()
            Clock.schedule_once(self._update_ui)
            time.sleep(self.sim_speed)
        if self.simulation.is_over:
            Clock.schedule_once(self._end_sim)

    def _end_sim(self, _dt):
        self.is_running = False
        self.btn_start.text = '▶  Start Outbreak'
        self.btn_start.background_color = (0.13, 0.52, 0.13, 1)
        self._update_ui(None)

    def _reset_sim(self, _inst):
        self.is_running = False
        if self.sim_thread and self.sim_thread.is_alive():
            self.sim_thread.join(timeout=1)
        self.simulation = OutbreakSimulation(
            transmission_rate=self.sl_trans.value,
            removal_rate=self.sl_rem.value,
        )
        self.map_widget.simulation = self.simulation
        self.map_widget.selected_city = None
        self.map_widget._label_cache.clear()
        self.btn_start.text = '▶  Start Outbreak'
        self.btn_start.background_color = (0.13, 0.52, 0.13, 1)
        self.btn_quarantine.state = 'normal'
        self.btn_quarantine.text = 'Travel Ban'
        self.event_log.clear()
        self._graph_tick = 0
        self._update_ui(None)

    # ─── strategic actions ───────────────────────────
    def _toggle_quarantine(self, _inst):
        on = self.btn_quarantine.state == 'down'
        self.simulation.quarantine_active = on
        self.btn_quarantine.text = 'Travel Ban: ON' if on else 'Travel Ban'
        with self.simulation.lock:
            self.simulation.events.append(
                f"Day {self.simulation.day}: Global travel ban "
                f"{'ACTIVATED' if on else 'LIFTED'}"
            )

    def _mass_vaccinate(self, _inst):
        for city in self.simulation.cities:
            if city.infection_ratio < 0.5 and not city.is_nuked:
                self.simulation.vaccinate_city(city, 0.05)

    def _quarantine_selected(self, _inst):
        c = self.map_widget.selected_city
        if c:
            self.simulation.toggle_city_quarantine(c)
            self._update_ui(None)

    def _vaccinate_selected(self, _inst):
        c = self.map_widget.selected_city
        if c:
            self.simulation.vaccinate_city(c, 0.15)
            self._update_ui(None)

    def _nuke_selected(self, _inst):
        city = self.map_widget.selected_city
        if not city:
            return

        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        content.add_widget(Label(
            text=(
                f'NUKE {city.name}?\n\n'
                f'This will kill ALL {city.population:,} inhabitants!\n'
                f'This CANNOT be undone.'
            ),
            color=(1, 0.3, 0.3, 1),
        ))
        btns = BoxLayout(spacing=10)
        popup = Popup(
            title='⚠  CONFIRM NUCLEAR STRIKE  ⚠',
            content=content, size_hint=(0.65, 0.4),
            background_color=(0.15, 0.05, 0.05, 1),
        )

        def do_nuke(_):
            self.simulation.nuke_city(city)
            popup.dismiss()
            self._update_ui(None)

        btn_yes = Button(
            text='☢  CONFIRM NUKE',
            background_color=(0.70, 0.10, 0.10, 1),
        )
        btn_no = Button(
            text='Cancel', background_color=(0.30, 0.30, 0.30, 1),
        )
        btn_yes.bind(on_press=do_nuke)
        btn_no.bind(on_press=popup.dismiss)
        btns.add_widget(btn_yes)
        btns.add_widget(btn_no)
        content.add_widget(btns)
        popup.open()

    # ─── UI refresh ──────────────────────────────────
    def _update_ui(self, _dt):
        # --- map ---
        self.map_widget.draw_cities()

        # --- graph (throttled to every 3rd frame) ---
        self._graph_tick += 1
        if self._graph_tick % 3 == 0 or not self.is_running:
            self.ax.clear()
            if self.simulation.history_s:
                days = range(len(self.simulation.history_s))
                self.ax.fill_between(
                    days, self.simulation.history_s, alpha=0.12, color='cyan',
                )
                self.ax.fill_between(
                    days, self.simulation.history_r, alpha=0.12, color='yellow',
                )
                self.ax.plot(
                    days, self.simulation.history_s, 'c-',
                    label='Susceptible', linewidth=1.5,
                )
                self.ax.plot(
                    days, self.simulation.history_i, 'm-',
                    label='Infected', linewidth=2,
                )
                self.ax.plot(
                    days, self.simulation.history_r, 'y-',
                    label='Removed', linewidth=1.5,
                )
                if self.simulation.history_new:
                    self.ax.bar(
                        days, self.simulation.history_new,
                        alpha=0.18, color='red', label='New Cases',
                    )
            self.ax.set_title("SIR Model", color='white', fontsize=10)
            self.ax.set_xlabel("Days", color='white', fontsize=8)
            self.ax.set_ylabel("Population", color='white', fontsize=8)
            self.ax.legend(
                fontsize=7, loc='right',
                facecolor='#2c3e50', edgecolor='#555', labelcolor='white',
            )
            self.ax.grid(True, linestyle='--', alpha=0.18)
            self.ax.set_facecolor('#12141a')
            self.ax.tick_params(colors='white', labelsize=7)
            for spine in self.ax.spines.values():
                spine.set_edgecolor('#333')
            self.fig.tight_layout()
            self.fig_canvas.draw()

        # --- stats ---
        with self.simulation.lock:
            total_pop = sum(c.population for c in self.simulation.cities)
            total_s   = sum(c.susceptible for c in self.simulation.cities)
            total_i   = sum(c.infected    for c in self.simulation.cities)
            total_r   = sum(c.removed     for c in self.simulation.cities)
            overrun   = sum(1 for c in self.simulation.cities
                           if c.infection_ratio > 0.5)
            infected  = sum(1 for c in self.simulation.cities
                           if c.infected > 0)
            n_cities  = len(self.simulation.cities)
            day       = self.simulation.day
            r0        = self.simulation.effective_r0
            vax       = self.simulation.total_vaccinated
            events    = list(self.simulation.events)

        pct = (total_i / total_pop * 100) if total_pop > 0 else 0.0

        self.lbl_day.text  = f'Day: {day}'
        self.lbl_r0.text   = f'R₀: {r0:.2f}'
        self.lbl_sus.text  = f'Susceptible: {int(total_s):,}'
        self.lbl_inf.text  = f'Infected: {int(total_i):,}'
        self.lbl_rem.text  = f'Casualties: {int(total_r):,}'
        self.lbl_cinf.text = f'Cities Infected: {infected}/{n_cities}'
        self.lbl_over.text = f'Overrun: {overrun}'
        self.lbl_vax.text  = f'Vaccinated: {vax:,}'

        self.progress.value = pct
        self.lbl_pct.text   = f'{pct:.1f}%'

        # --- city info ---
        city = self.map_widget.selected_city
        if city and not city.is_nuked:
            q_tag = "Yes" if city.is_quarantined else "No"
            self.lbl_city.text = (
                f'[b]{city.name}[/b]  |  Pop: {city.population:,}\n'
                f'S: {int(city.susceptible):,}  I: {int(city.infected):,}  '
                f'R: {int(city.removed):,}  '
                f'({city.infection_ratio*100:.1f}% infected)\n'
                f'Quarantined: {q_tag}  |  '
                f'Vaccinated: {city.vaccination_rate*100:.0f}%'
            )
            self.lbl_city.markup = True
            self.btn_c_quar.disabled = False
            self.btn_c_vax.disabled  = False
            self.btn_nuke.disabled   = False
            self.btn_c_quar.text = (
                'Release City' if city.is_quarantined else 'Quarantine'
            )
        elif city and city.is_nuked:
            self.lbl_city.text = f'[b]{city.name}[/b]  —  DESTROYED'
            self.lbl_city.markup = True
            self.btn_c_quar.disabled = True
            self.btn_c_vax.disabled  = True
            self.btn_nuke.disabled   = True
        else:
            self.lbl_city.text = 'Click a city on the map for details'
            self.btn_c_quar.disabled = True
            self.btn_c_vax.disabled  = True
            self.btn_nuke.disabled   = True

        # --- event log ---
        self.event_log.update(events)

if __name__ == '__main__':
    OutbreakApp().run()