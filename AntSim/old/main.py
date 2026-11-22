import pygame
import random
import math
import numpy as np
from collections import deque, defaultdict
import copy

# Initialize Pygame
pygame.init()

# Constants
WIDTH, HEIGHT = 800, 600
ANT_COUNT = 60
FEEDING_SPOT_COUNT = 6
OBSTACLE_COUNT = 10
PREDATOR_COUNT = 2

ANT_SIZE = 5
FEEDING_SPOT_SIZE = 20
NEST_SIZE = 35
ANT_SPEED = 2
FOOD_DETECTION_RANGE = 80
FOOD_COLLECTION_RATE = 0.5
MAX_FOOD_CAPACITY = 12
PHEROMONE_EVAPORATION_RATE = 0.99

# Ant Types
SCOUT = 0
WORKER = 1
SOLDIER = 2

# Pheromone types
FOOD_PHEROMONE = 0
DANGER_PHEROMONE = 1

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
BROWN = (139, 69, 19)
GREEN = (34, 139, 34)
RED = (255, 0, 0)
YELLOW = (255, 255, 0)
BLUE = (0, 0, 255)
GRAY = (128, 128, 128)
PURPLE = (128, 0, 128)
ORANGE = (255, 165, 0)
PINK = (255, 192, 203)
DARK_RED = (139, 0, 0)

# Set up display
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Advanced Ant Colony Simulation with MDP & MCTS")
clock = pygame.time.Clock()

