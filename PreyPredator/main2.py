import matplotlib.pyplot as plt
import matplotlib.animation as animation
import random
import math
from collections import Counter

# ------------------------------
# CONFIGURATION
# ------------------------------
GRID_WIDTH = 80
GRID_HEIGHT = 60

NUM_PREY = 30
NUM_PREDATORS = 15
NUM_FOOD = 80

MUTATION_RATE = 0.1
MCTS_SIMULATIONS = 3
MCTS_DEPTH = 2

PREY_ACTIONS = ["UP", "DOWN", "LEFT", "RIGHT", "STAY"]
PREDATOR_ACTIONS = ["UP", "DOWN", "LEFT", "RIGHT", "STAY", "HUNT"]

# ------------------------------
# ENTITY CLASSES
# ------------------------------
class Food:
    def __init__(self, x, y):
        self.x = x
        self.y = y

class Prey:
    def __init__(self, x, y, speed=1, vision=5, agility=0.5, metabolism=1, energy=20, lineage=None):
        self.x = x
        self.y = y
        self.speed = speed
        self.vision = vision
        self.agility = agility
        self.metabolism = metabolism
        self.energy = energy
        self.lineage = lineage if lineage else [id(self)]

    def get_state(self, food_list, predator_list):
        nearest_food = min(food_list, key=lambda f: abs(f.x-self.x)+abs(f.y-self.y), default=None)
        nearest_pred = min(predator_list, key=lambda p: abs(p.x-self.x)+abs(p.y-self.y), default=None)
        return (self.x, self.y,
                nearest_food.x if nearest_food else -1,
                nearest_food.y if nearest_food else -1,
                nearest_pred.x if nearest_pred else -1,
                nearest_pred.y if nearest_pred else -1,
                self.energy)

    def select_action(self, food_list, predator_list):
        best_action = "STAY"
        best_reward = -float('inf')
        for action in PREY_ACTIONS:
            total_reward = 0
            for _ in range(MCTS_SIMULATIONS):
                total_reward += self.simulate_action(action, food_list, predator_list, depth=MCTS_DEPTH)
            if total_reward > best_reward:
                best_reward = total_reward
                best_action = action
        return best_action

    def simulate_action(self, action, food_list, predator_list, depth):
        new_x, new_y = self.x, self.y
        if action=="UP": new_y -= self.speed
        elif action=="DOWN": new_y += self.speed
        elif action=="LEFT": new_x -= self.speed
        elif action=="RIGHT": new_x += self.speed
        new_x = max(0, min(new_x, GRID_WIDTH-1))
        new_y = max(0, min(new_y, GRID_HEIGHT-1))

        reward = -self.metabolism
        for f in food_list:
            if f.x==new_x and f.y==new_y:
                reward += 10
        for p in predator_list:
            if abs(p.x-new_x)+abs(p.y-new_y) < 2:
                reward -= 5*(1-self.agility)

        if depth <= 1:
            return reward
        next_action = random.choice(PREY_ACTIONS)
        return reward + 0.9*self.simulate_action(next_action, food_list, predator_list, depth-1)

    def move(self, action):
        if action=="UP": self.y -= self.speed
        elif action=="DOWN": self.y += self.speed
        elif action=="LEFT": self.x -= self.speed
        elif action=="RIGHT": self.x += self.speed
        self.x = max(0, min(self.x, GRID_WIDTH-1))
        self.y = max(0, min(self.y, GRID_HEIGHT-1))

    def reproduce(self):
        if self.energy > 30:
            self.energy //= 2
            child_speed = max(1, self.speed + random.choice([-1,0,1]) if random.random() < MUTATION_RATE else self.speed)
            child_vision = max(1, self.vision + random.choice([-1,0,1]) if random.random() < MUTATION_RATE else self.vision)
            child_agility = min(1, max(0, self.agility + random.choice([-0.1,0,0.1]) if random.random()<MUTATION_RATE else self.agility))
            child_metabolism = max(0.1, self.metabolism + random.choice([-0.1,0,0.1]) if random.random()<MUTATION_RATE else self.metabolism)
            return Prey(self.x, self.y, child_speed, child_vision, child_agility, child_metabolism, self.energy, self.lineage+[id(self)])
        return None

