#!/usr/bin/env python3
"""
CivSim - Civilization Simulator
A hex-based civilization simulation with MDP decision-making,
MCTS planning, diplomacy, technology, wonders, and dynamic events.
"""

import random
import math
import copy
from collections import defaultdict, deque

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.patches import RegularPolygon, Circle, Patch, FancyBboxPatch
from matplotlib.lines import Line2D
from matplotlib.gridspec import GridSpec
from matplotlib.widgets import Button, Slider

# ============================================================
# CONFIGURATION
# ============================================================
CONFIG = {
    "map_radius": 8,
    "hex_size": 1.0,
    "num_initial_civs": 5,
    "max_turns": 2000,
    "animation_interval": 700,
    "rebellion_stability": 0.18,
    "overthrow_stability": 0.12,
    "trade_bonus_base": 0.012,
    "max_log": 80,
}

# ============================================================
# HEX UTILITIES
# ============================================================
HEX_DIRS = [(+1, 0), (+1, -1), (0, -1), (-1, 0), (-1, +1), (0, +1)]


def hex_neighbors(q, r):
    return [(q + dq, r + dr) for dq, dr in HEX_DIRS]


def hex_distance(q1, r1, q2, r2):
    return (abs(q1 - q2) + abs(q1 + r1 - q2 - r2) + abs(r1 - r2)) // 2


def hex_to_pixel(q, r, size=1.0):
    x = size * 3.0 / 2.0 * q
    y = size * math.sqrt(3) * (r + q / 2.0)
    return x, y


def pixel_to_hex(x, y, size=1.0):
    q = (2.0 / 3.0 * x) / size
    r = (-1.0 / 3.0 * x + math.sqrt(3) / 3.0 * y) / size
    s = -q - r
    rq, rr, rs = round(q), round(r), round(s)
    dq, dr, ds = abs(rq - q), abs(rr - r), abs(rs - s)
    if dq > dr and dq > ds:
        rq = -rr - rs
    elif dr > ds:
        rr = -rq - rs
    return int(rq), int(rr)


def generate_hex_grid(radius):
    return {
        (q, r)
        for q in range(-radius, radius + 1)
        for r in range(-radius, radius + 1)
        if -radius <= q + r <= radius
    }


# ============================================================
# TERRAIN
# ============================================================
TERRAINS = {
    "plains":   {"color": "#e0d9a0", "growth": 1.0, "defense": 1.0, "food": 1.0, "symbol": "🌾"},
    "mountain":  {"color": "#8b8b8b", "growth": 0.3, "defense": 1.8, "food": 0.2, "symbol": "⛰️"},
    "water":     {"color": "#4a90e2", "growth": 0.0, "defense": 1.0, "food": 0.5, "symbol": "🌊"},
    "forest":    {"color": "#4fa24f", "growth": 0.7, "defense": 1.3, "food": 0.8, "symbol": "🌲"},
    "desert":    {"color": "#e0b563", "growth": 0.4, "defense": 0.8, "food": 0.3, "symbol": "🏜️"},
    "swamp":     {"color": "#2e8b57", "growth": 0.5, "defense": 1.1, "food": 0.6, "symbol": "🦆"},
    "hills":     {"color": "#d2b48c", "growth": 0.8, "defense": 1.4, "food": 0.7, "symbol": "🏔️"},
    "volcano":   {"color": "#ff4500", "growth": 0.2, "defense": 1.6, "food": 0.1, "symbol": "🌋"},
    "tundra":    {"color": "#c0d9e0", "growth": 0.4, "defense": 1.0, "food": 0.4, "symbol": "❄️"},
    "jungle":    {"color": "#228b22", "growth": 0.9, "defense": 1.1, "food": 0.9, "symbol": "🦜"},
    "coast":     {"color": "#5ba3cf", "growth": 0.8, "defense": 1.0, "food": 1.2, "symbol": "🏖️"},
}

# ============================================================
# RESOURCES
# ============================================================
RESOURCES = {
    "iron":      {"bonus": "military",   "value": 0.10, "color": "#555555", "symbol": "⚒"},
    "gold":      {"bonus": "economy",    "value": 0.12, "color": "#ffd700", "symbol": "🪙"},
    "food":      {"bonus": "population", "value": 0.15, "color": "#88cc44", "symbol": "🍞"},
    "knowledge": {"bonus": "culture",    "value": 0.10, "color": "#8a2be2", "symbol": "📚"},
    "stone":     {"bonus": "economy",    "value": 0.08, "color": "#a9a9a9", "symbol": "🪨"},
    "spices":    {"bonus": "economy",    "value": 0.12, "color": "#ff6347", "symbol": "🌶"},
    "horses":    {"bonus": "military",   "value": 0.12, "color": "#d2b48c", "symbol": "🐴"},
    "silk":      {"bonus": "culture",    "value": 0.10, "color": "#dda0dd", "symbol": "🧵"},
    "wood":      {"bonus": "economy",    "value": 0.08, "color": "#8b4513", "symbol": "🪵"},
    "gems":      {"bonus": "economy",    "value": 0.15, "color": "#ff69b4", "symbol": "💎"},
    "fish":      {"bonus": "population", "value": 0.10, "color": "#4169e1", "symbol": "🐟"},
}

RESOURCE_CHANCES = {
    "plains":   {"food": 0.35, "horses": 0.10, "gold": 0.05, "spices": 0.05},
    "mountain":  {"iron": 0.30, "gold": 0.15, "stone": 0.20, "gems": 0.05},
    "forest":    {"food": 0.20, "wood": 0.30, "knowledge": 0.08, "silk": 0.05},
    "desert":    {"spices": 0.15, "gold": 0.08, "gems": 0.05},
    "swamp":     {"food": 0.15, "silk": 0.05, "fish": 0.10},
    "hills":     {"iron": 0.15, "stone": 0.20, "horses": 0.08, "gems": 0.03},
    "volcano":   {"iron": 0.25, "gold": 0.10, "gems": 0.08},
    "tundra":    {"food": 0.08, "stone": 0.15, "iron": 0.05},
    "jungle":    {"food": 0.20, "silk": 0.10, "spices": 0.10, "wood": 0.05},
    "coast":     {"fish": 0.35, "food": 0.10, "spices": 0.05, "gold": 0.03},
    "water":     {},
}

