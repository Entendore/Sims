"""
Advanced Ecosystem Simulator
=============================
A comprehensive predator-prey evolution simulator combining the best of
three prior projects with major improvements and new features.

Combined features from originals:
  - Lineage tracking with unique colors (main.py)
  - Smart decision-making with reward evaluation (main2.py)
  - Multi-tier food chain: Plants → Herbivores → Predators → Apex (main3.py)
  - Trait evolution tracking (all)

New features & improvements:
  - Full Genome system with crossover + Gaussian mutation
  - Environmental seasons (Spring/Summer/Autumn/Winter) and terrain patches
  - Camouflage vs detection mechanic
  - Cooperation & pack-warning behavior
  - Shannon Diversity Index tracking
  - Trait-space scatter (speed × perception)
  - Energy distribution histograms
  - Interactive pause/play + speed slider
  - Real-time event log
  - Dark-themed multi-panel dashboard
  - Spatial hash for faster neighbor lookups
  - Configurable via single Config class
"""

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.widgets import Slider, Button
import numpy as np
import random
import math
import colorsys
from collections import defaultdict


# ================================================================
#  CONFIGURATION
# ================================================================
class Config:
    # World dimensions
    WORLD_W = 120
    WORLD_H = 90

    # Initial populations
    NUM_PLANTS      = 120
    NUM_HERBIVORES  = 40
    NUM_PREDATORS   = 15
    NUM_APEX        = 4

    # Starting energy
    PLANT_ENERGY        = 15
    HERB_INITIAL_ENERGY = 50
    PRED_INITIAL_ENERGY = 60
    APEX_INITIAL_ENERGY = 80

    # Reproduction energy thresholds
    HERB_REPRO_ENERGY = 80
    PRED_REPRO_ENERGY = 100
    APEX_REPRO_ENERGY = 130

    # Genetics
    MUTATION_RATE     = 0.15
    MUTATION_STRENGTH = 0.20
    CROSSOVER_RATE    = 0.50

    # Environment
    PLANT_REGROWTH  = 0.07
    SEASON_LENGTH   = 120      # frames per season
    TERRAIN_PATCHES = 10
    MAX_PLANTS      = 350

    # Population cap per species
    MAX_POP = 400

    # Animation
    MAX_STEPS     = 3000
    ANIM_INTERVAL = 60        # ms between frames

    # Trait bounds
    SPEED_RANGE       = (0.5, 5.0)
    PERCEPTION_RANGE  = (3.0, 25.0)
    SIZE_RANGE        = (0.5, 3.0)
    METABOLISM_RANGE  = (0.3, 2.0)
    AGGRESSION_RANGE  = (0.0, 2.0)
    CAMOUFLAGE_RANGE  = (0.0, 1.0)
    COOPERATION_RANGE = (0.0, 1.0)
    AGILITY_RANGE     = (0.3, 2.0)


cfg = Config()


# ================================================================
#  GENOME SYSTEM  –  gene-level mutation + sexual crossover
# ================================================================
class Gene:
    """A single continuous gene with clamped bounds."""
    __slots__ = ("value", "lo", "hi", "name")

    def __init__(self, value: float, lo: float, hi: float, name: str = ""):
        self.value = value
        self.lo = lo
        self.hi = hi
        self.name = name

    def mutate(self):
        if random.random() < cfg.MUTATION_RATE:
            sigma = cfg.MUTATION_STRENGTH * (self.hi - self.lo)
            self.value = max(self.lo, min(self.hi, self.value + random.gauss(0, sigma)))

    def copy(self):
        return Gene(self.value, self.lo, self.hi, self.name)


class Genome:
    """Collection of genes – supports mutation and crossover."""

    GENE_DEFS = {                          # name → (lo, hi)
        "speed":       cfg.SPEED_RANGE,
        "perception":  cfg.PERCEPTION_RANGE,
        "size":        cfg.SIZE_RANGE,
        "metabolism":  cfg.METABOLISM_RANGE,
        "aggression":  cfg.AGGRESSION_RANGE,
        "camouflage":  cfg.CAMOUFLAGE_RANGE,
        "cooperation": cfg.COOPERATION_RANGE,
        "agility":     cfg.AGILITY_RANGE,
    }

    def __init__(self):
        self.genes: dict[str, Gene] = {}

    def add(self, name: str, value: float):
        lo, hi = self.GENE_DEFS[name]
        self.genes[name] = Gene(value, lo, hi, name)

    def get(self, name: str) -> float:
        return self.genes[name].value

    def mutate(self):
        for g in self.genes.values():
            g.mutate()

    def copy(self) -> "Genome":
        gn = Genome()
        for n, g in self.genes.items():
            gn.genes[n] = g.copy()
        return gn

    @staticmethod
    def crossover(a: "Genome", b: "Genome") -> "Genome":
        child = Genome()
        for n in a.genes:
            src = a.genes[n] if random.random() < 0.5 else b.genes[n]
            child.genes[n] = src.copy()
        return child

    def distance(self, other: "Genome") -> float:
        total = 0.0
        for n in self.genes:
            g1, g2 = self.genes[n], other.genes[n]
            span = g1.hi - g1.lo
            if span > 0:
                total += abs(g1.value - g2.value) / span
        return total / len(self.genes)


