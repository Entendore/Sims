#!/usr/bin/env python3
"""
Enhanced Evolution Simulation
==============================
Features:
  - 6 heritable traits: size, speed, sense_range, aggression, efficiency, max_age
  - Food / energy system with foraging AI (seek food, flee threats, hunt prey)
  - Collision-based reproduction with energy cost & population cap
  - Predation: large aggressive creatures hunt smaller ones
  - Death from starvation or old age; immigration if population crashes
  - Seasonal food variation (Spring → Summer → Autumn → Winter)
  - 7-level taxonomy lineage tracking with mutation
  - Real-time trait-average bar chart
  - Population & species-count history line graph
  - Interactive zoomable / pannable lineage tree
  - Creature click-selection with live stat strip & detail inspector
  - Pause / Play, speed (1×–5×), and Reset controls
  - Memory-safe: stores lightweight parent info, not object references
"""

import math
import random
from collections import defaultdict, deque

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.graphics import Color, Line, Rectangle, Ellipse
from kivy.core.window import Window

# ====================================================================
# Constants
# ====================================================================
TAXONOMY_LEVELS = [
    "Kingdom", "Phylum", "Class", "Order", "Family", "Genus", "Species"
]

MAX_POPULATION     = 80
MAX_FOOD           = 60
FOOD_SPAWN_BASE    = 8        # base frames between food spawns
FOOD_ENERGY        = 40
REPRO_ENERGY_COST  = 50       # energy each parent spends
REPRO_DISTANCE     = 25       # proximity needed to reproduce
REPRO_CHANCE       = 0.12     # per-eligible-pair per-frame
INITIAL_POPULATION = 25
SEASON_LENGTH      = 600      # frames per season
IMMIGRATION_THRESHOLD = 4     # spawn newcomer if pop drops below this
MAX_TREE_NODES     = 60       # limit displayed lineage-tree nodes

SEASONS = ["Spring", "Summer", "Autumn", "Winter"]
SEASON_FOOD_MULT = {"Spring": 1.0, "Summer": 1.6,
                    "Autumn": 0.8, "Winter": 0.3}
SEASON_BG = {"Spring": (0.35, 0.75, 0.35),
             "Summer": (0.85, 0.85, 0.20),
             "Autumn": (0.75, 0.45, 0.18),
             "Winter": (0.45, 0.65, 0.85)}


def _clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


def generate_lineage_name(level, parent_name=None):
    prefix = parent_name[:3] if parent_name else ""
    return f"{prefix}{TAXONOMY_LEVELS[level][:3]}{random.randint(1, 99)}"


# ====================================================================
# Food
# ====================================================================
class Food:
    _next_id = 0

    def __init__(self, x, y, energy=FOOD_ENERGY):
        Food._next_id += 1
        self.id   = Food._next_id
        self.x    = x
        self.y    = y
        self.energy = energy
        self.radius = 4


