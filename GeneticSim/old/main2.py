import math, random
from matplotlib import pyplot as plt, patches
from matplotlib.animation import FuncAnimation

TAXONOMY_LEVELS = ["Kingdom", "Phylum", "Class", "Order", "Family", "Genus", "Species"]
MAX_POPULATION = 100  # population cap

def generate_lineage_name(level, parent_name=None):
    if parent_name:
        return f"{parent_name[:3]}_{TAXONOMY_LEVELS[level][:3]}{random.randint(1,99)}"
    else:
        return f"{TAXONOMY_LEVELS[level][:3]}_{random.randint(1,99)}"

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
            self.lineage_color = [min(max(c,0),1) for c in self.lineage_color]

            self.lineage_hierarchy = []
            for i in range(len(TAXONOMY_LEVELS)):
                parent_choice = random.choice([parent1,parent2])
                name = generate_lineage_name(i) if random.random()<0.1 else parent_choice.lineage_hierarchy[i]
                self.lineage_hierarchy.append(name)

            self.lineage_id = self.lineage_hierarchy[-1]
            self.x = (parent1.x + parent2.x)/2
            self.y = (parent1.y + parent2.y)/2
        else:
            self.size = random.uniform(10,30)
            self.speed = random.uniform(1,3)
            self.x = x
            self.y = y
            self.lineage_color = [random.uniform(0.2,1),random.uniform(0.2,1),random.uniform(0.2,1)]
            self.lineage_hierarchy = [generate_lineage_name(i) for i in range(len(TAXONOMY_LEVELS))]
            self.lineage_id = self.lineage_hierarchy[-1]

        self.angle = random.uniform(0,360)
        self.sides = max(3, int(3 + self.speed*2))
        self.offsets = [random.uniform(-0.2,0.2) for _ in range(self.sides)]  # stable shape offsets

    def move(self, width, height):
        self.x += math.cos(math.radians(self.angle))*self.speed
        self.y += math.sin(math.radians(self.angle))*self.speed

        if self.x <= 0 or self.x >= width: self.angle = 180 - self.angle + random.uniform(-5,5)
        if self.y <= 0 or self.y >= height: self.angle = -self.angle + random.uniform(-5,5)
        self.x = min(max(self.x,0),width)
        self.y = min(max(self.y,0),height)

    def reproduce(self, partner):
        return Creature((self.x+partner.x)/2,(self.y+partner.y)/2,parent1=self,parent2=partner)

    def get_shape_points(self):
        points=[]
        for i in range(self.sides):
            angle = 2*math.pi*i/self.sides + math.radians(self.angle)
            radius = self.size*(1+self.offsets[i])
            px = self.x + math.cos(angle)*radius
            py = self.y + math.sin(angle)*radius
            points.append((px,py))
        return points

class EvolutionSimulation:
    def __init__(self, pop_size=30,width=800,height=600):
        self.population = [Creature(random.uniform(0,width),random.uniform(0,height)) for _ in range(pop_size)]
        self.width=width
        self.height=height
        self.generation=0
        self.collision_dist=15
        self.lineage_nodes={}  # species -> info
        self.tree_positions={} # species -> (level,y)
        self.level_next_y = {}  # keeps track of next available y per level

    def step(self):
        for c in self.population: 
            c.move(self.width,self.height)

        new_creatures=[]
        for i,c1 in enumerate(self.population):
            for j in range(i+1,len(self.population)):
                c2=self.population[j]
                if len(self.population)+len(new_creatures) >= MAX_POPULATION:
                    break
                if math.hypot(c1.x-c2.x,c1.y-c2.y) < self.collision_dist and random.random() < 0.3:
                    child = c1.reproduce(c2)
                    new_creatures.append(child)
                    self.register_lineage(child)
        if new_creatures:
            self.population.extend(new_creatures)
            self.generation += 1

    def register_lineage(self, creature):
        species = creature.lineage_hierarchy[-1]
        parent_species = creature.parent1.lineage_hierarchy[-1] if creature.parent1 else None
        level = len(creature.lineage_hierarchy)-1
        if species not in self.lineage_nodes:
            self.lineage_nodes[species] = {
                'parent': parent_species,
                'color': creature.lineage_color,
                'level': level,
                'children': []
            }
            if parent_species:
                self.lineage_nodes[parent_species]['children'].append(species)

        if level not in self.level_next_y:
            self.level_next_y[level] = 5
        if species not in self.tree_positions:
            parent_y = self.tree_positions[parent_species][1] if parent_species and parent_species in self.tree_positions else self.level_next_y[level]
            y = self.level_next_y[level]
            self.tree_positions[species] = (level, y)
            self.level_next_y[level] += 3

# --------------------
# Visualization
# --------------------
sim = EvolutionSimulation()
fig, axes = plt.subplots(1,3,figsize=(18,6))
ax_env, ax_chart, ax_tree = axes

ax_env.set_xlim(0,sim.width)
ax_env.set_ylim(0,sim.height)
ax_env.set_aspect('equal')

# Bar chart setup
ax_chart.set_ylim(0,50)
ax_chart.set_xlim(0,3)
ax_chart.set_xticks([0,1,2])
ax_chart.set_xticklabels(['Size','Speed','Blue'])
bars = ax_chart.bar([0,1,2],[0,0,0],color=['cyan','magenta','blue'])

ax_tree.set_xlim(-0.5,7.5)
ax_tree.set_ylim(0,50)
ax_tree.set_title("Lineage Tree")

def update(frame):
    ax_env.clear()
    ax_env.set_xlim(0,sim.width)
    ax_env.set_ylim(0,sim.height)
    ax_env.set_title(f"Generation {sim.generation}")

    sim.step()

    # Draw creatures
    for c in sim.population:
        pts = c.get_shape_points()
        ax_env.add_patch(patches.Polygon(pts,closed=True,color=c.lineage_color))

    # Update bar chart
    avg_size = sum(c.size for c in sim.population)/len(sim.population)
    avg_speed = sum(c.speed for c in sim.population)/len(sim.population)
    avg_blue = sum(c.lineage_color[2] for c in sim.population)/len(sim.population)
    for rect,val in zip(bars,[avg_size,avg_speed,avg_blue]):
        rect.set_height(val)

    # Draw lineage tree
    ax_tree.clear()
    ax_tree.set_xlim(-0.5,7.5)
    ax_tree.set_ylim(0,max(max(sim.level_next_y.values(),default=10)+5,50))
    ax_tree.set_title("Lineage Tree")
    for species, info in sim.lineage_nodes.items():
        x, y = sim.tree_positions[species]
        parent = info['parent']
        if parent and parent in sim.tree_positions:
            px, py = sim.tree_positions[parent]
            ax_tree.plot([px, x], [py, y], color='black')
        ax_tree.add_patch(patches.Rectangle((x-0.4,y-0.4),0.8,0.8,color=info['color']))
        ax_tree.text(x, y, species, fontsize=8, ha='center', va='center')

ani = FuncAnimation(fig, update, frames=500, interval=100)
plt.tight_layout()
plt.show()
