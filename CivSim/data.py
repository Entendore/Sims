# data.py
"""
Static data: terrains, resources, tech tree, wonders, civ names, traits, great people.
"""
import random

TERRAINS = {
    "plains":   {"color": "#e0d9a0", "growth": 1.0, "defense": 1.0, "food": 1.0, "symbol": "🌾"},
    "mountain": {"color": "#8b8b8b", "growth": 0.3, "defense": 1.8, "food": 0.2, "symbol": "⛰️"},
    "water":    {"color": "#4a90e2", "growth": 0.0, "defense": 1.0, "food": 0.5, "symbol": "🌊"},
    "forest":   {"color": "#4fa24f", "growth": 0.7, "defense": 1.3, "food": 0.8, "symbol": "🌲"},
    "desert":   {"color": "#e0b563", "growth": 0.4, "defense": 0.8, "food": 0.3, "symbol": "🏜️"},
    "swamp":    {"color": "#2e8b57", "growth": 0.5, "defense": 1.1, "food": 0.6, "symbol": "🦆"},
    "hills":    {"color": "#d2b48c", "growth": 0.8, "defense": 1.4, "food": 0.7, "symbol": "🏔️"},
    "volcano":  {"color": "#ff4500", "growth": 0.2, "defense": 1.6, "food": 0.1, "symbol": "🌋"},
    "tundra":   {"color": "#c0d9e0", "growth": 0.4, "defense": 1.0, "food": 0.4, "symbol": "❄️"},
    "jungle":   {"color": "#228b22", "growth": 0.9, "defense": 1.1, "food": 0.9, "symbol": "🦜"},
    "coast":    {"color": "#5ba3cf", "growth": 0.8, "defense": 1.0, "food": 1.2, "symbol": "🏖️"},
}

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
    "oil":       {"bonus": "economy",    "value": 0.18, "color": "#333333", "symbol": "🛢"},
    "uranium":   {"bonus": "military",   "value": 0.20, "color": "#00ff00", "symbol": "☢"},
    "coal":      {"bonus": "economy",    "value": 0.12, "color": "#2c2c2c", "symbol": "⬛"},
}

RESOURCE_CHANCES = {
    "plains":   {"food": 0.35, "horses": 0.10, "gold": 0.05, "spices": 0.05},
    "mountain": {"iron": 0.30, "gold": 0.15, "stone": 0.20, "gems": 0.05, "coal": 0.05, "uranium": 0.02},
    "forest":   {"food": 0.20, "wood": 0.30, "knowledge": 0.08, "silk": 0.05},
    "desert":   {"spices": 0.15, "gold": 0.08, "gems": 0.05, "oil": 0.08},
    "swamp":    {"food": 0.15, "silk": 0.05, "fish": 0.10},
    "hills":    {"iron": 0.15, "stone": 0.20, "horses": 0.08, "gems": 0.03, "coal": 0.06},
    "volcano":  {"iron": 0.25, "gold": 0.10, "gems": 0.08, "uranium": 0.03},
    "tundra":   {"food": 0.08, "stone": 0.15, "iron": 0.05, "oil": 0.04},
    "jungle":   {"food": 0.20, "silk": 0.10, "spices": 0.10, "wood": 0.05},
    "coast":    {"fish": 0.35, "food": 0.10, "spices": 0.05, "gold": 0.03},
    "water":    {},
}

TECH_TREE = {
    "agriculture":      {"prereqs": [],                                  "effects": {"food_bonus": 0.10},                              "cost": 10,  "era": "ancient"},
    "mining":           {"prereqs": [],                                  "effects": {"military_bonus": 0.05},                         "cost": 10,  "era": "ancient"},
    "pottery":          {"prereqs": ["agriculture"],                     "effects": {"population_bonus": 0.05},                       "cost": 15,  "era": "ancient"},
    "bronze_working":   {"prereqs": ["mining"],                          "effects": {"military_bonus": 0.10},                         "cost": 20,  "era": "ancient"},
    "writing":          {"prereqs": ["pottery"],                         "effects": {"culture_bonus": 0.10},                          "cost": 25,  "era": "classical"},
    "iron_working":     {"prereqs": ["bronze_working"],                  "effects": {"military_bonus": 0.15},                         "cost": 30,  "era": "classical"},
    "currency":         {"prereqs": ["writing"],                         "effects": {"economy_bonus": 0.10},                          "cost": 30,  "era": "classical"},
    "mathematics":      {"prereqs": ["writing"],                         "effects": {"culture_bonus": 0.10},                          "cost": 35,  "era": "classical"},
    "compass":          {"prereqs": ["currency"],                        "effects": {"economy_bonus": 0.08, "expansion_bonus": 0.10}, "cost": 35,  "era": "medieval"},
    "machinery":        {"prereqs": ["mathematics"],                     "effects": {"economy_bonus": 0.08, "military_bonus": 0.05},  "cost": 45,  "era": "medieval"},
    "engineering":      {"prereqs": ["mathematics", "iron_working"],     "effects": {"economy_bonus": 0.15, "defense_bonus": 0.10},   "cost": 50,  "era": "medieval"},
    "feudalism":        {"prereqs": ["currency"],                        "effects": {"stability_bonus": 0.10},                        "cost": 40,  "era": "medieval"},
    "gunpowder":        {"prereqs": ["engineering"],                     "effects": {"military_bonus": 0.20},                         "cost": 60,  "era": "renaissance"},
    "chemistry":        {"prereqs": ["gunpowder"],                       "effects": {"military_bonus": 0.08, "economy_bonus": 0.05},  "cost": 65,  "era": "renaissance"},
    "banking":          {"prereqs": ["currency", "feudalism"],           "effects": {"economy_bonus": 0.20},                          "cost": 55,  "era": "renaissance"},
    "printing":         {"prereqs": ["machinery"],                       "effects": {"culture_bonus": 0.20},                          "cost": 50,  "era": "renaissance"},
    "industrialism":    {"prereqs": ["gunpowder", "banking"],            "effects": {"economy_bonus": 0.25},                          "cost": 80,  "era": "industrial"},
    "nationalism":      {"prereqs": ["printing"],                        "effects": {"military_bonus": 0.15, "stability_bonus": 0.10},"cost": 70,  "era": "industrial"},
    "electricity":      {"prereqs": ["industrialism", "chemistry"],      "effects": {"economy_bonus": 0.15, "culture_bonus": 0.10},   "cost": 90,  "era": "industrial"},
    "flight":           {"prereqs": ["electricity"],                     "effects": {"military_bonus": 0.12, "expansion_bonus": 0.12},"cost": 100, "era": "industrial"},
    "nuclear_physics":  {"prereqs": ["flight", "nationalism"],           "effects": {"military_bonus": 0.25},                         "cost": 120, "era": "modern"},
    "globalization":    {"prereqs": ["electricity", "banking"],          "effects": {"economy_bonus": 0.20, "culture_bonus": 0.10},   "cost": 110, "era": "modern"},
    "computing":        {"prereqs": ["electricity", "nationalism"],      "effects": {"culture_bonus": 0.20, "economy_bonus": 0.10},   "cost": 130, "era": "information"},
    "space_flight":     {"prereqs": ["nuclear_physics", "computing"],    "effects": {"culture_bonus": 0.30, "military_bonus": 0.10},  "cost": 150, "era": "information"},
    "synthetic_biology":{"prereqs": ["computing", "chemistry"],          "effects": {"population_bonus": 0.15, "food_bonus": 0.15},   "cost": 140, "era": "information"},
}