# ====================================================================
# Creature
# ====================================================================
class Creature:
    _next_id = 0

    def __init__(self, x, y, parent1=None, parent2=None):
        Creature._next_id += 1
        self.id    = Creature._next_id
        self.age   = 0
        self.alive = True

        # --- inherited or random traits ---
        if parent1 and parent2:
            self.size        = self._inh(parent1.size,        parent2.size,        5,   40,  2.0)
            self.speed       = self._inh(parent1.speed,       parent2.speed,       0.5,  5,  0.3)
            self.sense_range = self._inh(parent1.sense_range, parent2.sense_range, 20, 200, 15)
            self.aggression  = self._inh(parent1.aggression,  parent2.aggression,  0,    1,  0.08)
            self.efficiency  = self._inh(parent1.efficiency,  parent2.efficiency,  0.3,  2,  0.12)
            self.max_age     = self._inh(parent1.max_age,     parent2.max_age,     300, 2500, 100)

            self.lineage_color = [
                _clamp((parent1.lineage_color[i] + parent2.lineage_color[i]) / 2
                       + random.uniform(-0.05, 0.05))
                for i in range(3)
            ]

            self.lineage_hierarchy = []
            for i in range(len(TAXONOMY_LEVELS)):
                donor = random.choice([parent1, parent2])
                if random.random() < 0.10:
                    name = generate_lineage_name(i, donor.lineage_hierarchy[i])
                else:
                    name = donor.lineage_hierarchy[i]
                self.lineage_hierarchy.append(name)
            self.lineage_id = self.lineage_hierarchy[-1]

            self.x = (parent1.x + parent2.x) / 2 + random.uniform(-10, 10)
            self.y = (parent1.y + parent2.y) / 2 + random.uniform(-10, 10)
            self.energy = 55

            # lightweight parent snapshot (breaks reference chain)
            self.p1_id    = parent1.id
            self.p2_id    = parent2.id
            self.p1_pos   = (parent1.x, parent1.y)
            self.p2_pos   = (parent2.x, parent2.y)
            self.p1_color = tuple(parent1.lineage_color)
            self.p2_color = tuple(parent2.lineage_color)
            self.p1_species = parent1.lineage_hierarchy[-1]
            self.p2_species = parent2.lineage_hierarchy[-1]
        else:
            self.size        = random.uniform(10, 30)
            self.speed       = random.uniform(1, 3)
            self.sense_range = random.uniform(40, 150)
            self.aggression  = random.uniform(0, 0.5)
            self.efficiency  = random.uniform(0.5, 1.5)
            self.max_age     = random.uniform(600, 1800)
            self.x = x
            self.y = y
            self.lineage_color = [random.uniform(0.25, 1) for _ in range(3)]
            self.lineage_hierarchy = [generate_lineage_name(i)
                                      for i in range(len(TAXONOMY_LEVELS))]
            self.lineage_id = self.lineage_hierarchy[-1]
            self.energy = 100

            self.p1_id = self.p2_id = None
            self.p1_pos = self.p2_pos = None
            self.p1_color = self.p2_color = None
            self.p1_species = self.p2_species = None

        self.angle  = random.uniform(0, 360)
        self.sides  = max(3, int(3 + self.speed * 2))
        self.offsets = [random.uniform(-0.15, 0.15) for _ in range(self.sides)]
        self._wander_cd = 0

    # ---- helpers ----
    @staticmethod
    def _inh(a, b, lo, hi, mut):
        return max(lo, min(hi, (a + b) / 2 + random.uniform(-mut, mut)))

    def energy_cost(self):
        """Bigger & faster → more drain; higher efficiency → less drain."""
        return 0.03 * (self.size / 20) * (self.speed / 3) / max(self.efficiency, 0.1)

    def energy_ratio(self):
        return max(0.0, min(1.0, self.energy / 150))

    def can_reproduce(self):
        return self.alive and self.energy > REPRO_ENERGY_COST + 15

    # ---- AI movement ----
    def move(self, w, h, foods, creatures):
        if not self.alive:
            return
        self.age += 1
        self.energy -= self.energy_cost()
        if self.energy <= 0 or self.age > self.max_age:
            self.alive = False
            return

        # nearest food
        best_f, best_d = None, self.sense_range
        for f in foods:
            d = math.hypot(self.x - f.x, self.y - f.y)
            if d < best_d:
                best_d, best_f = d, f

        # flee threat
        flee_a = None
        for o in creatures:
            if o is self or not o.alive:
                continue
            d = math.hypot(self.x - o.x, self.y - o.y)
            if (d < self.sense_range * 0.6
                    and o.size > self.size * 1.2
                    and o.aggression > 0.3):
                flee_a = math.degrees(math.atan2(self.y - o.y, self.x - o.x))
                break

        # hunt prey
        prey, prey_d = None, self.sense_range * 0.5
        if self.aggression > 0.25:
            for o in creatures:
                if o is self or not o.alive:
                    continue
                d = math.hypot(self.x - o.x, self.y - o.y)
                if (d < prey_d and o.size < self.size * 0.65
                        and random.random() < self.aggression):
                    prey, prey_d = o, d

        # steering
        if flee_a is not None:
            self.angle = flee_a + random.uniform(-10, 10)
        elif prey is not None:
            self.angle = math.degrees(
                math.atan2(prey.y - self.y, prey.x - self.x))
        elif best_f is not None:
            self.angle = math.degrees(
                math.atan2(best_f.y - self.y, best_f.x - self.x))
        else:
            self._wander_cd += 1
            if self._wander_cd > random.randint(30, 80):
                self.angle += random.uniform(-40, 40)
                self._wander_cd = 0

        self.x += math.cos(math.radians(self.angle)) * self.speed
        self.y += math.sin(math.radians(self.angle)) * self.speed

        if self.x <= 0 or self.x >= w:
            self.angle = 180 - self.angle + random.uniform(-5, 5)
        if self.y <= 0 or self.y >= h:
            self.angle = -self.angle + random.uniform(-5, 5)
        self.x = max(1, min(self.x, w - 1))
        self.y = max(1, min(self.y, h - 1))

    # ---- eating ----
    def try_eat_food(self, foods):
        if not self.alive:
            return []
        eaten = []
        for f in foods:
            if math.hypot(self.x - f.x, self.y - f.y) < self.size * 0.5 + f.radius:
                self.energy = min(150, self.energy + f.energy * self.efficiency)
                eaten.append(f)
        return eaten

    def try_hunt(self, creatures):
        if not self.alive or self.aggression < 0.15:
            return []
        killed = []
        for o in creatures:
            if o is self or not o.alive:
                continue
            if math.hypot(self.x - o.x, self.y - o.y) < (self.size + o.size) * 0.35:
                if o.size < self.size * 0.65 and random.random() < self.aggression * 0.25:
                    o.alive = False
                    self.energy = min(150,
                                      self.energy + o.size * 1.5 * self.efficiency)
                    killed.append(o)
        return killed

    # ---- reproduction ----
    def reproduce(self, partner):
        self.energy    -= REPRO_ENERGY_COST
        partner.energy -= REPRO_ENERGY_COST
        return Creature(0, 0, parent1=self, parent2=partner)

    # ---- rendering ----
    def get_shape_points(self):
        pts = []
        for i in range(self.sides):
            a = 2 * math.pi * i / self.sides + math.radians(self.angle)
            r = self.size * (1 + self.offsets[i])
            pts.extend([self.x + math.cos(a) * r,
                        self.y + math.sin(a) * r])
        return pts


