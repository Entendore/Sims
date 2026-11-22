import matplotlib.pyplot as plt
import matplotlib.animation as animation
import random
import math
from collections import Counter, defaultdict

# --- CONFIGURATION ---
WIDTH, HEIGHT = 100, 100
NUM_FOOD = 50
NUM_PREY = 20
NUM_PRED1 = 5
NUM_PRED2 = 2
FOOD_RESPAWN_RATE = 0.05
MAX_AGE = 100
REPRODUCE_ENERGY = 80
MUTATION_RATE = 0.1

# --- ENTITY CLASSES ---
class Food:
    def __init__(self):
        self.x = random.randint(0, WIDTH-1)
        self.y = random.randint(0, HEIGHT-1)

class Agent:
    def __init__(self, x=None, y=None, speed=None, perception=None, energy_efficiency=None,
                 move_strategy=None, lineage=None):
        self.x = x if x is not None else random.randint(0, WIDTH-1)
        self.y = y if y is not None else random.randint(0, HEIGHT-1)
        self.age = 0
        self.energy = 50
        self.speed = speed if speed is not None else random.uniform(1,5)
        self.perception = perception if perception is not None else random.randint(5,20)
        self.energy_efficiency = energy_efficiency if energy_efficiency is not None else random.uniform(0.5,1.0)
        self.move_strategy = move_strategy if move_strategy is not None else random.uniform(0,1)
        self.lineage = lineage if lineage else []

    def distance(self, other):
        return math.hypot(self.x - other.x, self.y - other.y)

    def move(self, options, **kwargs):
        best_score = -float('inf')
        best_move = (self.x, self.y)
        for dx, dy in options:
            nx, ny = max(0, min(WIDTH-1, self.x + dx)), max(0, min(HEIGHT-1, self.y + dy))
            score = self.evaluate_move(nx, ny, **kwargs)
            if score > best_score:
                best_score = score
                best_move = (nx, ny)
        self.x, self.y = best_move
        self.age += 1
        self.energy -= self.speed * (1 - self.energy_efficiency)

    def evaluate_move(self, nx, ny, **kwargs):
        return random.random()

    def reproduce(self):
        if self.energy >= REPRODUCE_ENERGY:
            self.energy /= 2
            child = self.__class__(
                speed=max(0.1, self.speed + random.uniform(-MUTATION_RATE, MUTATION_RATE)),
                perception=max(1, int(self.perception + random.randint(-1,1))),
                energy_efficiency=max(0.1,min(1.0,self.energy_efficiency + random.uniform(-0.05,0.05))),
                move_strategy=min(1.0,max(0.0,self.move_strategy + random.uniform(-0.1,0.1))),
                lineage=self.lineage + ['child']
            )
            return child
        return None

