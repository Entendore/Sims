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

NUM_PREY = 50
NUM_PREDATORS = 20
NUM_FOOD = 100

MUTATION_RATE = 0.1

# ------------------------------
# ENTITY CLASSES
# ------------------------------
class Food:
    def __init__(self, x, y):
        self.x = x
        self.y = y

class Prey:
    def __init__(self, x, y, speed=1, vision=5, energy=20, lineage=None):
        self.x = x
        self.y = y
        self.speed = speed
        self.vision = vision
        self.energy = energy
        self.lineage = lineage if lineage else [id(self)]

    def move_towards(self, targets):
        if not targets:
            self.x += random.randint(-1, 1) * self.speed
            self.y += random.randint(-1, 1) * self.speed
        else:
            target = min(targets, key=lambda t: (self.x - t.x)**2 + (self.y - t.y)**2)
            dx = target.x - self.x
            dy = target.y - self.y
            dist = math.sqrt(dx**2 + dy**2)
            if dist != 0:
                self.x += int(round(self.speed * dx / dist))
                self.y += int(round(self.speed * dy / dist))
        self.x = max(0, min(GRID_WIDTH-1, self.x))
        self.y = max(0, min(GRID_HEIGHT-1, self.y))

    def reproduce(self):
        if self.energy > 30:
            self.energy //= 2
            child_speed = max(1, self.speed + random.choice([-1,0,1]) if random.random() < MUTATION_RATE else self.speed)
            child_vision = max(1, self.vision + random.choice([-1,0,1]) if random.random() < MUTATION_RATE else self.vision)
            return Prey(self.x, self.y, child_speed, child_vision, self.energy, self.lineage + [id(self)])
        return None

class Predator:
    def __init__(self, x, y, speed=1, vision=7, energy=40, lineage=None):
        self.x = x
        self.y = y
        self.speed = speed
        self.vision = vision
        self.energy = energy
        self.lineage = lineage if lineage else [id(self)]

    def move_towards(self, targets):
        if not targets:
            self.x += random.randint(-1, 1) * self.speed
            self.y += random.randint(-1, 1) * self.speed
        else:
            target = min(targets, key=lambda t: (self.x - t.x)**2 + (self.y - t.y)**2)
            dx = target.x - self.x
            dy = target.y - self.y
            dist = math.sqrt(dx**2 + dy**2)
            if dist != 0:
                self.x += int(round(self.speed * dx / dist))
                self.y += int(round(self.speed * dy / dist))
        self.x = max(0, min(GRID_WIDTH-1, self.x))
        self.y = max(0, min(GRID_HEIGHT-1, self.y))

    def reproduce(self):
        if self.energy > 60:
            self.energy //= 2
            child_speed = max(1, self.speed + random.choice([-1,0,1]) if random.random() < MUTATION_RATE else self.speed)
            child_vision = max(1, self.vision + random.choice([-1,0,1]) if random.random() < MUTATION_RATE else self.vision)
            return Predator(self.x, self.y, child_speed, child_vision, self.energy, self.lineage + [id(self)])
        return None

# ------------------------------
# UTILITY FUNCTIONS
# ------------------------------
def distance(a, b):
    return abs(a.x - b.x) + abs(a.y - b.y)

def spawn_food(num):
    return [Food(random.randint(0, GRID_WIDTH-1), random.randint(0, GRID_HEIGHT-1)) for _ in range(num)]

def get_lineage_color(lineage_id):
    random.seed(lineage_id)
    return (random.random(), random.random(), random.random())

def average_trait(entities, trait):
    if not entities:
        return 0
    return sum(getattr(e, trait) for e in entities) / len(entities)

def highlight_lineage_colors(entities):
    # Count living members per lineage
    lineage_counts = Counter([e.lineage[0] for e in entities])
    max_count = max(lineage_counts.values()) if lineage_counts else 1
    colors = []
    for e in entities:
        base_color = get_lineage_color(e.lineage[0])
        # Brighter if lineage is more populous
        factor = lineage_counts[e.lineage[0]] / max_count
        bright_color = tuple(min(1, c * factor + 0.3) for c in base_color)
        colors.append(bright_color)
    return colors