# ====================================================================
# Simulation Widget
# ====================================================================
class EvolutionWidget(Widget):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.population = []
        self.foods      = []
        self.frame      = 0
        self.generation = 0
        self.season_idx = 0
        self.paused     = False
        self.sim_speed  = 1
        self.selected   = None
        self.total_births = 0
        self.total_deaths = 0

        # lineage bookkeeping
        self.lineage_nodes  = {}   # species -> {parent, color, level, children}
        self.tree_positions = {}   # species -> (level, y_index)
        self._level_y       = {}
        self._species_order = []   # insertion order for trimming

        # history
        self.pop_history = deque(maxlen=300)
        self.spp_history = deque(maxlen=300)
        self.avg_traits  = deque(maxlen=300)

        Clock.schedule_interval(self._tick, 1 / 30)
        self.bind(size=self._on_first_size)

    # ---- init on first valid size ----
    def _on_first_size(self, *_):
        if not self.population and self.width > 10:
            self.reset()

    # ---- full reset ----
    def reset(self):
        Creature._next_id = 0
        Food._next_id     = 0
        self.population.clear()
        self.foods.clear()
        self.frame      = 0
        self.generation = 0
        self.season_idx = 0
        self.selected   = None
        self.total_births = 0
        self.total_deaths = 0
        self.lineage_nodes.clear()
        self.tree_positions.clear()
        self._level_y.clear()
        self._species_order.clear()
        self.pop_history.clear()
        self.spp_history.clear()
        self.avg_traits.clear()

        for _ in range(INITIAL_POPULATION):
            c = Creature(random.uniform(20, self.width - 20),
                         random.uniform(20, self.height - 20))
            self.population.append(c)
            self._reg_lineage(c)
        for _ in range(30):
            self.foods.append(Food(random.uniform(10, self.width - 10),
                                   random.uniform(10, self.height - 10)))

    # ---- click to select creature ----
    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return False
        for c in self.population:
            if c.alive and math.hypot(c.x - touch.x, c.y - touch.y) < c.size:
                self.selected = c
                return True
        self.selected = None
        return super().on_touch_down(touch)

    # ---- lineage registration ----
    def _reg_lineage(self, c):
        sp  = c.lineage_hierarchy[-1]
        psp = c.p1_species                       # use snapshot, not ref
        lv  = len(c.lineage_hierarchy) - 1
        if sp in self.lineage_nodes:
            return
        self.lineage_nodes[sp] = {
            'parent': psp, 'color': c.lineage_color,
            'level': lv, 'children': []
        }
        if psp and psp in self.lineage_nodes:
            self.lineage_nodes[psp]['children'].append(sp)
        if lv not in self._level_y:
            self._level_y[lv] = 1
        self.tree_positions[sp] = (lv, self._level_y[lv])
        self._level_y[lv] += 1
        self._species_order.append(sp)

        # trim oldest entries when tree grows too large
        while len(self._species_order) > MAX_TREE_NODES:
            old = self._species_order.pop(0)
            self.lineage_nodes.pop(old, None)
            self.tree_positions.pop(old, None)

    # ---- season helpers ----
    @property
    def season(self):
        return SEASONS[self.season_idx % 4]

    @property
    def season_color(self):
        return SEASON_BG[self.season]

    @property
    def food_multiplier(self):
        return SEASON_FOOD_MULT[self.season]

    # ---- main tick ----
    def _tick(self, dt):
        if self.paused or not self.population:
            self._draw()
            return
        for _ in range(self.sim_speed):
            self._step()
        self._draw()
        if self.parent:
            self.parent.refresh_charts(self)

    # ---- single simulation step ----
    def _step(self):
        self.frame += 1
        w, h = self.width, self.height
        if w < 10 or h < 10:
            return

        # advance season
        if self.frame % SEASON_LENGTH == 0:
            self.season_idx += 1

        # move creatures
        for c in self.population:
            c.move(w, h, self.foods, self.population)

        # eat food (dedup so two creatures don't double-consume)
        eaten_ids = set()
        for c in self.population:
            if c.alive:
                for f in c.try_eat_food(self.foods):
                    if f.id not in eaten_ids:
                        eaten_ids.add(f.id)
                    else:
                        # undo energy if someone else already ate it
                        c.energy = max(0, c.energy - f.energy * c.efficiency)
        if eaten_ids:
            self.foods = [f for f in self.foods if f.id not in eaten_ids]

        # hunt
        for c in self.population:
            c.try_hunt(self.population)

        # spawn food
        interval = max(1, int(FOOD_SPAWN_BASE / self.food_multiplier))
        if self.frame % interval == 0 and len(self.foods) < MAX_FOOD:
            self.foods.append(Food(random.uniform(10, w - 10),
                                   random.uniform(10, h - 10)))

        # reproduction
        alive = [c for c in self.population if c.alive]
        babies = []
        paired = set()
        for i, c1 in enumerate(alive):
            if not c1.can_reproduce() or c1.id in paired:
                continue
            for j in range(i + 1, len(alive)):
                c2 = alive[j]
                if not c2.can_reproduce() or c2.id in paired:
                    continue
                if math.hypot(c1.x - c2.x, c1.y - c2.y) < REPRO_DISTANCE:
                    if random.random() < REPRO_CHANCE:
                        if len(self.population) + len(babies) < MAX_POPULATION:
                            baby = c1.reproduce(c2)
                            babies.append(baby)
                            self._reg_lineage(baby)
                            self.total_births += 1
                            paired.update([c1.id, c2.id])
                            break

        # remove dead
        before = len(self.population)
        self.population = [c for c in self.population if c.alive]
        self.total_deaths += before - len(self.population)
        self.population.extend(babies)

        # immigration if population crashes
        if len(self.population) < IMMIGRATION_THRESHOLD and self.frame % 60 == 0:
            c = Creature(random.uniform(20, w - 20),
                         random.uniform(20, h - 20))
            self.population.append(c)
            self._reg_lineage(c)

        # generation counter
        if self.frame % 300 == 0:
            self.generation += 1

        # history snapshots (every 30 frames)
        if self.frame % 30 == 0:
            alive = [c for c in self.population if c.alive]
            n = len(alive) or 1
            self.pop_history.append(len(alive))
            self.spp_history.append(
                len(set(c.lineage_hierarchy[-1] for c in alive)))
            self.avg_traits.append({
                'size':  sum(c.size for c in alive) / n,
                'speed': sum(c.speed for c in alive) / n,
                'sense': sum(c.sense_range for c in alive) / n,
                'aggr':  sum(c.aggression for c in alive) / n,
                'eff':   sum(c.efficiency for c in alive) / n,
            })

    # ---- render ----
    def _draw(self):
        self.canvas.clear()
        w, h = self.width, self.height
        if w < 10:
            return

        with self.canvas:
            # season background tint
            sc = self.season_color
            Color(sc[0], sc[1], sc[2], 0.045)
            Rectangle(pos=(0, 0), size=(w, h))

            # food dots
            for f in self.foods:
                Color(0.15, 0.82, 0.15, 0.75)
                Ellipse(pos=(f.x - f.radius, f.y - f.radius),
                        size=(f.radius * 2, f.radius * 2))

            # lineage lines (from parent birth-position to child)
            for c in self.population:
                if not c.alive:
                    continue
                if c.p1_pos:
                    Color(*c.p1_color, 0.12)
                    Line(points=[c.p1_pos[0], c.p1_pos[1], c.x, c.y],
                         width=0.5)

            # creatures
            for c in self.population:
                if not c.alive:
                    continue

                # sense-range ring for selected
                if c is self.selected:
                    Color(*c.lineage_color, 0.06)
                    Ellipse(pos=(c.x - c.sense_range,
                                 c.y - c.sense_range),
                            size=(c.sense_range * 2,
                                  c.sense_range * 2))

                # body polygon
                alpha = 0.45 + 0.55 * c.energy_ratio()
                Color(*c.lineage_color, alpha)
                pts = c.get_shape_points()
                if len(pts) >= 6:
                    Line(points=pts, close=True, width=1.4)

                # energy bar
                bw = c.size * 1.2
                bx = c.x - bw / 2
                by = c.y + c.size + 3
                Color(0.25, 0.25, 0.25, 0.55)
                Rectangle(pos=(bx, by), size=(bw, 3))
                er = c.energy_ratio()
                Color(1 - er, er, 0, 0.75)
                Rectangle(pos=(bx, by), size=(bw * er, 3))

                # selection marker
                if c is self.selected:
                    Color(1, 1, 0, 0.9)
                    Ellipse(pos=(c.x - 3, c.y - 3), size=(6, 6))


