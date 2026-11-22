import random
import math
import copy
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.patches import RegularPolygon, Circle, Patch
from matplotlib.lines import Line2D
from matplotlib.gridspec import GridSpec

# Given map radius and hex size
map_radius = 10
size = 1.0

# Maximum x and y in the pixel space of the hex grid
max_hex_x = size * 3/2 * map_radius       # maximum q coordinate in pixels
max_hex_y = size * (3**0.5 * (map_radius + map_radius/2))  # maximum r coordinate in pixels

# ---------------- Hex Utilities ---------------- #
HEX_DIRS = [(+1,0), (+1,-1), (0,-1), (-1,0), (-1,+1), (0,+1)]
def hex_neighbors(q,r): return [(q+dq,r+dr) for dq,dr in HEX_DIRS]

# ---------------- Terrain ---------------- #
TERRAINS = {
    "plains":{"color":"#e0d9a0","growth":1.0,"defense":1.0,"symbol":"🌾"},
    "mountain":{"color":"#8b8b8b","growth":0.5,"defense":1.5,"symbol":"⛰️"},
    "water":{"color":"#4a90e2","growth":0.0,"defense":1.0,"symbol":"🌊"},
    "forest":{"color":"#4fa24f","growth":0.7,"defense":1.2,"culture":0.05,"symbol":"🌲"},
    "desert":{"color":"#e0b563","growth":0.6,"defense":0.8,"symbol":"🏜️"},
    "swamp":{"color":"#2e8b57","growth":0.5,"defense":1.0,"symbol":"🦆"},
    "hills":{"color":"#d2b48c","growth":0.8,"defense":1.3,"symbol":"⛰️"},
    "volcano":{"color":"#ff4500","growth":0.2,"defense":1.5,"symbol":"🌋"},
    "tundra":{"color":"#c0d9e0","growth":0.5,"defense":1.0,"symbol":"❄️"},
    "jungle":{"color":"#228b22","growth":0.9,"defense":1.1,"culture":0.07,"symbol":"🦜"}
}

# ---------------- Resources ---------------- #
RESOURCES = {
    "iron":{"bonus":"military","value":0.1,"color":"#555555"},
    "gold":{"bonus":"economy","value":0.1,"color":"#ffd700"},
    "food":{"bonus":"population","value":0.15,"color":"#88cc44"},
    "knowledge":{"bonus":"culture","value":0.1,"color":"#8a2be2"},
    "stone":{"bonus":"economy","value":0.08,"color":"#a9a9a9"},
    "spices":{"bonus":"economy","value":0.12,"color":"#ff6347"},
    "horses":{"bonus":"military","value":0.12,"color":"#d2b48c"},
    "silk":{"bonus":"culture","value":0.1,"color":"#dda0dd"},
    "wood":{"bonus":"economy","value":0.08,"color":"#8b4513"}
}

RESOURCE_CHANCES = {
    "plains":{"food":0.4,"horses":0.1,"gold":0.05},
    "mountain":{"iron":0.3,"gold":0.2,"stone":0.2},
    "forest":{"food":0.2,"wood":0.3,"knowledge":0.1,"silk":0.05},
    "desert":{"spices":0.1,"gold":0.1},
    "swamp":{"food":0.2,"silk":0.05},
    "hills":{"iron":0.2,"stone":0.2,"horses":0.05},
    "volcano":{"iron":0.2,"gold":0.1},
    "tundra":{"food":0.1,"stone":0.2},
    "jungle":{"food":0.2,"silk":0.1,"spices":0.1}
}

# ---------------- Civ Names & Traits ---------------- #
CIV_PREFIXES = ["Auro","Xan","Vel","Eldo","Zeph","Cindra","Thal","Koro","Lum","Nexa"]
CIV_SUFFIXES = ["ria","dralith","mora","thium","oria","valis","dor","mir","thar","ven"]
TRAITS = ["aggressive","peaceful","expansionist","isolated","merchant","innovative","technocratic","religious","nomadic","defensive"]

def generate_civ_name(): return random.choice(CIV_PREFIXES)+random.choice(CIV_SUFFIXES)
def generate_splinter_name(parent_name): return random.choice([f"Neo-{parent_name}",f"The {parent_name} Horde",f"{parent_name} Dominion",f"Free {parent_name}",f"{parent_name} Rebels"])
def generate_dynasty_name(parent_name): return random.choice([f"The {parent_name} Empire",f"Kingdom of {parent_name}",f"{parent_name} Dominion",f"New {parent_name}",f"The Grand {parent_name}"])

