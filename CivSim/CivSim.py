import random
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

    def step(self,civs,world,terrain,resources):
        if not self.alive: return
        growth_factor=sum(TERRAINS[terrain.get(h,"plains")]["growth"] for h in self.hexes)/len(self.hexes)
        self.population+=int(random.gauss(self.stability*5*growth_factor,6))
        self.stability-=max(0,len(self.hexes)-10)*0.005
        self.attempt_expansion(world,terrain)
        self.maybe_rebellion(civs,world)
        self.maybe_overthrow(civs,world)
        self.spread_culture()
        self.trade(civs)
        self.develop_tech()
        self.climate_event()
        if self.population<=0 or self.stability<=0.05:
            for h in self.hexes: del world[h]
            self.hexes.clear()
            self.alive=False
            history_log.append(f"💀 {self.name} collapsed")

    # ---------------- Expansion ---------------- #
    def attempt_expansion(self,world,terrain):
        attempts=max(1,int(self.military*10))
        for _ in range(attempts):
            if not self.hexes: break
            origin=random.choice(list(self.hexes))
            for nq,nr in hex_neighbors(*origin):
                ttype=terrain.get((nq,nr),"plains")
                if ttype=="water" or (nq,nr) in world: continue
                if random.random()<min(1.0,self.military*TERRAINS[ttype]["growth"]):
                    self.hexes.add((nq,nr))
                    world[(nq,nr)]=self.name
                    self.moving_units.append({"from":origin,"to":(nq,nr),"progress":0.0})
                    break

    # ---------------- Culture ---------------- #
    def spread_culture(self):
        for h in self.hexes:
            if h not in cultural_map: cultural_map[h]={}
            cultural_map[h][self.name]=cultural_map[h].get(self.name,0)+self.culture
            for nq,nr in hex_neighbors(*h):
                if (nq,nr) not in cultural_map: cultural_map[(nq,nr)]={}
                cultural_map[(nq,nr)][self.name]=cultural_map[(nq,nr)].get(self.name,0)+self.culture*0.1

    def trade(self,civs): pass
    def develop_tech(self): self.culture+=0.005*random.random()
    def climate_event(self):
        for h in self.hexes:
            if random.random()<0.01:
                disaster_type=random.choice(["flood","drought","plague","volcano"])
                active_disasters[h]=(disaster_type,3)
                history_log.append(f"{self.name} suffered {disaster_type} at {h}")

    def maybe_rebellion(self,civs,world):
        if random.random()<0.005 and self.population>100:
            name=generate_splinter_name(self.name)
            nq,nr=random.choice(list(self.hexes))
            new_civ=Civilization(name,nq,nr,trait=random.choice(TRAITS),parent=self.name)
            civs.append(new_civ)
            self.population=int(self.population*0.7)
            history_log.append(f"⚔️ {new_civ.name} rebelled from {self.name}")

    def maybe_overthrow(self,civs,world):
        if random.random()<0.002 and self.population>150:
            old_name=self.name
            self.name=generate_dynasty_name(self.name)
            history_log.append(f"👑 {old_name} dynasty overthrown, new name: {self.name}")

# ---------------- Map Generation ---------------- #
def generate_terrain(map_radius):
    terrain={}
    for q in range(-map_radius,map_radius+1):
        for r in range(-map_radius,map_radius+1):
            if -map_radius<=q+r<=map_radius:
                terrain[(q,r)]=random.choices(list(TERRAINS.keys()),weights=[30,10,10,10,10,5,5,5,5,10])[0]
    return terrain

def generate_resources(terrain,map_radius):
    resources={}
    for h,t in terrain.items():
        for res,ch in RESOURCE_CHANCES.get(t,{}).items():
            if random.random()<ch: resources[h]=res; break
    return resources

# ---------------- Hex to Pixel ---------------- #
def hex_to_pixel(q,r,size=1.0):
    x=size*3/2*q
    y=size*(3**0.5*(r+q/2))
    return x,y