# ====================================================================
# Trait Bar Chart
# ====================================================================
class TraitChart(Widget):

    def __init__(self, **kw):
        super().__init__(**kw)
        self._data  = {}
        self._lbls  = []

    def update(self, traits_deque):
        if not traits_deque:
            return
        self._data = traits_deque[-1]
        self._draw()

    def _draw(self):
        self.canvas.clear()
        for l in self._lbls:
            self.remove_widget(l)
        self._lbls.clear()
        w, h = self.width, self.height
        if w < 20 or h < 20:
            return

        ml, mr, mt, mb = 5, 5, 5, 24
        cw, ch = w - ml - mr, h - mt - mb

        items = [
            ("Size",  self._data.get('size',  0), 40,  (0,   0.9, 0.9)),
            ("Speed", self._data.get('speed', 0),  5,   (0.9, 0,   0.9)),
            ("Sense", self._data.get('sense', 0), 200, (0.9, 0.9, 0)),
            ("Aggr",  self._data.get('aggr',  0),  1,   (0.9, 0.2, 0.2)),
            ("Eff",   self._data.get('eff',   0),  2,   (0.2, 0.9, 0.2)),
        ]
        n   = len(items)
        gap = 4
        bw  = (cw - gap * (n + 1)) / n

        with self.canvas:
            Color(0.08, 0.08, 0.12, 0.85)
            Rectangle(pos=(0, 0), size=(w, h))

            for i, (name, val, maxv, col) in enumerate(items):
                x     = ml + gap + i * (bw + gap)
                ratio = val / maxv if maxv else 0
                bh    = ratio * ch
                Color(*col, 0.8)
                Rectangle(pos=(x, mb), size=(bw, bh))
                Color(*col, 0.25)
                Line(rectangle=(x, mb, bw, ch), width=0.5)

                lbl = Label(text=f"{name}\n{val:.1f}", font_size=9,
                            color=(*col, 1), halign='center', valign='top',
                            size=(bw, mb), pos=(x, 0))
                self.add_widget(lbl)
                self._lbls.append(lbl)


