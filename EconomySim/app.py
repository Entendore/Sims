import random
import math
import json
import os
from collections import deque

from kivy.app import App
from kivy.uix.widget import Widget
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.slider import Slider
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle, Ellipse, Line, RoundedRectangle
from kivy.animation import Animation
from kivy.properties import (
    NumericProperty, StringProperty, ListProperty,
    BooleanProperty, DictProperty, OptionProperty
)
from kivy.core.window import Window
from kivy.metrics import dp, sp

Window.clearcolor = (0.08, 0.08, 0.12, 1)

# ========================= CONFIGURATION =========================
SAVE_FILE = 'economy_save.json'

BUILDING_INFO = {
    'gatherer': {
        'cost': 150, 'color': (0.15, 0.70, 0.15, 1), 'size': (65, 65),
        'workers': 1, 'name': 'Gatherer', 'max_storage': 10,
        'desc': 'Gathers raw resources from the environment'
    },
    'processor': {
        'cost': 350, 'color': (0.80, 0.50, 0.10, 1), 'size': (80, 80),
        'workers': 2, 'name': 'Processor', 'max_storage': 15,
        'desc': 'Converts 2 raw materials into 1 processed material'
    },
    'manufacturer': {
        'cost': 600, 'color': (0.15, 0.40, 0.85, 1), 'size': (95, 95),
        'workers': 3, 'name': 'Manufacturer', 'max_storage': 10,
        'desc': 'Converts 3 processed materials into 1 product'
    },
    'market': {
        'cost': 1000, 'color': (0.85, 0.12, 0.18, 1), 'size': (110, 110),
        'workers': 0, 'name': 'Market', 'max_storage': 20,
        'desc': 'Sells products for money. Prices fluctuate.'
    },
    'warehouse': {
        'cost': 400, 'color': (0.55, 0.35, 0.80, 1), 'size': (70, 70),
        'workers': 0, 'name': 'Warehouse', 'max_storage': 50,
        'desc': 'Stores excess raw and processed materials'
    },
}

UPGRADE_BASE_COST = 200
UPGRADE_COST_MULT = 1.75
MAX_LEVEL = 10
MAX_PARTICLES = 50

EVENT_TEMPLATES = [
    {'name': '📈 Economic Boom',     'desc': 'All production +50% for 30s',
     'duration': 30, 'effect': 'production_boost', 'value': 1.5},
    {'name': '📉 Recession',         'desc': 'All production -30% for 30s',
     'duration': 30, 'effect': 'production_boost', 'value': 0.7},
    {'name': '⛏️ Supply Shortage',   'desc': 'Gathering -50% for 20s',
     'duration': 20, 'effect': 'gather_boost', 'value': 0.5},
    {'name': '💡 Innovation',        'desc': 'Random building +1 level!',
     'duration': 0,  'effect': 'upgrade_random', 'value': 1},
    {'name': '👥 Population Surge',  'desc': '+15 population',
     'duration': 0,  'effect': 'add_population', 'value': 15},
    {'name': '🌊 Flood',            'desc': 'Lost 30% raw materials',
     'duration': 0,  'effect': 'disaster_raw', 'value': 0.3},
    {'name': '🤝 Trade Deal',        'desc': 'Market prices +50% for 25s',
     'duration': 25, 'effect': 'price_boost', 'value': 1.5},
    {'name': '🏭 Strike',           'desc': 'Manufacturing -60% for 20s',
     'duration': 20, 'effect': 'manufacture_boost', 'value': 0.4},
    {'name': '💰 Gold Rush',         'desc': '+$500!',
     'duration': 0,  'effect': 'add_money', 'value': 500},
    {'name': '📋 Tax Break',         'desc': 'Upgrade costs -30% for 30s',
     'duration': 30, 'effect': 'upgrade_discount', 'value': 0.7},
]

SPEED_OPTIONS = {'⏸': 0, '▶': 1, '▶▶': 2, '▶▶▶': 4}


# ========================= FLOATING TEXT =========================
class FloatingText(Label):
    """Text that floats upward and fades out."""
    def __init__(self, text, pos, color=(0.2, 1, 0.2, 1), font_size=14, **kwargs):
        super().__init__(
            text=text, color=color, font_size=sp(font_size),
            size_hint=(None, None), size=(160, 22),
            halign='left', valign='middle', **kwargs
        )
        self.pos = pos
        anim = Animation(y=pos[1] + 55, opacity=0, duration=1.6)
        anim.bind(on_complete=lambda *a: self._remove())
        anim.start(self)

    def _remove(self):
        if self.parent:
            self.parent.remove_widget(self)


# ========================= RESOURCE PARTICLE =========================
class ResourceParticle(Widget):
    """Animated particle traveling between buildings."""
    def __init__(self, start_pos, end_pos, color, speed=1.0, **kwargs):
        super().__init__(**kwargs)
        self.size = (9, 9)
        self.pos = start_pos
        self.end_pos = end_pos
        with self.canvas:
            self._color_instr = Color(*color)
            self._ellipse = Ellipse(pos=self.pos, size=self.size)
            self._color_instr2 = Color(color[0], color[1], color[2], 0.3)
            self._glow = Ellipse(pos=(self.pos[0] - 3, self.pos[1] - 3), size=(15, 15))
        self.bind(pos=self._update_canvas)
        duration = max(0.3, 1.0 / speed)
        anim = Animation(pos=end_pos, duration=duration, t='in_out_sine')
        anim.bind(on_complete=lambda *a: self._remove())
        anim.start(self)

    def _update_canvas(self, instance, value):
        self._ellipse.pos = value
        self._glow.pos = (value[0] - 3, value[1] - 3)

    def _remove(self):
        if self.parent:
            self.parent.remove_widget(self)