class Predator:
    def __init__(self, x, y, speed=1, vision=7, aggressiveness=1.0, stamina=1, energy=40, lineage=None):
        self.x = x
        self.y = y
        self.speed = speed
        self.vision = vision
        self.aggressiveness = aggressiveness
        self.stamina = stamina
        self.energy = energy
        self.lineage = lineage if lineage else [id(self)]

    def select_action(self, prey_list):
        best_action = "STAY"
        best_reward = -float('inf')
        for action in PREDATOR_ACTIONS:
            total_reward = 0
            for _ in range(MCTS_SIMULATIONS):
                total_reward += self.simulate_action(action, prey_list, depth=MCTS_DEPTH)
            if total_reward > best_reward:
                best_reward = total_reward
                best_action = action
        return best_action

    def simulate_action(self, action, prey_list, depth):
        new_x, new_y = self.x, self.y
        if action=="UP": new_y -= self.speed
        elif action=="DOWN": new_y += self.speed
        elif action=="LEFT": new_x -= self.speed
        elif action=="RIGHT": new_x += self.speed
        new_x = max(0, min(new_x, GRID_WIDTH-1))
        new_y = max(0, min(new_y, GRID_HEIGHT-1))

        reward = -self.stamina
        for p in prey_list:
            if abs(p.x-new_x)+abs(p.y-new_y) < 2:
                reward += 10*self.aggressiveness

        if depth <= 1:
            return reward
        next_action = random.choice(PREDATOR_ACTIONS)
        return reward + 0.9*self.simulate_action(next_action, prey_list, depth-1)

    def move(self, action):
        if action=="UP": self.y -= self.speed
        elif action=="DOWN": self.y += self.speed
        elif action=="LEFT": self.x -= self.speed
        elif action=="RIGHT": self.x += self.speed
        self.x = max(0, min(self.x, GRID_WIDTH-1))
        self.y = max(0, min(self.y, GRID_HEIGHT-1))

    def reproduce(self):
        if self.energy > 60:
            self.energy //= 2
            child_speed = max(1, self.speed + random.choice([-1,0,1]) if random.random() < MUTATION_RATE else self.speed)
            child_vision = max(1, self.vision + random.choice([-1,0,1]) if random.random() < MUTATION_RATE else self.vision)
            child_aggressiveness = max(0, min(2, self.aggressiveness + random.choice([-0.1,0,0.1]) if random.random()<MUTATION_RATE else self.aggressiveness))
            child_stamina = max(0.1, self.stamina + random.choice([-0.1,0,0.1]) if random.random()<MUTATION_RATE else self.stamina)
            return Predator(self.x, self.y, child_speed, child_vision, child_aggressiveness, child_stamina, self.energy, self.lineage+[id(self)])
        return None

# ------------------------------
# UTILITY FUNCTIONS
# ------------------------------
def spawn_food(num):
    return [Food(random.randint(0, GRID_WIDTH-1), random.randint(0, GRID_HEIGHT-1)) for _ in range(num)]

def distance(a, b):
    return abs(a.x - b.x) + abs(a.y - b.y)

def get_lineage_color(lineage_id):
    random.seed(lineage_id)
    return (random.random(), random.random(), random.random())

def highlight_lineage_colors(entities):
    lineage_counts = Counter([e.lineage[0] for e in entities])
    max_count = max(lineage_counts.values()) if lineage_counts else 1
    colors = []
    for e in entities:
        base_color = get_lineage_color(e.lineage[0])
        factor = lineage_counts[e.lineage[0]] / max_count
        bright_color = tuple(min(1, c*factor+0.3) for c in base_color)
        colors.append(bright_color)
    return colors

def average_trait(entities, trait):
    if not entities:
        return 0
    return sum(getattr(e, trait) for e in entities)/len(entities)