# ====================================================================
# Population / Species History Graph
# ====================================================================
class PopGraph(Widget):

    def __init__(self, **kw):
        super().__init__(**kw)
        self._pop = []
        self._spp = []
        self._lbls = []

    def update(self, ph, sh):
        self._pop = list(ph)
        self._spp = list(sh)
        self._draw()

    def _draw(self):
        self.canvas.clear()
        for l in self._lbls:
            self.remove_widget(l)
        self._lbls.clear()
        w, h = self.width, self.height
        if w < 30 or h < 30:
            return

        m = 28
        cw, ch = w - 2 * m, h - 2 * m
        mx = max(self._pop) if self._pop else 1
        mx = max(mx, 1)

        with self.canvas:
            Color(0.08, 0.08, 0.12, 0.85)
            Rectangle(pos=(0, 0), size=(w, h))

            # grid
            Color(0.25, 0.25, 0.25, 0.4)
            for i in range(5):
                y = m + i * ch / 4
                Line(points=[m, y, m + cw, y], width=0.5)

            # population line
            if len(self._pop) > 1:
                pts = []
                for i, v in enumerate(self._pop):
                    x = m + i / max(len(self._pop) - 1, 1) * cw
                    y = m + v / mx * ch
                    pts.extend([x, y])
                Color(0, 0.9, 0.9, 0.85)
                Line(points=pts, width=1.5)

            # species line
            if len(self._spp) > 1:
                pts = []
                for i, v in enumerate(self._spp):
                    x = m + i / max(len(self._spp) - 1, 1) * cw
                    y = m + v / mx * ch
                    pts.extend([x, y])
                Color(0.95, 0.9, 0.1, 0.85)
                Line(points=pts, width=1.3)

        # legend
        for txt, col, dx in [("— Pop", (0, 0.9, 0.9, 1), 0),
                              ("— Spp", (0.95, 0.9, 0.1, 1), 55)]:
            lbl = Label(text=txt, font_size=9, color=col,
                        size=(55, 14), pos=(m + dx, h - 14))
            self.add_widget(lbl)
            self._lbls.append(lbl)