# ============================================================
# TECHNOLOGY TREE
# ============================================================
TECH_TREE = {
    "agriculture": {
        "prereqs": [],
        "effects": {"food_bonus": 0.10},
        "cost": 10,
        "era": "ancient",
    },
    "mining": {
        "prereqs": [],
        "effects": {"military_bonus": 0.05},
        "cost": 10,
        "era": "ancient",
    },
    "pottery": {
        "prereqs": ["agriculture"],
        "effects": {"population_bonus": 0.05},
        "cost": 15,
        "era": "ancient",
    },
    "bronze_working": {
        "prereqs": ["mining"],
        "effects": {"military_bonus": 0.10},
        "cost": 20,
        "era": "ancient",
    },
    "writing": {
        "prereqs": ["pottery"],
        "effects": {"culture_bonus": 0.10},
        "cost": 25,
        "era": "classical",
    },
    "iron_working": {
        "prereqs": ["bronze_working"],
        "effects": {"military_bonus": 0.15},
        "cost": 30,
        "era": "classical",
    },
    "currency": {
        "prereqs": ["writing"],
        "effects": {"economy_bonus": 0.10},
        "cost": 30,
        "era": "classical",
    },
    "mathematics": {
        "prereqs": ["writing"],
        "effects": {"culture_bonus": 0.10},
        "cost": 35,
        "era": "classical",
    },
    "engineering": {
        "prereqs": ["mathematics", "iron_working"],
        "effects": {"economy_bonus": 0.15, "defense_bonus": 0.10},
        "cost": 50,
        "era": "medieval",
    },
    "feudalism": {
        "prereqs": ["currency"],
        "effects": {"stability_bonus": 0.10},
        "cost": 40,
        "era": "medieval",
    },
    "gunpowder": {
        "prereqs": ["engineering"],
        "effects": {"military_bonus": 0.20},
        "cost": 60,
        "era": "renaissance",
    },
    "banking": {
        "prereqs": ["currency", "feudalism"],
        "effects": {"economy_bonus": 0.20},
        "cost": 55,
        "era": "renaissance",
    },
    "printing": {
        "prereqs": ["engineering"],
        "effects": {"culture_bonus": 0.20},
        "cost": 50,
        "era": "renaissance",
    },
    "industrialism": {
        "prereqs": ["gunpowder", "banking"],
        "effects": {"economy_bonus": 0.25},
        "cost": 80,
        "era": "industrial",
    },
    "nationalism": {
        "prereqs": ["printing"],
        "effects": {"military_bonus": 0.15, "stability_bonus": 0.10},
        "cost": 70,
        "era": "industrial",
    },
}

# ============================================================
# WONDERS
# ============================================================
WONDERS = [
    {"name": "Great Pyramid",   "cost": 50,  "effects": {"military_bonus": 0.05, "economy_bonus": 0.05},  "prereq_tech": "mining"},
    {"name": "Hanging Gardens",  "cost": 60,  "effects": {"population_bonus": 0.10, "culture_bonus": 0.05}, "prereq_tech": "agriculture"},
    {"name": "Great Library",    "cost": 70,  "effects": {"culture_bonus": 0.15},                         "prereq_tech": "writing"},
    {"name": "Colosseum",        "cost": 65,  "effects": {"stability_bonus": 0.10, "military_bonus": 0.05}, "prereq_tech": "iron_working"},
    {"name": "Silk Road",        "cost": 80,  "effects": {"economy_bonus": 0.20},                         "prereq_tech": "currency"},
    {"name": "Grand Cathedral",  "cost": 90,  "effects": {"culture_bonus": 0.10, "stability_bonus": 0.15}, "prereq_tech": "feudalism"},
    {"name": "Arsenal",          "cost": 85,  "effects": {"military_bonus": 0.20},                        "prereq_tech": "gunpowder"},
    {"name": "Stock Exchange",   "cost": 100, "effects": {"economy_bonus": 0.25},                        "prereq_tech": "banking"},
]

# ============================================================
# CIV NAMES & TRAITS
# ============================================================
CIV_PREFIXES = [
    "Auro", "Xan", "Vel", "Eldo", "Zeph", "Cindra", "Thal", "Koro",
    "Lum", "Nexa", "Pyra", "Drak", "Syl", "Vor", "Keth", "Myra",
]
CIV_SUFFIXES = [
    "ria", "dralith", "mora", "thium", "oria", "valis", "dor", "mir",
    "thar", "ven", "gar", "sis", "lon", "rax", "dorn", "fell",
]
TRAITS = [
    "aggressive", "peaceful", "expansionist", "isolated", "merchant",
    "innovative", "technocratic", "religious", "nomadic", "defensive",
]

TRAIT_EFFECTS = {
    "aggressive":    {"military": 0.10, "economy": -0.05, "war_chance": 0.10},
    "peaceful":      {"military": -0.05, "economy": 0.05,  "war_chance": -0.08},
    "expansionist":  {"military": 0.05,  "economy": 0.05,  "expansion_bonus": 0.20},
    "isolated":      {"economy": -0.05,  "culture": 0.10,  "war_chance": -0.05},
    "merchant":      {"economy": 0.15,   "military": -0.05, "trade_bonus": 0.02},
    "innovative":    {"culture": 0.10,   "tech_bonus": 0.20},
    "technocratic":  {"culture": 0.05,   "tech_bonus": 0.30, "military": -0.05},
    "religious":     {"culture": 0.15,   "stability": 0.05,  "war_chance": 0.03},
    "nomadic":       {"expansion_bonus": 0.30, "stability": -0.05},
    "defensive":     {"military": 0.05,  "defense_bonus": 0.20, "expansion_bonus": -0.10},
}


def generate_civ_name():
    return random.choice(CIV_PREFIXES) + random.choice(CIV_SUFFIXES)


def generate_splinter_name(parent):
    return random.choice([
        f"Neo-{parent}",
        f"{parent} Horde",
        f"{parent} Dominion",
        f"Free {parent}",
        f"{parent} Rebels",
    ])


def generate_dynasty_name(parent):
    return random.choice([
        f"The {parent} Empire",
        f"Kingdom of {parent}",
        f"{parent} Republic",
        f"New {parent}",
        f"Grand {parent}",
    ])


