# config.py
"""
CivSim — Configuration and shared global state.
"""
from collections import deque

CONFIG = {
    "map_radius": 8,
    "hex_size": 1.0,
    "num_initial_civs": 5,
    "max_turns": 2000,
    "timer_interval": 500,
    "rebellion_stability": 0.18,
    "overthrow_stability": 0.12,
    "trade_bonus_base": 0.012,
    "max_log": 80,
    # Golden Age
    "golden_age_trigger_stability": 0.75,
    "golden_age_trigger_economy": 0.60,
    "golden_age_duration": 10,
    "golden_age_chance": 0.02,
    # War Weariness
    "war_weariness_rate": 0.003,
    "war_weariness_extended_rate": 0.005,
    "war_weariness_extended_threshold": 15,
    # Great People
    "great_person_base_chance": 0.015,
    # Victory Conditions
    "science_victory_min_techs": 18,
    "cultural_victory_min_culture": 1.5,
    "cultural_victory_min_wonders": 5,
    "economic_victory_min_economy": 1.8,
    "economic_victory_min_population": 2000,
    # AI
    "ai_strategy_reevaluate_interval": 10,
    "ai_min_strategy_duration": 8,
    "ai_threat_proximity_range": 10,
    "ai_coalition_threshold": 0.6,
    # Recording
    "recording_fps": 10,
    "recording_width": 1280,
    "recording_height": 720,
}

history_log = deque(maxlen=CONFIG["max_log"])
cultural_map = {}
active_disasters = {}
paused = False


def categorize_log(msg):
    """Categorize a log message for filtering."""
    if any(e in msg for e in ("⚔️", "🏹", "🗡️")):
        return "war"
    if "🔬" in msg:
        return "tech"
    if any(e in msg for e in ("🤝", "🕊️")):
        return "diplomacy"
    if any(e in msg for e in ("⚠️", "🌋", "🌊", "🔥", "☣️", "💥", "❄️")):
        return "disaster"
    if any(e in msg for e in ("🏗️", "🏛️")):
        return "wonder"
    if "💀" in msg:
        return "collapse"
    if "👑" in msg:
        return "overthrow"
    if "🏆" in msg:
        return "victory"
    if "🌟" in msg:
        return "golden_age"
    if "👤" in msg:
        return "great_person"
    return "other"