# ---- factory helpers ----
def _rand(lo, hi):
    return random.uniform(lo, hi)

def herbivore_genome() -> Genome:
    g = Genome()
    g.add("speed",       _rand(1.0, 3.0))
    g.add("perception",  _rand(8, 15))
    g.add("size",        _rand(0.8, 1.5))
    g.add("metabolism",  _rand(0.5, 1.0))
    g.add("aggression",  _rand(0.0, 0.3))
    g.add("camouflage",  _rand(0.2, 0.6))
    g.add("cooperation", _rand(0.0, 0.5))
    g.add("agility",     _rand(0.8, 1.5))
    return g

def predator_genome() -> Genome:
    g = Genome()
    g.add("speed",       _rand(2.0, 4.0))
    g.add("perception",  _rand(10, 20))
    g.add("size",        _rand(1.2, 2.0))
    g.add("metabolism",  _rand(0.8, 1.5))
    g.add("aggression",  _rand(0.5, 1.5))
    g.add("camouflage",  _rand(0.0, 0.3))
    g.add("cooperation", _rand(0.0, 0.3))
    g.add("agility",     _rand(0.5, 1.2))
    return g

def apex_genome() -> Genome:
    g = Genome()
    g.add("speed",       _rand(2.5, 4.5))
    g.add("perception",  _rand(12, 22))
    g.add("size",        _rand(2.0, 3.0))
    g.add("metabolism",  _rand(1.0, 2.0))
    g.add("aggression",  _rand(1.0, 2.0))
    g.add("camouflage",  _rand(0.0, 0.15))
    g.add("cooperation", _rand(0.0, 0.2))
    g.add("agility",     _rand(0.4, 1.0))
    return g


# ================================================================
#  ENVIRONMENT  –  terrain + seasons
# ================================================================
class TerrainPatch:
    __slots__ = ("x", "y", "r", "kind")
    def __init__(self, x, y, r, kind):
        self.x, self.y, self.r, self.kind = x, y, r, kind


class Environment:
    SEASON_NAMES  = ("Spring", "Summer", "Autumn", "Winter")
    SEASON_EMOJI  = ("\u2022", "\u2600", "\u2767", "\u2744")
    SEASON_COLORS = ("#90EE90", "#FFD700", "#FF8C00", "#87CEEB")

    SPEED_MOD  = {"forest": 0.7, "water": 0.4, "plains": 1.0, "desert": 0.85}
    GROWTH_MOD = {"forest": 1.5, "water": 0.2, "plains": 1.0, "desert": 0.3}
    SEASON_GROWTH = (1.3, 1.0, 0.7, 0.25)

    def __init__(self):
        self.season = 0
        self.timer  = 0
        self.patches: list[TerrainPatch] = []
        kinds = list(self.SPEED_MOD.keys())
        for _ in range(cfg.TERRAIN_PATCHES):
            self.patches.append(TerrainPatch(
                random.randint(10, cfg.WORLD_W - 10),
                random.randint(10, cfg.WORLD_H - 10),
                random.randint(8, 22),
                random.choice(kinds),
            ))

    def terrain_at(self, x, y) -> str:
        for p in self.patches:
            if math.hypot(x - p.x, y - p.y) < p.r:
                return p.kind
        return "plains"

    def speed_mod(self, x, y) -> float:
        return self.SPEED_MOD.get(self.terrain_at(x, y), 1.0)

    def plant_growth(self, x, y) -> float:
        return self.GROWTH_MOD.get(self.terrain_at(x, y), 1.0) * self.SEASON_GROWTH[self.season]

    def tick(self):
        self.timer += 1
        if self.timer >= cfg.SEASON_LENGTH:
            self.timer = 0
            self.season = (self.season + 1) % 4

    @property
    def name(self):
        return self.SEASON_NAMES[self.season]

    @property
    def emoji(self):
        return self.SEASON_EMOJI[self.season]

    @property
    def color(self):
        return self.SEASON_COLORS[self.season]