# ============================================================
# ENHANCED MDP  (9-state, 4-action, deterministic)
# ============================================================
class CivMDP:
    """
    States  = (stability_level, economy_level)  each in {0,1,2}
    Actions = "military" | "economy" | "culture" | "stability"
    Solved via value-iteration.
    """

    STATES = [(s, e) for s in range(3) for e in range(3)]
    ACTIONS = ["military", "economy", "culture", "stability"]

    # Deterministic transition table: (s,e,action) -> (s',e')
    TRANS = {
        (0, 0, "military"):  (1, 0), (0, 0, "economy"):  (0, 1),
        (0, 0, "culture"):   (1, 0), (0, 0, "stability"): (1, 0),
        (0, 1, "military"):  (1, 0), (0, 1, "economy"):  (0, 2),
        (0, 1, "culture"):   (1, 1), (0, 1, "stability"): (1, 1),
        (0, 2, "military"):  (1, 1), (0, 2, "economy"):  (0, 2),
        (0, 2, "culture"):   (1, 2), (0, 2, "stability"): (1, 2),
        (1, 0, "military"):  (2, 0), (1, 0, "economy"):  (1, 1),
        (1, 0, "culture"):   (2, 0), (1, 0, "stability"): (2, 0),
        (1, 1, "military"):  (2, 0), (1, 1, "economy"):  (1, 2),
        (1, 1, "culture"):   (2, 1), (1, 1, "stability"): (2, 1),
        (1, 2, "military"):  (2, 1), (1, 2, "economy"):  (1, 2),
        (1, 2, "culture"):   (2, 2), (1, 2, "stability"): (2, 2),
        (2, 0, "military"):  (2, 0), (2, 0, "economy"):  (2, 1),
        (2, 0, "culture"):   (2, 0), (2, 0, "stability"): (2, 0),
        (2, 1, "military"):  (1, 0), (2, 1, "economy"):  (2, 2),
        (2, 1, "culture"):   (2, 1), (2, 1, "stability"): (2, 1),
        (2, 2, "military"):  (1, 1), (2, 2, "economy"):  (2, 2),
        (2, 2, "culture"):   (2, 2), (2, 2, "stability"): (2, 2),
    }

    @staticmethod
    def _reward(action, s, ns):
        if action == "military":
            return 5 if ns[0] > s[0] else (-2 if ns[1] < s[1] else 1)
        if action == "economy":
            return 8 if ns[1] > s[1] else (-1 if ns[0] < s[0] else 2)
        if action == "culture":
            return 4 if ns[0] >= s[0] else 0
        # stability
        return 6 if ns[0] > s[0] else 1

    def __init__(self, gamma=0.9, epsilon=0.01):
        self.gamma = gamma
        self.policy, self.values = self._solve(epsilon)

    def _solve(self, eps):
        V = {s: 0.0 for s in self.STATES}
        while True:
            delta = 0.0
            for s in self.STATES:
                v = V[s]
                best = -1e9
                for a in self.ACTIONS:
                    ns = self.TRANS[s + (a,)]
                    r = self._reward(a, s, ns)
                    best = max(best, r + self.gamma * V[ns])
                V[s] = best
                delta = max(delta, abs(v - V[s]))
            if delta < eps:
                break
        policy = {}
        for s in self.STATES:
            policy[s] = max(
                self.ACTIONS,
                key=lambda a: self._reward(a, s, self.TRANS[s + (a,)])
                + self.gamma * V[self.TRANS[s + (a,)]],
            )
        return policy, V

    @staticmethod
    def civ_to_state(civ):
        s = 0 if civ.stability < 0.35 else (1 if civ.stability < 0.65 else 2)
        e = 0 if civ.economy < 0.35 else (1 if civ.economy < 0.65 else 2)
        return (s, e)

    def get_action(self, civ):
        return self.policy.get(self.civ_to_state(civ), "economy")


# ============================================================
# MCTS FOR EXPANSION PLANNING  (UCB1)
# ============================================================
class ExpansionMCTS:
    """Selects the best empty hex for a civ to expand into."""

    def __init__(self, civ, world, terrain, resources, iterations=60):
        self.civ = civ
        self.world = world
        self.terrain = terrain
        self.resources = resources
        self.iterations = iterations

    def _candidates(self):
        cands = set()
        for h in self.civ.hexes:
            for n in hex_neighbors(*h):
                if n not in self.world and self.terrain.get(n, "plains") != "water":
                    cands.add(n)
        return list(cands)

    def _evaluate(self, h):
        t = self.terrain.get(h, "plains")
        score = TERRAINS[t]["growth"] * 10 + TERRAINS[t]["food"] * 5 + TERRAINS[t]["defense"] * 2
        if h in self.resources:
            score += RESOURCES[self.resources[h]]["value"] * 20
        adj_own = sum(1 for n in hex_neighbors(*h) if n in self.civ.hexes)
        score += adj_own * 3
        for n in hex_neighbors(*h):
            if n not in self.world and n not in self.civ.hexes:
                if self.terrain.get(n, "plains") != "water":
                    score += self._eval_simple(n) * 0.1
        return score

    def _eval_simple(self, h):
        t = self.terrain.get(h, "plains")
        s = TERRAINS[t]["growth"] * 5
        if h in self.resources:
            s += RESOURCES[self.resources[h]]["value"] * 10
        return s

    def search(self):
        cands = self._candidates()
        if not cands:
            return None
        if len(cands) == 1:
            return cands[0]
        scores = {h: 0.0 for h in cands}
        visits = {h: 0 for h in cands}
        total = 0
        for _ in range(self.iterations):
            unvisited = [h for h in cands if visits[h] == 0]
            if unvisited:
                h = random.choice(unvisited)
            else:
                log_t = math.log(max(1, total))
                h = max(
                    cands,
                    key=lambda c: scores[c] / visits[c]
                    + 1.4 * math.sqrt(log_t / visits[c]),
                )
            result = self._evaluate(h) + random.gauss(0, 2)
            scores[h] += result
            visits[h] += 1
            total += 1
        return max(cands, key=lambda h: scores[h] / max(1, visits[h]))


# ============================================================
# GLOBAL STATE
# ============================================================
history_log = deque(maxlen=CONFIG["max_log"])
cultural_map = {}
active_disasters = {}
paused = False
selected_hex = None

# Pre-compute MDP policy once
_mdp = CivMDP()

# ============================================================
# CIVILIZATION CLASS
# ============================================================
CIV_COLORS = [
    "#e6194b", "#3cb44b", "#ffe119", "#4363d8", "#f58231",
    "#911eb4", "#42d4f4", "#f032e6", "#bfef45", "#fabed4",
    "#469990", "#dcbeff", "#9A6324", "#fffac8", "#800000",
    "#aaffc3", "#808000", "#ffd8b1", "#000075", "#a9a9a9",
]


