# --------------------
# main.py
# --------------------
import math
from random import uniform, choice, randint

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.clock import Clock
from kivy.graphics import Color, Line, Rectangle
from kivy.core.window import Window

# --------------------
# Lineage Helper
# --------------------
TAXONOMY_LEVELS = ["Kingdom", "Phylum", "Class", "Order", "Family", "Genus", "Species"]

def generate_lineage_name(level, parent_name=None):
    if parent_name:
        return f"{parent_name[:3]}_{TAXONOMY_LEVELS[level][:3]}{randint(1,99)}"
    else:
        return f"{TAXONOMY_LEVELS[level][:3]}_{randint(1,99)}"

# --------------------
# Creature Class
# --------------------
class Creature:
    _id_counter = 0
    def __init__(self, x, y, parent1=None, parent2=None):
        self.id = Creature._id_counter
        Creature._id_counter += 1
        self.parent1 = parent1
        self.parent2 = parent2

        if parent1 and parent2:
            self.size = max(5, min(40, (parent1.size + parent2.size)/2 + uniform(-2,2)))
            self.speed = max(0.5, min(5, (parent1.speed + parent2.speed)/2 + uniform(-0.5,0.5)))
            self.lineage_color = [
                (parent1.lineage_color[0] + parent2.lineage_color[0])/2 + uniform(-0.05,0.05),
                (parent1.lineage_color[1] + parent2.lineage_color[1])/2 + uniform(-0.05,0.05),
                (parent1.lineage_color[2] + parent2.lineage_color[2])/2 + uniform(-0.05,0.05)
            ]
            self.lineage_color = [max(0, min(1, c)) for c in self.lineage_color]
            self.lineage_hierarchy = []
            for i in range(len(TAXONOMY_LEVELS)):
                parent_choice = choice([parent1, parent2])
                if uniform(0,1) < 0.1:  # mutation
                    name = generate_lineage_name(i)
                else:
                    name = parent_choice.lineage_hierarchy[i]
                self.lineage_hierarchy.append(name)
            self.lineage_id = self.lineage_hierarchy[-1]
            self.x = (parent1.x + parent2.x)/2
            self.y = (parent1.y + parent2.y)/2
        else:
            self.size = uniform(10, 30)
            self.speed = uniform(1, 3)
            self.x = x
            self.y = y
            self.lineage_color = [uniform(0.2,1), uniform(0.2,1), uniform(0.2,1)]
            self.lineage_hierarchy = [generate_lineage_name(i) for i in range(len(TAXONOMY_LEVELS))]
            self.lineage_id = self.lineage_hierarchy[-1]

        self.fitness = 0
        self.angle = uniform(0, 360)

    def move(self, width, height):
        self.x += math.cos(math.radians(self.angle)) * self.speed
        self.y += math.sin(math.radians(self.angle)) * self.speed
        if self.x <= 0 or self.x >= width: self.angle = 180 - self.angle
        if self.y <= 0 or self.y >= height: self.angle = -self.angle
        self.x = max(0, min(self.x, width))
        self.y = max(0, min(self.y, height))
        self.fitness = math.hypot(self.x - width/2, self.y - height/2)

    def reproduce(self, partner):
        return Creature(0,0, parent1=self, parent2=partner)

    def get_shape_points(self):
        sides = int(3 + self.speed*2)
        points = []
        for i in range(sides):
            angle = 2*math.pi*i/sides + math.radians(self.angle)
            radius = self.size * (0.8 + uniform(-0.2,0.2))
            px = self.x + math.cos(angle)*radius
            py = self.y + math.sin(angle)*radius
            points.extend([px, py])
        return points

