import random
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.patches import RegularPolygon, Circle
from matplotlib.gridspec import GridSpec

# ---------------- Hex Utilities ---------------- #
HEX_DIRS = [(+1,0), (+1,-1), (0,-1), (-1,0), (-1,+1), (0,+1)]
def hex_neighbors(q, r):
    return [(q+dq, r+dr) for dq, dr in HEX_DIRS]

# ---------------- Terrain ---------------- #
TERRAINS = {
    "plains": {"color":"#e0d9a0", "growth":1.0, "defense":1.0},
    "mountain": {"color":"#8b8b8b", "growth":0.5, "defense":1.5},
    "water": {"color":"#4a90e2", "growth":0.0, "defense":1.0},
    "forest": {"color":"#4fa24f", "growth":0.7, "defense":1.2, "culture":0.05},
    "desert": {"color":"#e0b563", "growth":0.6, "defense":0.8}
}

# ---------------- Resources ---------------- #
RESOURCES = {
    "iron": {"bonus":"military", "value":0.1, "color":"#555555"},
    "gold": {"bonus":"economy", "value":0.1, "color":"#ffd700"},
    "food": {"bonus":"population", "value":0.15, "color":"#88cc44"},
    "knowledge": {"bonus":"culture", "value":0.1, "color":"#8a2be2"}
}

# ---------------- Civilization Names ---------------- #
CIV_PREFIXES = ["Auro", "Xan", "Vel", "Eldo", "Zeph", "Cindra", "Thal", "Koro", "Lum", "Nexa"]
CIV_SUFFIXES = ["ria", "dralith", "mora", "thium", "oria", "valis", "dor", "mir", "thar", "ven"]

def generate_civ_name():
    return random.choice(CIV_PREFIXES) + random.choice(CIV_SUFFIXES)

def generate_splinter_name(parent_name):
    styles = [f"Neo-{parent_name}", f"The {parent_name} Horde", f"{parent_name} Dominion",
              f"Free {parent_name}", f"{parent_name} Rebels"]
    return random.choice(styles)

def generate_dynasty_name(parent_name):
    styles = [f"The {parent_name} Empire", f"Kingdom of {parent_name}",
              f"{parent_name} Dominion", f"New {parent_name}", f"The Grand {parent_name}"]
    return random.choice(styles)

# ---------------- History & Culture ---------------- #
history_log = []
cultural_map = {}
event_queue = []