# ========================= BASE BUILDING =========================
class Building(Widget):
    """Base class for all buildings."""
    building_type = StringProperty('')
    level = NumericProperty(1)
    workers_assigned = NumericProperty(0)
    active = BooleanProperty(True)
    pulse_phase = NumericProperty(0)

    def __init__(self, building_type, **kwargs):
        info = BUILDING_INFO[building_type]
        self.building_type = building_type
        self.base_color = info['color']
        self.base_size = info['size']
        self.workers_needed = info['workers']
        self.max_storage = info['max_storage']
        self.building_name = info['name']
        self.size = info['size']
        self._selected = False
        super().__init__(**kwargs)
        self.bind(pos=self._request_redraw, size=self._request_redraw,
                  level=self._request_redraw)
        self._redraw_scheduled = False

    def _request_redraw(self, *args):
        if not self._redraw_scheduled:
            self._redraw_scheduled = True
            Clock.schedule_once(self._do_redraw, 0)

    def _do_redraw(self, dt=None):
        self._redraw_scheduled = False
        self.draw()

    def draw(self):
        self.canvas.clear()
        with self.canvas:
            # Shadow
            Color(0, 0, 0, 0.25)
            RoundedRectangle(pos=(self.x + 3, self.y - 3), size=self.size, radius=[10])
            # Body
            r, g, b, a = self.base_color
            level_tint = min(1, 0.08 * (self.level - 1))
            Color(r + level_tint, g + level_tint, b + level_tint, a)
            self._body = RoundedRectangle(pos=self.pos, size=self.size, radius=[10])
            # Border (highlighted if selected)
            if self._selected:
                Color(1, 1, 0.3, 0.9)
            else:
                Color(1, 1, 1, 0.15)
            Line(rounded_rectangle=(self.x, self.y, self.width, self.height, 10), width=1.5)
            # Level indicator dots
            dot_size = 4
            for i in range(min(self.level, MAX_LEVEL)):
                dx = self.x + 6 + i * (dot_size + 3)
                dy = self.y + self.height - 8
                Color(1, 1, 0.2, 0.85)
                Ellipse(pos=(dx, dy), size=(dot_size, dot_size))
            # Icon
            self._draw_icon()
            # Storage bar background
            bar_w = self.width - 12
            bar_h = 5
            bar_x = self.x + 6
            bar_y = self.y + 4
            Color(0.15, 0.15, 0.2, 0.6)
            Rectangle(pos=(bar_x, bar_y), size=(bar_w, bar_h))

    def _draw_icon(self):
        pass  # Override in subclasses

    def draw_storage_bar(self, current, maximum):
        bar_w = self.width - 12
        bar_h = 5
        bar_x = self.x + 6
        bar_y = self.y + 4
        fill = min(1.0, current / max(1, maximum))
        with self.canvas:
            Color(0.2, 0.8, 0.2, 0.75)
            Rectangle(pos=(bar_x, bar_y), size=(bar_w * fill, bar_h))

    def get_upgrade_cost(self, discount=1.0):
        return int(UPGRADE_BASE_COST * (UPGRADE_COST_MULT ** (self.level - 1)) * discount)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self._selected = True
            self._request_redraw()
            return True
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        if self._selected:
            self._selected = False
            self._request_redraw()
            if self.collide_point(*touch.pos):
                return True
        return super().on_touch_up(touch)


# ========================= GATHERER =========================
class ResourceGatherer(Building):
    def __init__(self, **kwargs):
        super().__init__('gatherer', **kwargs)
        self.raw_materials = 0
        self.production_rate = 1.0

    def _draw_icon(self):
        cx = self.x + self.width / 2
        cy = self.y + self.height / 2 + 2
        with self.canvas:
            Color(1, 1, 1, 0.9)
            Ellipse(pos=(cx - 14, cy - 14), size=(28, 28))
            Color(0.1, 0.5, 0.1, 1)
            Line(points=[cx - 7, cy, cx + 7, cy], width=2.5)
            Line(points=[cx, cy - 7, cx, cy + 7], width=2.5)

    def gather(self, boost=1.0):
        produced = self.production_rate * self.level * boost
        self.raw_materials += produced
        return produced

    def draw(self):
        super().draw()
        self.draw_storage_bar(self.raw_materials, self.max_storage * self.level)


# ========================= PROCESSOR =========================
class Processor(Building):
    def __init__(self, **kwargs):
        super().__init__('processor', **kwargs)
        self.raw_materials = 0
        self.processed_materials = 0
        self.process_rate = 1.0

    def _draw_icon(self):
        cx = self.x + self.width / 2
        cy = self.y + self.height / 2 + 2
        with self.canvas:
            Color(1, 1, 1, 0.9)
            Rectangle(pos=(cx - 15, cy - 15), size=(30, 30))
            Color(0.6, 0.35, 0.05, 1)
            Line(rectangle=(cx - 15, cy - 15, 30, 30), width=2)
            # Gear teeth
            Color(0.6, 0.35, 0.05, 1)
            for angle in range(0, 360, 45):
                rad = math.radians(angle)
                tx = cx + 18 * math.cos(rad)
                ty = cy + 18 * math.sin(rad)
                Ellipse(pos=(tx - 3, ty - 3), size=(6, 6))

    def process(self, boost=1.0):
        raw_needed = 2
        if self.raw_materials >= raw_needed:
            self.raw_materials -= raw_needed
            produced = self.process_rate * self.level * boost
            self.processed_materials += produced
            return produced
        return 0

    def draw(self):
        super().draw()
        total = self.raw_materials + self.processed_materials
        self.draw_storage_bar(total, self.max_storage * self.level)


# ========================= MANUFACTURER =========================
class Manufacturer(Building):
    def __init__(self, **kwargs):
        super().__init__('manufacturer', **kwargs)
        self.processed_materials = 0
        self.products = 0
        self.manufacture_rate = 1.0

    def _draw_icon(self):
        cx = self.x + self.width / 2
        cy = self.y + self.height / 2 + 2
        with self.canvas:
            Color(1, 1, 1, 0.9)
            Ellipse(pos=(cx - 20, cy - 20), size=(40, 40))
            Color(0.08, 0.25, 0.65, 1)
            Line(ellipse=(cx - 20, cy - 20, 40, 40), width=2)
            # Inner circle
            Color(0.08, 0.25, 0.65, 1)
            Ellipse(pos=(cx - 10, cy - 10), size=(20, 20))
            Color(0.5, 0.7, 1, 1)
            Ellipse(pos=(cx - 5, cy - 5), size=(10, 10))

    def manufacture(self, boost=1.0):
        processed_needed = 3
        if self.processed_materials >= processed_needed:
            self.processed_materials -= processed_needed
            produced = self.manufacture_rate * self.level * boost
            self.products += produced
            return produced
        return 0

    def draw(self):
        super().draw()
        total = self.processed_materials + self.products
        self.draw_storage_bar(total, self.max_storage * self.level)


# ========================= MARKET =========================
class Market(Building):
    def __init__(self, **kwargs):
        super().__init__('market', **kwargs)
        self.products = 0
        self.base_price = 10
        self.price = 10
        self.demand = 5
        self.total_sold = 0

    def _draw_icon(self):
        cx = self.x + self.width / 2
        cy = self.y + self.height / 2 + 2
        with self.canvas:
            Color(1, 1, 1, 0.9)
            Rectangle(pos=(cx - 20, cy - 20), size=(40, 40))
            Color(0.7, 0.08, 0.12, 1)
            Line(rectangle=(cx - 20, cy - 20, 40, 40), width=2.5)
            # Dollar sign approximation
            Line(points=[cx - 5, cy + 12, cx + 5, cy + 8], width=2)
            Line(points=[cx + 5, cy + 8, cx - 5, cy + 2], width=2)
            Line(points=[cx - 5, cy + 2, cx + 5, cy - 4], width=2)
            Line(points=[cx + 5, cy - 4, cx - 5, cy - 8], width=2)
            Line(points=[cx, cy + 14, cx, cy - 10], width=2)

    def sell(self, amount):
        sold = min(amount, self.products)
        if sold > 0:
            self.products -= sold
            revenue = int(sold * self.price)
            self.total_sold += sold
            return revenue
        return 0

    def update_price(self, total_supply):
        supply_factor = max(0.3, 1.0 - total_supply * 0.02)
        demand_factor = 1.0 + self.demand * 0.05
        self.price = max(3, int(self.base_price * supply_factor * demand_factor))
        self.demand = min(20, self.demand + 0.02)

    def draw(self):
        super().draw()
        self.draw_storage_bar(self.products, self.max_storage * self.level)
        # Price tag
        with self.canvas:
            Color(1, 0.85, 0, 0.9)
            price_label = f'${self.price}'
            # Small indicator rectangle
            tag_w = len(price_label) * 7 + 8
            Color(0, 0, 0, 0.5)
            Rectangle(pos=(self.x + self.width - tag_w - 2, self.y + self.height - 20),
                      size=(tag_w, 14))