# ====================================================================
# Lineage Tree (zoom & pan)
# ====================================================================
class LineageTree(Widget):

    def __init__(self, **kw):
        super().__init__(**kw)
        self._nodes  = {}
        self._pos    = {}
        self.zoom    = 1.0
        self.ox      = 0.0
        self.oy      = 0.0
        self._touch  = {}
        self._lbls   = []
        Window.bind(on_mouse_scroll=self._scroll)

    def _scroll(self, win, x, y, sx, sy):
        if not self.collide_point(*Window.mouse_pos):
            return False
        self.zoom = max(0.3, min(3.0,
                                 self.zoom * (1.1 if sy > 0 else 0.9)))
        self._redraw()
        return True

    def on_touch_down(self, t):
        if not self.collide_point(*t.pos):
            return False
        self._touch[t.id] = t.pos
        return True

    def on_touch_move(self, t):
        if t.id in self._touch:
            dx = t.x - self._touch[t.id][0]
            dy = t.y - self._touch[t.id][1]
            self.ox += dx
            self.oy += dy
            self._touch[t.id] = t.pos
            self._redraw()
        return True

    def on_touch_up(self, t):
        self._touch.pop(t.id, None)
        return True

    def update(self, nodes, positions):
        self._nodes = nodes
        self._pos   = positions
        self._redraw()

    def _redraw(self):
        self.canvas.clear()
        for l in self._lbls:
            self.remove_widget(l)
        self._lbls.clear()
        if not self._nodes:
            return

        w, h = self.width, self.height
        nw  = 80 * self.zoom
        nh  = 22 * self.zoom
        lx  = (nw + 25) * self.zoom
        dy  = (nh + 6)  * self.zoom

        with self.canvas:
            Color(0.06, 0.06, 0.10, 0.92)
            Rectangle(pos=(0, 0), size=(w, h))

            # edges
            for sp, info in self._nodes.items():
                if sp not in self._pos:
                    continue
                par = info['parent']
                if par and par in self._pos:
                    lv, idx = self._pos[sp]
                    plv, pidx = self._pos[par]
                    px = 8 + plv * lx + self.ox + nw / 2
                    py = h - 8 - pidx * dy + self.oy
                    cx = 8 + lv  * lx + self.ox + nw / 2
                    cy = h - 8 - idx  * dy + self.oy
                    Color(0.35, 0.35, 0.35, 0.6)
                    Line(points=[px, py, cx, cy], width=1)

            # nodes
            for sp, info in self._nodes.items():
                if sp not in self._pos:
                    continue
                lv, idx = self._pos[sp]
                x = 8 + lv * lx + self.ox
                y = h - 8 - idx * dy + self.oy - nh
                Color(*info['color'], 0.8)
                Rectangle(pos=(x, y), size=(nw, nh))
                Color(0.6, 0.6, 0.6, 0.2)
                Line(rectangle=(x, y, nw, nh), width=0.5)

                lbl = Label(
                    text=sp[:10],
                    font_size=max(7, int(9 * self.zoom)),
                    color=(0, 0, 0, 1),
                    size=(nw, nh), pos=(x, y),
                    halign='center', valign='middle')
                self.add_widget(lbl)
                self._lbls.append(lbl)