# ================================================================
#  SPATIAL HASH  –  O(n) neighbor queries instead of O(n²)
# ================================================================
class SpatialHash:
    def __init__(self, cell_size=20):
        self.cs = cell_size
        self.buckets: dict[tuple, list] = defaultdict(list)

    def clear(self):
        self.buckets.clear()

    def _key(self, x, y):
        return (int(x // self.cs), int(y // self.cs))

    def insert(self, obj):
        self.buckets[self._key(obj.x, obj.y)].append(obj)

    def query(self, x, y, radius):
        results = []
        cr = int(radius // self.cs) + 1
        cx, cy = int(x // self.cs), int(y // self.cs)
        r2 = radius * radius
        for dx in range(-cr, cr + 1):
            for dy in range(-cr, cr + 1):
                for obj in self.buckets.get((cx + dx, cy + dy), ()):
                    if (obj.x - x) ** 2 + (obj.y - y) ** 2 <= r2:
                        results.append(obj)
        return results


# ================================================================
#  ENTITY CLASSES
# ================================================================
class Plant:
    __slots__ = ("x", "y", "energy", "age")

    def __init__(self, x=None, y=None):
        self.x = x if x is not None else random.randint(0, cfg.WORLD_W - 1)
        self.y = y if y is not None else random.randint(0, cfg.WORLD_H - 1)
        self.energy = cfg.PLANT_ENERGY
        self.age = 0


_next_id = 0

class Organism:
    __slots__ = ("id", "x", "y", "genome", "energy", "species",
                 "age", "alive", "lineage_id", "generation")

    def __init__(self, x, y, genome, energy, species):
        global _next_id
        _next_id += 1
        self.id = _next_id
        self.x, self.y = float(x), float(y)
        self.genome = genome
        self.energy = energy
        self.species = species        # "herbivore" | "predator" | "apex"
        self.age = 0
        self.alive = True
        self.lineage_id = random.randint(0, 99999)
        self.generation = 0

    # shorthand trait accessors
    @property
    def speed(self):       return self.genome.get("speed")
    @property
    def perception(self):  return self.genome.get("perception")
    @property
    def size(self):        return self.genome.get("size")
    @property
    def metabolism(self):  return self.genome.get("metabolism")
    @property
    def aggression(self):  return self.genome.get("aggression")
    @property
    def camouflage(self):  return self.genome.get("camouflage")
    @property
    def cooperation(self): return self.genome.get("cooperation")
    @property
    def agility(self):     return self.genome.get("agility")

    def dist(self, other):
        return math.hypot(self.x - other.x, self.y - other.y)

    # --- movement helpers ---
    def _clamp(self):
        self.x = max(0.0, min(float(cfg.WORLD_W - 1), self.x))
        self.y = max(0.0, min(float(cfg.WORLD_H - 1), self.y))

    def move_toward(self, tx, ty, env):
        dx, dy = tx - self.x, ty - self.y
        d = math.hypot(dx, dy)
        if d > 0:
            s = min(self.speed * env.speed_mod(self.x, self.y), d)
            self.x += dx / d * s
            self.y += dy / d * s
        self._clamp()

    def move_away(self, tx, ty, env):
        dx, dy = self.x - tx, self.y - ty
        d = math.hypot(dx, dy)
        if d > 0:
            s = self.speed * env.speed_mod(self.x, self.y)
            self.x += dx / d * s
            self.y += dy / d * s
        else:
            a = random.uniform(0, 2 * math.pi)
            s = self.speed * env.speed_mod(self.x, self.y)
            self.x += math.cos(a) * s
            self.y += math.sin(a) * s
        self._clamp()

    def wander(self, env):
        a = random.uniform(0, 2 * math.pi)
        s = self.speed * env.speed_mod(self.x, self.y) * 0.5
        self.x += math.cos(a) * s
        self.y += math.sin(a) * s
        self._clamp()

    def metabolic_cost(self):
        return self.metabolism * (0.3 * self.speed + 0.2 * self.size + 0.05 * self.perception)

    def can_reproduce(self):
        return self.energy >= {"herbivore": cfg.HERB_REPRO_ENERGY,
                               "predator":  cfg.PRED_REPRO_ENERGY,
                               "apex":      cfg.APEX_REPRO_ENERGY}[self.species]

    def reproduce(self, mate=None):
        if not self.can_reproduce():
            return None
        self.energy *= 0.5
        child_genome = Genome.crossover(self.genome, mate.genome) \
                        if mate and random.random() < cfg.CROSSOVER_RATE \
                        else self.genome.copy()
        child_genome.mutate()
        init_e = {"herbivore": cfg.HERB_INITIAL_ENERGY,
                  "predator":  cfg.PRED_INITIAL_ENERGY,
                  "apex":      cfg.APEX_INITIAL_ENERGY}[self.species] * 0.4
        child = Organism(
            max(0, min(cfg.WORLD_W - 1, self.x + random.uniform(-3, 3))),
            max(0, min(cfg.WORLD_H - 1, self.y + random.uniform(-3, 3))),
            child_genome, init_e, self.species,
        )
        child.lineage_id = self.lineage_id
        child.generation = self.generation + 1
        return child


# ================================================================
#  ECOSYSTEM  –  main simulation driver
# ================================================================
class Ecosystem:
    def __init__(self):
        self.env = Environment()
        self.plants: list[Plant] = []
        self.orgs: dict[str, list[Organism]] = {
            "herbivore": [], "predator": [], "apex": []}
        self.shash = SpatialHash(cell_size=20)
        self.step = 0
        self.events: list[str] = []
        self.history = defaultdict(list)

        # initial populations
        for _ in range(cfg.NUM_PLANTS):
            self.plants.append(Plant())
        for _ in range(cfg.NUM_HERBIVORES):
            self.orgs["herbivore"].append(Organism(
                random.randint(0, cfg.WORLD_W-1), random.randint(0, cfg.WORLD_H-1),
                herbivore_genome(), cfg.HERB_INITIAL_ENERGY, "herbivore"))
        for _ in range(cfg.NUM_PREDATORS):
            self.orgs["predator"].append(Organism(
                random.randint(0, cfg.WORLD_W-1), random.randint(0, cfg.WORLD_H-1),
                predator_genome(), cfg.PRED_INITIAL_ENERGY, "predator"))
        for _ in range(cfg.NUM_APEX):
            self.orgs["apex"].append(Organism(
                random.randint(0, cfg.WORLD_W-1), random.randint(0, cfg.WORLD_H-1),
                apex_genome(), cfg.APEX_INITIAL_ENERGY, "apex"))

    # ---------- spatial hash rebuild ----------
    def _rebuild_hash(self):
        self.shash.clear()
        for lst in self.orgs.values():
            for o in lst:
                if o.alive:
                    self.shash.insert(o)

    # ---------- one simulation tick ----------
    def tick(self):
        self.step += 1
        self.events.clear()
        self.env.tick()
        self._rebuild_hash()
        self._regrow_plants()
        self._update_herbivores()
        self._update_predators()
        self._update_apex()
        # remove dead
        for sp in self.orgs:
            self.orgs[sp] = [o for o in self.orgs[sp] if o.alive]
        # population cap
        for sp in self.orgs:
            if len(self.orgs[sp]) > cfg.MAX_POP:
                self.orgs[sp].sort(key=lambda o: o.energy, reverse=True)
                self.orgs[sp] = self.orgs[sp][:cfg.MAX_POP]
        self._record()

    # ---------- plant regrowth ----------
    def _regrow_plants(self):
        rate = cfg.PLANT_REGROWTH * self.env.SEASON_GROWTH[self.env.season]
        n_new = int(len(self.plants) * rate)
        for _ in range(n_new):
            x = random.randint(0, cfg.WORLD_W - 1)
            y = random.randint(0, cfg.WORLD_H - 1)
            if random.random() < self.env.plant_growth(x, y):
                self.plants.append(Plant(x, y))
        # age & cull
        alive = []
        for p in self.plants:
            p.age += 1
            if p.age < 60:
                alive.append(p)
        self.plants = alive[:cfg.MAX_PLANTS]

    # ---------- herbivore AI ----------
    def _update_herbivores(self):
        babies = []
        for h in self.orgs["herbivore"]:
            if not h.alive:
                continue
            h.energy -= h.metabolic_cost()
            h.age += 1

            # perceive threats & food via spatial hash
            threats = [o for o in self.shash.query(h.x, h.y, h.perception * 1.5)
                       if o.species in ("predator", "apex") and o.alive]
            foods   = [p for p in self.plants
                       if math.hypot(p.x - h.x, p.y - h.y) < h.perception]
            friends = [o for o in self.shash.query(h.x, h.y, h.perception * 0.5)
                       if o.species == "herbivore" and o.id != h.id and o.alive]

            # decision: flee or forage
            fled = False
            if threats:
                nearest = min(threats, key=lambda t: h.dist(t))
                detect = 1.0 - h.camouflage * 0.7   # camouflage helps hide
                if random.random() < detect:
                    h.move_away(nearest.x, nearest.y, self.env)
                    fled = True
                    # cooperation: warn nearby friends
                    if h.cooperation > 0.3:
                        for f in friends[:3]:
                            f.move_away(nearest.x, nearest.y, self.env)

            if not fled:
                if foods:
                    target = min(foods, key=lambda f: math.hypot(f.x - h.x, f.y - h.y))
                    h.move_toward(target.x, target.y, self.env)
                else:
                    h.wander(self.env)

            # eat
            for p in self.plants[:]:
                if math.hypot(h.x - p.x, h.y - p.y) < h.size + 1.5:
                    h.energy += p.energy
                    self.plants.remove(p)
                    break

            # reproduce (with mate if cooperative)
            mate = None
            if h.cooperation > 0.5:
                for f in friends:
                    if f.can_reproduce():
                        mate = f; break
            if h.can_reproduce():
                child = h.reproduce(mate)
                if child:
                    babies.append(child)

            if h.energy <= 0:
                h.alive = False
                self.events.append(f"Herb starved ({h.x:.0f},{h.y:.0f})")

        self.orgs["herbivore"].extend(babies)

    # ---------- predator AI ----------
    def _update_predators(self):
        babies = []
        for p in self.orgs["predator"]:
            if not p.alive:
                continue
            p.energy -= p.metabolic_cost()
            p.age += 1

            prey_list = [o for o in self.shash.query(p.x, p.y, p.perception)
                         if o.species == "herbivore" and o.alive]
            apex_list = [o for o in self.shash.query(p.x, p.y, p.perception)
                         if o.species == "apex" and o.alive]
            friends   = [o for o in self.shash.query(p.x, p.y, p.perception * 0.5)
                         if o.species == "predator" and o.id != p.id and o.alive]

            # flee apex if low aggression
            fled = False
            if apex_list:
                nearest_apex = min(apex_list, key=lambda a: p.dist(a))
                if p.aggression < 1.0 and p.dist(nearest_apex) < p.perception * 0.7:
                    p.move_away(nearest_apex.x, nearest_apex.y, self.env)
                    fled = True

            if not fled:
                if prey_list:
                    # pick prey least able to hide
                    best, best_score = None, -1e9
                    for pr in prey_list:
                        detect = 1.0 - pr.camouflage * 0.5
                        score  = detect - p.dist(pr) * 0.05
                        if score > best_score:
                            best_score = score; best = pr
                    if best and (random.random() < (1.0 - best.camouflage * 0.5)
                                 or p.dist(best) < p.perception * 0.3):
                        p.move_toward(best.x, best.y, self.env)
                    else:
                        p.wander(self.env)
                else:
                    p.wander(self.env)

            # hunt – catch chance depends on speed vs agility
            for pr in self.orgs["herbivore"]:
                if pr.alive and p.dist(pr) < p.size + pr.size:
                    catch = min(1.0, (p.speed * p.aggression) /
                               (p.speed * p.aggression + pr.speed * pr.agility))
                    if random.random() < catch:
                        p.energy += pr.energy * 0.7
                        pr.alive = False
                        self.events.append(f"Pred caught herb ({p.x:.0f},{p.y:.0f})")
                        break

            # reproduce
            mate = None
            if p.cooperation > 0.5:
                for f in friends:
                    if f.can_reproduce():
                        mate = f; break
            if p.can_reproduce():
                child = p.reproduce(mate)
                if child:
                    babies.append(child)

            if p.energy <= 0:
                p.alive = False
                self.events.append(f"Pred starved ({p.x:.0f},{p.y:.0f})")

        self.orgs["predator"].extend(babies)

    # ---------- apex predator AI ----------
    def _update_apex(self):
        babies = []
        for a in self.orgs["apex"]:
            if not a.alive:
                continue
            a.energy -= a.metabolic_cost()
            a.age += 1

            pred_list = [o for o in self.shash.query(a.x, a.y, a.perception)
                         if o.species == "predator" and o.alive]
            herb_list = [o for o in self.shash.query(a.x, a.y, a.perception)
                         if o.species == "herbivore" and o.alive]

            if pred_list:
                target = min(pred_list, key=lambda t: a.dist(t))
                a.move_toward(target.x, target.y, self.env)
            elif herb_list and a.energy < 70:
                target = min(herb_list, key=lambda t: a.dist(t))
                a.move_toward(target.x, target.y, self.env)
            else:
                a.wander(self.env)

            # eat predators
            for pr in self.orgs["predator"]:
                if pr.alive and a.dist(pr) < a.size + pr.size:
                    catch = min(1.0, a.speed / (a.speed + pr.speed))
                    if random.random() < catch * a.aggression:
                        a.energy += pr.energy * 0.6
                        pr.alive = False
                        self.events.append(f"Apex caught pred ({a.x:.0f},{a.y:.0f})")
                        break
            # also eat herbivores opportunistically
            for h in self.orgs["herbivore"]:
                if h.alive and a.dist(h) < a.size + h.size:
                    a.energy += h.energy * 0.35
                    h.alive = False
                    break

            if a.can_reproduce():
                child = a.reproduce()
                if child:
                    babies.append(child)

            if a.energy <= 0:
                a.alive = False
                self.events.append(f"Apex starved ({a.x:.0f},{a.y:.0f})")

        self.orgs["apex"].extend(babies)

    # ---------- record history ----------
    def _record(self):
        for sp in ("herbivore", "predator", "apex"):
            self.history[f"{sp}_pop"].append(len(self.orgs[sp]))
            orgs = self.orgs[sp]
            for trait in ("speed", "perception", "size", "metabolism",
                          "aggression", "camouflage", "cooperation", "agility"):
                if orgs:
                    self.history[f"{sp}_{trait}"].append(
                        sum(getattr(o, trait) for o in orgs) / len(orgs))
                else:
                    self.history[f"{sp}_{trait}"].append(0)
        self.history["plant_pop"].append(len(self.plants))
        self.history["season"].append(self.env.season)
        # Shannon diversity
        total = sum(len(v) for v in self.orgs.values())
        H = 0
        if total > 0:
            for sp in self.orgs:
                p = len(self.orgs[sp]) / total
                if p > 0:
                    H -= p * math.log(p)
        self.history["diversity"].append(H)

    # ---------- quick stats ----------
    def stats(self):
        lines = []
        for sp, emoji in [("herbivore","🐰"),("predator","🦊"),("apex","🦁")]:
            n = len(self.orgs[sp])
            if n:
                avg_e = sum(o.energy for o in self.orgs[sp]) / n
                lines.append(f"{emoji} {sp}: {n}  avgE={avg_e:.0f}")
            else:
                lines.append(f"{emoji} {sp}: EXTINCT")
        lines.append(f"🌿 Plants: {len(self.plants)}")
        return "\n".join(lines)


# ================================================================
#  VISUALIZER  –  dark-themed multi-panel dashboard
# ================================================================
class Visualizer:
    # short labels for species
    SP = {"herbivore": ("herb", "#2ecc71", "o"),
          "predator":  ("pred", "#e74c3c", "^"),
          "apex":      ("apex", "#e67e22", "D")}

    def __init__(self, eco: Ecosystem):
        self.eco = eco
        self.paused = False
        self.lineage_clr = defaultdict(self._rnd_color)

        # ---- figure & grid ----
        self.fig = plt.figure(figsize=(19, 11))
        self.fig.patch.set_facecolor("#1a1a2e")
        gs = self.fig.add_gridspec(3, 4, hspace=0.38, wspace=0.32,
                                   left=0.04, right=0.98, top=0.93, bottom=0.08)

        self.ax_main       = self.fig.add_subplot(gs[0:2, 0:2])
        self.ax_pop        = self.fig.add_subplot(gs[0, 2])
        self.ax_speed      = self.fig.add_subplot(gs[0, 3])
        self.ax_perception = self.fig.add_subplot(gs[1, 2])
        self.ax_special    = self.fig.add_subplot(gs[1, 3])
        self.ax_energy     = self.fig.add_subplot(gs[2, 0])
        self.ax_diversity  = self.fig.add_subplot(gs[2, 1])
        self.ax_traitspace = self.fig.add_subplot(gs[2, 2])
        self.ax_log        = self.fig.add_subplot(gs[2, 3])

        all_ax = [self.ax_main, self.ax_pop, self.ax_speed, self.ax_perception,
                  self.ax_special, self.ax_energy, self.ax_diversity,
                  self.ax_traitspace, self.ax_log]
        for ax in all_ax:
            ax.set_facecolor("#16213e")
            ax.tick_params(colors="#bbb", labelsize=7)
            for sp in ax.spines.values():
                sp.set_color("#333366")

        self.fig.suptitle("🌿 Advanced Ecosystem Simulator",
                          fontsize=16, color="#e0e0e0", fontweight="bold")

        # ---- widgets ----
        ax_btn = self.fig.add_axes([0.42, 0.01, 0.07, 0.03])
        self.btn = Button(ax_btn, "⏸ Pause", color="#333366", hovercolor="#555588")
        self.btn.label.set_color("#e0e0e0")
        self.btn.on_clicked(self._toggle)

        ax_sl = self.fig.add_axes([0.54, 0.015, 0.14, 0.02])
        self.slider = Slider(ax_sl, "Speed", 1, 5, valinit=1, valstep=1, color="#4a90d9")
        self.slider.label.set_color("#e0e0e0")
        self.slider.valtext.set_color("#e0e0e0")

    @staticmethod
    def _rnd_color():
        return colorsys.hsv_to_rgb(random.random(),
                                   random.uniform(0.5, 1),
                                   random.uniform(0.7, 1))

    def _toggle(self, _):
        self.paused = not self.paused
        self.btn.label.set_text("▶ Play" if self.paused else "⏸ Pause")

    # ---- draw helpers ----
    def _draw_terrain(self, ax):
        clr = {"forest": "#1a4d1a", "water": "#1a3a5c",
               "plains": "#2d4a2d", "desert": "#5c4a1a"}
        alp = {"forest": 0.25, "water": 0.35, "plains": 0.12, "desert": 0.22}
        for p in self.eco.env.patches:
            ax.add_patch(plt.Circle((p.x, p.y), p.r,
                         color=clr.get(p.kind, "#2d4a2d"),
                         alpha=alp.get(p.kind, 0.15)))

    def _draw_main(self):
        ax = self.ax_main; ax.clear()
        ax.set_xlim(0, cfg.WORLD_W); ax.set_ylim(0, cfg.WORLD_H)
        ax.set_facecolor("#0d1117"); ax.set_xticks([]); ax.set_yticks([])
        self._draw_terrain(ax)
        # season border
        for sp in ax.spines.values():
            sp.set_color(self.eco.env.color); sp.set_linewidth(3)
        # plants
        if self.eco.plants:
            ax.scatter([p.x for p in self.eco.plants],
                       [p.y for p in self.eco.plants],
                       c="#2ecc71", s=6, alpha=0.45, marker="s", zorder=1)
        # organisms
        for sp, (_, clr, mk) in self.SP.items():
            orgs = self.eco.orgs[sp]
            if not orgs:
                continue
            xs = [o.x for o in orgs]
            ys = [o.y for o in orgs]
            sizes = [15 + o.size * 12 for o in orgs]
            alphas = [min(1, 0.4 + o.energy / 180) for o in orgs]
            colors = [self.lineage_clr[o.lineage_id] for o in orgs]
            for x, y, s, a, c in zip(xs, ys, sizes, alphas, colors):
                ax.scatter(x, y, c=[c], s=s, alpha=a, marker=mk,
                           edgecolors=clr, linewidths=0.4, zorder=3 + {"herbivore":0,"predator":1,"apex":2}[sp])
            # subtle perception circles for a few
            for o in orgs[:5]:
                if o.energy > 30:
                    ax.add_patch(plt.Circle((o.x, o.y), o.perception,
                                 fill=False, color=clr, alpha=0.04, lw=0.4))
        e = self.eco.env
        ax.set_title(
            f'{e.emoji} {e.name} | Step {self.eco.step} | '
            f'🌿{len(self.eco.plants)} '
            f'🐰{len(self.eco.orgs["herbivore"])} '
            f'🦊{len(self.eco.orgs["predator"])} '
            f'🦁{len(self.eco.orgs["apex"])}',
            color="#e0e0e0", fontsize=10, pad=5)

    def _line(self, ax, key, color, label, **kw):
        data = self.eco.history.get(key, [])
        if data:
            ax.plot(data, color=color, linewidth=1.2, label=label, **kw)

    def _fill(self, ax, key, color, label):
        data = self.eco.history.get(key, [])
        if data:
            ax.fill_between(range(len(data)), data, alpha=0.15, color=color)

    def _draw_pop(self):
        ax = self.ax_pop; ax.clear(); ax.set_facecolor("#16213e")
        for sp, (_, clr, _) in self.SP.items():
            self._fill(ax, f"{sp}_pop", clr, sp)
            self._line(ax, f"{sp}_pop", clr, sp.capitalize())
        self._line(ax, "plant_pop", "#27ae60", "Plants", linestyle="--", alpha=0.5)
        ax.set_title("Population Dynamics", color="#e0e0e0", fontsize=9)
        ax.legend(fontsize=5, loc="upper right", facecolor="#16213e",
                  edgecolor="#333366", labelcolor="#e0e0e0")
        ax.set_xlabel("Step", color="#aaa", fontsize=7)

    def _draw_speed(self):
        ax = self.ax_speed; ax.clear(); ax.set_facecolor("#16213e")
        for sp, (_, clr, _) in self.SP.items():
            self._line(ax, f"{sp}_speed", clr, sp.capitalize())
        ax.set_title("Avg Speed", color="#e0e0e0", fontsize=9)
        ax.legend(fontsize=5, loc="upper right", facecolor="#16213e",
                  edgecolor="#333366", labelcolor="#e0e0e0")

    def _draw_perception(self):
        ax = self.ax_perception; ax.clear(); ax.set_facecolor("#16213e")
        for sp, (_, clr, _) in self.SP.items():
            self._line(ax, f"{sp}_perception", clr, sp.capitalize())
        ax.set_title("Avg Perception", color="#e0e0e0", fontsize=9)
        ax.legend(fontsize=5, loc="upper right", facecolor="#16213e",
                  edgecolor="#333366", labelcolor="#e0e0e0")

    def _draw_special(self):
        ax = self.ax_special; ax.clear(); ax.set_facecolor("#16213e")
        self._line(ax, "herbivore_camouflage", "#2ecc71", "Herb Camo")
        self._line(ax, "predator_aggression",  "#e74c3c", "Pred Aggr")
        self._line(ax, "apex_aggression",       "#e67e22", "Apex Aggr")
        self._line(ax, "herbivore_agility",     "#1abc9c", "Herb Agility")
        self._line(ax, "herbivore_cooperation", "#9b59b6", "Herb Coop")
        ax.set_title("Specialised Traits", color="#e0e0e0", fontsize=9)
        ax.legend(fontsize=5, loc="upper right", facecolor="#16213e",
                  edgecolor="#333366", labelcolor="#e0e0e0")

    def _draw_energy(self):
        ax = self.ax_energy; ax.clear(); ax.set_facecolor("#16213e")
        for sp, (_, clr, _) in self.SP.items():
            es = [o.energy for o in self.eco.orgs[sp] if o.alive]
            if es:
                ax.hist(es, bins=15, alpha=0.45, color=clr, label=sp.capitalize())
        ax.set_title("Energy Distribution", color="#e0e0e0", fontsize=9)
        ax.legend(fontsize=5, loc="upper right", facecolor="#16213e",
                  edgecolor="#333366", labelcolor="#e0e0e0")
        ax.set_xlabel("Energy", color="#aaa", fontsize=7)

    def _draw_diversity(self):
        ax = self.ax_diversity; ax.clear(); ax.set_facecolor("#16213e")
        d = self.eco.history.get("diversity", [])
        if d:
            ax.plot(d, color="#9b59b6", lw=1.5)
            ax.fill_between(range(len(d)), d, alpha=0.18, color="#9b59b6")
        ax.set_title("Shannon Diversity H'", color="#e0e0e0", fontsize=9)
        ax.set_xlabel("Step", color="#aaa", fontsize=7)

    def _draw_traitspace(self):
        ax = self.ax_traitspace; ax.clear(); ax.set_facecolor("#16213e")
        for sp, (_, clr, mk) in self.SP.items():
            orgs = self.eco.orgs[sp]
            if orgs:
                ax.scatter([o.speed for o in orgs],
                           [o.perception for o in orgs],
                           c=clr, s=[o.size * 8 for o in orgs],
                           alpha=0.55, marker=mk, label=sp.capitalize(),
                           edgecolors="white", linewidths=0.2)
        ax.set_title("Trait Space (Speed × Perception)", color="#e0e0e0", fontsize=9)
        ax.set_xlabel("Speed", color="#aaa", fontsize=7)
        ax.set_ylabel("Perception", color="#aaa", fontsize=7)
        ax.legend(fontsize=5, loc="upper right", facecolor="#16213e",
                  edgecolor="#333366", labelcolor="#e0e0e0")

    def _draw_log(self):
        ax = self.ax_log; ax.clear(); ax.set_facecolor("#16213e")
        ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.set_xticks([]); ax.set_yticks([])
        ax.set_title("Event Log", color="#e0e0e0", fontsize=9)
        evts = self.eco.events[-10:] or ["Waiting…"]
        for i, e in enumerate(evts):
            c = "#e74c3c" if "starved" in e else "#f39c12" if "caught" in e else "#ccc"
            ax.text(0.03, 0.95 - i * 0.09, e, color=c, fontsize=6,
                    transform=ax.transAxes, va="top", fontfamily="monospace")
        # stats footer
        ax.text(0.03, 0.06, self.eco.stats(), color="#888", fontsize=5.5,
                transform=ax.transAxes, va="bottom", fontfamily="monospace")

    # ---- animation callback ----
    def _update(self, frame):
        if self.paused:
            return
        for _ in range(int(self.slider.val)):
            self.eco.tick()
        self._draw_main()
        self._draw_pop()
        self._draw_speed()
        self._draw_perception()
        self._draw_special()
        self._draw_energy()
        self._draw_diversity()
        self._draw_traitspace()
        self._draw_log()

    def run(self):
        self.ani = animation.FuncAnimation(
            self.fig, self._update,
            frames=cfg.MAX_STEPS, interval=cfg.ANIM_INTERVAL, repeat=False)
        plt.show()


# ================================================================
#  ENTRY POINT
# ================================================================
if __name__ == "__main__":
    print("=" * 55)
    print("  🌿  Advanced Ecosystem Simulator")
    print("  Combining lineage tracking, MCTS-style AI,")
    print("  multi-tier food chain, genome evolution,")
    print("  seasons, terrain, and interactive dashboard.")
    print("=" * 55)
    ecosystem = Ecosystem()
    viz = Visualizer(ecosystem)
    viz.run()