# --- Subclasses ---
class Prey(Agent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.lineage = self.lineage + ['prey']

    def eat(self, foods):
        for f in foods:
            if self.distance(f) < 2:
                self.energy += 20
                foods.remove(f)
                return

    def evaluate_move(self, nx, ny, predators1=None, predators2=None, foods=None, **kwargs):
        flee_score = 0
        seek_score = 0
        for pred in (predators1 or []) + (predators2 or []):
            dist = math.hypot(nx - pred.x, ny - pred.y)
            if dist < self.perception: flee_score += dist
        for f in foods or []:
            dist = math.hypot(nx - f.x, ny - f.y)
            seek_score -= dist
        return self.move_strategy * seek_score + (1-self.move_strategy) * flee_score + random.random()*0.1

class Predator1(Agent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.lineage = self.lineage + ['pred1']

    def eat(self, preys):
        for p in preys:
            if self.distance(p) < 2:
                self.energy += 40
                preys.remove(p)
                return

    def evaluate_move(self, nx, ny, preys=None, predators2=None, **kwargs):
        hunt_score = 0
        avoid_score = 0
        for p in preys or []:
            dist = math.hypot(nx - p.x, ny - p.y)
            hunt_score -= dist
        for p2 in predators2 or []:
            dist = math.hypot(nx - p2.x, ny - p2.y)
            if dist < self.perception: avoid_score += dist
        return self.move_strategy * hunt_score + (1-self.move_strategy) * avoid_score + random.random()*0.1

class Predator2(Agent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.lineage = self.lineage + ['pred2']

    def eat(self, predators1):
        for p in predators1:
            if self.distance(p) < 2:
                self.energy += 50
                predators1.remove(p)
                return

    def evaluate_move(self, nx, ny, predators1=None, predators2=None, **kwargs):
        hunt_score = 0
        avoid_score = 0
        for p in predators1 or []:
            dist = math.hypot(nx - p.x, ny - p.y)
            hunt_score -= dist
        for p2 in predators2 or []:
            dist = math.hypot(nx - p2.x, ny - p2.y)
            if dist < self.perception: avoid_score += dist
        return self.move_strategy * hunt_score + (1-self.move_strategy) * avoid_score + random.random()*0.1

# --- INITIALIZATION ---
foods = [Food() for _ in range(NUM_FOOD)]
preys = [Prey() for _ in range(NUM_PREY)]
predators1 = [Predator1() for _ in range(NUM_PRED1)]
predators2 = [Predator2() for _ in range(NUM_PRED2)]
moves = [(dx,dy) for dx in [-1,0,1] for dy in [-1,0,1]]

# --- PLOTTING ---
fig, axes = plt.subplots(3,2,figsize=(14,14))
ax_ecosystem = axes[0,0]
ax_population = axes[0,1]
ax_speed = axes[1,0]
ax_perception = axes[1,1]
ax_efficiency = axes[2,0]
ax_strategy = axes[2,1]

pop_history = {'prey':[], 'pred1':[], 'pred2':[]}
lineage_traits = defaultdict(lambda: {'speed':[], 'perception':[], 'efficiency':[], 'strategy':[]})
frame_number = 0

def update(frame):
    global frame_number
    frame_number += 1
    # Clear axes
    for ax in [ax_ecosystem, ax_population, ax_speed, ax_perception, ax_efficiency, ax_strategy]:
        ax.clear()

    # Set limits and labels
    ax_ecosystem.set_xlim(0, WIDTH); ax_ecosystem.set_ylim(0, HEIGHT)
    ax_ecosystem.set_title("Ecosystem")
    ax_population.set_xlabel("Frame"); ax_population.set_ylabel("Population"); ax_population.set_title("Population Over Time")
    ax_speed.set_xlabel("Frame"); ax_speed.set_ylabel("Avg Speed"); ax_speed.set_title("Lineage Speed")
    ax_perception.set_xlabel("Frame"); ax_perception.set_ylabel("Avg Perception"); ax_perception.set_title("Lineage Perception")
    ax_efficiency.set_xlabel("Frame"); ax_efficiency.set_ylabel("Avg Efficiency"); ax_efficiency.set_title("Lineage Energy Efficiency")
    ax_strategy.set_xlabel("Frame"); ax_strategy.set_ylabel("Avg Strategy"); ax_strategy.set_title("Lineage Move Strategy")

    # Spawn food
    if random.random() < FOOD_RESPAWN_RATE: foods.append(Food())

    # Update agents
    for agent_list, kwargs in [(preys, {'predators1':predators1,'predators2':predators2,'foods':foods}),
                               (predators1, {'preys':preys,'predators2':predators2}),
                               (predators2, {'predators1':predators1,'predators2':predators2})]:
        for a in agent_list[:]:
            a.move(moves, **kwargs)
            if isinstance(a, Prey): a.eat(foods)
            elif isinstance(a, Predator1): a.eat(preys)
            elif isinstance(a, Predator2): a.eat(predators1)
            child = a.reproduce()
            if child: agent_list.append(child)
            if a.energy <=0 or a.age>MAX_AGE: agent_list.remove(a)

    # Plot ecosystem
    for f in foods: ax_ecosystem.plot(f.x,f.y,'yo')
    def plot_agents(agents, color):
        for a in agents: ax_ecosystem.plot(a.x,a.y,'o',color=color)
    plot_agents(preys,'green'); plot_agents(predators1,'red'); plot_agents(predators2,'magenta')

    # Population over time
    pop_history['prey'].append(len(preys))
    pop_history['pred1'].append(len(predators1))
    pop_history['pred2'].append(len(predators2))
    ax_population.plot(pop_history['prey'],'g-',label='Prey')
    ax_population.plot(pop_history['pred1'],'r-',label='Pred1')
    ax_population.plot(pop_history['pred2'],'m-',label='Pred2')
    ax_population.legend()

    # Update lineage traits
    for agent_list in [preys,predators1,predators2]:
        for a in agent_list:
            lin = tuple(a.lineage)
            lineage_traits[lin]['speed'].append(a.speed)
            lineage_traits[lin]['perception'].append(a.perception)
            lineage_traits[lin]['efficiency'].append(a.energy_efficiency)
            lineage_traits[lin]['strategy'].append(a.move_strategy)

    # Plot traits for each lineage
    for lin,data in lineage_traits.items():
        if data['speed']: ax_speed.plot(frame_number,sum(data['speed'])/len(data['speed']),'o')
        if data['perception']: ax_perception.plot(frame_number,sum(data['perception'])/len(data['perception']),'o')
        if data['efficiency']: ax_efficiency.plot(frame_number,sum(data['efficiency'])/len(data['efficiency']),'o')
        if data['strategy']: ax_strategy.plot(frame_number,sum(data['strategy'])/len(data['strategy']),'o')

ani = animation.FuncAnimation(fig, update, frames=500, interval=200)
plt.show()