# ====================================================================
# Inspector Popup
# ====================================================================
def show_inspector(creature):
    box = BoxLayout(orientation='vertical', spacing=2, padding=8)
    if creature is None:
        box.add_widget(Label(text="Click a creature in the\n"
                                  "simulation first!", font_size=14))
    else:
        hier = creature.lineage_hierarchy
        lines = [
            f"  ID:  {creature.id}",
            f"  Species:  {hier[-1]}",
            f"  Genus:  {hier[-2]}",
            f"  Family:  {hier[-3]}",
            f"  Order:  {hier[-4]}",
            f"  Age:  {creature.age:.0f} / {creature.max_age:.0f}",
            f"  Energy:  {creature.energy:.1f} / 150",
            f"  Size:  {creature.size:.1f}",
            f"  Speed:  {creature.speed:.2f}",
            f"  Sense Range:  {creature.sense_range:.1f}",
            f"  Aggression:  {creature.aggression:.2f}",
            f"  Efficiency:  {creature.efficiency:.2f}",
            f"  Shape Sides:  {creature.sides}",
            f"  Position:  ({creature.x:.0f}, {creature.y:.0f})",
            f"  Full Lineage:",
            f"    {' > '.join(hier)}",
        ]
        for ln in lines:
            box.add_widget(Label(text=ln, font_size=11,
                                 size_hint_y=None, height=20,
                                 halign='left', valign='middle'))
    Popup(title="🧬 Creature Inspector", content=box,
          size_hint=(0.55, 0.7)).open()