def draw_hex(ax,q,r,color="#ffffff",alpha=1.0,linewidth=1.0,size=1.0):
    x,y=hex_to_pixel(q,r,size)
    hex_patch=RegularPolygon((x,y),numVertices=6,radius=size*0.95,orientation=0,
                             facecolor=color,edgecolor="black",linewidth=linewidth,alpha=alpha)
    ax.add_patch(hex_patch)

# ---------------- (Other drawing functions adapted for size) ---------------- #
# Terrain symbols, resources, overlays, moving units, disasters, trade, legends, charts...

# ---------------- Simulation Setup ---------------- #
map_radius=10
size=1.0
terrain=generate_terrain(map_radius)
resources=generate_resources(terrain,map_radius)
world={}
civs=[Civilization(generate_civ_name(),0,0), Civilization(generate_civ_name(),3,-2)]
for civ in civs:
    for h in civ.hexes: world[h]=civ.name

fig=plt.figure(figsize=(16,8))
gs=GridSpec(1,2,width_ratios=[3,1])
ax_map=fig.add_subplot(gs[0])
ax_chart=fig.add_subplot(gs[1])

# Axes limits to fit all hexes
ax_map.set_xlim(-map_radius*size*2,map_radius*size*2)
ax_map.set_ylim(-map_radius*size*2,map_radius*size*2)
ax_map.set_aspect('equal')
ax_map.axis('off')

# ---------------- Animation Loop ---------------- #
def draw_terrain_symbols(ax, terrain, size=1.0):
    for h, t in terrain.items():
        x, y = hex_to_pixel(*h, size)
        ax.text(x, y + 0.3*size, TERRAINS[t]["symbol"], ha='center', va='center', fontsize=10)

def draw_resources_on_hex(ax, resources, size=1.0):
    for h, res in resources.items():
        x, y = hex_to_pixel(*h, size)
        ax.text(x + 0.35*size, y + 0.35*size, res[0].upper(), ha='center', va='center', fontsize=6, color=RESOURCES[res]["color"], weight='bold')

def draw_hex_overlays(ax, civ, resources, size=1.0):
    for h in civ.hexes:
        x, y = hex_to_pixel(*h, size)
        ax.text(x, y, str(int(civ.military*100)), ha='center', va='center', fontsize=8, color="red", weight='bold')
        ax.text(x, y - 0.35*size, str(civ.population), ha='center', va='center', fontsize=6)
        ax.text(x, y + 0.35*size, f"{int(civ.stability*100)}", ha='center', va='center', fontsize=6)
        if h in resources:
            res = resources[h]
            ax.text(x + 0.5*size, y + 0.5*size, res[0].upper(), ha='center', va='center', fontsize=6, color=RESOURCES[res]["color"])

def draw_moving_units(ax, civ, size=1.0, dt=0.2):
    finished=[]
    for i, move in enumerate(civ.moving_units):
        fx, fy = move["from"]
        tx, ty = move["to"]
        x = fx + (tx-fx)*move["progress"]
        y = fy + (ty-fy)*move["progress"]
        x_draw, y_draw = hex_to_pixel(x, y, size)
        ax.add_patch(Circle((x_draw, y_draw), radius=0.3*size, color=civ.color, alpha=0.8))
        move["progress"] += dt
        if move["progress"] >= 1.0: finished.append(i)
    for i in reversed(finished): civ.moving_units.pop(i)

def draw_disasters(ax, size=1.0):
    finished=[]
    for h, (dtype, turns) in active_disasters.items():
        x, y = hex_to_pixel(*h, size)
        icons = {"flood":"🌊","drought":"🔥","plague":"☣️","volcano":"🌋"}
        ax.text(x, y, icons[dtype], ha='center', va='center', fontsize=10)
        active_disasters[h] = (dtype, turns-1)
        if turns-1 <= 0: finished.append(h)
    for h in finished: del active_disasters[h]