# ========================= WAREHOUSE =========================
class Warehouse(Building):
    def __init__(self, **kwargs):
        super().__init__('warehouse', **kwargs)
        self.raw_materials = 0
        self.processed_materials = 0

    def _draw_icon(self):
        cx = self.x + self.width / 2
        cy = self.y + self.height / 2 + 2
        with self.canvas:
            Color(1, 1, 1, 0.9)
            # Box shape
            Rectangle(pos=(cx - 16, cy - 16), size=(32, 32))
            Color(0.4, 0.22, 0.6, 1)
            Line(rectangle=(cx - 16, cy - 16, 32, 32), width=2)
            # Cross
            Line(points=[cx - 16, cy, cx + 16, cy], width=1.5)
            Line(points=[cx, cy - 16, cx, cy + 16], width=1.5)

    def get_total(self):
        return self.raw_materials + self.processed_materials

    def draw(self):
        super().draw()
        cap = self.max_storage * self.level
        self.draw_storage_bar(self.get_total(), cap)


# ========================= ACTIVE EVENT =========================
class ActiveEvent:
    def __init__(self, template, start_time):
        self.name = template['name']
        self.desc = template['desc']
        self.effect = template['effect']
        self.value = template['value']
        self.duration = template['duration']
        self.start_time = start_time
        self.end_time = start_time + template['duration']