# ------------------------------
# SIMULATION INITIALIZATION
# ------------------------------
prey_list = [Prey(random.randint(0, GRID_WIDTH-1), random.randint(0, GRID_HEIGHT-1)) for _ in range(NUM_PREY)]
predator_list = [Predator(random.randint(0, GRID_WIDTH-1), random.randint(0, GRID_HEIGHT-1)) for _ in range(NUM_PREDATORS)]
food_list = spawn_food(NUM_FOOD)

fig, (ax_grid, ax_traits) = plt.subplots(2, 1, figsize=(10,12))

prey_speed_history, prey_vision_history, predator_speed_history, predator_vision_history = [], [], [], []

# ------------------------------
# ANIMATION UPDATE
# ------------------------------
def update(frame):
    global prey_list, predator_list, food_list
    ax_grid.clear()
    ax_grid.set_xlim(0, GRID_WIDTH)
    ax_grid.set_ylim(0, GRID_HEIGHT)
    ax_grid.set_title(f"Predator-Prey Simulation Step {frame}")

    # ---- Update Prey ----
    new_prey = []
    for prey in prey_list:
        action = prey.select_action(food_list, predator_list)
        prey.move(action)
        prey.energy -= prey.metabolism

        eaten_food = [f for f in food_list if f.x==prey.x and f.y==prey.y]
        for f in eaten_food:
            prey.energy += 10
            food_list.remove(f)

        child = prey.reproduce()
        if child:
            new_prey.append(child)
    prey_list.extend(new_prey)
    prey_list = [p for p in prey_list if p.energy>0]

    # ---- Update Predators ----
    new_predators = []
    for pred in predator_list:
        action = pred.select_action(prey_list)
        pred.move(action)
        pred.energy -= pred.stamina

        eaten_prey = [p for p in prey_list if p.x==pred.x and p.y==pred.y]
        for p in eaten_prey:
            pred.energy += p.energy * pred.aggressiveness
            prey_list.remove(p)

        child = pred.reproduce()
        if child:
            new_predators.append(child)
    predator_list.extend(new_predators)
    predator_list = [pr for pr in predator_list if pr.energy>0]

    # ---- Spawn Food ----
    if random.random()<0.1:
        food_list.append(Food(random.randint(0, GRID_WIDTH-1), random.randint(0, GRID_HEIGHT-1)))

    # ---- Draw Food ----
    ax_grid.scatter([f.x for f in food_list], [f.y for f in food_list], c='yellow', marker='s', label='Food')
    # ---- Draw Prey ----
    prey_colors = highlight_lineage_colors(prey_list)
    ax_grid.scatter([p.x for p in prey_list], [p.y for p in prey_list], c=prey_colors, marker='o', label='Prey')
    # ---- Draw Predators ----
    pred_colors = highlight_lineage_colors(predator_list)
    ax_grid.scatter([pr.x for pr in predator_list], [pr.y for pr in predator_list], c=pred_colors, marker='^', label='Predator')
    ax_grid.legend(loc='upper right')

    # ---- Update Trait Evolution ----
    prey_speed_history.append(average_trait(prey_list,'speed'))
    prey_vision_history.append(average_trait(prey_list,'vision'))
    predator_speed_history.append(average_trait(predator_list,'speed'))
    predator_vision_history.append(average_trait(predator_list,'vision'))

    ax_traits.clear()
    ax_traits.plot(prey_speed_history,label='Prey Speed',color='green')
    ax_traits.plot(prey_vision_history,label='Prey Vision',color='lime')
    ax_traits.plot(predator_speed_history,label='Predator Speed',color='red')
    ax_traits.plot(predator_vision_history,label='Predator Vision',color='orange')
    ax_traits.set_title("Average Trait Evolution")
    ax_traits.set_xlabel("Step")
    ax_traits.set_ylabel("Trait Value")
    ax_traits.legend()

ani = animation.FuncAnimation(fig, update, frames=500, interval=100)
plt.tight_layout()
plt.show()
