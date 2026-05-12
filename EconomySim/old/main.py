from kivy.app import App
from kivy.uix.widget import Widget
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.slider import Slider
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle, Ellipse, Line
from kivy.animation import Animation
from kivy.properties import NumericProperty, StringProperty, ListProperty
from kivy.core.window import Window
from kivy.graphics.vertex_instructions import RoundedRectangle
import random
import math

Window.clearcolor = (0.1, 0.1, 0.15, 1)

class ResourceGatherer(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size = (60, 60)
        self.resources = 0
        self.production_rate = 1
        self.draw_base()

    def draw_base(self):
        self.canvas.clear()
        with self.canvas:
            Color(0.2, 0.8, 0.2, 1)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[10])
            Color(1, 1, 1, 1)
            Ellipse(pos=(self.x + 15, self.y + 15), size=(30, 30))
            Color(0, 0, 0, 1)
            Line(points=[self.x + 20, self.y + 30, self.x + 40, self.y + 30], width=2)
            Line(points=[self.x + 30, self.y + 20, self.x + 30, self.y + 40], width=2)

    def gather(self):
        self.resources += self.production_rate
        # Animate gathering
        anim = Animation(size=(70, 70), duration=0.2) + Animation(size=(60, 60), duration=0.2)
        anim.start(self)

class Processor(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size = (80, 80)
        self.raw_materials = 0
        self.processed_materials = 0
        self.capacity = 5
        self.draw_base()

    def draw_base(self):
        self.canvas.clear()
        with self.canvas:
            Color(0.8, 0.5, 0.2, 1)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[15])
            Color(1, 1, 1, 1)
            Rectangle(pos=(self.x + 20, self.y + 20), size=(40, 40))
            Color(0, 0, 0, 1)
            Line(rectangle=(self.x + 20, self.y + 20, 40, 40), width=2)

    def process(self):
        if self.raw_materials >= 2:
            self.raw_materials -= 2
            self.processed_materials += 1
            # Animate processing
            anim = Animation(opacity=0.5, duration=0.3) + Animation(opacity=1, duration=0.3)
            anim.start(self)

class Manufacturer(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size = (100, 100)
        self.processed_materials = 0
        self.products = 0
        self.money = 100
        self.draw_base()

    def draw_base(self):
        self.canvas.clear()
        with self.canvas:
            Color(0.2, 0.4, 0.8, 1)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[20])
            Color(1, 1, 1, 1)
            Ellipse(pos=(self.x + 25, self.y + 25), size=(50, 50))
            Color(0, 0, 0, 1)
            Line(ellipse=(self.x + 25, self.y + 25, 50, 50), width=2)

    def manufacture(self):
        if self.processed_materials >= 3:
            self.processed_materials -= 3
            self.products += 1
            # Animate manufacturing
            anim = Animation(rotation=360, duration=0.5)
            anim.start(self)

class Market(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size = (120, 120)
        self.demand = 5
        self.price = 10
        self.draw_base()

    def draw_base(self):
        self.canvas.clear()
        with self.canvas:
            Color(0.9, 0.2, 0.2, 1)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[25])
            Color(1, 1, 1, 1)
            Rectangle(pos=(self.x + 30, self.y + 30), size=(60, 60))
            Color(0, 0, 0, 1)
            Line(rectangle=(self.x + 30, self.y + 30, 60, 60), width=3)

class ResourceParticle(Widget):
    def __init__(self, start_pos, end_pos, color, **kwargs):
        super().__init__(**kwargs)
        self.size = (10, 10)
        self.pos = start_pos
        self.color = color
        with self.canvas:
            Color(*color)
            Ellipse(pos=self.pos, size=self.size)
        
        # Animate movement
        anim = Animation(pos=end_pos, duration=1.5) 
        anim.bind(on_complete=self.remove_from_parent)
        anim.start(self)

    def remove_from_parent(self, *args):
        if self.parent:
            self.parent.remove_widget(self)

class EconomySimulation(Widget):
    money = NumericProperty(1000)
    population = NumericProperty(50)
    resource_rate = NumericProperty(1.0)
    processing_rate = NumericProperty(1.0)
    manufacturing_rate = NumericProperty(1.0)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.gatherers = []
        self.processors = []
        self.manufacturers = []
        self.market = None
        self.particles = []
        
        self.setup_economy()
        Clock.schedule_interval(self.update, 1.0/30.0)  # 30 FPS

    def setup_economy(self):
        # Create gatherers
        for i in range(3):
            gatherer = ResourceGatherer()
            gatherer.pos = (100 + i * 150, 400)
            self.add_widget(gatherer)
            self.gatherers.append(gatherer)

        # Create processors
        for i in range(2):
            processor = Processor()
            processor.pos = (150 + i * 200, 250)
            self.add_widget(processor)
            self.processors.append(processor)

        # Create manufacturers
        for i in range(2):
            manufacturer = Manufacturer()
            manufacturer.pos = (200 + i * 250, 100)
            self.add_widget(manufacturer)
            self.manufacturers.append(manufacturer)

        # Create market
        self.market = Market()
        self.market.pos = (Window.width - 200, Window.height / 2 - 60)
        self.add_widget(self.market)

    def update(self, dt):
        # Resource gathering
        for gatherer in self.gatherers:
            if random.random() < 0.1 * self.resource_rate:
                gatherer.gather()
                # Send resources to random processor
                if self.processors:
                    processor = random.choice(self.processors)
                    particle = ResourceParticle(
                        gatherer.pos,
                        processor.pos,
                        (0.2, 0.8, 0.2, 1)
                    )
                    self.add_widget(particle)

        # Processing
        for processor in self.processors:
            # Receive resources from gatherers
            for gatherer in self.gatherers:
                if gatherer.resources > 0 and processor.raw_materials < processor.capacity:
                    gatherer.resources -= 1
                    processor.raw_materials += 1
            
            # Process materials
            if random.random() < 0.05 * self.processing_rate:
                processor.process()
                # Send processed materials to random manufacturer
                if processor.processed_materials > 0 and self.manufacturers:
                    manufacturer = random.choice(self.manufacturers)
                    particle = ResourceParticle(
                        processor.pos,
                        manufacturer.pos,
                        (0.8, 0.5, 0.2, 1)
                    )
                    self.add_widget(particle)

        # Manufacturing
        for manufacturer in self.manufacturers:
            # Receive processed materials
            for processor in self.processors:
                if processor.processed_materials > 0 and manufacturer.processed_materials < 10:
                    processor.processed_materials -= 1
                    manufacturer.processed_materials += 1
            
            # Manufacture products
            if random.random() < 0.03 * self.manufacturing_rate:
                manufacturer.manufacture()
                # Sell products
                if manufacturer.products > 0:
                    manufacturer.products -= 1
                    manufacturer.money += self.market.price
                    self.money += self.market.price * 0.1  # Tax revenue