# ========================= ECONOMY SIMULATION =========================
class EconomySimulation(Widget):
    money = NumericProperty(1000)
    population = NumericProperty(50)
    total_raw = NumericProperty(0)
    total_processed = NumericProperty(0)
    total_products = NumericProperty(0)
    total_gdp = NumericProperty(0)
    game_time = NumericProperty(0)
    game_day = NumericProperty(1)
    game_speed = NumericProperty(1)
    paused = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.gatherers = []
        self.processors = []
        self.manufacturers = []
        self.markets = []
        self.warehouses = []
        self.active_events = []
        self.event_log = deque(maxlen=20)
        self.achievements = set()
        self.money_history = deque(maxlen=200)
        self.particle_count = 0
        self.last_event_time = 0
        self._game_tick_accumulator = 0.0
        self._next_place_pos = [80, 0]

        self._setup_initial_economy()
        Clock.schedule_interval(self._render_update, 1.0 / 30.0)

    def _get_row_y(self, row):
        rows = {1: 0.78, 2: 0.55, 3: 0.32, 4: 0.12}
        return int(Window.height * rows.get(row, 0.5))

    def _setup_initial_economy(self):
        y1 = self._get_row_y(1)
        y2 = self._get_row_y(2)
        y3 = self._get_row_y(3)
        y4 = self._get_row_y(4)
        for i in range(3):
            g = ResourceGatherer()
            g.pos = (80 + i * 160, y1)
            self.add_widget(g)
            self.gatherers.append(g)
        for i in range(2):
            p = Processor()
            p.pos = (140 + i * 220, y2)
            self.add_widget(p)
            self.processors.append(p)
        for i in range(2):
            m = Manufacturer()
            m.pos = (180 + i * 280, y3)
            self.add_widget(m)
            self.manufacturers.append(m)
        mk = Market()
        mk.pos = (Window.width - 250, y4)
        self.add_widget(mk)
        self.markets.append(mk)
        w = Warehouse()
        w.pos = (Window.width - 400, y2)
        self.add_widget(w)
        self.warehouses.append(w)

    def _get_next_place_position(self, row_hint=None):
        if row_hint is None:
            row_hint = 1
        y = self._get_row_y(row_hint)
        x = self._next_place_pos[0]
        self._next_place_pos[0] += 160
        if self._next_place_pos[0] > Window.width - 200:
            self._next_place_pos[0] = 80
        return (x, y)

    # ---------- Event Modifiers ----------
    def _get_production_boost(self):
        boost = 1.0
        for ev in self.active_events:
            if ev.effect == 'production_boost':
                boost *= ev.value
        return boost

    def _get_gather_boost(self):
        boost = self._get_production_boost()
        for ev in self.active_events:
            if ev.effect == 'gather_boost':
                boost *= ev.value
        return boost

    def _get_manufacture_boost(self):
        boost = self._get_production_boost()
        for ev in self.active_events:
            if ev.effect == 'manufacture_boost':
                boost *= ev.value
        return boost

    def _get_price_boost(self):
        boost = 1.0
        for ev in self.active_events:
            if ev.effect == 'price_boost':
                boost *= ev.value
        return boost

    def _get_upgrade_discount(self):
        discount = 1.0
        for ev in self.active_events:
            if ev.effect == 'upgrade_discount':
                discount *= ev.value
        return discount

    # ---------- Particles ----------
    def _spawn_particle(self, start, end, color, speed=1.0):
        if self.particle_count >= MAX_PARTICLES:
            return
        p = ResourceParticle(start, end, color, speed=speed)
        self.add_widget(p)
        self.particle_count += 1
        p.bind(parent=lambda *a: None)
        Clock.schedule_once(lambda dt: self._dec_particle(), 1.5 / speed)

    def _dec_particle(self):
        self.particle_count = max(0, self.particle_count - 1)

    def _spawn_floating_text(self, text, pos, color=(0.2, 1, 0.2, 1)):
        ft = FloatingText(text, pos, color)
        self.add_widget(ft)

    # ---------- Game Tick ----------
    def _render_update(self, dt):
        if self.paused or self.game_speed == 0:
            return
        self._game_tick_accumulator += dt * self.game_speed
        tick_interval = 1.0
        while self._game_tick_accumulator >= tick_interval:
            self._game_tick_accumulator -= tick_interval
            self._game_tick()

    def _game_tick(self):
        self.game_time += 1
        self.game_day = int(self.game_time / 60) + 1

        # Expire events
        expired = [e for e in self.active_events if self.game_time >= e.end_time]
        for e in expired:
            self.active_events.remove(e)

        gather_boost = self._get_gather_boost()
        manuf_boost = self._get_manufacture_boost()
        price_boost = self._get_price_boost()

        # --- Gathering ---
        for g in self.gatherers:
            if not g.active:
                continue
            if random.random() < 0.12 * g.production_rate * g.level * gather_boost:
                produced = g.gather(gather_boost)
                cap = g.max_storage * g.level
                overflow = max(0, g.raw_materials - cap)
                if overflow > 0:
                    g.raw_materials = cap
                    # Overflow to warehouse
                    for w in self.warehouses:
                        w_cap = w.max_storage * w.level
                        space = w_cap - w.raw_materials
                        if space > 0:
                            transfer = min(overflow, space)
                            w.raw_materials += transfer
                            overflow -= transfer
                            self._spawn_particle(
                                (g.x + g.width / 2, g.y + g.height / 2),
                                (w.x + w.width / 2, w.y + w.height / 2),
                                (0.25, 0.85, 0.25, 0.9), speed=1.2)
                            if overflow <= 0:
                                break
                # Particle to processor
                if self.processors:
                    target = random.choice(self.processors)
                    self._spawn_particle(
                        (g.x + g.width / 2, g.y + g.height / 2),
                        (target.x + target.width / 2, target.y + target.height / 2),
                        (0.25, 0.85, 0.25, 0.9))

        # --- Transfer raw to processors ---
        for p in self.processors:
            cap = p.max_storage * p.level
            for g in self.gatherers:
                if g.raw_materials > 0 and p.raw_materials < cap:
                    transfer = min(g.raw_materials, cap - p.raw_materials, 2)
                    g.raw_materials -= transfer
                    p.raw_materials += transfer
            # Pull from warehouses
            for w in self.warehouses:
                if w.raw_materials > 0 and p.raw_materials < cap:
                    transfer = min(w.raw_materials, cap - p.raw_materials, 2)
                    w.raw_materials -= transfer
                    p.raw_materials += transfer
                    self._spawn_particle(
                        (w.x + w.width / 2, w.y + w.height / 2),
                        (p.x + p.width / 2, p.y + p.height / 2),
                        (0.55, 0.35, 0.8, 0.8), speed=1.1)

        # --- Processing ---
        for p in self.processors:
            if not p.active:
                continue
            if random.random() < 0.08 * p.process_rate * p.level:
                produced = p.process(gather_boost)
                if produced > 0 and self.manufacturers:
                    target = random.choice(self.manufacturers)
                    self._spawn_particle(
                        (p.x + p.width / 2, p.y + p.height / 2),
                        (target.x + target.width / 2, target.y + target.height / 2),
                        (0.85, 0.55, 0.15, 0.9))
                    # Overflow to warehouse
                    cap = p.max_storage * p.level
                    if p.processed_materials > cap:
                        overflow = p.processed_materials - cap
                        p.processed_materials = cap
                        for w in self.warehouses:
                            w_cap = w.max_storage * w.level
                            space = w_cap - w.processed_materials
                            if space > 0:
                                transfer = min(overflow, space)
                                w.processed_materials += transfer
                                overflow -= transfer
                                if overflow <= 0:
                                    break

        # --- Transfer processed to manufacturers ---
        for m in self.manufacturers:
            cap = m.max_storage * m.level
            for p in self.processors:
                if p.processed_materials > 0 and m.processed_materials < cap:
                    transfer = min(p.processed_materials, cap - m.processed_materials, 2)
                    p.processed_materials -= transfer
                    m.processed_materials += transfer
            # Pull from warehouses
            for w in self.warehouses:
                if w.processed_materials > 0 and m.processed_materials < cap:
                    transfer = min(w.processed_materials, cap - m.processed_materials, 2)
                    w.processed_materials -= transfer
                    m.processed_materials += transfer

        # --- Manufacturing ---
        for m in self.manufacturers:
            if not m.active:
                continue
            if random.random() < 0.05 * m.manufacture_rate * m.level * manuf_boost:
                produced = m.manufacture(manuf_boost)
                if produced > 0:
                    # Send products to markets
                    if self.markets:
                        target = random.choice(self.markets)
                        self._spawn_particle(
                            (m.x + m.width / 2, m.y + m.height / 2),
                            (target.x + target.width / 2, target.y + target.height / 2),
                            (0.25, 0.5, 0.95, 0.9))

        # --- Transfer products to markets ---
        for mk in self.markets:
            cap = mk.max_storage * mk.level
            for m in self.manufacturers:
                if m.products > 0 and mk.products < cap:
                    transfer = min(m.products, cap - mk.products, 3)
                    m.products -= transfer
                    mk.products += transfer

        # --- Market selling ---
        total_supply = 0
        for mk in self.markets:
            mk.update_price(total_supply)
            actual_price = int(mk.price * price_boost)
            if mk.products > 0 and random.random() < 0.15:
                revenue = mk.sell(min(mk.products, mk.demand))
                if revenue > 0:
                    self.money += revenue
                    self._spawn_floating_text(
                        f'+${revenue}',
                        (mk.x, mk.y + mk.height),
                        (1, 0.85, 0, 1))
            total_supply += mk.products

        # --- Population growth ---
        if self.money > 500 and random.random() < 0.02:
            growth = random.randint(1, 3)
            self.population += growth
            self._spawn_floating_text(
                f'+{growth} pop',
                (self.x + 50, self.y + 50),
                (0, 1, 1, 1))

        # --- Tax income ---
        tax = int(len(self.markets) * 2 + len(self.manufacturers) * 1)
        if tax > 0:
            self.money += tax

        # --- Random events ---
        if self.game_time - self.last_event_time >= 25 + random.randint(0, 20):
            if random.random() < 0.4:
                self._trigger_random_event()
                self.last_event_time = self.game_time

        # --- Update stats ---
        self._update_stats()
        self._check_achievements()

        # --- Money history ---
        if int(self.game_time) % 3 == 0:
            self.money_history.append(self.money)

        # --- Redraw buildings ---
        for b in self.gatherers + self.processors + self.manufacturers + self.markets + self.warehouses:
            b.draw()

    def _update_stats(self):
        self.total_raw = sum(g.raw_materials for g in self.gatherers)
        self.total_raw += sum(w.raw_materials for w in self.warehouses)
        self.total_processed = sum(p.processed_materials for p in self.processors)
        self.total_processed += sum(w.processed_materials for w in self.warehouses)
        self.total_products = sum(mk.products for mk in self.markets)
        gdp = self.money
        for m in self.manufacturers:
            gdp += m.products * 10
        for mk in self.markets:
            gdp += mk.total_sold * 5
        self.total_gdp = int(gdp)

    def _trigger_random_event(self):
        template = random.choice(EVENT_TEMPLATES)
        ev = ActiveEvent(template, self.game_time)

        # Immediate effects
        if ev.effect == 'upgrade_random':
            all_buildings = self.gatherers + self.processors + self.manufacturers + self.markets + self.warehouses
            if all_buildings:
                b = random.choice(all_buildings)
                if b.level < MAX_LEVEL:
                    b.level += 1
        elif ev.effect == 'add_population':
            self.population += int(ev.value)
        elif ev.effect == 'disaster_raw':
            for g in self.gatherers:
                lost = g.raw_materials * ev.value
                g.raw_materials -= lost
            for w in self.warehouses:
                lost = w.raw_materials * ev.value
                w.raw_materials -= lost
        elif ev.effect == 'add_money':
            self.money += int(ev.value)
            self._spawn_floating_text(
                f'+${int(ev.value)}',
                (Window.width / 2, Window.height / 2),
                (1, 0.85, 0, 1))

        # Duration effects
        if ev.duration > 0:
            self.active_events.append(ev)

        self.event_log.appendleft(
            f'Day {self.game_day}: {ev.name} - {ev.desc}')
        self._spawn_floating_text(
            ev.name,
            (Window.width / 2 - 100, Window.height - 80),
            (1, 1, 0.3, 1))

    def _check_achievements(self):
        checks = [
            ('first_1000', self.money >= 1000, '💰 First $1,000'),
            ('pop_100', self.population >= 100, '👥 Population 100'),
            ('gdp_5000', self.total_gdp >= 5000, '🏛️ GDP $5,000'),
            ('day_10', self.game_day >= 10, '📅 Survived 10 Days'),
            ('day_30', self.game_day >= 30, '📅 30 Days Strong'),
            ('money_10000', self.money >= 10000, '💰 $10,000'),
            ('money_50000', self.money >= 50000, '💰 $50,000'),
            ('buildings_10', len(self._all_buildings()) >= 10, '🏗️ 10 Buildings'),
            ('buildings_20', len(self._all_buildings()) >= 20, '🏗️ 20 Buildings'),
            ('level_5', any(b.level >= 5 for b in self._all_buildings()), '⭐ Level 5 Building'),
            ('level_10', any(b.level >= 10 for b in self._all_buildings()), '⭐⭐ Level 10 Building!'),
        ]
        for key, condition, text in checks:
            if key not in self.achievements and condition:
                self.achievements.add(key)
                self._spawn_floating_text(
                    f'🏆 Achievement: {text}',
                    (Window.width / 2 - 120, Window.height - 120),
                    (1, 0.85, 0, 1))

    def _all_buildings(self):
        return self.gatherers + self.processors + self.manufacturers + self.markets + self.warehouses

    # ---------- Building Actions ----------
    def buy_building(self, building_type):
        info = BUILDING_INFO[building_type]
        cost = info['cost']
        if self.money < cost:
            return False
        if self.population < info['workers']:
            return False
        self.money -= cost
        row_map = {'gatherer': 1, 'processor': 2, 'manufacturer': 3,
                   'market': 4, 'warehouse': 2}
        pos = self._get_next_place_position(row_map.get(building_type, 2))
        if building_type == 'gatherer':
            b = ResourceGatherer()
            self.gatherers.append(b)
        elif building_type == 'processor':
            b = Processor()
            self.processors.append(b)
        elif building_type == 'manufacturer':
            b = Manufacturer()
            self.manufacturers.append(b)
        elif building_type == 'market':
            b = Market()
            self.markets.append(b)
        elif building_type == 'warehouse':
            b = Warehouse()
            self.warehouses.append(b)
        else:
            return False
        b.pos = pos
        self.add_widget(b)
        b.draw()
        self._spawn_floating_text(
            f'-${cost}', (b.x, b.y + b.height),
            (1, 0.3, 0.3, 1))
        return True

    def upgrade_building(self, building):
        if building.level >= MAX_LEVEL:
            return False
        discount = self._get_upgrade_discount()
        cost = building.get_upgrade_cost(discount)
        if self.money < cost:
            return False
        self.money -= cost
        building.level += 1
        building.draw()
        self._spawn_floating_text(
            f'⬆ Lvl {building.level} (-${cost})',
            (building.x, building.y + building.height),
            (0.3, 0.7, 1, 1))
        return True

    def sell_building(self, building):
        refund = int(BUILDING_INFO[building.building_type]['cost'] * 0.5 * building.level)
        self.money += refund
        if building in self.gatherers:
            self.gatherers.remove(building)
        elif building in self.processors:
            self.processors.remove(building)
        elif building in self.manufacturers:
            self.manufacturers.remove(building)
        elif building in self.markets:
            self.markets.remove(building)
        elif building in self.warehouses:
            self.warehouses.remove(building)
        self.remove_widget(building)
        self._spawn_floating_text(
            f'+${refund} (sold)', (building.x, building.y + building.height),
            (1, 0.85, 0, 1))
        return True

    # ---------- Save/Load ----------
    def save_game(self):
        data = {
            'money': self.money,
            'population': self.population,
            'game_time': self.game_time,
            'achievements': list(self.achievements),
            'money_history': list(self.money_history),
            'event_log': list(self.event_log),
            'buildings': []
        }
        for b in self._all_buildings():
            bdata = {
                'type': b.building_type,
                'pos': list(b.pos),
                'level': b.level,
            }
            if isinstance(b, ResourceGatherer):
                bdata['raw'] = b.raw_materials
            elif isinstance(b, Processor):
                bdata['raw'] = b.raw_materials
                bdata['processed'] = b.processed_materials
            elif isinstance(b, Manufacturer):
                bdata['processed'] = b.processed_materials
                bdata['products'] = b.products
            elif isinstance(b, Market):
                bdata['products'] = b.products
                bdata['demand'] = b.demand
                bdata['total_sold'] = b.total_sold
            elif isinstance(b, Warehouse):
                bdata['raw'] = b.raw_materials
                bdata['processed'] = b.processed_materials
            data['buildings'].append(bdata)
        try:
            with open(SAVE_FILE, 'w') as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            print(f'Save error: {e}')
            return False

    def load_game(self):
        try:
            with open(SAVE_FILE, 'r') as f:
                data = json.load(f)
        except Exception as e:
            print(f'Load error: {e}')
            return False

        # Remove current buildings
        for b in list(self._all_buildings()):
            self.remove_widget(b)
        self.gatherers.clear()
        self.processors.clear()
        self.manufacturers.clear()
        self.markets.clear()
        self.warehouses.clear()

        self.money = data.get('money', 1000)
        self.population = data.get('population', 50)
        self.game_time = data.get('game_time', 0)
        self.achievements = set(data.get('achievements', []))
        self.money_history = deque(data.get('money_history', []), maxlen=200)
        self.event_log = deque(data.get('event_log', []), maxlen=20)

        class_map = {
            'gatherer': ResourceGatherer,
            'processor': Processor,
            'manufacturer': Manufacturer,
            'market': Market,
            'warehouse': Warehouse,
        }
        list_map = {
            'gatherer': self.gatherers,
            'processor': self.processors,
            'manufacturer': self.manufacturers,
            'market': self.markets,
            'warehouse': self.warehouses,
        }

        for bdata in data.get('buildings', []):
            btype = bdata['type']
            cls = class_map.get(btype)
            if not cls:
                continue
            b = cls()
            b.pos = tuple(bdata.get('pos', (100, 100)))
            b.level = bdata.get('level', 1)
            if isinstance(b, ResourceGatherer):
                b.raw_materials = bdata.get('raw', 0)
            elif isinstance(b, Processor):
                b.raw_materials = bdata.get('raw', 0)
                b.processed_materials = bdata.get('processed', 0)
            elif isinstance(b, Manufacturer):
                b.processed_materials = bdata.get('processed', 0)
                b.products = bdata.get('products', 0)
            elif isinstance(b, Market):
                b.products = bdata.get('products', 0)
                b.demand = bdata.get('demand', 5)
                b.total_sold = bdata.get('total_sold', 0)
            elif isinstance(b, Warehouse):
                b.raw_materials = bdata.get('raw', 0)
                b.processed_materials = bdata.get('processed', 0)
            self.add_widget(b)
            b.draw()
            list_map[btype].append(b)

        return True