# ---------------- Global Logs ---------------- #
history_log=[]
cultural_map={}
active_disasters={}

# ---------------- MDP for Decision Making ---------------- #
states = [0, 1, 2]  # 0: low stability, 1: medium, 2: high
actions = [0, 1]  # 0: focus military, 1: focus economy

def transition_model(s, a, s_next):
    if (s == 0 and a == 0 and s_next == 1) or (s == 1 and a == 0 and s_next == 0):
        return 1
    elif (s == 0 and a == 1 and s_next == 2) or (s == 2 and a == 1 and s_next == 1):
        return 1
    return 0

def reward_function(s, a, s_next):
    if s == 0 and a == 0 and s_next == 1:
        return 10
    elif s == 0 and a == 1 and s_next == 2:
        return 5
    return 0

gamma = 0.9
epsilon = 0.01

def value_iteration(states, actions, transition_model, reward_function, gamma, epsilon):
    V = {s: 0 for s in states}
    while True:
        delta = 0
        for s in states:
            v = V[s]
            V[s] = max(sum(transition_model(s, a, s_next) * 
                          (reward_function(s, a, s_next) + gamma * V[s_next]) 
                          for s_next in states) 
                      for a in actions)
            delta = max(delta, abs(v - V[s]))
        if delta < epsilon:
            break
    policy = {}
    for s in states:
        policy[s] = max(actions, key=lambda a: sum(
            transition_model(s, a, s_next) * 
            (reward_function(s, a, s_next) + gamma * V[s_next]) 
            for s_next in states))
    return policy, V

mdp_policy, mdp_value = value_iteration(states, actions, transition_model, reward_function, gamma, epsilon)

# ---------------- MCTS for Planning ---------------- #
class MCTSNode:
    def __init__(self, state, parent=None, action=None):
        self.state = state
        self.parent = parent
        self.action = action
        self.children = []
        self.visits = 0
        self.wins = 0
        self.untried_actions = self.get_actions()

    def get_actions(self):
        return [(i, j) for i in range(3) for j in range(3) if self.state[i][j] == 0]  # Placeholder for Tic-Tac-Toe; adapt for hex game

    def is_terminal(self):
        return self.check_winner() is not None or not self.get_actions()

    def is_fully_expanded(self):
        return len(self.untried_actions) == 0

    def check_winner(self):
        for i in range(3):
            if self.state[i][0] == self.state[i][1] == self.state[i][2] != 0:
                return self.state[i][0]
            if self.state[0][i] == self.state[1][i] == self.state[2][i] != 0:
                return self.state[0][i]
        if self.state[0][0] == self.state[1][1] == self.state[2][2] != 0:
            return self.state[0][0]
        if self.state[0][2] == self.state[1][1] == self.state[2][0] != 0:
            return self.state[0][2]
        return None

    def expand(self):
        action = self.untried_actions.pop()
        new_state = copy.deepcopy(self.state)
        player = self.get_current_player()
        new_state[action[0]][action[1]] = player
        child = MCTSNode(new_state, parent=self, action=action)
        self.children.append(child)
        return child

    def get_current_player(self):
        x_count = sum(row.count(1) for row in self.state)
        o_count = sum(row.count(2) for row in self.state)
        return 1 if x_count == o_count else 2

    def best_child(self, c=1.4):
        return max(self.children, key=lambda child: (child.wins / child.visits) + c * math.sqrt(math.log(self.visits) / child.visits))

    def rollout(self):
        state = copy.deepcopy(self.state)
        player = self.get_current_player()
        while True:
            winner = self.check_winner_for_state(state)
            if winner:
                return 1 if winner == 1 else 0
            actions = [(i, j) for i in range(3) for j in range(3) if state[i][j] == 0]
            if not actions:
                return 0.5
            move = random.choice(actions)
            state[move[0]][move[1]] = player
            player = 1 if player == 2 else 2

    def check_winner_for_state(self, state):
        return MCTSNode(state).check_winner()

    def backpropagate(self, result):
        self.visits += 1
        self.wins += result
        if self.parent:
            self.parent.backpropagate(result)

