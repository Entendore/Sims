# civilization.py
"""
Civilization entity: stats, per-turn logic, diplomacy, combat, golden ages,
great people, and war weariness.
"""
import random
from collections import defaultdict
from config import CONFIG, history_log, cultural_map, active_disasters
from hex_utils import hex_neighbors
from data import (
    TERRAINS, RESOURCES, TECH_TREE, WONDERS, TRAITS, TRAIT_EFFECTS,
    CIV_COLORS, GREAT_PEOPLE,
    generate_civ_name, generate_splinter_name, generate_dynasty_name,
)
from ai import CivMDP, ExpansionMCTS

_mdp = CivMDP()


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
        self.era = "ancient"
        self.strategy_name = "economy"
        # Golden Age
        self.in_golden_age = False
        self.golden_age_turns = 0
        # Great Person
        self.great_person = None       # {"type": ..., "turns_left": ...}
        self.great_person_name = ""
        # War weariness tracker
        self._war_turns = {}
        # Internal world reference (set each step)
        self._world = {}
        self._rivers = set()
        self.stats_history = defaultdict(list)
        self._record_stats()
        self._apply_trait()

    # ------------------------------------------------------------------
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
        # Great person bonus
        if self.great_person:
            gp = GREAT_PEOPLE[self.great_person["type"]]
            bkey = f"{gp['bonus']}_bonus"
            if gp["bonus"] == "research":
                self.bonuses["culture_bonus"] += gp["value"]
            elif gp["bonus"] == "wonder":
                self.bonuses["economy_bonus"] += gp["value"]
            else:
                self.bonuses[bkey] += gp["value"]
        # Golden age bonus
        if self.in_golden_age:
            self.bonuses["economy_bonus"] += 0.15
            self.bonuses["culture_bonus"] += 0.15
            self.bonuses["military_bonus"] += 0.10

    # ------------------------------------------------------------------
    @property
    def total_army(self):
        return sum(self.armies.values())

    @property
    def power(self):
        return (self.population * 0.3 + self.military * 40 + self.economy * 30 +
                self.culture * 20 + len(self.hexes) * 5 + len(self.technologies) * 10)

    # ------------------------------------------------------------------
    def step(self, civs, world, terrain, resources, rivers=None):
        if not self.alive:
            return
        self._world = world
        self._rivers = rivers or set()
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

        # Stability decay from over-extension
        over = max(0, len(self.hexes) - 8) * 0.003
        sb = self.bonuses.get("stability_bonus", 0)
        self.stability = max(0.03, min(1.0, self.stability - over + sb * 0.01))

        # MDP action
        action = _mdp.get_action(self)
        self.strategy_name = action
        self._do_action(action)

        self._research()
        self._build_wonder()
        self._expand(world, terrain, resources, self._rivers)
        self._recruit()
        self._attack(world, terrain, civs)
        self._move_armies()
        self._update_truces()
        self._diplomacy(civs)
        self._trade(civs)
        self._spread_culture()
        self._trigger_disasters(terrain)
        self._suffer_disasters()
        self._maybe_rebellion(civs, world)
        self._maybe_overthrow()
        self._war_weariness()
        self._check_golden_age()
        self._maybe_great_person()

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

        # Collapse check
        if self.population <= 0 or self.stability <= 0.03:
            for h in list(self.hexes):
                world.pop(h, None)
            self.hexes.clear()
            self.alive = False
            history_log.append(f"💀 {self.name} collapsed!")

    # ------------------------------------------------------------------
    # Core systems
    # ------------------------------------------------------------------
    def _do_action(self, action):
        mb = self.bonuses.get("military_bonus", 0)
        eb = self.bonuses.get("economy_bonus", 0)
        cb = self.bonuses.get("culture_bonus", 0)
        if action == "military":
            self.military += 0.012 * (1 + mb); self.economy -= 0.004
        elif action == "economy":
            self.economy += 0.012 * (1 + eb); self.military -= 0.003
        elif action == "culture":
            self.culture += 0.010 * (1 + cb)
        elif action == "stability":
            self.stability = min(1.0, self.stability + 0.015); self.economy -= 0.002
        self.military = max(0.05, min(2.0, self.military))
        self.economy = max(0.05, min(2.0, self.economy))
        self.culture = max(0.05, min(2.0, self.culture))
        self.stability = max(0.03, min(1.0, self.stability))

    def _research(self):
        tb = self.bonuses.get("culture_bonus", 0) + TRAIT_EFFECTS.get(self.trait, {}).get("tech_bonus", 0)
        rate = 0.5 + self.culture * 0.3 + tb
        if self.researching is None:
            avail = [t for t, info in TECH_TREE.items()
                     if t not in self.technologies and all(p in self.technologies for p in info["prereqs"])]
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
            avail = [w for w in WONDERS
                     if w["name"] not in built_names and w["prereq_tech"] in self.technologies]
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

    def _expand(self, world, terrain, resources, rivers=None):
        rivers = rivers or set()
        eb = TRAIT_EFFECTS.get(self.trait, {}).get("expansion_bonus", 0)
        attempts = max(1, int((self.military + eb) * 8))
        for _ in range(attempts):
            if not self.hexes:
                break
            origin = random.choice(list(self.hexes))
            cands = [n for n in hex_neighbors(*origin)
                     if terrain.get(n, "plains") != "water" and n not in world]
            if not cands:
                continue
            if self.trait in ("expansionist", "aggressive") and len(cands) > 1:
                target = ExpansionMCTS(self, world, terrain, resources, rivers).search()
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
                break

    def _recruit(self):
        for h in list(self.armies):
            if h in self.hexes:
                self.armies[h] += int(self.military * 2 * self.economy * random.uniform(0.5, 1.5))
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
            mh, tgt, ma = max(attacks, key=lambda x: x[2] / (1 + enemy.armies.get(x[1], 1)))
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
                    border = [n for n in nbrs
                              if any(nn not in self.hexes and nn in self._world
                                     for nn in hex_neighbors(*n))]
                    to = random.choice(border) if border else random.choice(nbrs)
                    sz = self.armies.pop(h, 0)
                    self.armies[to] = self.armies.get(to, 0) + sz

    def _update_truces(self):
        expired = [n for n, t in self.truce.items() if t <= 1]
        for n in expired:
            del self.truce[n]
        for n in list(self.truce):
            self.truce[n] -= 1

    def _diplomacy(self, civs):
        wc = TRAIT_EFFECTS.get(self.trait, {}).get("war_chance", 0)
        if random.random() < 0.05:
            others = [c for c in civs if c.alive and c != self
                      and c.name not in self.allies and c.name not in self.enemies
                      and c.name not in self.truce]
            if others:
                p = random.choice(others)
                if self.trait in ("peaceful", "merchant") or p.trait in ("peaceful", "merchant"):
                    if random.random() < 0.3:
                        self.allies.add(p.name); p.allies.add(self.name)
                        history_log.append(f"🤝 {self.name} allied with {p.name}")
                        return
                if random.random() < 0.15 + wc:
                    if not any(a in self.allies for a in p.allies):
                        self.enemies.add(p.name); p.enemies.add(self.name)
                        history_log.append(f"⚔️ {self.name} declared war on {p.name}!")
        for en in list(self.enemies):
            if random.random() < 0.02:
                e = next((c for c in civs if c.name == en and c.alive), None)
                if e:
                    self.enemies.discard(en); e.enemies.discard(self.name)
                    t = random.randint(5, 15)
                    self.truce[en] = t; e.truce[self.name] = t
                    history_log.append(f"🕊️ {self.name} made peace with {en}")
        if self.trait == "aggressive" and self.allies and random.random() < 0.01:
            an = random.choice(list(self.allies))
            a = next((c for c in civs if c.name == an and c.alive), None)
            if a:
                self.allies.discard(an); a.allies.discard(self.name)
                self.enemies.add(an); a.enemies.add(self.name)
                history_log.append(f"🗡️ {self.name} betrayed {an}!")

    def _trade(self, civs):
        tb = TRAIT_EFFECTS.get(self.trait, {}).get("trade_bonus", CONFIG["trade_bonus_base"])
        for p in civs:
            if (p.alive and p != self and self.name < p.name
                    and (p.name in self.allies
                         or (self.trait in ("merchant", "peaceful")
                             and p.trait in ("merchant", "peaceful")))):
                eb = self.bonuses.get("economy_bonus", 0)
                peb = p.bonuses.get("economy_bonus", 0)
                self.economy += tb * p.economy * (1 + eb)
                p.economy += tb * self.economy * (1 + peb)

    def _spread_culture(self):
        cb = self.bonuses.get("culture_bonus", 0)
        for h in self.hexes:
            cultural_map.setdefault(h, {})
            cultural_map[h][self.name] = cultural_map[h].get(self.name, 0) + self.culture * (1 + cb)
            for n in hex_neighbors(*h):
                cultural_map.setdefault(n, {})
                cultural_map[n][self.name] = cultural_map[n].get(self.name, 0) + self.culture * 0.05

    # ------------------------------------------------------------------
    # Disasters
    # ------------------------------------------------------------------
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
                history_log.append(f"⚠️ {self.name}: {dt} at ({h[0]},{h[1]})")

    def _suffer_disasters(self):
        for h in list(self.hexes):
            if h in active_disasters:
                dt, _ = active_disasters[h]
                if dt in ("flood", "blizzard"):
                    self.population -= random.randint(2, 8); self.economy -= 0.005
                elif dt == "drought":
                    self.population -= random.randint(1, 5); self.economy -= 0.01
                elif dt == "plague":
                    self.population -= random.randint(5, 20); self.stability -= 0.01
                elif dt in ("volcano", "earthquake"):
                    self.population -= random.randint(5, 15); self.economy -= 0.01; self.stability -= 0.005
                if h in self.armies:
                    self.armies[h] = max(0, self.armies[h] - random.randint(2, 8))

    # ------------------------------------------------------------------
    # Rebellion & overthrow
    # ------------------------------------------------------------------
    def _maybe_rebellion(self, civs, world):
        if (self.stability < CONFIG["rebellion_stability"] and self.population > 100
                and len(self.hexes) >= 3 and random.random() < 0.03):
            n = len(self.hexes) // 3
            rh = random.sample(list(self.hexes), max(1, n))
            name = generate_splinter_name(self.name)
            rq, rr = rh[0]
            nc = Civilization(name, rq, rr, trait=random.choice(TRAITS), parent=self.name)
            nc.hexes = set(rh)
            nc.armies = {h: max(5, self.armies.get(h, 10) // 2) for h in rh}
            for h in rh:
                self.hexes.discard(h); world[h] = nc.name; self.armies.pop(h, None)
            nc.population = self.population // 4
            self.population = int(self.population * 0.75)
            self.enemies.add(nc.name); nc.enemies.add(self.name)
            civs.append(nc)
            history_log.append(f"⚔️ {nc.name} rebelled from {self.name}!")

    def _maybe_overthrow(self):
        if (self.stability < CONFIG["overthrow_stability"] and self.population > 100
                and random.random() < 0.02):
            old = self.name
            self.name = generate_dynasty_name(old)
            self.stability = min(0.8, self.stability + 0.2)
            history_log.append(f"👑 {old} overthrown! Now: {self.name}")

    # ------------------------------------------------------------------
    # Golden Age
    # ------------------------------------------------------------------
    def _check_golden_age(self):
        if self.in_golden_age:
            self.golden_age_turns -= 1
            if self.golden_age_turns <= 0:
                self.in_golden_age = False
                history_log.append(f"🌟 {self.name}'s Golden Age ends")
            return
        if (self.stability >= CONFIG["golden_age_trigger_stability"]
                and self.economy >= CONFIG["golden_age_trigger_economy"]
                and random.random() < CONFIG["golden_age_chance"]):
            self.in_golden_age = True
            self.golden_age_turns = CONFIG["golden_age_duration"]
            history_log.append(f"🌟 {self.name} enters a Golden Age!")

    # ------------------------------------------------------------------
    # Great People
    # ------------------------------------------------------------------
    def _maybe_great_person(self):
        if self.great_person:
            self.great_person["turns_left"] -= 1
            if self.great_person["turns_left"] <= 0:
                gp_type = self.great_person["type"]
                self.great_person = None
                self.great_person_name = ""
                history_log.append(f"👤 {self.name}'s {gp_type} departs")
            return
        if random.random() < CONFIG["great_person_base_chance"] * (1 + self.culture):
            gp_type = random.choice(list(GREAT_PEOPLE.keys()))
            gp = GREAT_PEOPLE[gp_type]
            self.great_person = {"type": gp_type, "turns_left": gp["duration"]}
            self.great_person_name = gp_type
            history_log.append(f"👤 {self.name}: {gp['symbol']} {gp_type} appears!")

    # ------------------------------------------------------------------
    # War Weariness
    # ------------------------------------------------------------------
    def _war_weariness(self):
        for ename in list(self.enemies):
            self._war_turns[ename] = self._war_turns.get(ename, 0) + 1
        for ename in list(self._war_turns):
            if ename not in self.enemies:
                del self._war_turns[ename]
        for ename, turns in self._war_turns.items():
            if turns > CONFIG["war_weariness_extended_threshold"]:
                self.stability -= CONFIG["war_weariness_extended_rate"]
            else:
                self.stability -= CONFIG["war_weariness_rate"]
        self.stability = max(0.03, self.stability)