# ========================= CONNECTION LINES WIDGET =========================
class ConnectionOverlay(Widget):
    """Draws connection lines between buildings."""
    def __init__(self, simulation, **kwargs):
        super().__init__(**kwargs)
        self.simulation = simulation
        Clock.schedule_interval(self.draw_connections, 0.5)

    def draw_connections(self, dt=None):
        self.canvas.clear()
        sim = self.simulation
        with self.canvas:
            # Gatherers → Processors
            Color(0.25, 0.65, 0.25, 0.15)
            for g in sim.gatherers:
                for p in sim.processors:
                    self._draw_dashed_line(
                        g.x + g.width / 2, g.y + g.height / 2,
                        p.x + p.width / 2, p.y + p.height / 2)

            # Processors → Manufacturers
            Color(0.75, 0.45, 0.1, 0.15)
            for p in sim.processors:
                for m in sim.manufacturers:
                    self._draw_dashed_line(
                        p.x + p.width / 2, p.y + p.height / 2,
                        m.x + m.width / 2, m.y + m.height / 2)

            # Manufacturers → Markets
            Color(0.2, 0.4, 0.8, 0.15)
            for m in sim.manufacturers:
                for mk in sim.markets:
                    self._draw_dashed_line(
                        m.x + m.width / 2, m.y + m.height / 2,
                        mk.x + mk.width / 2, mk.y + mk.height / 2)

            # Warehouses → Processors (dotted)
            Color(0.55, 0.35, 0.8, 0.1)
            for w in sim.warehouses:
                for p in sim.processors:
                    self._draw_dashed_line(
                        w.x + w.width / 2, w.y + w.height / 2,
                        p.x + p.width / 2, p.y + p.height / 2, dash=8)

            # Active event indicators
            Color(1, 1, 0.2, 0.08)
            for ev in sim.active_events:
                r = 30 + 20 * math.sin(sim.game_time * 0.1)
                cx = Window.width / 2
                cy = Window.height / 2
                Ellipse(pos=(cx - r, cy - r), size=(r * 2, r * 2))

    def _draw_dashed_line(self, x1, y1, x2, y2, dash=12, gap=8):
        dx = x2 - x1
        dy = y2 - y1
        dist = math.sqrt(dx * dx + dy * dy)
        if dist < 1:
            return
        steps = int(dist / (dash + gap))
        for i in range(steps):
            t1 = i * (dash + gap) / dist
            t2 = min(1, (i * (dash + gap) + dash) / dist)
            sx = x1 + dx * t1
            sy = y1 + dy * t1
            ex = x1 + dx * t2
            ey = y1 + dy * t2
            Line(points=[sx, sy, ex, ey], width=1)