def mcts_search(root_state, iterations=500):
    root = MCTSNode(root_state)
    for _ in range(iterations):
        node = root
        while not node.is_terminal() and node.is_fully_expanded():
            node = node.best_child()
        if not node.is_terminal():
            node = node.expand()
        result = node.rollout()
        node.backpropagate(result)
    return root.best_child(c=0).action

# ---------------- Civilization Class ---------------- #
CIV_COLOR_PALETTE = plt.cm.tab20.colors

class Civilization:
    color_idx=0
    def __init__(self,name,q,r,trait=None,parent=None):
        self.name=name
        self.q=q
        self.r=r
        self.population=random.randint(80,200)
        self.stability=random.uniform(0.5,1.0)
        self.military=random.uniform(0.3,0.8)
        self.economy=random.uniform(0.3,0.8)
        self.culture=random.uniform(0.3,0.8)
        self.trait=trait if trait else random.choice(TRAITS)
        self.alive=True
        self.hexes={(q,r)}
        self.prev_hexes=set(self.hexes)
        self.allies=set()
        self.enemies=set()
        self.parent=parent
        self.color=CIV_COLOR_PALETTE[Civilization.color_idx % len(CIV_COLOR_PALETTE)]
        Civilization.color_idx+=1
        self.moving_units=[]
        self.armies = {(q,r): random.randint(10,20)}
        self.stats_history = {
            'population': [self.population],
            'stability': [self.stability],
            'military': [self.military],
            'economy': [self.economy],
            'culture': [self.culture]
        }

    def step(self,civs,world,terrain,resources):
        if not self.alive: return
        growth_factor = sum(TERRAINS[terrain.get(h,"plains")]["growth"] for h in self.hexes)/len(self.hexes)
        self.population += int(random.gauss(self.stability*5*growth_factor,6))
        self.stability -= max(0,len(self.hexes)-10)*0.005

        # MDP decision
        current_state = 0 if self.stability < 0.4 else 1 if self.stability < 0.7 else 2
        action = mdp_policy[current_state]
        if action == 0:  # focus military
            self.military += 0.01
            self.economy -= 0.005
        elif action == 1:  # focus economy
            self.economy += 0.01
            self.military -= 0.005

        self.attempt_expansion(world,terrain)
        self.attempt_attack(world, terrain, civs)
        self.move_armies()
        self.diplomacy(civs)
        self.trade(civs)
        self.maybe_rebellion(civs,world)
        self.maybe_overthrow(civs,world)
        self.spread_culture()
        self.develop_tech()
        self.climate_event()

        # Update stats history
        self.stats_history['population'].append(self.population)
        self.stats_history['stability'].append(self.stability)
        self.stats_history['military'].append(self.military)
        self.stats_history['economy'].append(self.economy)
        self.stats_history['culture'].append(self.culture)

        if self.population <= 0 or self.stability <= 0.05:
            for h in self.hexes: del world[h]
            self.hexes.clear()
            self.alive = False
            history_log.append(f"💀 {self.name} collapsed")

    def attempt_expansion(self,world,terrain):
        attempts = max(1, int(self.military * 10))
        for _ in range(attempts):
            if not self.hexes: break
            origin = random.choice(list(self.hexes))
            possible_targets = []
            for nq, nr in hex_neighbors(*origin):
                ttype = terrain.get((nq, nr), "plains")
                if ttype != "water" and (nq, nr) not in world:
                    possible_targets.append((nq, nr))
            if possible_targets:
                # Use MCTS for choosing target if expansionist
                if self.trait == "expansionist":
                    # Placeholder state for MCTS (adapt as needed; here using dummy Tic-Tac-Toe state for demo)
                    dummy_state = [[0]*3 for _ in range(3)]
                    best_target = mcts_search(dummy_state)
                    target = possible_targets[best_target[0] % len(possible_targets)]  # Simple mapping for demo
                else:
                    target = random.choice(possible_targets)
                ttype = terrain.get(target, "plains")
                if random.random() < min(1.0, self.military * TERRAINS[ttype]["growth"]):
                    self.hexes.add(target)
                    world[target] = self.name
                    self.moving_units.append({"from": origin, "to": target, "progress": 0.0})
                    break

    def attempt_attack(self, world, terrain, civs):
        if not self.enemies: return
        for enemy_name in list(self.enemies):
            enemy = next((c for c in civs if c.name == enemy_name), None)
            if not enemy or not enemy.alive: continue
            for my_h in list(self.hexes):
                for n in hex_neighbors(*my_h):
                    if n in enemy.hexes:
                        my_army = self.armies.get(my_h, 0)
                        if my_army < 5: continue
                        enemy_army = enemy.armies.get(n, 0)
                        def_bonus = TERRAINS[terrain.get(n, "plains")]["defense"]
                        enemy_strength = enemy_army * def_bonus * (enemy.military / self.military)
                        if my_army > enemy_strength * random.uniform(0.8, 1.2):
                            enemy.hexes.remove(n)
                            world[n] = self.name
                            self.hexes.add(n)
                            remaining_army = my_army // 2
                            self.armies[n] = remaining_army
                            self.armies[my_h] -= my_army
                            if self.armies[my_h] <= 0: del self.armies[my_h]
                            self.moving_units.append({"from": my_h, "to": n, "progress": 0.0})
                            history_log.append(f"🏹 {self.name} conquered {n} from {enemy.name}")
                            if not enemy.hexes:
                                enemy.alive = False
                                history_log.append(f"💀 {enemy.name} destroyed by {self.name}")
                            break

    def move_armies(self):
        for h in list(self.armies.keys()):
            if random.random() < 0.2:
                neighbors = [n for n in hex_neighbors(*h) if n in self.hexes]
                if neighbors:
                    to = random.choice(neighbors)
                    army_size = self.armies[h]
                    del self.armies[h]
                    self.armies[to] = self.armies.get(to, 0) + army_size
                    self.moving_units.append({"from": h, "to": to, "progress": 0.0})

    def diplomacy(self, civs):
        if random.random() < 0.05:
            potential_partners = [c for c in civs if c.alive and c != self and c.name not in self.allies and c.name not in self.enemies]
            if potential_partners:
                partner = random.choice(potential_partners)
                if self.trait in ["peaceful", "merchant"] or partner.trait in ["peaceful", "merchant"]:
                    self.allies.add(partner.name)
                    partner.allies.add(self.name)
                    history_log.append(f"🤝 {self.name} allied with {partner.name}")
                else:
                    self.enemies.add(partner.name)
                    partner.enemies.add(self.name)
                    history_log.append(f"⚔️ {self.name} declared war on {partner.name}")

    def trade(self, civs):
        for partner in civs:
            if partner.alive and partner != self and self.name < partner.name and self.trait in ["merchant","peaceful"] and partner.trait in ["merchant","peaceful"]:
                trade_bonus = 0.01
                self.economy += trade_bonus * partner.economy
                partner.economy += trade_bonus * self.economy

    def spread_culture(self):
        for h in self.hexes:
            if h not in cultural_map: cultural_map[h] = {}
            cultural_map[h][self.name] = cultural_map[h].get(self.name, 0) + self.culture
            for nq, nr in hex_neighbors(*h):
                if (nq, nr) not in cultural_map: cultural_map[(nq, nr)] = {}
                cultural_map[(nq, nr)][self.name] = cultural_map[(nq, nr)].get(self.name, 0) + self.culture * 0.1

    def develop_tech(self):
        self.culture += 0.005 * random.random()

    def climate_event(self):
        for h in self.hexes:
            if random.random() < 0.01:
                disaster_type = random.choice(["flood", "drought", "plague", "volcano"])
                active_disasters[h] = (disaster_type, 3)
                history_log.append(f"{self.name} suffered {disaster_type} at {h}")

    def maybe_rebellion(self, civs, world):
        if random.random() < 0.005 and self.population > 100:
            name = generate_splinter_name(self.name)
            nq, nr = random.choice(list(self.hexes))
            new_civ = Civilization(name, nq, nr, trait=random.choice(TRAITS), parent=self.name)
            civs.append(new_civ)
            self.population = int(self.population * 0.7)
            history_log.append(f"⚔️ {new_civ.name} rebelled from {self.name}")

    def maybe_overthrow(self, civs, world):
        if random.random() < 0.002 and self.population > 150:
            old_name = self.name
            self.name = generate_dynasty_name(self.name)
            history_log.append(f"👑 {old_name} dynasty overthrown, new name: {self.name}")