WONDERS = [
    {"name": "Great Pyramid",   "cost": 50,  "effects": {"military_bonus": 0.05, "economy_bonus": 0.05},  "prereq_tech": "mining"},
    {"name": "Hanging Gardens", "cost": 60,  "effects": {"population_bonus": 0.10, "culture_bonus": 0.05}, "prereq_tech": "agriculture"},
    {"name": "Great Library",   "cost": 70,  "effects": {"culture_bonus": 0.15},                         "prereq_tech": "writing"},
    {"name": "Colosseum",       "cost": 65,  "effects": {"stability_bonus": 0.10, "military_bonus": 0.05}, "prereq_tech": "iron_working"},
    {"name": "Silk Road",       "cost": 80,  "effects": {"economy_bonus": 0.20},                         "prereq_tech": "currency"},
    {"name": "Grand Cathedral", "cost": 90,  "effects": {"culture_bonus": 0.10, "stability_bonus": 0.15}, "prereq_tech": "feudalism"},
    {"name": "Machu Picchu",    "cost": 75,  "effects": {"economy_bonus": 0.10, "stability_bonus": 0.10}, "prereq_tech": "engineering"},
    {"name": "Angkor Wat",      "cost": 80,  "effects": {"culture_bonus": 0.15, "population_bonus": 0.05}, "prereq_tech": "feudalism"},
    {"name": "Arsenal",         "cost": 85,  "effects": {"military_bonus": 0.20},                        "prereq_tech": "gunpowder"},
    {"name": "Stock Exchange",  "cost": 100, "effects": {"economy_bonus": 0.25},                        "prereq_tech": "banking"},
    {"name": "Eiffel Tower",    "cost": 95,  "effects": {"culture_bonus": 0.15, "economy_bonus": 0.10},  "prereq_tech": "industrialism"},
    {"name": "United Nations",  "cost": 120, "effects": {"stability_bonus": 0.20, "culture_bonus": 0.10}, "prereq_tech": "globalization"},
]

GREAT_PEOPLE = {
    "Great General":   {"bonus": "military",  "value": 0.20, "duration": 8, "symbol": "⚔️"},
    "Great Merchant":  {"bonus": "economy",   "value": 0.20, "duration": 8, "symbol": "💰"},
    "Great Scientist": {"bonus": "research",  "value": 0.50, "duration": 8, "symbol": "🔬"},
    "Great Artist":    {"bonus": "culture",   "value": 0.20, "duration": 8, "symbol": "🎨"},
    "Great Engineer":  {"bonus": "wonder",    "value": 0.50, "duration": 8, "symbol": "🔨"},
}

ERA_ORDER = ["ancient", "classical", "medieval", "renaissance", "industrial", "modern", "information"]

ERA_COLORS = {
    "ancient": "#a0522d", "classical": "#cd853f", "medieval": "#8b0000",
    "renaissance": "#daa520", "industrial": "#708090", "modern": "#4682b4",
    "information": "#9370db",
}

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

CIV_COLORS = [
    "#e6194b", "#3cb44b", "#ffe119", "#4363d8", "#f58231",
    "#911eb4", "#42d4f4", "#f032e6", "#bfef45", "#fabed4",
    "#469990", "#dcbeff", "#9A6324", "#fffac8", "#800000",
    "#aaffc3", "#808000", "#ffd8b1", "#000075", "#a9a9a9",
]


def generate_civ_name():
    return random.choice(CIV_PREFIXES) + random.choice(CIV_SUFFIXES)


def generate_splinter_name(parent):
    return random.choice([
        f"Neo-{parent}", f"{parent} Horde", f"{parent} Dominion",
        f"Free {parent}", f"{parent} Rebels", f"{parent} Secession",
    ])


def generate_dynasty_name(parent):
    return random.choice([
        f"The {parent} Empire", f"Kingdom of {parent}", f"{parent} Republic",
        f"New {parent}", f"Grand {parent}", f"{parent} Federation",
    ])