# ------------------------------
# SIMULATION INITIALIZATION
# ------------------------------
prey_list = [Prey(random.randint(0, GRID_WIDTH-1), random.randint(0, GRID_HEIGHT-1)) for _ in range(NUM_PREY)]
predator_list = [Predator(random.randint(0, GRID_WIDTH-1), random.randint(0, GRID_HEIGHT-1)) for _ in range(NUM_PREDATORS)]
food_list = spawn_food(NUM_FOOD)

fig, (ax_grid, ax_traits) = plt.subplots(2, 1, figsize=(10,12))
frame_count = 0

# Track trait evolution
prey_speed_history = []
prey_vision_history = []
predator_speed_history = []
predator_vision_history = []

# ------------------------------
# ANIMATION UPDATE FUNCTION
# ------------------------------
def update(frame):
    global prey_list, predator_list, food_list, frame_count
    frame_count += 1
    ax_grid.clear()
    ax_grid.set_xlim(0, GRID_WIDTH)
    ax_grid.set_ylim(0, GRID_HEIGHT)
    ax_grid.set_title(f"Predator-Prey Simulation (Step {frame})")

    # Update Prey
    new_prey = []
    for prey in prey_list:
        visible_food = [f for f in food_list if distance(prey, f) <= prey.vision]
        prey.move_towards(visible_food)
        prey.energy -= 1

        eaten_food = [f for f in food_list if f.x == prey.x and f.y == prey.y]
        for f in eaten_food:
            prey.energy += 10
            food_list.remove(f)

        child = prey.reproduce()
        if child:
            new_prey.append(child)

    prey_list.extend(new_prey)
    prey_list = [p for p in prey_list if p.energy > 0]

    # Update Predators
    new_predators = []
    for predator in predator_list:
        visible_prey = [p for p in prey_list if distance(predator, p) <= predator.vision]
        predator.move_towards(visible_prey)
        predator.energy -= 1

        eaten_prey = [p for p in prey_list if p.x == predator.x and p.y == predator.y]
        for p in eaten_prey:
            predator.energy += p.energy
            prey_list.remove(p)

        child = predator.reproduce()
        if child:
            new_predators.append(child)

    predator_list.extend(new_predators)
    predator_list = [pred for pred in predator_list if pred.energy > 0]

    # Occasionally spawn food
    if random.random() < 0.1:
        food_list.append(Food(random.randint(0, GRID_WIDTH-1), random.randint(0, GRID_HEIGHT-1)))

    # Draw Food
    ax_grid.scatter([f.x for f in food_list], [f.y for f in food_list], c='yellow', marker='s', label='Food')

    # Draw Prey with lineage highlighting
    prey_colors = highlight_lineage_colors(prey_list)
    ax_grid.scatter([p.x for p in prey_list], [p.y for p in prey_list], c=prey_colors, marker='o', label='Prey')

    # Draw Predators with lineage highlighting
    predator_colors = highlight_lineage_colors(predator_list)
    ax_grid.scatter([pr.x for pr in predator_list], [pr.y for pr in predator_list], c=predator_colors, marker='^', label='Predator')

    ax_grid.legend(loc='upper right')

    # ------------------------------
    # Update Trait Evolution
    # ------------------------------
    prey_speed_history.append(average_trait(prey_list, 'speed'))
    prey_vision_history.append(average_trait(prey_list, 'vision'))
    predator_speed_history.append(average_trait(predator_list, 'speed'))
    predator_vision_history.append(average_trait(predator_list, 'vision'))

    ax_traits.clear()
    ax_traits.plot(prey_speed_history, label='Prey Speed', color='green')
    ax_traits.plot(prey_vision_history, label='Prey Vision', color='lime')
    ax_traits.plot(predator_speed_history, label='Predator Speed', color='red')
    ax_traits.plot(predator_vision_history, label='Predator Vision', color='orange')
    ax_traits.set_title("Average Trait Evolution")
    ax_traits.set_xlabel("Step")
    ax_traits.set_ylabel("Trait Value")
    ax_traits.legend()

ani = animation.FuncAnimation(fig, update, frames=500, interval=100)
plt.tight_layout()
plt.show()