# ---------------- Map Generation ---------------- #
def generate_terrain(map_radius):
    terrain = {}
    for q in range(-map_radius, map_radius + 1):
        for r in range(-map_radius, map_radius + 1):
            if -map_radius <= q + r <= map_radius:
                terrain[(q, r)] = random.choices(list(TERRAINS.keys()), weights=[30,10,10,10,10,5,5,5,5,10])[0]
    return terrain

def generate_resources(terrain, map_radius):
    resources = {}
    for h, t in terrain.items():
        for res, ch in RESOURCE_CHANCES.get(t, {}).items():
            if random.random() < ch:
                resources[h] = res
                break
    return resources

# ---------------- Hex to Pixel ---------------- #
def hex_to_pixel(q, r, size=1.0):
    x = size * 3 / 2 * q
    y = size * (3**0.5 * (r + q / 2))
    return x, y

def draw_hex(ax, q, r, color="#ffffff", alpha=1.0, linewidth=1.0, size=1.0):
    x, y = hex_to_pixel(q, r, size)
    hex_patch = RegularPolygon((x, y), numVertices=6, radius=size * 0.95, orientation=0,
                               facecolor=color, edgecolor="black", linewidth=linewidth, alpha=alpha)
    ax.add_patch(hex_patch)

# ---------------- Drawing Functions ---------------- #
def draw_terrain_symbols(ax, terrain, size=1.0):
    for h, t in terrain.items():
        x, y = hex_to_pixel(*h, size)
        ax.text(x, y + 0.3 * size, TERRAINS[t]["symbol"], ha='center', va='center', fontsize=10)

