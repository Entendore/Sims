# --------------------
# evolution_matplotlib.py
# --------------------
import math
import random
from matplotlib import pyplot as plt
from matplotlib import patches
from matplotlib.animation import FuncAnimation

# --------------------
# Lineage Helper
# --------------------
TAXONOMY_LEVELS = ["Kingdom", "Phylum", "Class", "Order", "Family", "Genus", "Species"]

def generate_lineage_name(level, parent_name=None):
    if parent_name:
        return f"{parent_name[:3]}_{TAXONOMY_LEVELS[level][:3]}{random.randint(1,99)}"
    else:
        return f"{TAXONOMY_LEVELS[level][:3]}_{random.randint(1,99)}"

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
            self.size = max(5, min(40, (parent1.size + parent2.size)/2 + random.uniform(-2,2)))
            self.speed = max(0.5, min(5, (parent1.speed + parent2.speed)/2 + random.uniform(-0.5,0.5)))
            self.lineage_color = [
                (parent1.lineage_color[0] + parent2.lineage_color[0])/2 + random.uniform(-0.05,0.05),
                (parent1.lineage_color[1] + parent2.lineage_color[1])/2 + random.uniform(-0.05,0.05),
                (parent1.lineage_color[2] + parent2.lineage_color[2])/2 + random.uniform(-0.05,0.05)
            ]
            self.lineage_color = [max(0, min(1, c)) for c in self.lineage_color]
            self.lineage_hierarchy = []
            for i in range(len(TAXONOMY_LEVELS)):
                parent_choice = random.choice([parent1, parent2])
                if random.uniform(0,1) < 0.1:
                    name = generate_lineage_name(i)
                else:
                    name = parent_choice.lineage_hierarchy[i]
                self.lineage_hierarchy.append(name)
            self.lineage_id = self.lineage_hierarchy[-1]
            self.x = (parent1.x + parent2.x)/2
            self.y = (parent1.y + parent2.y)/2
        else:
            self.size = random.uniform(10, 30)
            self.speed = random.uniform(1, 3)
            self.x = x
            self.y = y
            self.lineage_color = [random.uniform(0.2,1), random.uniform(0.2,1), random.uniform(0.2,1)]
            self.lineage_hierarchy = [generate_lineage_name(i) for i in range(len(TAXONOMY_LEVELS))]
            self.lineage_id = self.lineage_hierarchy[-1]

        self.fitness = 0
        self.angle = random.uniform(0, 360)

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
            radius = self.size * (0.8 + random.uniform(-0.2,0.2))
            px = self.x + math.cos(angle)*radius
            py = self.y + math.sin(angle)*radius
            points.append((px, py))
        return points

# --------------------
# Simulation
# --------------------
class EvolutionSimulation:
    def __init__(self, population_size=30, width=800, height=600):
        self.population_size = population_size
        self.population = [Creature(random.uniform(0,width), random.uniform(0,height))
                           for _ in range(population_size)]
        self.width = width
        self.height = height
        self.generation = 0

    def step(self):
        for c in self.population:
            c.move(self.width, self.height)
        if random.randint(0, 29) == 0:  # evolve every ~30 frames
            self.evolve()

    def evolve(self):
        self.population.sort(key=lambda c: -c.fitness)
        survivors = self.population[:self.population_size//2]
        new_population = []
        while len(new_population) < self.population_size:
            p1 = random.choice(survivors)
            p2 = random.choice(survivors)
            new_population.append(p1.reproduce(p2))
        self.population = new_population
        self.generation += 1

# --------------------
# Matplotlib Visualization
# --------------------
sim = EvolutionSimulation()

fig, axes = plt.subplots(1,2, figsize=(12,6))
ax_env, ax_chart = axes
ax_env.set_xlim(0, sim.width)
ax_env.set_ylim(0, sim.height)
ax_env.set_title("Creature Evolution")
ax_env.set_aspect('equal')
ax_chart.set_ylim(0, 50)
ax_chart.set_xlim(0, 3)
ax_chart.set_xticks([0,1,2])
ax_chart.set_xticklabels(['Size','Speed','Blue'])
bars = ax_chart.bar([0,1,2],[0,0,0], color=['cyan','magenta','blue'])
ax_chart.set_title("Average Traits")

patches_list = []

def update(frame):
    ax_env.clear()
    ax_env.set_xlim(0, sim.width)
    ax_env.set_ylim(0, sim.height)
    ax_env.set_title(f"Generation {sim.generation}")
    sim.step()

    # Draw creatures
    for c in sim.population:
        pts = c.get_shape_points()
        polygon = patches.Polygon(pts, closed=True, color=c.lineage_color)
        ax_env.add_patch(polygon)

    # Draw average traits
    avg_size = sum(c.size for c in sim.population)/len(sim.population)
    avg_speed = sum(c.speed for c in sim.population)/len(sim.population)
    avg_blue = sum(c.lineage_color[2] for c in sim.population)/len(sim.population)
    for rect, val in zip(bars, [avg_size, avg_speed, avg_blue]):
        rect.set_height(val)
    ax_chart.relim()
    ax_chart.autoscale_view()

ani = FuncAnimation(fig, update, frames=200, interval=100)
plt.tight_layout()
plt.show()
