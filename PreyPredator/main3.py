import matplotlib.pyplot as plt
import matplotlib.animation as animation
import random
import math
from collections import Counter

# --- CONFIGURATION ---
WIDTH, HEIGHT = 100, 100
NUM_FOOD = 50
NUM_PREY = 20
NUM_PRED1 = 5
NUM_PRED2 = 2
FOOD_RESPAWN_RATE = 0.05
MAX_AGE = 100
MCTS_SIMULATIONS = 10
REPRODUCE_ENERGY = 80
MUTATION_RATE = 0.1

# --- ENTITY CLASSES ---
class Food:
    def __init__(self):
        self.x = random.randint(0, WIDTH-1)
        self.y = random.randint(0, HEIGHT-1)

class Agent:
    def __init__(self, x=None, y=None, speed=None, perception=None, lineage=None):
        self.x = x if x is not None else random.randint(0, WIDTH-1)
        self.y = y if y is not None else random.randint(0, HEIGHT-1)
        self.age = 0
        self.energy = 50
        self.speed = speed if speed is not None else random.uniform(1,5)
        self.perception = perception if perception is not None else random.randint(5,20)
        self.lineage = lineage if lineage else []

    def distance(self, other):
        return math.hypot(self.x - other.x, self.y - other.y)

    def move(self, target=None):
        best_score = -float('inf')
        best_move = (self.x, self.y)
        for _ in range(MCTS_SIMULATIONS):
            dx, dy = random.randint(-1,1), random.randint(-1,1)
            nx, ny = max(0, min(WIDTH-1, self.x + dx)), max(0, min(HEIGHT-1, self.y + dy))
            score = 0
            if target:
                dist = math.hypot(nx - target.x, ny - target.y)
                score = -dist
            if score > best_score:
                best_score = score
                best_move = (nx, ny)
        self.x, self.y = best_move
        self.age += 1
        self.energy -= 1

    def reproduce(self):
        if self.energy >= REPRODUCE_ENERGY:
            self.energy /= 2
            child_speed = max(0.1, self.speed + random.uniform(-MUTATION_RATE, MUTATION_RATE))
            child_perception = max(1, int(self.perception + random.randint(-1,1)))
            child = self.__class__(speed=child_speed, perception=child_perception, lineage=self.lineage + ['child'])
            return child
        return None

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

# --- INITIALIZATION ---
foods = [Food() for _ in range(NUM_FOOD)]
preys = [Prey() for _ in range(NUM_PREY)]
predators1 = [Predator1() for _ in range(NUM_PRED1)]
predators2 = [Predator2() for _ in range(NUM_PRED2)]

# --- PLOTTING SETUP ---
fig, (ax_ecosystem, ax_traits) = plt.subplots(1, 2, figsize=(12,6))
ax_ecosystem.set_xlim(0, WIDTH)
ax_ecosystem.set_ylim(0, HEIGHT)
ax_traits.set_xlim(0, 500)
ax_traits.set_ylim(0, 10)
ax_traits.set_xlabel("Frame")
ax_traits.set_ylabel("Average Trait Value")
lines = {'prey_speed':[], 'pred1_speed':[], 'pred2_speed':[]}

# --- SIMULATION ---
frame_number = 0

def update(frame):
    global frame_number
    frame_number += 1
    ax_ecosystem.clear()
    ax_ecosystem.set_xlim(0, WIDTH)
    ax_ecosystem.set_ylim(0, HEIGHT)
    ax_traits.clear()
    ax_traits.set_xlabel("Frame")
    ax_traits.set_ylabel("Average Trait Value")

    # Spawn food
    if random.random() < FOOD_RESPAWN_RATE:
        foods.append(Food())

    # Prey actions
    for prey in preys[:]:
        if foods:
            nearest_food = min(foods, key=lambda f: prey.distance(f))
            prey.move(target=nearest_food)
        else:
            prey.move()
        prey.eat(foods)
        child = prey.reproduce()
        if child:
            preys.append(child)
        if prey.energy <= 0 or prey.age > MAX_AGE:
            preys.remove(prey)
        else:
            ax_ecosystem.plot(prey.x, prey.y, 'go')  # green = prey

    # Predator1 actions
    for pred in predators1[:]:
        if preys:
            nearest_prey = min(preys, key=lambda p: pred.distance(p))
            pred.move(target=nearest_prey)
        else:
            pred.move()
        pred.eat(preys)
        child = pred.reproduce()
        if child:
            predators1.append(child)
        if pred.energy <= 0 or pred.age > MAX_AGE:
            predators1.remove(pred)
        else:
            ax_ecosystem.plot(pred.x, pred.y, 'ro')  # red = predator1

    # Predator2 actions
    for pred in predators2[:]:
        if predators1:
            nearest_pred = min(predators1, key=lambda p: pred.distance(p))
            pred.move(target=nearest_pred)
        else:
            pred.move()
        pred.eat(predators1)
        child = pred.reproduce()
        if child:
            predators2.append(child)
        if pred.energy <= 0 or pred.age > MAX_AGE:
            predators2.remove(pred)
        else:
            ax_ecosystem.plot(pred.x, pred.y, 'mo')  # magenta = predator2

    # Draw food
    for f in foods:
        ax_ecosystem.plot(f.x, f.y, 'yo')  # yellow = food

    # --- TRAIT VISUALIZATION ---
    if preys:
        avg_prey_speed = sum([p.speed for p in preys])/len(preys)
    else:
        avg_prey_speed = 0
    if predators1:
        avg_pred1_speed = sum([p.speed for p in predators1])/len(predators1)
    else:
        avg_pred1_speed = 0
    if predators2:
        avg_pred2_speed = sum([p.speed for p in predators2])/len(predators2)
    else:
        avg_pred2_speed = 0

    lines['prey_speed'].append(avg_prey_speed)
    lines['pred1_speed'].append(avg_pred1_speed)
    lines['pred2_speed'].append(avg_pred2_speed)

    ax_traits.plot(lines['prey_speed'], 'g-', label='Prey Speed')
    ax_traits.plot(lines['pred1_speed'], 'r-', label='Pred1 Speed')
    ax_traits.plot(lines['pred2_speed'], 'm-', label='Pred2 Speed')
    ax_traits.legend()
    ax_traits.set_xlim(0, max(500, frame_number))

ani = animation.FuncAnimation(fig, update, frames=500, interval=200)
plt.show()