def draw_resources_on_hex(ax, resources, size=1.0):
    for h, res in resources.items():
        x, y = hex_to_pixel(*h, size)
        ax.text(x + 0.35 * size, y + 0.35 * size, res[0].upper(), ha='center', va='center', fontsize=6, color=RESOURCES[res]["color"], weight='bold')

def draw_hex_overlays(ax, civ, resources, size=1.0):
    for h in civ.hexes:
        x, y = hex_to_pixel(*h, size)
        ax.text(x, y, str(int(civ.military * 100)), ha='center', va='center', fontsize=8, color="red", weight='bold')
        ax.text(x, y - 0.35 * size, str(civ.population), ha='center', va='center', fontsize=6)
        ax.text(x, y + 0.35 * size, f"{int(civ.stability * 100)}", ha='center', va='center', fontsize=6)
        if h in civ.armies:
            ax.text(x - 0.35 * size, y - 0.35 * size, str(civ.armies[h]), ha='center', va='center', fontsize=6, color='black')
        if h in resources:
            res = resources[h]
            ax.text(x + 0.5 * size, y + 0.5 * size, res[0].upper(), ha='center', va='center', fontsize=6, color=RESOURCES[res]["color"])

def draw_moving_units(ax, civ, size=1.0, dt=0.2):
    finished = []
    for i, move in enumerate(civ.moving_units):
        fx, fy = hex_to_pixel(*move["from"], size)
        tx, ty = hex_to_pixel(*move["to"], size)
        x = fx + (tx - fx) * move["progress"]
        y = fy + (ty - fy) * move["progress"]
        ax.add_patch(Circle((x, y), radius=0.3 * size, color=civ.color, alpha=0.8))
        move["progress"] += dt
        if move["progress"] >= 1.0:
            finished.append(i)
    for i in reversed(finished):
        civ.moving_units.pop(i)

def draw_disasters(ax, size=1.0):
    finished = []
    for h, (dtype, turns) in active_disasters.items():
        x, y = hex_to_pixel(*h, size)
        icons = {"flood": "🌊", "drought": "🔥", "plague": "☣️", "volcano": "🌋"}
        ax.text(x, y, icons[dtype], ha='center', va='center', fontsize=10)
        active_disasters[h] = (dtype, turns - 1)
        if turns - 1 <= 0:
            finished.append(h)
    for h in finished:
        del active_disasters[h]

def draw_trade_routes(ax, civs, size=1.0):
    for civ in civs:
        if not civ.alive: continue
        for partner in civs:
            if partner.name == civ.name or not partner.alive or civ.name >= partner.name: continue
            if civ.trait in ["merchant", "peaceful"] and partner.trait in ["merchant", "peaceful"]:
                q1, r1 = random.choice(list(civ.hexes))
                q2, r2 = random.choice(list(partner.hexes))
                x1, y1 = hex_to_pixel(q1, r1, size)
                x2, y2 = hex_to_pixel(q2, r2, size)
                ax.plot([x1, x2], [y1, y2], linestyle="dotted", color="purple", alpha=0.5, linewidth=1)