class Civilization:
    _cid = 0

    def __init__(self, name, q, r, trait=None, parent=None):
        self.name = name
        self.trait = trait or random.choice(TRAITS)
        self.parent = parent
        self.alive = True

        self.population = random.randint(80, 200)
        self.stability = random.uniform(0.50, 0.90)
        self.military = random.uniform(0.30, 0.70)
        self.economy = random.uniform(0.30, 0.70)
        self.culture = random.uniform(0.20, 0.60)

        self.hexes = {(q, r)}
        self.capital = (q, r)
        self.armies = {(q, r): random.randint(15, 30)}

        self.allies = set()
        self.enemies = set()
        self.truce = {}

        self.technologies = set()
        self.researching = None
        self.research_progress = 0.0

        self.wonders_built = []
        self.wonder_progress = None
        self.bonuses = defaultdict(float)

        self.color = CIV_COLORS[Civilization._cid % len(CIV_COLORS)]
        Civilization._cid += 1
        self.moving_units = []
        self.era = "ancient"

        self.stats_history = defaultdict(list)
        self._record_stats()
        self._apply_trait()

    # ---- helpers ----
    def _apply_trait(self):
        fx = TRAIT_EFFECTS.get(self.trait, {})
        for stat in ("military", "economy", "culture", "stability"):
            if stat in fx:
                val = getattr(self, stat) + fx[stat]
                setattr(self, stat, max(0.05, val))

    def _record_stats(self):
        self.stats_history["population"].append(self.population)
        self.stats_history["stability"].append(self.stability)
        self.stats_history["military"].append(self.military)
        self.stats_history["economy"].append(self.economy)
        self.stats_history["culture"].append(self.culture)
        self.stats_history["territory"].append(len(self.hexes))

    def _recalc_bonuses(self, resources):
        self.bonuses = defaultdict(float)
        for tech in self.technologies:
            for eff, val in TECH_TREE[tech]["effects"].items():
                self.bonuses[eff] += val
        for w in self.wonders_built:
            for eff, val in w["effects"].items():
                self.bonuses[eff] += val
        for h in self.hexes:
            if h in resources:
                rname = resources[h]
                self.bonuses[f"{RESOURCES[rname]['bonus']}_bonus"] += RESOURCES[rname]["value"]

    @property
    def total_army(self):
        return sum(self.armies.values())

    @property
    def power(self):
        return (
            self.population * 0.3
            + self.military * 40
            + self.economy * 30
            + self.culture * 20
            + len(self.hexes) * 5
            + len(self.technologies) * 10
        )

    # ---- main step ----
    def step(self, civs, world, terrain, resources):
        if not self.alive:
            return

        self._recalc_bonuses(resources)

        # Population growth
        if self.hexes:
            gf = sum(TERRAINS[terrain.get(h, "plains")]["growth"] for h in self.hexes) / len(self.hexes)
            ff = sum(TERRAINS[terrain.get(h, "plains")]["food"] for h in self.hexes) / len(self.hexes)
        else:
            gf, ff = 0.5, 0.5
        pb = self.bonuses.get("population_bonus", 0)
        growth = self.stability * 5 * gf * (1 + ff) * (1 + pb)
        self.population += int(random.gauss(growth, 5))
        self.population = max(0, self.population)

        # Stability decay from overextension
        over = max(0, len(self.hexes) - 8) * 0.003
        sb = self.bonuses.get("stability_bonus", 0)
        self.stability = max(0.03, min(1.0, self.stability - over + sb * 0.01))

        # MDP action
        action = _mdp.get_action(self)
        self._do_action(action)

        # Technology
        self._research()

        # Wonders
        self._build_wonder()

        # Expansion
        self._expand(world, terrain, resources)

        # Military
        self._recruit()
        self._attack(world, terrain, civs)
        self._move_armies()

        # Diplomacy
        self._update_truces()
        self._diplomacy(civs)
        self._trade(civs)

        # Culture
        self._spread_culture()

        # Disasters
        self._trigger_disasters(terrain)
        self._suffer_disasters()

        # Rebellion / Overthrow
        self._maybe_rebellion(civs, world)
        self._maybe_overthrow()

        # Era
        tc = len(self.technologies)
        if tc >= 10:
            self.era = "industrial"
        elif tc >= 7:
            self.era = "renaissance"
        elif tc >= 4:
            self.era = "medieval"
        elif tc >= 1:
            self.era = "classical"
        else:
            self.era = "ancient"

        self._record_stats()

        if self.population <= 0 or self.stability <= 0.03:
            for h in list(self.hexes):
                world.pop(h, None)
            self.hexes.clear()
            self.alive = False
            history_log.append(f"💀 {self.name} collapsed!")

    # ---- actions ----
    def _do_action(self, action):
        mb = self.bonuses.get("military_bonus", 0)
        eb = self.bonuses.get("economy_bonus", 0)
        cb = self.bonuses.get("culture_bonus", 0)
        if action == "military":
            self.military += 0.012 * (1 + mb)
            self.economy -= 0.004
        elif action == "economy":
            self.economy += 0.012 * (1 + eb)
            self.military -= 0.003
        elif action == "culture":
            self.culture += 0.010 * (1 + cb)
        elif action == "stability":
            self.stability = min(1.0, self.stability + 0.015)
            self.economy -= 0.002
        self.military = max(0.05, min(2.0, self.military))
        self.economy = max(0.05, min(2.0, self.economy))
        self.culture = max(0.05, min(2.0, self.culture))
        self.stability = max(0.03, min(1.0, self.stability))

    def _research(self):
        tb = self.bonuses.get("culture_bonus", 0) + TRAIT_EFFECTS.get(self.trait, {}).get("tech_bonus", 0)
        rate = 0.5 + self.culture * 0.3 + tb
        if self.researching is None:
            avail = [
                t
                for t, info in TECH_TREE.items()
                if t not in self.technologies
                and all(p in self.technologies for p in info["prereqs"])
            ]
            if avail:
                weights = []
                for t in avail:
                    w = 1.0
                    info = TECH_TREE[t]
                    if self.trait == "aggressive" and "military_bonus" in info["effects"]:
                        w *= 2
                    elif self.trait == "merchant" and "economy_bonus" in info["effects"]:
                        w *= 2
                    elif self.trait == "innovative" and "culture_bonus" in info["effects"]:
                        w *= 2
                    w /= info["cost"]
                    weights.append(w)
                self.researching = random.choices(avail, weights=weights, k=1)[0]
                self.research_progress = 0.0
        if self.researching:
            self.research_progress += rate
            if self.research_progress >= TECH_TREE[self.researching]["cost"]:
                self.technologies.add(self.researching)
                history_log.append(f"🔬 {self.name} discovered {self.researching}!")
                self.researching = None
                self.research_progress = 0.0

    def _build_wonder(self):
        if self.wonder_progress is None and random.random() < 0.04:
            built_names = {w["name"] for w in self.wonders_built}
            # Also exclude wonders already completed by ANY civ (global wonders)
            all_built = set()
            # We'll just check self for simplicity
            avail = [
                w for w in WONDERS
                if w["name"] not in built_names and w["prereq_tech"] in self.technologies
            ]
            if avail:
                w = random.choice(avail)
                self.wonder_progress = {"wonder": w, "progress": 0.0}
                history_log.append(f"🏗️ {self.name} started {w['name']}!")
        if self.wonder_progress:
            w = self.wonder_progress["wonder"]
            self.wonder_progress["progress"] += self.economy * 2 + len(self.hexes) * 0.1
            if self.wonder_progress["progress"] >= w["cost"]:
                self.wonders_built.append(w)
                history_log.append(f"🏛️ {self.name} completed {w['name']}!")
                self.wonder_progress = None

    def _expand(self, world, terrain, resources):
        eb = TRAIT_EFFECTS.get(self.trait, {}).get("expansion_bonus", 0)
        attempts = max(1, int((self.military + eb) * 8))
        for _ in range(attempts):
            if not self.hexes:
                break
            origin = random.choice(list(self.hexes))
            cands = [
                n
                for n in hex_neighbors(*origin)
                if terrain.get(n, "plains") != "water" and n not in world
            ]
            if not cands:
                continue
            if self.trait in ("expansionist", "aggressive") and len(cands) > 1:
                target = ExpansionMCTS(self, world, terrain, resources).search()
                if target is None:
                    target = random.choice(cands)
            else:
                target = random.choice(cands)
            tt = terrain.get(target, "plains")
            chance = min(0.95, self.military * TERRAINS[tt]["growth"] * (1 + eb))
            if random.random() < chance:
                self.hexes.add(target)
                world[target] = self.name
                self.armies[target] = max(3, self.armies.get(origin, 10) // 4)
                self.moving_units.append({"from": origin, "to": target, "progress": 0.0})
                break

    def _recruit(self):
        for h in list(self.armies):
            if h in self.hexes:
                self.armies[h] += int(
                    self.military * 2 * self.economy * random.uniform(0.5, 1.5)
                )
        if self.capital not in self.armies:
            self.armies[self.capital] = 10

    def _attack(self, world, terrain, civs):
        if not self.enemies:
            return
        for ename in list(self.enemies):
            enemy = next((c for c in civs if c.name == ename and c.alive), None)
            if not enemy:
                continue
            attacks = []
            for mh in list(self.hexes):
                ma = self.armies.get(mh, 0)
                if ma < 8:
                    continue
                for n in hex_neighbors(*mh):
                    if n in enemy.hexes:
                        attacks.append((mh, n, ma))
            if not attacks:
                continue
            mh, tgt, ma = max(
                attacks, key=lambda x: x[2] / (1 + enemy.armies.get(x[1], 1))
            )
            ea = enemy.armies.get(tgt, 0)
            df = TERRAINS[terrain.get(tgt, "plains")]["defense"]
            db = TRAIT_EFFECTS.get(enemy.trait, {}).get("defense_bonus", 0)
            mb = self.bonuses.get("military_bonus", 0)
            atk_str = ma * (1 + mb) * self.military
            def_str = ea * df * (1 + db) * enemy.military
            if atk_str > def_str * random.uniform(0.7, 1.3):
                enemy.hexes.discard(tgt)
                enemy.armies.pop(tgt, None)
                if tgt == enemy.capital and enemy.hexes:
                    enemy.capital = random.choice(list(enemy.hexes))
                world[tgt] = self.name
                self.hexes.add(tgt)
                rem = max(3, ma // 2)
                self.armies[tgt] = rem
                self.armies[mh] = max(0, self.armies.get(mh, 0) - ma + rem)
                if self.armies.get(mh, 0) <= 0:
                    self.armies.pop(mh, None)
                self.moving_units.append({"from": mh, "to": tgt, "progress": 0.0})
                history_log.append(f"🏹 {self.name} conquered from {enemy.name}")
                if not enemy.hexes:
                    enemy.alive = False
                    history_log.append(f"💀 {enemy.name} destroyed by {self.name}!")
            else:
                loss = ma // 3
                self.armies[mh] = max(0, self.armies.get(mh, 0) - loss)
                if self.armies.get(mh, 0) <= 0:
                    self.armies.pop(mh, None)

    def _move_armies(self):
        for h in list(self.armies):
            if h not in self.hexes:
                self.armies.pop(h, None)
                continue
            if random.random() < 0.15:
                nbrs = [n for n in hex_neighbors(*h) if n in self.hexes]
                if nbrs:
                    border = [
                        n
                        for n in nbrs
                        if any(
                            nn not in self.hexes and nn in self.world
                            for nn in hex_neighbors(*n)
                        )
                    ]
                    to = random.choice(border) if border else random.choice(nbrs)
                    sz = self.armies.pop(h, 0)
                    self.armies[to] = self.armies.get(to, 0) + sz
                    self.moving_units.append({"from": h, "to": to, "progress": 0.0})

    def _update_truces(self):
        expired = [n for n, t in self.truce.items() if t <= 1]
        for n in expired:
            del self.truce[n]
        for n in list(self.truce):
            self.truce[n] -= 1

    def _diplomacy(self, civs):
        wc = TRAIT_EFFECTS.get(self.trait, {}).get("war_chance", 0)
        if random.random() < 0.05:
            others = [
                c
                for c in civs
                if c.alive
                and c != self
                and c.name not in self.allies
                and c.name not in self.enemies
                and c.name not in self.truce
            ]
            if others:
                p = random.choice(others)
                if self.trait in ("peaceful", "merchant") or p.trait in (
                    "peaceful",
                    "merchant",
                ):
                    if random.random() < 0.3:
                        self.allies.add(p.name)
                        p.allies.add(self.name)
                        history_log.append(f"🤝 {self.name} allied with {p.name}")
                        return
                if random.random() < 0.15 + wc:
                    if not any(a in self.allies for a in p.allies):
                        self.enemies.add(p.name)
                        p.enemies.add(self.name)
                        history_log.append(
                            f"⚔️ {self.name} declared war on {p.name}!"
                        )
        # Peace offers
        for en in list(self.enemies):
            if random.random() < 0.02:
                e = next((c for c in civs if c.name == en and c.alive), None)
                if e:
                    self.enemies.discard(en)
                    e.enemies.discard(self.name)
                    t = random.randint(5, 15)
                    self.truce[en] = t
                    e.truce[self.name] = t
                    history_log.append(f"🕊️ {self.name} made peace with {en}")
        # Betrayal
        if self.trait == "aggressive" and self.allies and random.random() < 0.01:
            an = random.choice(list(self.allies))
            a = next((c for c in civs if c.name == an and c.alive), None)
            if a:
                self.allies.discard(an)
                a.allies.discard(self.name)
                self.enemies.add(an)
                a.enemies.add(self.name)
                history_log.append(f"🗡️ {self.name} betrayed {an}!")

    def _trade(self, civs):
        tb = TRAIT_EFFECTS.get(self.trait, {}).get(
            "trade_bonus", CONFIG["trade_bonus_base"]
        )
        for p in civs:
            if (
                p.alive
                and p != self
                and self.name < p.name
                and (
                    p.name in self.allies
                    or (
                        self.trait in ("merchant", "peaceful")
                        and p.trait in ("merchant", "peaceful")
                    )
                )
            ):
                eb = self.bonuses.get("economy_bonus", 0)
                peb = p.bonuses.get("economy_bonus", 0)
                self.economy += tb * p.economy * (1 + eb)
                p.economy += tb * self.economy * (1 + peb)

    def _spread_culture(self):
        cb = self.bonuses.get("culture_bonus", 0)
        for h in self.hexes:
            cultural_map.setdefault(h, {})
            cultural_map[h][self.name] = (
                cultural_map[h].get(self.name, 0) + self.culture * (1 + cb)
            )
            for n in hex_neighbors(*h):
                cultural_map.setdefault(n, {})
                cultural_map[n][self.name] = (
                    cultural_map[n].get(self.name, 0) + self.culture * 0.05
                )

    def _trigger_disasters(self, terrain):
        for h in self.hexes:
            if random.random() < 0.008:
                t = terrain.get(h, "plains")
                if t == "volcano":
                    dt = "volcano"
                elif t in ("swamp", "coast"):
                    dt = random.choice(["flood", "plague"])
                elif t == "desert":
                    dt = random.choice(["drought", "plague"])
                elif t == "tundra":
                    dt = random.choice(["blizzard", "drought"])
                else:
                    dt = random.choice(["flood", "drought", "plague", "earthquake"])
                active_disasters[h] = (dt, random.randint(2, 5))
                history_log.append(
                    f"⚠️ {self.name}: {dt} at ({h[0]},{h[1]})"
                )

    def _suffer_disasters(self):
        for h in list(self.hexes):
            if h in active_disasters:
                dt, _ = active_disasters[h]
                if dt in ("flood", "blizzard"):
                    self.population -= random.randint(2, 8)
                    self.economy -= 0.005
                elif dt == "drought":
                    self.population -= random.randint(1, 5)
                    self.economy -= 0.01
                elif dt == "plague":
                    self.population -= random.randint(5, 20)
                    self.stability -= 0.01
                elif dt in ("volcano", "earthquake"):
                    self.population -= random.randint(5, 15)
                    self.economy -= 0.01
                    self.stability -= 0.005
                    if h in self.armies:
                        self.armies[h] = max(
                            0, self.armies[h] - random.randint(2, 8)
                        )

    def _maybe_rebellion(self, civs, world):
        if (
            self.stability < CONFIG["rebellion_stability"]
            and self.population > 100
            and len(self.hexes) >= 3
            and random.random() < 0.03
        ):
            n = len(self.hexes) // 3
            rh = random.sample(list(self.hexes), max(1, n))
            name = generate_splinter_name(self.name)
            rq, rr = rh[0]
            nc = Civilization(
                name, rq, rr, trait=random.choice(TRAITS), parent=self.name
            )
            nc.hexes = set(rh)
            nc.armies = {h: max(5, self.armies.get(h, 10) // 2) for h in rh}
            for h in rh:
                self.hexes.discard(h)
                world[h] = nc.name
                self.armies.pop(h, None)
            nc.population = self.population // 4
            self.population = int(self.population * 0.75)
            self.enemies.add(nc.name)
            nc.enemies.add(self.name)
            civs.append(nc)
            history_log.append(f"⚔️ {nc.name} rebelled from {self.name}!")

    def _maybe_overthrow(self):
        if (
            self.stability < CONFIG["overthrow_stability"]
            and self.population > 100
            and random.random() < 0.02
        ):
            old = self.name
            self.name = generate_dynasty_name(old)
            self.stability = min(0.8, self.stability + 0.2)
            history_log.append(f"👑 {old} overthrown! Now: {self.name}")


# ============================================================
# MAP GENERATION
# ============================================================
def generate_terrain(radius):
    terrain = {}
    grid = list(generate_hex_grid(radius))
    elev_seeds = [
        (random.choice(grid), random.uniform(-1, 1))
        for _ in range(max(5, radius))
    ]
    moist_seeds = [
        (random.choice(grid), random.uniform(-1, 1))
        for _ in range(max(5, radius))
    ]
    for h in grid:
        e_num = sum(
            v / (hex_distance(*h, *s) + 1) ** 2 for s, v in elev_seeds
        )
        e_den = sum(
            1.0 / (hex_distance(*h, *s) + 1) ** 2 for s, _ in elev_seeds
        )
        e = e_num / e_den if e_den else 0
        m_num = sum(
            v / (hex_distance(*h, *s) + 1) ** 2 for s, v in moist_seeds
        )
        m_den = sum(
            1.0 / (hex_distance(*h, *s) + 1) ** 2 for s, _ in moist_seeds
        )
        m = m_num / m_den if m_den else 0
        if e > 0.6:
            terrain[h] = "mountain"
        elif e > 0.45:
            terrain[h] = "hills"
        elif e < -0.5:
            terrain[h] = "water"
        elif e < -0.3:
            terrain[h] = "coast"
        elif m > 0.4:
            terrain[h] = "jungle"
        elif m > 0.2:
            terrain[h] = "forest"
        elif m > 0.0:
            terrain[h] = "plains"
        elif m > -0.2:
            terrain[h] = "desert"
        else:
            terrain[h] = "tundra"
        if terrain[h] == "mountain" and random.random() < 0.15:
            terrain[h] = "volcano"
        elif terrain[h] in ("plains", "forest") and random.random() < 0.03:
            terrain[h] = "swamp"
    return terrain


def generate_resources(terrain):
    resources = {}
    for h, t in terrain.items():
        for res, ch in RESOURCE_CHANCES.get(t, {}).items():
            if random.random() < ch:
                resources[h] = res
                break
    return resources


# ============================================================
# SIMULATION ENGINE
# ============================================================
class SimEngine:
    def __init__(self):
        self.radius = CONFIG["map_radius"]
        self.terrain = generate_terrain(self.radius)
        self.resources = generate_resources(self.terrain)
        self.world = {}
        self.civs = []
        self.turn = 0
        self.victor = None
        self._place_civs()

    def _place_civs(self):
        grid = list(generate_hex_grid(self.radius))
        random.shuffle(grid)
        placed = 0
        for h in grid:
            if placed >= CONFIG["num_initial_civs"]:
                break
            if self.terrain.get(h, "plains") in ("water", "volcano", "mountain"):
                continue
            if any(hex_distance(*h, *c.capital) < 4 for c in self.civs):
                continue
            c = Civilization(generate_civ_name(), h[0], h[1])
            self.civs.append(c)
            self.world[h] = c.name
            placed += 1

    def step(self):
        if self.victor:
            return
        self.turn += 1
        alive = [c for c in self.civs if c.alive]
        random.shuffle(alive)
        for c in alive:
            c.step(self.civs, self.world, self.terrain, self.resources)
        # Tick disasters
        expired = [h for h, (_, t) in active_disasters.items() if t <= 1]
        for h in expired:
            del active_disasters[h]
        for h in list(active_disasters):
            dt, t = active_disasters[h]
            active_disasters[h] = (dt, t - 1)
        # Victory check
        alive = [c for c in self.civs if c.alive]
        if len(alive) == 1:
            self.victor = alive[0]
            history_log.append(f"🏆 {alive[0].name} wins by domination!")
        elif len(alive) == 0:
            history_log.append("💀 All civilizations have fallen!")

    @property
    def alive_civs(self):
        return [c for c in self.civs if c.alive]


# ============================================================
# RENDERER
# ============================================================
class Renderer:
    def __init__(self, engine):
        self.engine = engine
        self.dyn = []  # dynamic artists to clear each frame
        self.selected = None
        self._setup()

    def _setup(self):
        self.fig = plt.figure(figsize=(22, 11), facecolor="#1a1a2e")
        self.fig.suptitle(
            "CivSim — Civilization Simulator",
            fontsize=18,
            color="white",
            fontweight="bold",
            y=0.98,
        )

        gs = GridSpec(
            3,
            4,
            figure=self.fig,
            width_ratios=[3, 1, 1, 1],
            height_ratios=[2, 1, 1],
            hspace=0.40,
            wspace=0.30,
        )

        self.ax_map = self.fig.add_subplot(gs[:, 0])
        self.ax_pop = self.fig.add_subplot(gs[0, 1:3])
        self.ax_terr = self.fig.add_subplot(gs[0, 3])
        self.ax_log = self.fig.add_subplot(gs[1, 1:])
        self.ax_info = self.fig.add_subplot(gs[2, 1:])

        for ax in (self.ax_map, self.ax_pop, self.ax_terr, self.ax_log, self.ax_info):
            ax.set_facecolor("#16213e")

        r = self.engine.radius
        s = CONFIG["hex_size"]
        margin = 3
        self.ax_map.set_xlim(-r * s * 2 - margin, r * s * 2 + margin)
        self.ax_map.set_ylim(-r * s * 2 - margin, r * s * 2 + margin)
        self.ax_map.set_aspect("equal")
        self.ax_map.axis("off")

        self._draw_base()

        self.fig.canvas.mpl_connect("button_press_event", self._click)

        # Pause / play button
        ax_btn = self.fig.add_axes([0.02, 0.02, 0.07, 0.03])
        self.btn = Button(ax_btn, "⏯ Pause", color="#16213e", hovercolor="#0f3460")
        self.btn.label.set_color("white")
        self.btn.label.set_fontsize(9)
        self.btn.on_clicked(self._toggle_pause)

        # Speed slider
        ax_sl = self.fig.add_axes([0.12, 0.02, 0.18, 0.03])
        self.slider = Slider(
            ax_sl, "Speed", 0.2, 3.0, valinit=1.0, color="#e94560"
        )
        self.slider.label.set_color("white")
        self.slider.label.set_fontsize(9)
        self.slider.valtext.set_color("white")

    def _toggle_pause(self, _event):
        global paused
        paused = not paused
        self.btn.label.set_text("⏯ Play" if paused else "⏯ Pause")

    def _click(self, event):
        if event.inaxes == self.ax_map and event.xdata is not None:
            self.selected = pixel_to_hex(event.xdata, event.ydata, CONFIG["hex_size"])

    # ---- static base ----
    def _draw_base(self):
        s = CONFIG["hex_size"]
        for h, t in self.engine.terrain.items():
            x, y = hex_to_pixel(*h, s)
            p = RegularPolygon(
                (x, y),
                6,
                radius=s * 0.95,
                orientation=0,
                facecolor=TERRAINS[t]["color"],
                edgecolor="#333333",
                linewidth=0.4,
                alpha=0.9,
            )
            self.ax_map.add_patch(p)
            self.ax_map.text(
                x,
                y + 0.30 * s,
                TERRAINS[t]["symbol"],
                ha="center",
                va="center",
                fontsize=7,
                alpha=0.55,
            )
        for h, res in self.engine.resources.items():
            x, y = hex_to_pixel(*h, s)
            self.ax_map.text(
                x + 0.35 * s,
                y + 0.35 * s,
                RESOURCES[res]["symbol"],
                ha="center",
                va="center",
                fontsize=5,
                alpha=0.65,
            )

    # ---- clear dynamic artists ----
    def clear_dyn(self):
        for a in self.dyn:
            try:
                a.remove()
            except Exception:
                pass
        self.dyn.clear()

    # ---- main render ----
    def render(self):
        self.clear_dyn()
        s = CONFIG["hex_size"]
        alive = self.engine.alive_civs

        # --- territory overlay ---
        for civ in alive:
            for h in civ.hexes:
                x, y = hex_to_pixel(*h, s)
                p = RegularPolygon(
                    (x, y),
                    6,
                    radius=s * 0.95,
                    orientation=0,
                    facecolor=civ.color,
                    edgecolor="black",
                    linewidth=1.0,
                    alpha=0.50,
                )
                self.ax_map.add_patch(p)
                self.dyn.append(p)

            # Capital star
            if civ.capital in civ.hexes:
                cx, cy = hex_to_pixel(*civ.capital, s)
                t = self.ax_map.text(
                    cx, cy + 0.40 * s, "⭐",
                    ha="center", va="center", fontsize=10, zorder=6,
                )
                self.dyn.append(t)

        # --- army indicators ---
        for civ in alive:
            for h, army in civ.armies.items():
                if army > 0 and h in civ.hexes:
                    x, y = hex_to_pixel(*h, s)
                    t = self.ax_map.text(
                        x,
                        y - 0.28 * s,
                        f"⚔{army}",
                        ha="center",
                        va="center",
                        fontsize=4,
                        color="yellow",
                        zorder=5,
                    )
                    self.dyn.append(t)

        # --- moving units ---
        for civ in alive:
            done = []
            for i, mv in enumerate(civ.moving_units):
                fx, fy = hex_to_pixel(*mv["from"], s)
                tx, ty = hex_to_pixel(*mv["to"], s)
                prog = min(mv["progress"], 1.0)
                mx = fx + (tx - fx) * prog
                my = fy + (ty - fy) * prog
                c = Circle(
                    (mx, my), 0.18 * s, color=civ.color, alpha=0.9, zorder=5
                )
                self.ax_map.add_patch(c)
                self.dyn.append(c)
                mv["progress"] += 0.25
                if mv["progress"] >= 1.0:
                    done.append(i)
            for i in reversed(done):
                civ.moving_units.pop(i)

        # --- disasters ---
        dicons = {
            "flood": "🌊",
            "drought": "🔥",
            "plague": "☣️",
            "volcano": "🌋",
            "earthquake": "💥",
            "blizzard": "❄️",
        }
        for h, (dt, _turns) in active_disasters.items():
            x, y = hex_to_pixel(*h, s)
            t = self.ax_map.text(
                x,
                y,
                dicons.get(dt, "⚠️"),
                ha="center",
                va="center",
                fontsize=11,
                zorder=7,
            )
            self.dyn.append(t)

        # --- trade routes ---
        for civ in alive:
            for p in alive:
                if (
                    civ.name < p.name
                    and (
                        p.name in civ.allies
                        or (
                            civ.trait in ("merchant", "peaceful")
                            and p.trait in ("merchant", "peaceful")
                        )
                    )
                ):
                    if civ.hexes and p.hexes:
                        x1, y1 = hex_to_pixel(*civ.capital, s)
                        x2, y2 = hex_to_pixel(*p.capital, s)
                        (ln,) = self.ax_map.plot(
                            [x1, x2],
                            [y1, y2],
                            ":",
                            color="#dda0dd",
                            alpha=0.35,
                            linewidth=1,
                        )
                        self.dyn.append(ln)

        # --- war lines ---
        for civ in alive:
            for p in alive:
                if civ.name < p.name and p.name in civ.enemies:
                    if civ.hexes and p.hexes:
                        x1, y1 = hex_to_pixel(*civ.capital, s)
                        x2, y2 = hex_to_pixel(*p.capital, s)
                        (ln,) = self.ax_map.plot(
                            [x1, x2],
                            [y1, y2],
                            "--",
                            color="red",
                            alpha=0.25,
                            linewidth=0.8,
                        )
                        self.dyn.append(ln)

        # --- selected hex highlight ---
        if self.selected:
            q, r = self.selected
            if (q, r) in self.engine.terrain:
                x, y = hex_to_pixel(q, r, s)
                hl = RegularPolygon(
                    (x, y),
                    6,
                    radius=s * 1.02,
                    orientation=0,
                    facecolor="none",
                    edgecolor="white",
                    linewidth=2.5,
                    zorder=8,
                )
                self.ax_map.add_patch(hl)
                self.dyn.append(hl)

        # --- turn counter ---
        victxt = (
            f"  🏆 {self.engine.victor.name} WINS!" if self.engine.victor else ""
        )
        t = self.ax_map.text(
            0.02,
            0.98,
            f"Turn {self.engine.turn}{victxt}",
            transform=self.ax_map.transAxes,
            fontsize=13,
            color="white",
            va="top",
            fontweight="bold",
            bbox=dict(boxstyle="round", facecolor="#16213e", alpha=0.85),
        )
        self.dyn.append(t)

        # ---- side panels ----
        self._chart_pop(alive)
        self._chart_terr(alive)
        self._panel_log()
        self._panel_info(alive)

    # ---------- side-panel helpers ----------
    def _style_ax(self, ax, title):
        ax.clear()
        ax.set_facecolor("#16213e")
        ax.set_title(title, color="white", fontsize=10, pad=4)
        ax.tick_params(colors="white", labelsize=7)
        for sp in ax.spines.values():
            sp.set_color("#333")

    def _chart_pop(self, alive):
        self._style_ax(self.ax_pop, "Population over Time")
        for c in alive:
            d = c.stats_history["population"]
            if d:
                self.ax_pop.plot(
                    range(len(d)),
                    d,
                    color=c.color,
                    lw=1.5,
                    label=c.name[:10],
                    alpha=0.85,
                )
        if alive:
            self.ax_pop.legend(
                loc="upper left",
                fontsize=6,
                framealpha=0.5,
                labelcolor="white",
                facecolor="#16213e",
                ncol=2,
            )

    def _chart_terr(self, alive):
        self._style_ax(self.ax_terr, "Territory Size")
        if alive:
            sizes = [len(c.hexes) for c in alive]
            colors = [c.color for c in alive]
            labels = [c.name[:8] for c in alive]
            wedges, _texts = self.ax_terr.pie(
                sizes, colors=colors, startangle=90, textprops={"fontsize": 6}
            )
            self.ax_terr.legend(
                labels,
                loc="center left",
                bbox_to_anchor=(-0.35, 0.5),
                fontsize=5,
                framealpha=0.3,
                labelcolor="white",
                facecolor="#16213e",
            )

    def _panel_log(self):
        self.ax_log.clear()
        self.ax_log.set_facecolor("#16213e")
        self.ax_log.axis("off")
        self.ax_log.set_title("Event Log", color="white", fontsize=10, pad=4)
        msgs = list(history_log)[-14:]
        for i, msg in enumerate(msgs):
            self.ax_log.text(
                0.02,
                0.95 - i * 0.07,
                msg,
                transform=self.ax_log.transAxes,
                fontsize=6.5,
                color="#cccccc",
                va="top",
                family="monospace",
            )

    def _panel_info(self, alive):
        self.ax_info.clear()
        self.ax_info.set_facecolor("#16213e")
        self.ax_info.axis("off")
        self.ax_info.set_title("Civilization Details", color="white", fontsize=10, pad=4)

        # Show selected hex info
        sel_text = ""
        if self.selected:
            q, r = self.selected
            t = self.engine.terrain.get((q, r), "???")
            res = self.engine.resources.get((q, r), "—")
            owner = self.engine.world.get((q, r), "unclaimed")
            sel_text = f"Hex ({q},{r}): {t}  Res: {res}  Owner: {owner}"

        y = 0.95
        if sel_text:
            self.ax_info.text(
                0.02, y, sel_text,
                transform=self.ax_info.transAxes,
                fontsize=7, color="#aaddff", va="top", family="monospace",
            )
            y -= 0.12

        for i, c in enumerate(alive[:6]):
            line = (
                f"{c.name[:14]:14s}  Pop:{c.population:>5d}  "
                f"Mil:{c.military:>4.0%}  Eco:{c.economy:>4.0%}  "
                f"Cul:{c.culture:>4.0%}  Stb:{c.stability:>4.0%}  "
                f"Hex:{len(c.hexes):>3d}  Era:{c.era[:3]}  "
                f"Tech:{len(c.technologies):>2d}"
            )
            self.ax_info.text(
                0.02,
                y - i * 0.12,
                line,
                transform=self.ax_info.transAxes,
                fontsize=6.5,
                color=c.color,
                va="top",
                family="monospace",
                fontweight="bold",
            )


# ============================================================
# MAIN
# ============================================================
def main():
    engine = SimEngine()
    renderer = Renderer(engine)

    def update(frame):
        global paused
        if not paused and engine.turn < CONFIG["max_turns"]:
            engine.step()
        renderer.render()

    ani = animation.FuncAnimation(
        renderer.fig,
        update,
        frames=CONFIG["max_turns"],
        interval=CONFIG["animation_interval"],
        repeat=False,
    )

    plt.show()


if __name__ == "__main__":
    main()