# ========================= STATS BAR =========================
class StatsBar(GridLayout):
    def __init__(self, simulation, **kwargs):
        super().__init__(**kwargs)
        self.simulation = simulation
        self.cols = 8
        self.size_hint = (1, None)
        self.height = 40
        self.spacing = 4
        self.padding = [8, 4]

        self.labels = {}
        stat_defs = [
            ('money', '💰 $0', (1, 0.85, 0, 1)),
            ('population', '👥 0', (0, 1, 1, 1)),
            ('gdp', '🏛️ GDP $0', (0.2, 1, 0.2, 1)),
            ('raw', '⛏ Raw: 0', (0.3, 0.85, 0.3, 1)),
            ('processed', '⚙ Proc: 0', (0.85, 0.55, 0.15, 1)),
            ('products', '📦 Prod: 0', (0.3, 0.5, 0.95, 1)),
            ('day', '📅 Day 1', (0.8, 0.8, 0.8, 1)),
            ('events', '⚡ Events: 0', (1, 1, 0.3, 1)),
        ]
        for key, default_text, color in stat_defs:
            lbl = Label(text=default_text, color=color, font_size=sp(13),
                       size_hint_x=1)
            self.add_widget(lbl)
            self.labels[key] = lbl

        Clock.schedule_interval(self._update, 0.5)

    def _update(self, dt):
        sim = self.simulation
        self.labels['money'].text = f'💰 ${int(sim.money):,}'
        self.labels['population'].text = f'👥 {int(sim.population)}'
        self.labels['gdp'].text = f'🏛️ ${int(sim.total_gdp):,}'
        self.labels['raw'].text = f'⛏ {sim.total_raw:.0f}'
        self.labels['processed'].text = f'⚙ {sim.total_processed:.0f}'
        self.labels['products'].text = f'📦 {sim.total_products:.0f}'
        self.labels['day'].text = f'📅 Day {sim.game_day}'
        self.labels['events'].text = f'⚡ {len(sim.active_events)}'