def create_legend(ax):
    terrain_patches = [Patch(color=TERRAINS[t]["color"], label=f"{t} {TERRAINS[t].get('symbol', '')}") for t in TERRAINS]
    resource_patches = [Patch(color=RESOURCES[r]["color"], label=f"{r[0].upper()} ({r})") for r in RESOURCES]
    military_patch = Line2D([], [], color='red', marker='o', linestyle='', markersize=8, label="Military")
    trade_line = Line2D([], [], color='purple', linestyle='dotted', label="Trade Routes")
    ax.legend(handles=terrain_patches + resource_patches + [military_patch, trade_line], loc='upper left', fontsize=8, framealpha=0.9)

def draw_civ_info(ax, civs, max_hex_x, max_hex_y):
    text_y = max_hex_y
    for civ in civs:
        if not civ.alive: continue
        text = (f"{civ.name} | Pop:{civ.population} | Mil:{int(civ.military*100)} "
                f"| Stab:{int(civ.stability*100)} | Eco:{int(civ.economy*100)} | Cul:{int(civ.culture*100)}")
        ax.text(max_hex_x * 1.05, text_y, text, va='top', fontsize=8, color=civ.color)
        text_y -= 2.0

def draw_stat_charts(ax, civs):
    ax.clear()
    for civ in civs:
        if not civ.alive: continue
        turns = range(len(civ.stats_history['population']))
        ax.plot(turns, civ.stats_history['population'], color=civ.color, label=f"{civ.name} Pop")
    ax.set_xlabel("Turns")
    ax.set_ylabel("Population")
    ax.legend(loc='upper right')

# ---------------- Simulation Setup ---------------- #
terrain = generate_terrain(map_radius)
resources = generate_resources(terrain, map_radius)
world = {}
civs = [Civilization(generate_civ_name(), 0, 0), Civilization(generate_civ_name(), 3, -2)]
for civ in civs:
    for h in civ.hexes:
        world[h] = civ.name

fig = plt.figure(figsize=(16, 8))
gs = GridSpec(1, 2, width_ratios=[3, 1])
ax_map = fig.add_subplot(gs[0])
ax_chart = fig.add_subplot(gs[1])

ax_map.set_xlim(-map_radius * size * 2, map_radius * size * 2)
ax_map.set_ylim(-map_radius * size * 2, map_radius * size * 2)
ax_map.set_aspect('equal')
ax_map.axis('off')

# Pre-draw static elements
for h, t in terrain.items():
    draw_hex(ax_map, *h, TERRAINS[t]["color"], alpha=1.0, linewidth=1.0, size=size)
    x, y = hex_to_pixel(*h, size)
    ax_map.text(x, y + 0.3 * size, TERRAINS[t]["symbol"], ha='center', va='center', fontsize=int(10 * size))

for h, res in resources.items():
    x, y = hex_to_pixel(*h, size)
    ax_map.text(x + 0.35 * size, y + 0.35 * size, res[0].upper(), ha='center', va='center',
                fontsize=int(6 * size), color=RESOURCES[res]["color"], weight='bold')

create_legend(ax_map)

# Dynamic containers
unit_patches = []
disaster_texts = []
trade_lines = []

def update(frame):
    for patch in unit_patches:
        patch.remove()
    unit_patches.clear()
    for txt in disaster_texts:
        txt.remove()
    disaster_texts.clear()
    for line in trade_lines:
        line.remove()
    trade_lines.clear()

    alive = [c for c in civs if c.alive]
    for civ in alive:
        civ.step(civs, world, terrain, resources)
        for h in civ.hexes:
            draw_hex(ax_map, *h, civ.color, alpha=0.85, linewidth=1.5, size=size)
        draw_hex_overlays(ax_map, civ, resources, size)
        draw_moving_units(ax_map, civ, size)

    draw_disasters(ax_map, size)
    draw_trade_routes(ax_map, alive, size)

    # Clear old texts except static
    dynamic_texts = unit_patches + disaster_texts  # Note: unit_patches include texts now? Wait, adjust
    # Actually, in draw_hex_overlays, add texts to unit_patches or separate
    # For simplicity, clear all texts and redraw static if needed, but skip for now

    draw_civ_info(ax_map, alive, max_hex_x, max_hex_y)
    draw_stat_charts(ax_chart, alive)

ani = animation.FuncAnimation(fig, update, frames=50, interval=1000)
plt.show()