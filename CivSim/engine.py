# engine.py
"""
Core simulation loop: multiple victory conditions, save/load, snapshots.
"""
import random
import pickle
from config import CONFIG, history_log, active_disasters, cultural_map
from hex_utils import hex_distance, generate_hex_grid
from data import generate_civ_name
from civilization import Civilization
from map_gen import generate_terrain, generate_resources, generate_rivers


class SimEngine:
    def __init__(self):
        self.radius = CONFIG["map_radius"]
        self.terrain = generate_terrain(self.radius)
        self.resources = generate_resources(self.terrain)
        self.rivers = generate_rivers(self.terrain)
        self.world = {}
        self.civs = []
        self.turn = 0
        self.victor = None
        self.victory_type = None
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
            c.step(self.civs, self.world, self.terrain, self.resources, self.rivers)
        # Tick disasters
        expired = [h for h, (_, t) in active_disasters.items() if t <= 1]
        for h in expired:
            del active_disasters[h]
        for h in list(active_disasters):
            dt, t = active_disasters[h]
            active_disasters[h] = (dt, t - 1)
        self._check_victory()

    def _check_victory(self):
        alive = [c for c in self.civs if c.alive]
        if len(alive) == 1:
            self.victor = alive[0]
            self.victory_type = "Domination"
            history_log.append(f"🏆 {alive[0].name} wins by Domination!")
            return
        if len(alive) == 0:
            history_log.append("💀 All civilizations have fallen!")
            return
        for c in alive:
            if len(c.technologies) >= CONFIG["science_victory_min_techs"]:
                self.victor = c
                self.victory_type = "Science"
                history_log.append(f"🏆 {c.name} wins by Science Victory!")
                return
        for c in alive:
            if (c.culture >= CONFIG["cultural_victory_min_culture"]
                    and len(c.wonders_built) >= CONFIG["cultural_victory_min_wonders"]):
                self.victor = c
                self.victory_type = "Cultural"
                history_log.append(f"🏆 {c.name} wins by Cultural Victory!")
                return
        for c in alive:
            if (c.economy >= CONFIG["economic_victory_min_economy"]
                    and c.population >= CONFIG["economic_victory_min_population"]):
                self.victor = c
                self.victory_type = "Economic"
                history_log.append(f"🏆 {c.name} wins by Economic Victory!")
                return

    @property
    def alive_civs(self):
        return [c for c in self.civs if c.alive]

    # ------------------------------------------------------------------
    # Save / Load
    # ------------------------------------------------------------------
    def save(self, filename="civsim_save.pkl"):
        state = {
            "radius": self.radius,
            "terrain": self.terrain,
            "resources": self.resources,
            "rivers": self.rivers,
            "world": self.world,
            "civs": self.civs,
            "turn": self.turn,
            "victor_name": self.victor.name if self.victor else None,
            "victory_type": self.victory_type,
            "active_disasters": dict(active_disasters),
            "cultural_map": cultural_map,
        }
        with open(filename, "wb") as f:
            pickle.dump(state, f)
        return filename

    @classmethod
    def load(cls, filename="civsim_save.pkl"):
        with open(filename, "rb") as f:
            state = pickle.load(f)
        engine = cls.__new__(cls)
        engine.radius = state["radius"]
        engine.terrain = state["terrain"]
        engine.resources = state["resources"]
        engine.rivers = state["rivers"]
        engine.world = state["world"]
        engine.civs = state["civs"]
        engine.turn = state["turn"]
        engine.victory_type = state.get("victory_type")
        victor_name = state.get("victor_name")
        engine.victor = next((c for c in engine.civs if c.name == victor_name), None)
        active_disasters.clear()
        active_disasters.update(state.get("active_disasters", {}))
        cultural_map.clear()
        cultural_map.update(state.get("cultural_map", {}))
        return engine

    def get_hex_info(self, hex_coord):
        q, r = hex_coord
        info = {"coord": hex_coord}
        info["terrain"] = self.terrain.get(hex_coord, "plains")
        info["resource"] = self.resources.get(hex_coord, None)
        info["is_river"] = hex_coord in self.rivers
        info["owner"] = self.world.get(hex_coord, None)
        info["army"] = 0
        info["army_owner"] = None
        info["disaster"] = active_disasters.get(hex_coord, None)
        info["culture_dominant"] = None
        info["is_capital"] = False

        if info["owner"]:
            civ = next((c for c in self.civs
                        if c.name == info["owner"] and c.alive), None)
            if civ:
                if hex_coord == civ.capital:
                    info["is_capital"] = True
                army = civ.armies.get(hex_coord, 0)
                if army > 0:
                    info["army"] = army
                    info["army_owner"] = civ.name

        cdata = cultural_map.get(hex_coord, {})
        if cdata:
            info["culture_dominant"] = max(cdata, key=cdata.get)
        return info