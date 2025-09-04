import random
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.patches import RegularPolygon, Circle, Rectangle

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
    styles = [f"Neo-{parent_name}", f"The {parent_name} Horde", f"{parent_name} Dominion", f"Free {parent_name}", f"{parent_name} Rebels"]
    return random.choice(styles)

def generate_dynasty_name(parent_name):
    styles = [f"The {parent_name} Empire", f"Kingdom of {parent_name}", f"{parent_name} Dominion", f"New {parent_name}", f"The Grand {parent_name}"]
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

# ---------------- Drawing Functions ---------------- #
def draw_hex(ax,q,r,facecolor,border="k",size=1,alpha=0.8,linewidth=1.0):
    x = size*(3**0.5*q + (3**0.5)/2*r)
    y = size*(3/2*r)
    hex_patch = RegularPolygon((x,y),numVertices=6,radius=size/1.1,orientation=0,
                               facecolor=facecolor, edgecolor=border, alpha=alpha, linewidth=linewidth)
    ax.add_patch(hex_patch)
    return x,y

def draw_resource(ax,q,r,color):
    x = 1*(3**0.5*q + (3**0.5)/2*r)
    y = 1*(3/2*r)
    ax.add_patch(Circle((x,y),radius=0.2,color=color,alpha=0.9))

# ---------------- Simulation ---------------- #
def simulate_hex(names,years=60,map_radius=10):
    terrain = {}
    for q in range(-map_radius,map_radius+1):
        for r in range(-map_radius,map_radius+1):
            if abs(q+r)>map_radius: continue
            terrain[(q,r)] = random.choices(list(TERRAINS.keys()),weights=[0.4,0.15,0.2,0.15,0.1])[0]

    resources = {}
    for h,t in terrain.items():
        if t=="water": continue
        if random.random()<0.25: resources[h]=random.choice(list(RESOURCES.keys()))

    starts = random.sample(list(terrain.keys()), len(names))
    civs = [Civilization(n, q, r) for n, (q, r) in zip(names, starts)]
    world = {list(c.hexes)[0]: c.name for c in civs}  # FIXED: no pop
    # No need to add again

    fig,ax = plt.subplots(figsize=(14,14))
    def update(frame):
        ax.clear()
        ax.set_title(f"Year {frame}",fontsize=18)
        ax.set_aspect("equal")
        ax.axis("off")
        alive = [c for c in civs if c.alive]
        for civ in alive: civ.step(alive,world,terrain,resources)

        # Terrain
        for (q,r),t in terrain.items(): draw_hex(ax,q,r,TERRAINS[t]["color"],alpha=0.4)

        # Resources
        for (q,r),res in resources.items(): draw_resource(ax,q,r,RESOURCES[res]["color"])

        # Civs & borders
        for civ in alive:
            for h in civ.hexes:
                draw_hex(ax,h[0],h[1],civ.color,alpha=0.85,linewidth=1.5)
                for nq,nr in hex_neighbors(*h):
                    neighbor = world.get((nq,nr))
                    if neighbor:
                        if neighbor in civ.allies: draw_hex(ax,h[0],h[1],facecolor='none',border='green',alpha=0.7,linewidth=2)
                        elif neighbor in civ.enemies: draw_hex(ax,h[0],h[1],facecolor='none',border='red',alpha=0.7,linewidth=2)

        # Cultural influence
        for (q,r),inf in cultural_map.items():
            if not inf: continue
            dominant = max(inf,key=inf.get)
            strength = min(0.5,inf[dominant]/10)
            color = next((c.color for c in civs if c.name==dominant),"gray")
            draw_hex(ax,q,r,color,alpha=strength)

        # Corner legend & stats
        ax.add_patch(Rectangle((map_radius*1.5,-map_radius*1.5),4,3,facecolor='white',alpha=0.8,edgecolor='black'))
        for idx,c in enumerate(alive):
            ax.add_patch(Rectangle((map_radius*1.55, -map_radius*1.45-0.25*idx),0.3,0.2,facecolor=c.color,edgecolor='black'))
            ax.text(map_radius*1.9,-map_radius*1.35-0.25*idx,f"{c.name} P:{c.population} S:{int(c.stability*100)} M:{int(c.military*100)}",fontsize=9)

        # Event pop-ups
        for i,(evt,ttl) in enumerate(list(event_queue)):
            ax.text(-map_radius*1.8, map_radius*1.2 - i*0.3, evt, fontsize=12, color='darkred', bbox=dict(facecolor='white',alpha=0.6))
            event_queue[i] = (evt, ttl-1)
        while event_queue and event_queue[0][1]<=0: event_queue.pop(0)

    ani = animation.FuncAnimation(fig,update,frames=years,interval=400,repeat=False)
    plt.show()

    print("\n📜 History Log:")
    for e in history_log: print(" -",e)

# ---------------- Run Simulation ---------------- #
if __name__=="__main__":
    civ_names = [generate_civ_name() for _ in range(6)]
    simulate_hex(civ_names,years=50,map_radius=10)