# ====================================================================
# Main Layout
# ====================================================================
class MainLayout(BoxLayout):

    def __init__(self, **kw):
        super().__init__(orientation='horizontal', **kw)
        self.spacing = 4
        self.padding = 4

        # --- simulation area ---
        self.evo = EvolutionWidget(size_hint=(0.7, 1))
        self.add_widget(self.evo)

        # --- right panel ---
        rp = BoxLayout(orientation='vertical', size_hint=(0.3, 1), spacing=3)

        # info
        self.lbl_info = Label(text="", size_hint=(1, 0.06),
                              font_size=12, color=(0.9, 0.9, 0.9, 1))
        rp.add_widget(self.lbl_info)

        self.lbl_stats = Label(text="", size_hint=(1, 0.04),
                               font_size=10, color=(0.65, 0.65, 0.65, 1))
        rp.add_widget(self.lbl_stats)

        # selected creature strip
        self.lbl_sel = Label(
            text="Click a creature to inspect",
            size_hint=(1, 0.06), font_size=10,
            color=(1, 1, 0.5, 1))
        rp.add_widget(self.lbl_sel)

        # charts
        self.trait_chart = TraitChart(size_hint=(1, 0.2))
        rp.add_widget(self.trait_chart)

        self.pop_graph = PopGraph(size_hint=(1, 0.2))
        rp.add_widget(self.pop_graph)

        self.lin_tree = LineageTree(size_hint=(1, 0.3))
        rp.add_widget(self.lin_tree)

        # controls
        ctrl = BoxLayout(orientation='horizontal',
                         size_hint=(1, 0.07), spacing=3)

        self.btn_pause = Button(text="⏸ Pause", font_size=11)
        self.btn_pause.bind(on_press=self._toggle_pause)
        ctrl.add_widget(self.btn_pause)

        self.btn_speed = Button(text="⏩ x1", font_size=11)
        self.btn_speed.bind(on_press=self._cycle_speed)
        ctrl.add_widget(self.btn_speed)

        btn_reset = Button(text="🔄 Reset", font_size=11)
        btn_reset.bind(on_press=lambda _: self.evo.reset())
        ctrl.add_widget(btn_reset)

        btn_inspect = Button(text="🔍 Inspect", font_size=11)
        btn_inspect.bind(on_press=lambda _: show_inspector(self.evo.selected))
        ctrl.add_widget(btn_inspect)

        rp.add_widget(ctrl)
        self.add_widget(rp)

    # ---- control callbacks ----
    def _toggle_pause(self, _):
        self.evo.paused = not self.evo.paused
        self.btn_pause.text = "▶ Play" if self.evo.paused else "⏸ Pause"

    def _cycle_speed(self, _):
        speeds = [1, 2, 3, 5]
        i = (speeds.index(self.evo.sim_speed)
             if self.evo.sim_speed in speeds else 0)
        self.evo.sim_speed = speeds[(i + 1) % len(speeds)]
        self.btn_speed.text = f"⏩ x{self.evo.sim_speed}"

    # ---- chart refresh (called from simulation tick) ----
    def refresh_charts(self, evo):
        alive = [c for c in evo.population if c.alive]
        n = len(alive) or 1
        sp_counts = defaultdict(int)
        for c in alive:
            sp_counts[c.lineage_hierarchy[-1]] += 1
        top_sp = max(sp_counts, key=sp_counts.get) if sp_counts else "—"

        season = evo.season
        sc = evo.season_color
        self.lbl_info.text = (
            f"Gen {evo.generation}  ·  Pop {len(alive)}  ·  "
            f"Species {len(sp_counts)}  ·  Top: {top_sp[:14]}  ·  "
            f"[color={_rgb_hex(sc)}]{season}[/color]"
        )
        self.lbl_stats.text = (
            f"Births {evo.total_births}  |  "
            f"Deaths {evo.total_deaths}  |  "
            f"Food {len(evo.foods)}"
        )

        # selected creature live strip
        sel = evo.selected
        if sel and sel.alive:
            self.lbl_sel.text = (
                f"#{sel.id}  E:{sel.energy:.0f}  "
                f"Sz:{sel.size:.1f}  Sp:{sel.speed:.1f}  "
                f"Ag:{sel.aggression:.2f}  "
                f"Age:{sel.age:.0f}/{sel.max_age:.0f}"
            )
        elif sel and not sel.alive:
            self.lbl_sel.text = f"#{sel.id}  [DEAD]"
            evo.selected = None
        else:
            self.lbl_sel.text = "Click a creature to inspect"

        # update charts at reduced rate
        if evo.frame % 15 == 0:
            self.trait_chart.update(evo.avg_traits)
            self.pop_graph.update(evo.pop_history, evo.spp_history)
        if evo.frame % 30 == 0:
            self.lin_tree.update(evo.lineage_nodes, evo.tree_positions)


def _rgb_hex(t):
    return f"#{int(t[0]*255):02x}{int(t[1]*255):02x}{int(t[2]*255):02x}"


# ====================================================================
# App
# ====================================================================
class EvolutionSimApp(App):
    def build(self):
        Window.clearcolor = (0.04, 0.04, 0.07, 1)
        return MainLayout()


if __name__ == "__main__":
    EvolutionSimApp().run()