class ControlPanel(BoxLayout):
    def __init__(self, simulation, **kwargs):
        super().__init__(**kwargs)
        self.simulation = simulation
        self.orientation = 'vertical'
        self.size_hint = (1, 0.2)
        self.padding = 10
        self.spacing = 10
        
        # Stats display
        stats_layout = GridLayout(cols=4, spacing=10, size_hint=(1, 0.5))
        
        self.money_label = Label(
            text=f'Money: ${self.simulation.money}',
            color=(1, 1, 0, 1),
            font_size=16
        )
        stats_layout.add_widget(self.money_label)
        
        self.population_label = Label(
            text=f'Population: {self.simulation.population}',
            color=(0, 1, 1, 1),
            font_size=16
        )
        stats_layout.add_widget(self.population_label)
        
        self.gdp_label = Label(
            text='GDP: $0',
            color=(0, 1, 0, 1),
            font_size=16
        )
        stats_layout.add_widget(self.gdp_label)
        
        self.efficiency_label = Label(
            text='Efficiency: 100%',
            color=(1, 0.5, 0, 1),
            font_size=16
        )
        stats_layout.add_widget(self.efficiency_label)
        
        self.add_widget(stats_layout)
        
        # Controls
        controls_layout = GridLayout(cols=3, spacing=10, size_hint=(1, 0.5))
        
        # Resource rate slider
        controls_layout.add_widget(Label(text='Resource Rate:', color=(1, 1, 1, 1)))
        self.resource_slider = Slider(min=0.1, max=3.0, value=1.0)
        self.resource_slider.bind(value=self.on_resource_rate_change)
        controls_layout.add_widget(self.resource_slider)
        
        # Processing rate slider
        controls_layout.add_widget(Label(text='Processing Rate:', color=(1, 1, 1, 1)))
        self.processing_slider = Slider(min=0.1, max=3.0, value=1.0)
        self.processing_slider.bind(value=self.on_processing_rate_change)
        controls_layout.add_widget(self.processing_slider)
        
        # Manufacturing rate slider
        controls_layout.add_widget(Label(text='Manufacturing Rate:', color=(1, 1, 1, 1)))
        self.manufacturing_slider = Slider(min=0.1, max=3.0, value=1.0)
        self.manufacturing_slider.bind(value=self.on_manufacturing_rate_change)
        controls_layout.add_widget(self.manufacturing_slider)
        
        self.add_widget(controls_layout)
        
        # Update stats
        Clock.schedule_interval(self.update_stats, 1.0)

    def on_resource_rate_change(self, instance, value):
        self.simulation.resource_rate = value

    def on_processing_rate_change(self, instance, value):
        self.simulation.processing_rate = value

    def on_manufacturing_rate_change(self, instance, value):
        self.simulation.manufacturing_rate = value

    def update_stats(self, dt):
        self.money_label.text = f'Money: ${int(self.simulation.money)}'
        self.population_label.text = f'Population: {self.simulation.population}'
        
        # Calculate GDP (sum of all money in the system)
        total_money = self.simulation.money
        for manufacturer in self.simulation.manufacturers:
            total_money += manufacturer.money
        self.gdp_label.text = f'GDP: ${int(total_money)}'
        
        # Calculate efficiency
        efficiency = min(100, (self.simulation.resource_rate + self.simulation.processing_rate + self.simulation.manufacturing_rate) * 33.33)
        self.efficiency_label.text = f'Efficiency: {efficiency:.0f}%'

class EconomyApp(App):
    def build(self):
        self.title = 'Economy Simulation'
        
        # Main layout
        main_layout = BoxLayout(orientation='vertical')
        
        # Simulation area
        self.simulation = EconomySimulation()
        
        # Control panel
        self.control_panel = ControlPanel(self.simulation)
        
        main_layout.add_widget(self.simulation)
        main_layout.add_widget(self.control_panel)
        
        return main_layout

if __name__ == '__main__':
    EconomyApp().run()