def draw_trade_routes(ax, civs, size=1.0):
    for civ in civs:
        if not civ.alive: continue
        for partner in civs:
            if partner.name==civ.name or not partner.alive: continue
            if civ.name < partner.name:
                if civ.trait in ["merchant","peaceful"] and partner.trait in ["merchant","peaceful"]:
                    q1,r1=random.choice(list(civ.hexes))
                    q2,r2=random.choice(list(partner.hexes))
                    x1,y1=hex_to_pixel(q1,r1,size)
                    x2,y2=hex_to_pixel(q2,r2,size)
                    ax.plot([x1,x2],[y1,y2], linestyle="dotted", color="purple", alpha=0.5, linewidth=1)

def create_legend(ax):
    terrain_patches=[Patch(color=TERRAINS[t]["color"],label=f"{t} {TERRAINS[t].get('symbol','')}") for t in TERRAINS]
    resource_patches=[Patch(color=RESOURCES[r]["color"],label=f"{r[0].upper()} ({r})") for r in RESOURCES]
    military_patch=Line2D([],[],color='red',marker='o',linestyle='',markersize=8,label="Military")
    trade_line=Line2D([],[],color='purple',linestyle='dotted',label="Trade Routes")
    ax.legend(handles=terrain_patches+resource_patches+[military_patch,trade_line], loc='upper left', fontsize=8, framealpha=0.9)

def draw_civ_info(ax,civs,max_hex_x,max_hex_y):
    text_y = max_hex_y
    for civ in civs:
        if not civ.alive: continue
        text = (f"{civ.name} | Pop:{civ.population} | Mil:{int(civ.military*100)} "
                f"| Stab:{int(civ.stability*100)} | Eco:{int(civ.economy*100)} | Cul:{int(civ.culture*100)}")
        ax.text(max_hex_x*1.05, text_y, text, va='top', fontsize=8, color=civ.color)
        text_y -= 2.0

def draw_stat_charts(ax,civs):
    ax.clear()
    names=[c.name for c in civs if c.alive]
    populations=[c.population for c in civs if c.alive]
    military=[c.military*100 for c in civs if c.alive]
    stability=[c.stability*100 for c in civs if c.alive]
    economy=[c.economy*100 for c in civs if c.alive]
    culture=[c.culture*100 for c in civs if c.alive]
    ax.barh(names,populations,color='lightgreen',label="Population")
    ax.barh(names,military,left=populations,color='red',label="Military")
    ax.barh(names,stability,left=[p+m for p,m in zip(populations,military)],color='blue',label="Stability")
    ax.barh(names,economy,left=[p+m+s for p,m,s in zip(populations,military,stability)],color='gold',label="Economy")
    ax.barh(names,culture,left=[p+m+s+e for p,m,s,e in zip(populations,military,stability,economy)],
            color='purple',label="Culture")
    ax.set_xlabel("Stats (stacked)")
    ax.legend(loc='upper right')

# ---------------- Update function ---------------- #
# ---------------- Pre-draw static map ---------------- #
fig=plt.figure(figsize=(16,8))
gs=GridSpec(1,2,width_ratios=[3,1])
ax_map=fig.add_subplot(gs[0])
ax_chart=fig.add_subplot(gs[1])

# Axes limits to fit all hexes
ax_map.set_xlim(-map_radius*size*2,map_radius*size*2)
ax_map.set_ylim(-map_radius*size*2,map_radius*size*2)
ax_map.set_aspect('equal')
ax_map.axis('off')

# Pre-draw terrain hexes
for h,t in terrain.items():
    draw_hex(ax_map,h[0],h[1],TERRAINS[t]["color"],alpha=1.0,linewidth=1.0,size=size)

# Pre-draw terrain symbols
for h,t in terrain.items():
    x, y = hex_to_pixel(*h, size)
    ax_map.text(x, y + 0.3*size, TERRAINS[t]["symbol"], ha='center', va='center', fontsize=int(10*size))