# ---------------- Civilization Class ---------------- #
CIV_COLOR_PALETTE = plt.cm.tab20.colors
class Civilization:
    color_idx = 0
    def __init__(self, name, q, r, trait=None, parent=None):
        self.name = name
        self.q = q
        self.r = r
        self.population = random.randint(80, 200)
        self.stability = random.uniform(0.5, 1.0)
        self.military = random.uniform(0.3, 0.8)
        self.economy = random.uniform(0.3, 0.8)
        self.culture = random.uniform(0.3, 0.8)
        self.trait = trait if trait else random.choice(["aggressive", "peaceful", "expansionist", "isolated"])
        self.alive = True
        self.hexes = {(q, r)}
        self.allies = set()
        self.enemies = set()
        self.parent = parent
        self.color = CIV_COLOR_PALETTE[Civilization.color_idx % len(CIV_COLOR_PALETTE)]
        Civilization.color_idx += 1

    def apply_resources(self, terrain, resources):
        for h in self.hexes:
            if h in resources:
                res = resources[h]
                bonus = RESOURCES[res]["bonus"]
                val = RESOURCES[res]["value"]
                if bonus == "military": self.military = min(1.0, self.military + val)
                elif bonus == "economy": self.economy = min(1.0, self.economy + val)
                elif bonus == "population": self.population += int(self.population * val)
                elif bonus == "culture": self.culture = min(1.0, self.culture + val)

    def maybe_rebellion(self, civs, world):
        if self.stability < 0.2 and len(self.hexes) > 3 and random.random() < 0.1:
            rebel_hexes = random.sample(list(self.hexes), len(self.hexes)//3)
            for h in rebel_hexes: self.hexes.remove(h)
            new_name = generate_splinter_name(self.name)
            nq, nr = rebel_hexes[0]
            rebel = Civilization(new_name, nq, nr, trait="isolated", parent=self.name)
            rebel.hexes = set(rebel_hexes)
            for h in rebel_hexes: world[h] = rebel.name
            civs.append(rebel)
            history_log.append(f"⚔️ {new_name} rebelled from {self.name}!")
            event_queue.append((f"⚔️ {new_name} rebelled from {self.name}", 5))

    def maybe_overthrow(self, civs, world):
        if self.trait != "isolated" or not self.parent: return
        parent = next((c for c in civs if c.name == self.parent and c.alive), None)
        if not parent: return
        rebel_strength = self.population + len(self.hexes)*20
        parent_strength = parent.population + len(parent.hexes)*20
        if rebel_strength > parent_strength * 1.2 and random.random() < 0.3:
            for h in parent.hexes: self.hexes.add(h); world[h] = self.name
            parent.alive = False; parent.hexes.clear()
            old_name = self.name
            self.name = generate_dynasty_name(parent.name)
            history_log.append(f"👑 {old_name} overthrew {parent.name} and became {self.name}")
            event_queue.append((f"👑 {old_name} overthrew {parent.name}!", 5))
            self.trait = random.choice(["aggressive","peaceful","expansionist","isolated"])
            self.parent = None

    def spread_culture(self):
        for h in self.hexes:
            if h not in cultural_map: cultural_map[h] = {}
            cultural_map[h][self.name] = cultural_map[h].get(self.name,0) + self.culture
            for nq,nr in hex_neighbors(*h):
                if (nq,nr) not in cultural_map: cultural_map[(nq,nr)] = {}
                cultural_map[(nq,nr)][self.name] = cultural_map[(nq,nr)].get(self.name,0) + self.culture*0.3

    def step(self, civs, world, terrain, resources):
        if not self.alive: return
        self.apply_resources(terrain, resources)
        growth_factor = sum(TERRAINS[terrain.get(h,"plains")]["growth"] for h in self.hexes)/len(self.hexes)
        self.population += int(random.gauss(self.stability*5*growth_factor,6))
        overext = max(0,len(self.hexes)-10)*0.005
        self.stability -= overext
        enemy_neighbors = sum(1 for h in self.hexes for nq,nr in hex_neighbors(*h) if world.get((nq,nr)) in self.enemies)
        self.stability -= enemy_neighbors*0.002
        if self.stability < 0.2: self.population = max(0,int(self.population*(0.95+random.uniform(-0.02,0.02))))
        if self.population <= 0 or self.stability <= 0.05:
            for h in self.hexes:
                if world.get(h)==self.name: del world[h]
            self.hexes.clear()
            self.alive = False
            history_log.append(f"💀 {self.name} collapsed!")
            event_queue.append((f"💀 {self.name} collapsed!",5))
            return
        expansion_attempts = max(1,self.population//60)
        for _ in range(expansion_attempts):
            if not self.hexes: break
            origin = random.choice(list(self.hexes))
            for nq,nr in hex_neighbors(*origin):
                ttype = terrain.get((nq,nr),"plains")
                if ttype=="water": continue
                if (nq,nr) not in world:
                    if random.random() < TERRAINS[ttype]["growth"]:
                        self.hexes.add((nq,nr))
                        world[(nq,nr)] = self.name
                        break
        self.maybe_rebellion(civs,world)
        self.maybe_overthrow(civs,world)
        self.spread_culture()

# ---------------- Drawing ---------------- #
def draw_hex(ax,q,r,facecolor,border="k",size=1,alpha=0.8,linewidth=1.0):
    x = size*(3**0.5*q + (3**0.5)/2*r)
    y = size*(3/2*r)
    ax.add_patch(RegularPolygon((x,y),numVertices=6,radius=size/1.1,
                                orientation=0, facecolor=facecolor, edgecolor=border, alpha=alpha, linewidth=linewidth))
    return x,y

def draw_resource(ax,q,r,color):
    x = 1*(3**0.5*q + (3**0.5)/2*r)
    y = 1*(3/2*r)
    ax.add_patch(Circle((x,y),radius=0.2,color=color,alpha=0.9))

# ---------------- Simulation with Full Charts ---------------- #
def simulate_hex_with_full_charts(names, years=60, map_radius=10):
    terrain = {}
    for q in range(-map_radius, map_radius+1):
        for r in range(-map_radius, map_radius+1):
            if abs(q+r) > map_radius: continue
            terrain[(q,r)] = random.choices(list(TERRAINS.keys()), weights=[0.4,0.15,0.2,0.15,0.1])[0]

    resources = {}
    for h,t in terrain.items():
        if t=="water": continue
        if random.random()<0.25: resources[h]=random.choice(list(RESOURCES.keys()))

    starts = random.sample(list(terrain.keys()), len(names))
    civs = [Civilization(n, q, r) for n, (q, r) in zip(names, starts)]
    world = {list(c.hexes)[0]: c.name for c in civs}

    # Prepare figure with GridSpec
    fig = plt.figure(figsize=(18,10))
    gs = GridSpec(1,2, width_ratios=[2,1])
    ax_map = fig.add_subplot(gs[0])
    ax_chart = fig.add_subplot(gs[1])

    all_qr = list(terrain.keys())
    x_coords = [ (3**0.5*q + (3**0.5)/2*r) for q,r in all_qr ]
    y_coords = [ (3/2*r) for q,r in all_qr ]
    margin = 2

    # Track historical stats for chart
    history_stats = {c.name: {"population":[],"stability":[],"military":[],"economy":[],"culture":[]} for c in civs}

    def update(frame):
        ax_map.clear()
        ax_chart.clear()
        ax_map.set_title(f"Year {frame}", fontsize=16)
        ax_map.set_aspect('equal'); ax_map.axis('off')

        alive = [c for c in civs if c.alive]
        for civ in alive: civ.step(alive, world, terrain, resources)

        # Draw terrain and resources
        for (q,r),t in terrain.items(): draw_hex(ax_map,q,r,TERRAINS[t]["color"],size=1,alpha=0.4)
        for (q,r),res in resources.items(): draw_resource(ax_map,q,r,RESOURCES[res]["color"])

        # Draw civilizations
        for civ in alive:
            for h in civ.hexes: draw_hex(ax_map,h[0],h[1],civ.color,alpha=0.85,linewidth=1.5)

        ax_map.set_xlim(min(x_coords)-margin, max(x_coords)+margin)
        ax_map.set_ylim(min(y_coords)-margin, max(y_coords)+margin)
        ax_map.invert_yaxis()

        # Update historical stats
        for c in civs:
            history_stats[c.name]["population"].append(c.population)
            history_stats[c.name]["stability"].append(c.stability)
            history_stats[c.name]["military"].append(c.military)
            history_stats[c.name]["economy"].append(c.economy)
            history_stats[c.name]["culture"].append(c.culture)

        # Draw charts with different line styles
        traits = ["population","stability","military","economy","culture"]
        styles = {"population":"-","stability":"--","military":":","economy":"-.", "culture":"-"}
        ax_chart.set_title("Civilization Stats Over Time")
        for c in civs:
            years_range = range(len(history_stats[c.name]["population"]))
            for trait in traits:
                data = history_stats[c.name][trait]
                if trait=="stability": data = [s*100 for s in data]
                ax_chart.plot(years_range, data, label=f"{c.name} {trait.capitalize()}", color=c.color, linestyle=styles[trait])
        ax_chart.set_xlabel("Year")
        ax_chart.set_ylabel("Value")
        ax_chart.legend(fontsize=7, loc='upper left')

    ani = animation.FuncAnimation(fig, update, frames=years, interval=400, repeat=False)
    plt.show()

# ---------------- Run Simulation ---------------- #
if __name__=="__main__":
    civ_names = [generate_civ_name() for _ in range(5)]
    simulate_hex_with_full_charts(civ_names, years=50, map_radius=8)