# ========================= CONTROL PANEL =========================
class ControlPanel(BoxLayout):
    def __init__(self, simulation, **kwargs):
        super().__init__(**kwargs)
        self.simulation = simulation
        self.orientation = 'vertical'
        self.size_hint = (1, None)
        self.height = 160
        self.padding = 6
        self.spacing = 4

        # Row 1: Rate sliders
        sliders_layout = GridLayout(cols=6, spacing=6, size_hint=(1, None), height=35)

        sliders_layout.add_widget(Label(text='Gather:', color=(0.3, 0.85, 0.3, 1),
                                        font_size=sp(12), size_hint_x=0.5))
        self.gather_slider = Slider(min=0.1, max=3.0, value=1.0, size_hint_x=1)
        self.gather_slider.bind(value=lambda i, v: setattr(self.simulation, '_gather_rate', v))
        sliders_layout.add_widget(self.gather_slider)

        sliders_layout.add_widget(Label(text='Process:', color=(0.85, 0.55, 0.15, 1),
                                        font_size=sp(12), size_hint_x=0.5))
        self.process_slider = Slider(min=0.1, max=3.0, value=1.0, size_hint_x=1)
        self.process_slider.bind(value=lambda i, v: setattr(self.simulation, '_process_rate', v))
        sliders_layout.add_widget(self.process_slider)

        sliders_layout.add_widget(Label(text='Manufact:', color=(0.3, 0.5, 0.95, 1),
                                        font_size=sp(12), size_hint_x=0.5))
        self.manuf_slider = Slider(min=0.1, max=3.0, value=1.0, size_hint_x=1)
        self.manuf_slider.bind(value=lambda i, v: setattr(self.simulation, '_manuf_rate', v))
        sliders_layout.add_widget(self.manuf_slider)

        self.add_widget(sliders_layout)

        # Row 2: Buy buttons
        buy_layout = GridLayout(cols=6, spacing=4, size_hint=(1, None), height=38)
        for btype, info in BUILDING_INFO.items():
            btn = Button(
                text=f'{info["name"]} (${info["cost"]})',
                font_size=sp(11),
                background_color=info['color'][:3] + (0.7,),
                color=(1, 1, 1, 1),
                size_hint_x=1
            )
            btn.bind(on_release=lambda inst, bt=btype: self._buy_building(bt))
            buy_layout.add_widget(btn)

        self.add_widget(buy_layout)

        # Row 3: Speed controls + action buttons
        action_layout = GridLayout(cols=8, spacing=4, size_hint=(1, None), height=38)

        # Speed buttons
        self.speed_buttons = {}
        for label, speed in SPEED_OPTIONS.items():
            btn = ToggleButton(
                text=label, font_size=sp(12),
                group='speed',
                background_color=(0.18, 0.18, 0.28, 1),
                color=(1, 1, 1, 1)
            )
            if speed == 1:
                btn.state = 'down'
            btn.bind(on_release=lambda inst, s=speed: self._set_speed(s))
            action_layout.add_widget(btn)
            self.speed_buttons[label] = btn

        # Action buttons
        save_btn = Button(text='💾 Save', font_size=sp(11),
                         background_color=(0.15, 0.5, 0.15, 0.8))
        save_btn.bind(on_release=lambda i: self._save())
        action_layout.add_widget(save_btn)

        load_btn = Button(text='📂 Load', font_size=sp(11),
                         background_color=(0.15, 0.3, 0.6, 0.8))
        load_btn.bind(on_release=lambda i: self._load())
        action_layout.add_widget(load_btn)

        event_btn = Button(text='📜 Events', font_size=sp(11),
                          background_color=(0.6, 0.4, 0.1, 0.8))
        event_btn.bind(on_release=lambda i: self._show_events())
        action_layout.add_widget(event_btn)

        achieve_btn = Button(text='🏆 Awards', font_size=sp(11),
                            background_color=(0.6, 0.5, 0.1, 0.8))
        achieve_btn.bind(on_release=lambda i: self._show_achievements())
        action_layout.add_widget(achieve_btn)

        self.add_widget(action_layout)

        # Row 4: Event log
        self.event_label = Label(
            text='Welcome to Economy Simulator!',
            color=(0.7, 0.7, 0.8, 1), font_size=sp(11),
            size_hint=(1, None), height=22,
            halign='left', valign='middle'
        )
        self.add_widget(self.event_label)

        Clock.schedule_interval(self._update_event_label, 1.0)

        # Initialize rate attributes
        self.simulation._gather_rate = 1.0
        self.simulation._process_rate = 1.0
        self.simulation._manuf_rate = 1.0

    def _set_speed(self, speed):
        self.simulation.game_speed = speed
        self.simulation.paused = (speed == 0)

    def _buy_building(self, btype):
        if self.simulation.buy_building(btype):
            pass  # Success feedback is handled in simulation
        else:
            self.event_label.text = f'❌ Cannot afford {BUILDING_INFO[btype]["name"]} or not enough population!'

    def _save(self):
        if self.simulation.save_game():
            self.event_label.text = '✅ Game saved successfully!'
        else:
            self.event_label.text = '❌ Save failed!'

    def _load(self):
        if self.simulation.load_game():
            self.event_label.text = '✅ Game loaded!'
        else:
            self.event_label.text = '❌ No save file found!'

    def _show_events(self):
        content = BoxLayout(orientation='vertical', padding=10, spacing=5)
        if self.simulation.event_log:
            for entry in list(self.simulation.event_log)[:15]:
                content.add_widget(Label(
                    text=entry, color=(0.8, 0.8, 0.9, 1),
                    font_size=sp(12), size_hint_y=None, height=25))
        else:
            content.add_widget(Label(text='No events yet.', color=(0.6, 0.6, 0.7, 1)))

        # Active events
        if self.simulation.active_events:
            content.add_widget(Label(text='--- Active Events ---',
                                    color=(1, 1, 0.3, 1), font_size=sp(13),
                                    size_hint_y=None, height=30))
            for ev in self.simulation.active_events:
                remaining = max(0, ev.end_time - self.simulation.game_time)
                content.add_widget(Label(
                    text=f'{ev.name} ({remaining:.0f}s left)',
                    color=(1, 0.7, 0.3, 1), font_size=sp(12),
                    size_hint_y=None, height=25))

        close_btn = Button(text='Close', size_hint_y=None, height=40,
                          background_color=(0.3, 0.15, 0.15, 1))
        content.add_widget(close_btn)

        scroll = ScrollView(size_hint=(1, 1))
        scroll.add_widget(content)

        popup = Popup(title='📜 Event Log', content=scroll,
                     size_hint=(0.7, 0.6),
                     background_color=(0.1, 0.1, 0.15, 0.95))
        close_btn.bind(on_release=popup.dismiss)
        popup.open()

    def _show_achievements(self):
        content = BoxLayout(orientation='vertical', padding=10, spacing=5)
        all_achievements = [
            ('first_1000', '💰 First $1,000'),
            ('pop_100', '👥 Population 100'),
            ('gdp_5000', '🏛️ GDP $5,000'),
            ('day_10', '📅 Survived 10 Days'),
            ('day_30', '📅 30 Days Strong'),
            ('money_10000', '💰 $10,000'),
            ('money_50000', '💰 $50,000'),
            ('buildings_10', '🏗️ 10 Buildings'),
            ('buildings_20', '🏗️ 20 Buildings'),
            ('level_5', '⭐ Level 5 Building'),
            ('level_10', '⭐⭐ Level 10 Building!'),
        ]
        for key, text in all_achievements:
            earned = key in self.simulation.achievements
            color = (1, 0.85, 0, 1) if earned else (0.4, 0.4, 0.4, 1)
            prefix = '✅ ' if earned else '🔒 '
            content.add_widget(Label(
                text=prefix + text, color=color,
                font_size=sp(13), size_hint_y=None, height=28))

        close_btn = Button(text='Close', size_hint_y=None, height=40,
                          background_color=(0.3, 0.15, 0.15, 1))
        content.add_widget(close_btn)

        scroll = ScrollView(size_hint=(1, 1))
        scroll.add_widget(content)

        popup = Popup(title='🏆 Achievements', content=scroll,
                     size_hint=(0.6, 0.7),
                     background_color=(0.1, 0.1, 0.15, 0.95))
        close_btn.bind(on_release=popup.dismiss)
        popup.open()

    def _update_event_label(self, dt):
        if self.simulation.event_log:
            self.event_label.text = self.simulation.event_log[0]