# Pre-draw static resources
for h,res in resources.items():
    x, y = hex_to_pixel(*h, size)
    ax_map.text(x + 0.35*size, y + 0.35*size, res[0].upper(), ha='center', va='center',
                fontsize=int(6*size), color=RESOURCES[res]["color"], weight='bold')

# Draw static legend once
create_legend(ax_map)

# ---------------- Dynamic elements containers ---------------- #
unit_patches = []
disaster_texts = []
trade_lines = []

# ---------------- Update function ---------------- #
def update(frame):
    # Remove previous dynamic elements
    for patch in unit_patches: patch.remove()
    unit_patches.clear()
    
    for txt in disaster_texts: txt.remove()
    disaster_texts.clear()
    
    for line in trade_lines: line.remove()
    trade_lines.clear()

    alive=[c for c in civs if c.alive]
    for civ in alive:
        civ.step(civs, world, terrain, resources)
        # Draw civ hexes
        for h in civ.hexes:
            draw_hex(ax_map,h[0],h[1],civ.color,alpha=0.85,linewidth=1.5,size=size)
        # Draw overlays (population, military, stability)
        for h in civ.hexes:
            x, y = hex_to_pixel(*h, size)
            txt1 = ax_map.text(x, y, str(int(civ.military*100)), ha='center', va='center', fontsize=int(8*size), color="red", weight='bold')
            txt2 = ax_map.text(x, y - 0.35*size, str(civ.population), ha='center', va='center', fontsize=int(6*size))
            txt3 = ax_map.text(x, y + 0.35*size, f"{int(civ.stability*100)}", ha='center', va='center', fontsize=int(6*size))
            unit_patches.extend([txt1, txt2, txt3])

        # Draw moving units
        finished=[]
        for i, move in enumerate(civ.moving_units):
            fx, fy = hex_to_pixel(*move["from"], size)
            tx, ty = hex_to_pixel(*move["to"], size)
            x = fx + (tx-fx)*move["progress"]
            y = fy + (ty-fy)*move["progress"]
            circle = ax_map.add_patch(Circle((x, y), radius=0.3*size, color=civ.color, alpha=0.8))
            unit_patches.append(circle)
            move["progress"] += 0.2
            if move["progress"] >= 1.0: finished.append(i)
        for i in reversed(finished): civ.moving_units.pop(i)

    # Draw disasters
    finished_disasters=[]
    for h, (dtype, turns) in active_disasters.items():
        x, y = hex_to_pixel(*h, size)
        icons = {"flood":"🌊","drought":"🔥","plague":"☣️","volcano":"🌋"}
        txt = ax_map.text(x, y, icons[dtype], ha='center', va='center', fontsize=int(10*size))
        disaster_texts.append(txt)
        active_disasters[h] = (dtype, turns-1)
        if turns-1 <= 0: finished_disasters.append(h)
    for h in finished_disasters: del active_disasters[h]

    # Draw trade routes dynamically
    for civ in alive:
        for partner in alive:
            if partner.name==civ.name: continue
            if civ.name < partner.name:
                if civ.trait in ["merchant","peaceful"] and partner.trait in ["merchant","peaceful"]:
                    q1,r1=random.choice(list(civ.hexes))
                    q2,r2=random.choice(list(partner.hexes))
                    x1,y1=hex_to_pixel(q1,r1,size)
                    x2,y2=hex_to_pixel(q2,r2,size)
                    line, = ax_map.plot([x1,x2],[y1,y2], linestyle="dotted", color="purple", alpha=0.5, linewidth=1)
                    trade_lines.append(line)

    # Draw civ info on side
    ax_map.texts = [t for t in ax_map.texts if t not in unit_patches+disaster_texts]  # remove old info
    draw_civ_info(ax_map, alive, max_hex_x, max_hex_y)

    # Update stats chart
    draw_stat_charts(ax_chart, alive)

ani = animation.FuncAnimation(fig, update, frames=50, interval=1000)
plt.show()