# --------------------
# Evolution Simulation Widget
# --------------------
class EvolutionWidget(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.population_size = 30
        self.population = []
        self.generation = 0
        self.frame_count = 0
        Clock.schedule_interval(self.update, 1/30)
        self.bind(size=self.on_size)

    def on_size(self, *args):
        if not self.population and self.width > 0 and self.height > 0:
            self.population = [Creature(uniform(0,self.width), uniform(0,self.height))
                               for _ in range(self.population_size)]

    def update(self, dt):
        if not self.population:
            return

        self.canvas.clear()
        self.frame_count += 1

        with self.canvas:
            for c in self.population:
                if c.parent1:
                    Color(*c.lineage_color, 0.3)
                    Line(points=[c.parent1.x, c.parent1.y, c.x, c.y], width=1.0)
                if c.parent2:
                    Color(*c.lineage_color, 0.3)
                    Line(points=[c.parent2.x, c.parent2.y, c.x, c.y], width=1.0)
            for c in self.population:
                Color(*c.lineage_color)
                points = c.get_shape_points()
                Line(points=points, close=True, width=1.5)

        self.parent.update_charts(self.population)

        if self.frame_count % (10*30) == 0:
            self.evolve()

    def evolve(self):
        self.population.sort(key=lambda c: -c.fitness)
        survivors = self.population[:self.population_size//2]
        new_population = []

        while len(new_population) < self.population_size:
            parent1 = choice(survivors)
            parent2 = choice(survivors)
            child = parent1.reproduce(parent2)
            new_population.append(child)

        self.population = new_population
        self.generation += 1

# --------------------
# Kivy-native Chart Widget
# --------------------
class NativeChart(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.avg_size = 0
        self.avg_speed = 0
        self.avg_blue = 0
        self.max_size = 1
        self.max_speed = 1
        self.max_blue = 0.01

    def update_chart(self, population):
        if not population:
            return

        self.avg_size = sum([c.size for c in population]) / len(population)
        self.avg_speed = sum([c.speed for c in population]) / len(population)
        self.avg_blue = sum([c.lineage_color[2] for c in population]) / len(population)

        self.max_size = max(self.max_size, self.avg_size)
        self.max_speed = max(self.max_speed, self.avg_speed)
        self.max_blue = max(self.max_blue, self.avg_blue)

        self.draw_chart()

    def draw_chart(self):
        self.canvas.clear()
        w, h = self.width, self.height
        margin = 10
        bar_width = (w - 4*margin)/3
        chart_height = h - 2*margin

        with self.canvas:
            Color(0,1,1)
            Rectangle(pos=(margin, margin), size=(bar_width, (self.avg_size/self.max_size)*chart_height))
            Color(1,0,1)
            Rectangle(pos=(2*margin + bar_width, margin), size=(bar_width, (self.avg_speed/self.max_speed)*chart_height))
            Color(0,0,1)
            Rectangle(pos=(3*margin + 2*bar_width, margin), size=(bar_width, (self.avg_blue/self.max_blue)*chart_height))

# --------------------
# Enhanced Lineage Tree Widget
# --------------------
class LineageTreeWidget(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.lineage_nodes = {}
        self.zoom = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self._touches = {}
        Window.bind(on_mouse_scroll=self.on_mouse_scroll)

    def on_mouse_scroll(self, window, x, y, scroll_x, scroll_y):
        factor = 1.1 if scroll_y > 0 else 0.9
        self.zoom *= factor
        self.redraw()
        return True

    def on_touch_down(self, touch):
        self._touches[touch.id] = touch.pos

    def on_touch_move(self, touch):
        if touch.id in self._touches:
            dx = touch.x - self._touches[touch.id][0]
            dy = touch.y - self._touches[touch.id][1]
            self.offset_x += dx
            self.offset_y += dy
            self._touches[touch.id] = touch.pos
            self.redraw()

    def on_touch_up(self, touch):
        if touch.id in self._touches:
            self._touches.pop(touch.id)

    def update_lineage(self, population):
        for c in population:
            species = c.lineage_hierarchy[-1]
            parent_species = c.parent1.lineage_hierarchy[-1] if c.parent1 else None
            if species not in self.lineage_nodes:
                self.lineage_nodes[species] = {
                    'parent': parent_species,
                    'children': [],
                    'level': 0,
                    'pos': (0,0),
                    'color': c.lineage_color
                }
                if parent_species:
                    self.lineage_nodes[parent_species]['children'].append(species)
        self.assign_levels()
        self.redraw()

    def assign_levels(self):
        for species in self.lineage_nodes:
            parent = self.lineage_nodes[species]['parent']
            self.lineage_nodes[species]['level'] = self.lineage_nodes[parent]['level']+1 if parent else 0

    def redraw(self):
        self.canvas.clear()
        self.clear_widgets()
        if not self.lineage_nodes:
            return
        w, h = self.width, self.height
        margin = 20
        node_width = 80
        node_height = 30
        sorted_species = list(self.lineage_nodes.keys())

        with self.canvas:
            for species, info in self.lineage_nodes.items():
                parent = info['parent']
                x = margin + info['level'] * (node_width + margin) * self.zoom + self.offset_x
                y = h - (margin + sorted_species.index(species)*(node_height+10)*self.zoom) + self.offset_y
                info['pos'] = (x,y)
                if parent:
                    px, py = self.lineage_nodes[parent]['pos']
                    Color(0,0,0)
                    Line(points=[px + node_width/2, py, x + node_width/2, y + node_height], width=1.2)
            for species, info in self.lineage_nodes.items():
                x, y = info['pos']
                Color(*info['color'])
                Rectangle(pos=(x, y), size=(node_width*self.zoom, node_height*self.zoom))
                label = Label(text=species, font_size=12*self.zoom, color=(0,0,0,1),
                              size=(node_width*self.zoom,node_height*self.zoom),
                              pos=(x, y))
                self.add_widget(label)

# --------------------
# Main App Layout
# --------------------
class EvolutionApp(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation='horizontal', **kwargs)
        self.spacing = 10
        self.padding = 10

        self.evo_widget = EvolutionWidget(size_hint=(0.7,1))
        self.add_widget(self.evo_widget)

        right_box = BoxLayout(orientation='vertical', size_hint=(0.3,1), spacing=5)
        self.gen_label = Label(text="Generation: 0", size_hint=(1,0.1))
        self.chart_widget = NativeChart(size_hint=(1,0.4))
        self.lineage_tree_widget = LineageTreeWidget(size_hint=(1,0.5))
        right_box.add_widget(self.gen_label)
        right_box.add_widget(self.chart_widget)
        right_box.add_widget(self.lineage_tree_widget)
        self.add_widget(right_box)

    def update_charts(self, population):
        self.chart_widget.update_chart(population)
        species_counts = {}
        for c in population:
            species_counts[c.lineage_hierarchy[-1]] = species_counts.get(c.lineage_hierarchy[-1],0)+1
        top_species = max(species_counts.items(), key=lambda x: x[1])[0] if species_counts else "None"
        self.gen_label.text = f"Gen: {self.evo_widget.generation} | Pop: {len(population)} | Top Species: {top_species}"
        self.lineage_tree_widget.update_lineage(population)

# --------------------
# Run App
# --------------------
class EvolutionSimulationApp(App):
    def build(self):
        return EvolutionApp()

if __name__ == "__main__":
    EvolutionSimulationApp().run()