# ========================= BUILDING INFO POPUP =========================
class BuildingInfoPopup(Popup):
    def __init__(self, building, simulation, **kwargs):
        self.building = building
        self.simulation = simulation
        super().__init__(**kwargs)

        content = BoxLayout(orientation='vertical', padding=15, spacing=8)

        # Building info
        info = BUILDING_INFO[building.building_type]
        title_text = f'{info["name"]} (Level {building.level})'

        details = f'{info["desc"]}\n\n'
        details += f'Level: {building.level}/{MAX_LEVEL}\n'
        details += f'Workers Needed: {building.workers_needed}\n'

        if isinstance(building, ResourceGatherer):
            details += f'Raw Materials: {building.raw_materials:.1f}\n'
            details += f'Production Rate: {building.production_rate * building.level:.1f}/tick\n'
            details += f'Storage: {building.raw_materials:.0f}/{building.max_storage * building.level}'
        elif isinstance(building, Processor):
            details += f'Raw Materials: {building.raw_materials:.1f}\n'
            details += f'Processed Materials: {building.processed_materials:.1f}\n'
            details += f'Process Rate: {building.process_rate * building.level:.1f}/tick\n'
            details += f'Storage: {building.raw_materials + building.processed_materials:.0f}/{building.max_storage * building.level}'
        elif isinstance(building, Manufacturer):
            details += f'Processed Materials: {building.processed_materials:.1f}\n'
            details += f'Products: {building.products:.1f}\n'
            details += f'Manufacture Rate: {building.manufacture_rate * building.level:.1f}/tick\n'
            details += f'Storage: {building.processed_materials + building.products:.0f}/{building.max_storage * building.level}'
        elif isinstance(building, Market):
            details += f'Products: {building.products:.1f}\n'
            details += f'Current Price: ${building.price}\n'
            details += f'Demand: {building.demand:.1f}\n'
            details += f'Total Sold: {building.total_sold}'
        elif isinstance(building, Warehouse):
            details += f'Raw Materials: {building.raw_materials:.1f}\n'
            details += f'Processed Materials: {building.processed_materials:.1f}\n'
            details += f'Total: {building.get_total():.0f}/{building.max_storage * building.level}'

        content.add_widget(Label(text=details, color=(0.85, 0.85, 0.9, 1),
                                font_size=sp(13), halign='left', valign='top'))

        # Buttons
        btn_layout = BoxLayout(spacing=8, size_hint_y=None, height=45)

        # Upgrade button
        discount = simulation._get_upgrade_discount() if hasattr(simulation, '_get_upgrade_discount') else 1.0
        upgrade_cost = building.get_upgrade_cost(discount)
        can_upgrade = building.level < MAX_LEVEL and simulation.money >= upgrade_cost
        upgrade_btn = Button(
            text=f'⬆ Upgrade (${upgrade_cost})',
            font_size=sp(12),
            background_color=(0.15, 0.5, 0.15, 1) if can_upgrade else (0.3, 0.3, 0.3, 1),
            disabled=not can_upgrade
        )
        upgrade_btn.bind(on_release=lambda i: self._upgrade())
        btn_layout.add_widget(upgrade_btn)

        # Sell button
        sell_value = int(BUILDING_INFO[building.building_type]['cost'] * 0.5 * building.level)
        sell_btn = Button(
            text=f'💲 Sell (${sell_value})',
            font_size=sp(12),
            background_color=(0.6, 0.15, 0.15, 1)
        )
        sell_btn.bind(on_release=lambda i: self._sell())
        btn_layout.add_widget(sell_btn)

        close_btn = Button(text='✖ Close', font_size=sp(12),
                          background_color=(0.3, 0.3, 0.4, 1))
        close_btn.bind(on_release=self.dismiss)
        btn_layout.add_widget(close_btn)

        content.add_widget(btn_layout)

        self.title = title_text
        self.content = content
        self.size_hint = (0.55, 0.45)
        self.background_color = (0.1, 0.1, 0.16, 0.95)
        self.title_color = (1, 1, 0.5, 1)

    def _upgrade(self):
        if self.simulation.upgrade_building(self.building):
            self.dismiss()

    def _sell(self):
        if self.simulation.sell_building(self.building):
            self.dismiss()


# ========================= BACKGROUND WIDGET =========================
class BackgroundWidget(Widget):
    """Draws the background grid and ambient effects."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(size=self._redraw, pos=self._redraw)
        self._phase = 0
        Clock.schedule_interval(self._animate, 1.0 / 10.0)

    def _animate(self, dt):
        self._phase += dt * 0.5
        self._redraw()

    def _redraw(self, *args):
        self.canvas.clear()
        with self.canvas:
            # Background
            Color(0.08, 0.08, 0.12, 1)
            Rectangle(pos=self.pos, size=self.size)

            # Grid
            Color(0.13, 0.13, 0.19, 0.4)
            grid_size = 60
            for x in range(0, int(self.width) + grid_size, grid_size):
                Line(points=[x, 0, x, self.height], width=0.5)
            for y in range(0, int(self.height) + grid_size, grid_size):
                Line(points=[0, y, self.width, y], width=0.5)

            # Ambient glow circles
            for i in range(3):
                cx = self.width * (0.2 + 0.3 * i) + 20 * math.sin(self._phase + i)
                cy = self.height * 0.5 + 30 * math.cos(self._phase * 0.7 + i * 2)
                Color(0.15, 0.15, 0.25, 0.08)
                r = 80 + 20 * math.sin(self._phase * 0.5 + i)
                Ellipse(pos=(cx - r, cy - r), size=(r * 2, r * 2))

            # Row labels
            Color(0.3, 0.3, 0.4, 0.3)
            rows = {1: 0.78, 2: 0.55, 3: 0.32, 4: 0.12}
            row_names = {1: 'GATHERING', 2: 'PROCESSING / STORAGE', 3: 'MANUFACTURING', 4: 'MARKETPLACE'}
            for row, y_frac in rows.items():
                y = int(Window.height * y_frac) + 35
                # Subtle horizontal line
                Line(points=[10, y - 30, self.width - 10, y - 30], width=0.5,
                     dash_offset=5)


# ========================= MAIN APP =========================
class EconomyApp(App):
    def build(self):
        self.title = '🏭 Economy Simulator'

        # Main layout
        main_layout = BoxLayout(orientation='vertical')

        # Stats bar
        self.simulation = EconomySimulation()
        self.stats_bar = StatsBar(self.simulation)
        main_layout.add_widget(self.stats_bar)

        # Simulation area with background
        sim_container = BoxLayout(orientation='horizontal')

        # Background
        self.background = BackgroundWidget(size=Window.size)

        # Simulation
        self.simulation.size_hint = (1, 1)

        # Connection overlay
        self.connections = ConnectionOverlay(self.simulation)

        # Stack: background, simulation, connections
        sim_stack = StackLayout()
        sim_stack.add_widget(self.background)
        sim_stack.add_widget(self.simulation)
        sim_stack.add_widget(self.connections)

        sim_container.add_widget(sim_stack)
        main_layout.add_widget(sim_container)

        # Control panel
        self.control_panel = ControlPanel(self.simulation)
        main_layout.add_widget(self.control_panel)

        # Building click handler
        self.simulation.bind(on_touch_down=self._handle_building_click)

        # Auto-save
        Clock.schedule_interval(self._autosave, 60)

        return main_layout

    def _handle_building_click(self, simulation, touch):
        for building in simulation._all_buildings():
            if building.collide_point(*touch.pos):
                popup = BuildingInfoPopup(building, simulation)
                popup.open()
                return True
        return False

    def _autosave(self, dt):
        self.simulation.save_game()


if __name__ == '__main__':
    EconomyApp().run()