class Obstacle:
    def __init__(self):
        self.width = random.randint(40, 120)
        self.height = random.randint(40, 120)
        self.x = random.randint(self.width//2, WIDTH - self.width//2)
        self.y = random.randint(self.height//2, HEIGHT - self.height//2)
        self.color = GRAY
        self.points = [
            (self.x - self.width//2, self.y - self.height//2),
            (self.x + self.width//2, self.y - self.height//2),
            (self.x + self.width//2, self.y + self.height//2),
            (self.x - self.width//2, self.y + self.height//2)
        ]
    
    def collides_with(self, x, y, buffer=5):
        return (self.x - self.width//2 - buffer <= x <= self.x + self.width//2 + buffer and 
                self.y - self.height//2 - buffer <= y <= self.y + self.height//2 + buffer)
    
    def get_distance_to_point(self, x, y):
        dx = max(self.x - self.width/2 - x, 0, x - (self.x + self.width/2))
        dy = max(self.y - self.height/2 - y, 0, y - (self.y + self.height/2))
        return math.sqrt(dx*dx + dy*dy)
    
    def draw(self, screen):
        pygame.draw.polygon(screen, self.color, self.points)
        pygame.draw.polygon(screen, BLACK, self.points, 2)

class Predator:
    def __init__(self):
        self.x = random.randint(50, WIDTH - 50)
        self.y = random.randint(50, HEIGHT - 50)
        self.size = 15
        self.speed = 1.2
        self.angle = random.uniform(0, 2 * math.pi)
        self.color = DARK_RED
        self.detection_range = 100
        self.cooldown = 0
        self.attack_power = 3
        
    def update(self, ants, pheromone_map):
        if self.cooldown > 0:
            self.cooldown -= 1
            
        if random.random() < 0.02:
            self.angle += random.uniform(-math.pi/4, math.pi/4)
        
        closest_ant = None
        min_distance = self.detection_range
        
        for ant in ants:
            distance = math.sqrt((self.x - ant.x)**2 + (self.y - ant.y)**2)
            if distance < min_distance and not ant.has_food:
                min_distance = distance
                closest_ant = ant
        
        if closest_ant:
            dx = closest_ant.x - self.x
            dy = closest_ant.y - self.y
            self.angle = math.atan2(dy, dx)
        else:
            self.angle += random.uniform(-0.1, 0.1)
        
        self.x += math.cos(self.angle) * self.speed
        self.y += math.sin(self.angle) * self.speed
        
        if self.x < self.size:
            self.x = self.size
            self.angle = math.pi - self.angle
        elif self.x > WIDTH - self.size:
            self.x = WIDTH - self.size
            self.angle = math.pi - self.angle
            
        if self.y < self.size:
            self.y = self.size
            self.angle = -self.angle
        elif self.y > HEIGHT - self.size:
            self.y = HEIGHT - self.size
            self.angle = -self.angle
        
        if self.cooldown <= 0:
            ants_to_remove = []
            for ant in ants:
                distance = math.sqrt((self.x - ant.x)**2 + (self.y - ant.y)**2)
                if distance < self.size + ANT_SIZE + 5:
                    if ant.ant_type == SOLDIER and random.random() < 0.5:
                        self.release_danger_pheromone(pheromone_map, ant.x, ant.y)
                    else:
                        ants_to_remove.append(ant)
                        
                    if len(ants_to_remove) >= self.attack_power:
                        break
            
            for ant in ants_to_remove:
                if ant in ants:
                    ants.remove(ant)
            
            if len(ants_to_remove) > 0:
                self.cooldown = 60
                self.release_danger_pheromone(pheromone_map, self.x, self.y)
    
    def release_danger_pheromone(self, pheromone_map, x, y):
        for i in range(-10, 11):
            for j in range(-10, 11):
                px, py = int(x) + i, int(y) + j
                if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                    distance = math.sqrt(i*i + j*j)
                    if distance < 10:
                        strength = 2.0 * (1 - distance/10)
                        pheromone_map[py, px] += strength
    
    def draw(self, screen):
        pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), self.size)
        eye_offset = self.size * 0.4
        left_eye_x = self.x + math.cos(self.angle - 0.5) * eye_offset
        left_eye_y = self.y + math.sin(self.angle - 0.5) * eye_offset
        right_eye_x = self.x + math.cos(self.angle + 0.5) * eye_offset
        right_eye_y = self.y + math.sin(self.angle + 0.5) * eye_offset
        
        pygame.draw.circle(screen, WHITE, (int(left_eye_x), int(left_eye_y)), 3)
        pygame.draw.circle(screen, WHITE, (int(right_eye_x), int(right_eye_y)), 3)
        pygame.draw.circle(screen, BLACK, (int(left_eye_x), int(left_eye_y)), 1)
        pygame.draw.circle(screen, BLACK, (int(right_eye_x), int(right_eye_y)), 1)
        
        mouth_x = self.x + math.cos(self.angle) * (self.size * 0.7)
        mouth_y = self.y + math.sin(self.angle) * (self.size * 0.7)
        pygame.draw.circle(screen, BLACK, (int(mouth_x), int(mouth_y)), 4)

class MDPDecisionMaker:
    """Markov Decision Process for ant decision making"""
    
    def __init__(self, ant_type):
        self.ant_type = ant_type
        self.state = "exploring"
        self.q_values = defaultdict(lambda: defaultdict(float))
        self.learning_rate = 0.1
        self.discount_factor = 0.9
        self.exploration_rate = 0.2
        
        # Type-specific parameters
        if ant_type == SCOUT:
            self.exploration_rate = 0.4  # Scouts explore more
        elif ant_type == WORKER:
            self.exploration_rate = 0.1  # Workers exploit more
        else:  # SOLDIER
            self.exploration_rate = 0.15  # Soldiers balance exploration/exploitation
    
    def get_state_key(self, ant, feeding_spots, nest_x, nest_y, pheromone_map, obstacles, predators):
        """Create a state representation for the MDP"""
        # Simplified state representation
        has_food = ant.has_food
        is_fleeing = ant.state == "fleeing"
        
        # Check for nearby food
        food_nearby = False
        for spot in feeding_spots:
            if spot.food_amount > 0:
                distance = math.sqrt((ant.x - spot.x)**2 + (ant.y - spot.y)**2)
                if distance < ant.detection_range:
                    food_nearby = True
                    break
        
        # Check for nearby danger
        danger_level = 0
        for predator in predators:
            distance = math.sqrt((ant.x - predator.x)**2 + (ant.y - predator.y)**2)
            if distance < 80:
                danger_level = min(2, int(distance / 40) + 1)  # 0, 1, or 2
        
        # Check for strong pheromones
        pheromone_strong = False
        radius = 15
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                x_pos = int(ant.x + dx)
                y_pos = int(ant.y + dy)
                if 0 <= x_pos < WIDTH and 0 <= y_pos < HEIGHT:
                    if pheromone_map[y_pos, x_pos] > 1.5:
                        pheromone_strong = True
                        break
            if pheromone_strong:
                break
        
        # Check if close to nest
        near_nest = math.sqrt((ant.x - nest_x)**2 + (ant.y - nest_y)**2) < 100
        
        return (has_food, is_fleeing, food_nearby, danger_level, pheromone_strong, near_nest)
    
    def get_actions(self, ant):
        """Get possible actions for current state"""
        if ant.state == "fleeing":
            return ["flee", "hide", "confront"]
        
        if ant.has_food:
            return ["return_to_nest", "follow_pheromone", "explore"]
        
        return ["search_food", "follow_pheromone", "explore", "patrol"]
    
    def get_reward(self, ant, action, next_state_info):
        """Calculate reward for taking an action"""
        reward = 0
        
        # Base rewards for different actions
        if action == "return_to_nest" and ant.has_food:
            reward += 5  # Good for colony
        elif action == "search_food" and next_state_info["found_food"]:
            reward += 10  # Found food!
        elif action == "follow_pheromone" and next_state_info["found_food_trail"]:
            reward += 3  # Following good trail
        elif action == "flee" and next_state_info["avoided_danger"]:
            reward += 8  # Successfully avoided danger
        elif action == "confront" and ant.ant_type == SOLDIER and next_state_info["protected_colony"]:
            reward += 15  # Soldier protected colony
        elif action == "explore" and next_state_info["found_new_area"]:
            reward += 4  # Discovered new area
        
        # Penalties
        if action == "search_food" and next_state_info["in_danger"]:
            reward -= 10  # Got into danger while searching
        elif action == "follow_pheromone" and next_state_info["followed_danger"]:
            reward -= 8  # Followed danger pheromone
        elif action == "confront" and ant.ant_type != SOLDIER and next_state_info["injured"]:
            reward -= 15  # Non-soldier got injured confronting danger
        
        return reward
    
    def choose_action(self, state, actions):
        """Choose action using epsilon-greedy policy"""
        if random.random() < self.exploration_rate:
            return random.choice(actions)
        
        # Choose best action based on Q-values
        best_action = actions[0]
        best_value = self.q_values[state][best_action]
        
        for action in actions[1:]:
            if self.q_values[state][action] > best_value:
                best_value = self.q_values[state][action]
                best_action = action
        
        return best_action
    
    def update_q_value(self, state, action, reward, next_state, next_actions):
        """Update Q-value using Q-learning"""
        # Get max Q-value for next state
        max_next_q = 0
        if next_actions:
            max_next_q = max(self.q_values[next_state][next_action] for next_action in next_actions)
        
        # Q-learning update
        current_q = self.q_values[state][action]
        new_q = current_q + self.learning_rate * (reward + self.discount_factor * max_next_q - current_q)
        self.q_values[state][action] = new_q

class MCTSAgent:
    """Monte Carlo Tree Search for path planning"""
    
    def __init__(self, ant, max_simulations=50):
        self.ant = ant
        self.max_simulations = max_simulations
        self.root = None
        
    class Node:
        def __init__(self, position, parent=None, action=None):
            self.position = position  # (x, y)
            self.parent = parent
            self.action = action  # angle of movement
            self.children = []
            self.visits = 0
            self.value = 0
            self.is_terminal = False
    
    def get_possible_actions(self, obstacles):
        """Get possible movement directions (angles)"""
        # Sample 8 directions around the ant
        angles = []
        for i in range(8):
            angle = i * (2 * math.pi / 8)
            angles.append(angle)
        return angles
    
    def simulate_path(self, start_pos, angle, obstacles, steps=10):
        """Simulate moving in a direction for a number of steps"""
        x, y = start_pos
        speed = self.ant.speed
        
        for _ in range(steps):
            new_x = x + math.cos(angle) * speed
            new_y = y + math.sin(angle) * speed
            
            # Check collision with obstacles
            collision = False
            for obstacle in obstacles:
                if obstacle.collides_with(new_x, new_y, 0):
                    collision = True
                    break
            
            if collision:
                break
                
            # Boundary checking
            if new_x < 0 or new_x > WIDTH or new_y < 0 or new_y > HEIGHT:
                break
                
            x, y = new_x, new_y
        
        return (x, y)
    
    def evaluate_position(self, position, target_info, pheromone_map):
        """Evaluate how good a position is"""
        x, y = position
        score = 0
        
        # If we have a specific target (like food or nest)
        if target_info["type"] == "food" and target_info["position"]:
            target_x, target_y = target_info["position"]
            distance = math.sqrt((x - target_x)**2 + (y - target_y)**2)
            score += 100 / (1 + distance)  # Higher score for closer to food
        
        elif target_info["type"] == "nest":
            target_x, target_y = target_info["position"]
            distance = math.sqrt((x - target_x)**2 + (y - target_y)**2)
            score += 100 / (1 + distance)  # Higher score for closer to nest
        
        # Check for pheromones
        if 0 <= int(x) < WIDTH and 0 <= int(y) < HEIGHT:
            pheromone_value = pheromone_map[int(y), int(x)]
            score += pheromone_value * 10  # Follow pheromone trails
        
        # Penalize for being close to obstacles
        min_obstacle_dist = float('inf')
        for obstacle in target_info["obstacles"]:
            dist = obstacle.get_distance_to_point(x, y)
            min_obstacle_dist = min(min_obstacle_dist, dist)
        
        if min_obstacle_dist < 30:
            score -= (30 - min_obstacle_dist) * 2  # Penalize being close to obstacles
        
        return score
    
    def select_best_path(self, target_info, obstacles, pheromone_map):
        """Use MCTS to find the best direction to move"""
        if not target_info or not target_info.get("position"):
            return None  # No target, let regular behavior handle it
        
        start_pos = (self.ant.x, self.ant.y)
        self.root = self.Node(start_pos)
        
        # Run simulations
        for _ in range(self.max_simulations):
            node = self._select_node(self.root, obstacles)
            if not node.is_terminal:
                self._expand_node(node, obstacles)
                result = self._simulate(node, target_info, obstacles, pheromone_map)
                self._backpropagate(node, result)
        
        # Choose best action
        if self.root.children:
            best_child = max(self.root.children, key=lambda c: c.value / max(1, c.visits))
            return best_child.action
        
        return None
    
    def _select_node(self, node, obstacles):
        """Select a node to expand using UCB1"""
        current = node
        
        while current.children and not current.is_terminal:
            # Use UCB1 to select child
            total_visits = sum(child.visits for child in current.children)
            if total_visits == 0:
                total_visits = 1
            
            best_child = None
            best_ucb = float('-inf')
            
            for child in current.children:
                if child.visits == 0:
                    ucb = float('inf')  # Prefer unexplored nodes
                else:
                    exploitation = child.value / child.visits
                    exploration = math.sqrt(2 * math.log(total_visits) / child.visits)
                    ucb = exploitation + exploration
                
                if ucb > best_ucb:
                    best_ucb = ucb
                    best_child = child
            
            if best_child:
                current = best_child
            else:
                break
        
        return current
    
    def _expand_node(self, node, obstacles):
        """Expand a node by adding children"""
        actions = self.get_possible_actions(obstacles)
        
        for action in actions:
            new_pos = self.simulate_path(node.position, action, obstacles, steps=3)
            child = self.Node(new_pos, parent=node, action=action)
            
            # Check if terminal (collision or boundary)
            x, y = new_pos
            if x < 0 or x > WIDTH or y < 0 or y > HEIGHT:
                child.is_terminal = True
            
            for obstacle in obstacles:
                if obstacle.collides_with(x, y, 0):
                    child.is_terminal = True
                    break
            
            node.children.append(child)
    
    def _simulate(self, node, target_info, obstacles, pheromone_map):
        """Simulate from node to estimate value"""
        # Use the evaluation function as a simple simulation
        return self.evaluate_position(node.position, target_info, pheromone_map)
    
    def _backpropagate(self, node, result):
        """Backpropagate result through tree"""
        current = node
        while current:
            current.visits += 1
            current.value += result
            current = current.parent

class Ant:
    def __init__(self, nest_x, nest_y, ant_type=WORKER):
        self.x = nest_x + random.randint(-NEST_SIZE, NEST_SIZE)
        self.y = nest_y + random.randint(-NEST_SIZE, NEST_SIZE)
        self.angle = random.uniform(0, 2 * math.pi)
        self.has_food = False
        self.food_carrying = 0
        self.target = None
        self.returning = False
        self.path_memory = deque(maxlen=25)
        self.ant_type = ant_type
        self.type_name = ["Scout", "Worker", "Soldier"][ant_type]
        self.state = "exploring"
        self.flee_timer = 0
        
        # Type-specific properties
        if ant_type == SCOUT:
            self.wander_strength = 0.5
            self.detection_range = FOOD_DETECTION_RANGE * 1.5
            self.speed = ANT_SPEED * 1.2
            self.color = PURPLE
            self.size = ANT_SIZE
            self.bravery = 0.3
        elif ant_type == WORKER:
            self.wander_strength = 0.3
            self.detection_range = FOOD_DETECTION_RANGE
            self.speed = ANT_SPEED
            self.color = BLACK
            self.size = ANT_SIZE
            self.bravery = 0.6
        else:  # SOLDIER
            self.wander_strength = 0.2
            self.detection_range = FOOD_DETECTION_RANGE * 0.8
            self.speed = ANT_SPEED * 0.8
            self.color = RED
            self.size = ANT_SIZE + 2
            self.bravery = 0.9
            
        self.avoidance_strength = 1.5
        self.pheromone_sensitivity = 0.8 if ant_type == WORKER else 0.5
        
        # Add MDP decision maker
        self.mdp = MDPDecisionMaker(ant_type)
        
        # Add MCTS for path planning (workers use it most, scouts less, soldiers least)
        mcts_simulations = 100 if ant_type == WORKER else (50 if ant_type == SCOUT else 30)
        self.mcts = MCTSAgent(self, max_simulations=mcts_simulations)
        
        # Decision making cooldown (to reduce computation)
        self.decision_cooldown = 0
        self.current_action = "explore"
        
    def sense_pheromones(self, pheromone_map):
        """Detect pheromones in the surrounding area"""
        if self.flee_timer > 0:
            return None, 0
            
        max_pheromone = 0
        best_direction = None
        
        radius = 15
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                x_pos = int(self.x + dx)
                y_pos = int(self.y + dy)
                
                if not (0 <= x_pos < WIDTH and 0 <= y_pos < HEIGHT):
                    continue
                
                pheromone_value = pheromone_map[y_pos, x_pos]
                
                if pheromone_value > 0.5 and pheromone_value > max_pheromone:
                    max_pheromone = pheromone_value
                    best_direction = math.atan2(dy, dx)
        
        return best_direction, max_pheromone
    
    def sense_danger_pheromones(self, pheromone_map):
        """Detect danger pheromones in the surrounding area"""
        max_danger = 0
        danger_direction = None
        
        radius = 30
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                x_pos = int(self.x + dx)
                y_pos = int(self.y + dy)
                
                if not (0 <= x_pos < WIDTH and 0 <= y_pos < HEIGHT):
                    continue
                
                pheromone_value = pheromone_map[y_pos, x_pos]
                
                if pheromone_value > 1.0 and pheromone_value > max_danger:
                    max_danger = pheromone_value
                    danger_direction = math.atan2(-dy, -dx)
        
        return danger_direction, max_danger
    
    def avoid_obstacles(self, obstacles):
        """Calculate avoidance vector based on nearby obstacles"""
        avoid_angle = self.angle
        avoid_strength = 0
        
        closest_obstacle = None
        min_distance = float('inf')
        
        for obstacle in obstacles:
            distance = obstacle.get_distance_to_point(self.x, self.y)
            if distance < min_distance:
                min_distance = distance
                closest_obstacle = obstacle
        
        if closest_obstacle and min_distance < 30:
            dx = self.x - closest_obstacle.x
            dy = self.y - closest_obstacle.y
            
            if dx == 0 and dy == 0:
                dx = random.uniform(-1, 1)
                dy = random.uniform(-1, 1)
                
            avoid_angle = math.atan2(dy, dx)
            avoid_strength = (30 - min_distance) / 30
            
        return avoid_angle, avoid_strength
    
    def make_mdp_decision(self, feeding_spots, nest_x, nest_y, pheromone_map, obstacles, predators):
        """Use MDP to decide what action to take"""
        # Get current state
        state = self.mdp.get_state_key(self, feeding_spots, nest_x, nest_y, pheromone_map, obstacles, predators)
        
        # Get possible actions
        actions = self.mdp.get_actions(self)
        
        # Remember if we're near food or danger for reward calculation
        found_food = False
        in_danger = False
        found_food_trail = False
        avoided_danger = False
        protected_colony = False
        found_new_area = False
        followed_danger = False
        injured = False
        
        # Check conditions for reward calculation
        for spot in feeding_spots:
            if spot.food_amount > 0:
                distance = math.sqrt((self.x - spot.x)**2 + (self.y - spot.y)**2)
                if distance < 30:  # Very close to food
                    found_food = True
        
        for predator in predators:
            distance = math.sqrt((self.x - predator.x)**2 + (self.y - predator.y)**2)
            if distance < 50:
                in_danger = True
        
        # Check for pheromones
        radius = 15
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                x_pos = int(self.x + dx)
                y_pos = int(self.y + dy)
                if 0 <= x_pos < WIDTH and 0 <= y_pos < HEIGHT:
                    if pheromone_map[y_pos, x_pos] > 1.5:
                        found_food_trail = True
                        break
        
        # Choose action
        action = self.mdp.choose_action(state, actions)
        self.current_action = action
        
        # Simulate outcome for learning (in real implementation, this would happen after action)
        next_state_info = {
            "found_food": found_food,
            "in_danger": in_danger,
            "found_food_trail": found_food_trail,
            "avoided_danger": not in_danger and self.state == "fleeing",
            "protected_colony": self.ant_type == SOLDIER and in_danger,
            "found_new_area": random.random() < 0.1,  # Small chance
            "followed_danger": False,
            "injured": False
        }
        
        # Calculate reward
        reward = self.mdp.get_reward(self, action, next_state_info)
        
        # Get next state and actions for Q-learning update
        next_state = self.mdp.get_state_key(self, feeding_spots, nest_x, nest_y, pheromone_map, obstacles, predators)
        next_actions = self.mdp.get_actions(self)
        
        # Update Q-values
        self.mdp.update_q_value(state, action, reward, next_state, next_actions)
        
        return action
    
    def plan_path_with_mcts(self, target_info, obstacles, pheromone_map):
        """Use MCTS to plan a path to a target"""
        if not target_info:
            return None
            
        return self.mcts.select_best_path(target_info, obstacles, pheromone_map)
    
    def update(self, feeding_spots, nest_x, nest_y, pheromone_map, obstacles, predators):
        # Store current position in memory
        self.path_memory.append((int(self.x), int(self.y)))
        
        # Update flee timer
        if self.flee_timer > 0:
            self.flee_timer -= 1
            if self.flee_timer <= 0:
                self.state = "exploring"
        
        # Check for danger pheromones
        if self.state != "fleeing":
            danger_direction, danger_level = self.sense_danger_pheromones(pheromone_map)
            if danger_level > 2.0 and random.random() > self.bravery:
                self.state = "fleeing"
                self.flee_timer = 120
                self.angle = danger_direction if danger_direction else self.angle + math.pi
        
        # Make MDP decision every few frames to reduce computation
        if self.decision_cooldown <= 0:
            self.make_mdp_decision(feeding_spots, nest_x, nest_y, pheromone_map, obstacles, predators)
            self.decision_cooldown = 15  # Make decisions every 15 frames
        else:
            self.decision_cooldown -= 1
        
        # Execute action based on MDP decision
        if self.current_action == "flee":
            self.state = "fleeing"
            # Find direction away from nearest predator
            nearest_predator = None
            min_distance = float('inf')
            for predator in predators:
                distance = math.sqrt((self.x - predator.x)**2 + (self.y - predator.y)**2)
                if distance < min_distance:
                    min_distance = distance
                    nearest_predator = predator
            
            if nearest_predator:
                dx = self.x - nearest_predator.x
                dy = self.y - nearest_predator.y
                self.angle = math.atan2(dy, dx)
        
        elif self.current_action == "hide":
            self.state = "fleeing"
            # Try to move toward nearest obstacle for cover
            nearest_obstacle = None
            min_distance = float('inf')
            for obstacle in obstacles:
                distance = obstacle.get_distance_to_point(self.x, self.y)
                if distance < min_distance:
                    min_distance = distance
                    nearest_obstacle = obstacle
            
            if nearest_obstacle:
                dx = nearest_obstacle.x - self.x
                dy = nearest_obstacle.y - self.y
                self.angle = math.atan2(dy, dx)
        
        elif self.current_action == "confront" and self.ant_type == SOLDIER:
            # Soldiers may confront predators to protect colony
            nearest_predator = None
            min_distance = float('inf')
            for predator in predators:
                distance = math.sqrt((self.x - predator.x)**2 + (self.y - predator.y)**2)
                if distance < min_distance:
                    min_distance = distance
                    nearest_predator = predator
            
            if nearest_predator and min_distance < 100:
                # Move toward predator
                dx = nearest_predator.x - self.x
                dy = nearest_predator.y - self.y
                self.angle = math.atan2(dy, dx)
        
        # Check if ant is at nest (drop off food)
        distance_to_nest = math.sqrt((self.x - nest_x)**2 + (self.y - nest_y)**2)
        if self.has_food and distance_to_nest < NEST_SIZE:
            self.has_food = False
            self.food_carrying = 0
            self.returning = False
            self.angle = random.uniform(0, 2 * math.pi)
            self.state = "exploring"
        
        # Look for food if not carrying any and not fleeing
        if not self.has_food and not self.returning and self.state != "fleeing":
            closest_feeding_spot = None
            min_distance = self.detection_range
            
            for spot in feeding_spots:
                if spot.food_amount > 0:
                    distance = math.sqrt((self.x - spot.x)**2 + (self.y - spot.y)**2)
                    if distance < min_distance:
                        min_distance = distance
                        closest_feeding_spot = spot
            
            # If found a feeding spot within range, target it
            if closest_feeding_spot:
                self.target = closest_feeding_spot
                
                # Use MCTS to plan path to food
                if self.current_action in ["search_food", "follow_pheromone"]:
                    target_info = {
                        "type": "food", 
                        "position": (closest_feeding_spot.x, closest_feeding_spot.y),
                        "obstacles": obstacles
                    }
                    mcts_angle = self.plan_path_with_mcts(target_info, obstacles, pheromone_map)
                    if mcts_angle is not None:
                        self.angle = mcts_angle
                    else:
                        dx = self.target.x - self.x
                        dy = self.target.y - self.y
                        self.angle = math.atan2(dy, dx)
                else:
                    dx = self.target.x - self.x
                    dy = self.target.y - self.y
                    self.angle = math.atan2(dy, dx)
                
                self.state = "foraging"
            else:
                # Use MDP action to decide what to do
                if self.current_action == "follow_pheromone":
                    pheromone_direction, pheromone_strength = self.sense_pheromones(pheromone_map)
                    if pheromone_strength > 1.0:
                        self.angle = pheromone_direction
                        self.state = "following_pheromone"
                    else:
                        self.angle += random.uniform(-self.wander_strength, self.wander_strength)
                        self.state = "exploring"
                elif self.current_action == "patrol":
                    # Patrol around nest or known areas
                    if random.random() < 0.1:
                        self.angle = random.uniform(0, 2 * math.pi)
                    self.state = "patrolling"
                else:  # explore
                    self.angle += random.uniform(-self.wander_strength, self.wander_strength)
                    self.state = "exploring"
                
        # If returning to nest with food
        elif self.returning:
            # Use MCTS to plan path to nest
            if self.current_action == "return_to_nest":
                target_info = {
                    "type": "nest", 
                    "position": (nest_x, nest_y),
                    "obstacles": obstacles
                }
                mcts_angle = self.plan_path_with_mcts(target_info, obstacles, pheromone_map)
                if mcts_angle is not None:
                    self.angle = mcts_angle
                else:
                    dx = nest_x - self.x
                    dy = nest_y - self.y
                    self.angle = math.atan2(dy, dx)
            else:
                dx = nest_x - self.x
                dy = nest_y - self.y
                self.angle = math.atan2(dy, dx)
            
            self.state = "returning"
            
            # Drop pheromone to mark path
            if self.ant_type == WORKER:
                pheromone_strength = 0.8
            elif self.ant_type == SCOUT:
                pheromone_strength = 0.5
            else:  # Soldier
                pheromone_strength = 0.3
                
            for point in self.path_memory:
                if 0 <= point[0] < WIDTH and 0 <= point[1] < HEIGHT:
                    pheromone_map[point[1], point[0]] += pheromone_strength
        
        # Check if at feeding spot
        if self.target and not self.has_food:
            distance = math.sqrt((self.x - self.target.x)**2 + (self.y - self.target.y)**2)
            if distance < FEEDING_SPOT_SIZE:
                # Collect food
                if self.ant_type == WORKER:
                    collection_efficiency = 1.0
                elif self.ant_type == SCOUT:
                    collection_efficiency = 0.7
                else:  # Soldier
                    collection_efficiency = 0.5
                    
                collect_amount = min(FOOD_COLLECTION_RATE * collection_efficiency, self.target.food_amount)
                self.target.food_amount -= collect_amount
                self.food_carrying = collect_amount
                self.has_food = True
                self.returning = True
                self.target = None
                
                # Drop pheromone at food source
                if self.ant_type == WORKER:
                    source_pheromone = 1.5
                elif self.ant_type == SCOUT:
                    source_pheromone = 1.0
                else:  # Soldier
                    source_pheromone = 0.5
                    
                for i in range(-5, 6):
                    for j in range(-5, 6):
                        x, y = int(self.x) + i, int(self.y) + j
                        if 0 <= x < WIDTH and 0 <= y < HEIGHT:
                            pheromone_map[y, x] += source_pheromone
        
        # Avoid obstacles
        avoid_angle, avoid_strength = self.avoid_obstacles(obstacles)
        if avoid_strength > 0:
            self.angle = self.angle * (1 - avoid_strength) + avoid_angle * avoid_strength
        
        # Special behavior for soldiers near danger
        if self.ant_type == SOLDIER and self.state == "fleeing":
            if random.random() < 0.05:
                self.flee_timer = max(0, self.flee_timer - 30)
        
        # Move ant
        current_speed = self.speed
        if self.state == "fleeing":
            current_speed *= 1.5
            
        self.x += math.cos(self.angle) * current_speed
        self.y += math.sin(self.angle) * current_speed
        
        # Boundary checking
        if self.x < 0:
            self.x = 0
            self.angle = math.pi - self.angle
        elif self.x > WIDTH:
            self.x = WIDTH
            self.angle = math.pi - self.angle
            
        if self.y < 0:
            self.y = 0
            self.angle = -self.angle
        elif self.y > HEIGHT:
            self.y = HEIGHT
            self.angle = -self.angle
            
        # Make sure ant doesn't get stuck inside obstacles
        for obstacle in obstacles:
            if obstacle.collides_with(self.x, self.y, 0):
                dx = self.x - obstacle.x
                dy = self.y - obstacle.y
                distance = math.sqrt(dx*dx + dy*dy)
                if distance == 0:
                    distance = 0.1
                self.x = obstacle.x + (dx / distance) * (obstacle.width/2 + 5)
                self.y = obstacle.y + (dy / distance) * (obstacle.height/2 + 5)
    
    def draw(self, screen):
        # Draw ant body
        color = ORANGE if self.has_food else self.color
        pygame.draw.circle(screen, color, (int(self.x), int(self.y)), self.size)
        
        # Draw direction indicator
        end_x = self.x + math.cos(self.angle) * self.size * 2
        end_y = self.y + math.sin(self.angle) * self.size * 2
        pygame.draw.line(screen, color, (self.x, self.y), (end_x, end_y), 2)
        
        # Draw state indicator
        if self.state == "fleeing":
            pygame.draw.circle(screen, RED, (int(self.x), int(self.y)), self.size + 3, 2)
        elif self.state == "foraging":
            pygame.draw.circle(screen, GREEN, (int(self.x), int(self.y)), self.size + 3, 2)
        elif self.state == "returning":
            pygame.draw.circle(screen, YELLOW, (int(self.x), int(self.y)), self.size + 3, 2)
        
        # Draw type indicator
        if self.ant_type == SCOUT:
            pygame.draw.circle(screen, PURPLE, (int(self.x), int(self.y)), self.size + 1, 1)
        elif self.ant_type == SOLDIER:
            pygame.draw.circle(screen, RED, (int(self.x), int(self.y)), self.size + 2, 1)

class FeedingSpot:
    def __init__(self):
        self.x = random.randint(FEEDING_SPOT_SIZE, WIDTH - FEEDING_SPOT_SIZE)
        self.y = random.randint(FEEDING_SPOT_SIZE, HEIGHT - FEEDING_SPOT_SIZE)
        self.food_amount = MAX_FOOD_CAPACITY
        self.initial_food = MAX_FOOD_CAPACITY
        self.regeneration_rate = 0.01
        self.retry_count = 0
        
    def update(self):
        if self.food_amount < self.initial_food:
            self.food_amount = min(self.initial_food, self.food_amount + self.regeneration_rate)
        
    def is_valid_position(self, obstacles):
        for obstacle in obstacles:
            if obstacle.collides_with(self.x, self.y, FEEDING_SPOT_SIZE):
                return False
        return True
        
    def draw(self, screen):
        ratio = self.food_amount / self.initial_food
        if ratio > 0.5:
            r = int(255 * (1 - (ratio - 0.5) * 2))
            g = 255
            b = 0
        else:
            r = 255
            g = int(255 * ratio * 2)
            b = 0
        color = (r, g, b)
        
        pygame.draw.circle(screen, color, (int(self.x), int(self.y)), FEEDING_SPOT_SIZE)
        
        font = pygame.font.SysFont(None, 20)
        text = font.render(f"{self.food_amount:.1f}", True, BLACK)
        screen.blit(text, (self.x - 15, self.y - 10))

# Create nest position
nest_x = WIDTH // 2
nest_y = HEIGHT // 2

# Create obstacles
obstacles = []
for _ in range(OBSTACLE_COUNT):
    obstacle = Obstacle()
    nest_distance = math.sqrt((obstacle.x - nest_x)**2 + (obstacle.y - nest_y)**2)
    while nest_distance < NEST_SIZE + max(obstacle.width, obstacle.height) / 2 + 20:
        obstacle = Obstacle()
        nest_distance = math.sqrt((obstacle.x - nest_x)**2 + (obstacle.y - nest_y)**2)
    obstacles.append(obstacle)

# Create feeding spots
feeding_spots = []
for _ in range(FEEDING_SPOT_COUNT):
    spot = FeedingSpot()
    attempts = 0
    while not spot.is_valid_position(obstacles) and attempts < 20:
        spot = FeedingSpot()
        attempts += 1
    feeding_spots.append(spot)

# Create predators
predators = [Predator() for _ in range(PREDATOR_COUNT)]

# Create ants with different types
ants = []
for _ in range(ANT_COUNT):
    rand_type = random.random()
    if rand_type < 0.35:
        ant_type = SCOUT
    elif rand_type < 0.7:
        ant_type = WORKER
    else:
        ant_type = SOLDIER
    ants.append(Ant(nest_x, nest_y, ant_type))

# Create pheromone map
pheromone_map = np.zeros((HEIGHT, WIDTH, 2), dtype=float)

# Main game loop
running = True
paused = False
show_pheromones = False
show_danger_pheromones = False
show_info = True
show_mdp_info = False

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                paused = not paused
            elif event.key == pygame.K_p:
                show_pheromones = not show_pheromones
                show_danger_pheromones = False
            elif event.key == pygame.K_d:
                show_danger_pheromones = not show_danger_pheromones
                show_pheromones = False
            elif event.key == pygame.K_i:
                show_info = not show_info
            elif event.key == pygame.K_m:
                show_mdp_info = not show_mdp_info
            elif event.key == pygame.K_r:
                # Reset simulation
                obstacles = []
                for _ in range(OBSTACLE_COUNT):
                    obstacle = Obstacle()
                    nest_distance = math.sqrt((obstacle.x - nest_x)**2 + (obstacle.y - nest_y)**2)
                    while nest_distance < NEST_SIZE + max(obstacle.width, obstacle.height) / 2 + 20:
                        obstacle = Obstacle()
                        nest_distance = math.sqrt((obstacle.x - nest_x)**2 + (obstacle.y - nest_y)**2)
                    obstacles.append(obstacle)
                
                feeding_spots = []
                for _ in range(FEEDING_SPOT_COUNT):
                    spot = FeedingSpot()
                    attempts = 0
                    while not spot.is_valid_position(obstacles) and attempts < 20:
                        spot = FeedingSpot()
                        attempts += 1
                    feeding_spots.append(spot)
                
                predators = [Predator() for _ in range(PREDATOR_COUNT)]
                
                ants = []
                for _ in range(ANT_COUNT):
                    rand_type = random.random()
                    if rand_type < 0.35:
                        ant_type = SCOUT
                    elif rand_type < 0.7:
                        ant_type = WORKER
                    else:
                        ant_type = SOLDIER
                    ants.append(Ant(nest_x, nest_y, ant_type))
                
                pheromone_map = np.zeros((HEIGHT, WIDTH, 2), dtype=float)
    
    if not paused:
        pheromone_map *= PHEROMONE_EVAPORATION_RATE
        
        for spot in feeding_spots:
            spot.update()
        
        for ant in ants[:]:
            ant.update(feeding_spots, nest_x, nest_y, pheromone_map[:, :, 0], obstacles, predators)
        
        for predator in predators:
            predator.update(ants, pheromone_map[:, :, 1])
    
    screen.fill(WHITE)
    
    if show_pheromones:
        max_pheromone = np.max(pheromone_map[:, :, 0])
        if max_pheromone > 0:
            display_map = (pheromone_map[:, :, 0] / max_pheromone * 255).astype(np.uint8)
            for y in range(HEIGHT):
                for x in range(WIDTH):
                    if display_map[y, x] > 5:
                        intensity = min(255, display_map[y, x])
                        pygame.draw.rect(screen, (0, int(intensity/2), 0), (x, y, 1, 1))
    
    if show_danger_pheromones:
        max_danger = np.max(pheromone_map[:, :, 1])
        if max_danger > 0:
            display_map = (pheromone_map[:, :, 1] / max_danger * 255).astype(np.uint8)
            for y in range(HEIGHT):
                for x in range(WIDTH):
                    if display_map[y, x] > 5:
                        intensity = min(255, display_map[y, x])
                        pygame.draw.rect(screen, (int(intensity/2), 0, 0), (x, y, 1, 1))
    
    for obstacle in obstacles:
        obstacle.draw(screen)
    
    for spot in feeding_spots:
        spot.draw(screen)
    
    pygame.draw.circle(screen, BROWN, (nest_x, nest_y), NEST_SIZE)
    pygame.draw.circle(screen, YELLOW, (nest_x, nest_y), NEST_SIZE - 5)
    
    for predator in predators:
        predator.draw(screen)
    
    for ant in ants:
        ant.draw(screen)
    
    font = pygame.font.SysFont(None, 24)
    controls_text = font.render("SPACE: Pause | P: Food Pheromones | D: Danger Pheromones | I: Info | M: MDP Info | R: Reset", True, BLACK)
    screen.blit(controls_text, (10, 10))
    
    remaining_food = sum(spot.food_amount for spot in feeding_spots)
    food_text = font.render(f"Remaining Food: {remaining_food:.1f}", True, BLACK)
    screen.blit(food_text, (10, 40))
    
    scout_count = sum(1 for ant in ants if ant.ant_type == SCOUT)
    worker_count = sum(1 for ant in ants if ant.ant_type == WORKER)
    soldier_count = sum(1 for ant in ants if ant.ant_type == SOLDIER)
    carrying_ants = sum(1 for ant in ants if ant.has_food)
    fleeing_ants = sum(1 for ant in ants if ant.state == "fleeing")
    
    if show_info:
        scout_text = font.render(f"Scouts: {scout_count}", True, PURPLE)
        worker_text = font.render(f"Workers: {worker_count}", True, BLACK)
        soldier_text = font.render(f"Soldiers: {soldier_count}", True, RED)
        carrying_text = font.render(f"Carrying Food: {carrying_ants}/{len(ants)}", True, ORANGE)
        fleeing_text = font.render(f"Fleeing: {fleeing_ants}", True, DARK_RED)
        predator_text = font.render(f"Predators: {len(predators)}", True, DARK_RED)
        
        screen.blit(scout_text, (10, 70))
        screen.blit(worker_text, (10, 100))
        screen.blit(soldier_text, (10, 130))
        screen.blit(carrying_text, (10, 160))
        screen.blit(fleeing_text, (10, 190))
        screen.blit(predator_text, (10, 220))
        
        legend_y = 250
        legend_text = font.render("LEGEND:", True, BLACK)
        screen.blit(legend_text, (10, legend_y))
        
        pygame.draw.circle(screen, PURPLE, (30, legend_y + 30), ANT_SIZE)
        scout_legend = font.render("Scout", True, BLACK)
        screen.blit(scout_legend, (50, legend_y + 20))
        
        pygame.draw.circle(screen, BLACK, (30, legend_y + 60), ANT_SIZE)
        worker_legend = font.render("Worker", True, BLACK)
        screen.blit(worker_legend, (50, legend_y + 50))
        
        pygame.draw.circle(screen, RED, (30, legend_y + 90), ANT_SIZE + 2)
        soldier_legend = font.render("Soldier", True, BLACK)
        screen.blit(soldier_legend, (50, legend_y + 80))
        
        pygame.draw.circle(screen, ORANGE, (30, legend_y + 120), ANT_SIZE)
        carrying_legend = font.render("Carrying Food", True, BLACK)
        screen.blit(carrying_legend, (50, legend_y + 110))
        
        pygame.draw.circle(screen, DARK_RED, (30, legend_y + 150), 15)
        predator_legend = font.render("Predator", True, BLACK)
        screen.blit(predator_legend, (50, legend_y + 140))
        
        # State indicators
        pygame.draw.circle(screen, RED, (30, legend_y + 180), ANT_SIZE + 3, 2)
        fleeing_legend = font.render("Fleeing Danger", True, BLACK)
        screen.blit(fleeing_legend, (50, legend_y + 170))
        
        pygame.draw.circle(screen, GREEN, (30, legend_y + 210), ANT_SIZE + 3, 2)
        foraging_legend = font.render("Foraging", True, BLACK)
        screen.blit(foraging_legend, (50, legend_y + 200))
        
        pygame.draw.circle(screen, YELLOW, (30, legend_y + 240), ANT_SIZE + 3, 2)
        returning_legend = font.render("Returning to Nest", True, BLACK)
        screen.blit(returning_legend, (50, legend_y + 230))
    
    # Display MDP information if toggled
    if show_mdp_info:
        mdp_y = 500
        mdp_title = font.render("MDP DECISION MAKING (Last 5 Ants):", True, BLUE)
        screen.blit(mdp_title, (10, mdp_y))
        
        displayed_ants = ants[-5:] if len(ants) >= 5 else ants
        for i, ant in enumerate(displayed_ants):
            ant_type_name = ["Scout", "Worker", "Soldier"][ant.ant_type]
            ant_color = [PURPLE, BLACK, RED][ant.ant_type]
            ant_info = font.render(f"{ant_type_name}: {ant.current_action} (State: {ant.state})", True, ant_color)
            screen.blit(ant_info, (10, mdp_y + 30 + i * 25))
    
    pygame.display.flip()
    clock.tick(60)

pygame.quit()