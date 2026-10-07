from __future__ import annotations

import random
import threading
import time

from .content import (
    MINOR_REALM_NAMES,
    minor_realm_name,
    EQUIP_SLOTS,
    item_slot,
    DESTINIES,
    DESTINY_DESCRIPTIONS,
    EXPLORATION_EVENTS,
    BOSS_MONSTERS,
    GACHA_TABLE,
    ITEMS,
    MONSTERS,
    PATH_TALENTS,
    REALMS,
    SHOP_CATEGORIES,
    SHOP_ORDER,
    TALENT_DESCRIPTIONS,
    REDEEM_CODES,
    TRIBULATION_REALMS, DAO_PATHS, DAO_STAGE_THRESHOLD, EXPLORE_ZONES, STATUS_EFFECTS, TRIAL_TOWER, ASCENSION_TOWER, SECT_TOWER, SECT_MISSIONS, INHERITANCE_EVENTS,
)
from .database import Database, Player

COOLDOWNS = {"cultivate": 25, "explore": 90, "hunt": 75, "song_tu": 30 * 60}
DAILY_COOLDOWN = 24 * 60 * 60
STARTING_STONES = 1000
GACHA_TICKET_ID = "thien_co_lenh"
BE_QUAN_COST = 50
BE_QUAN_INTERVAL = 5 * 60


def weighted_pick(rng: random.Random, entries):
    population = [item for item, _weight in entries]
    weights = [weight for _item, weight in entries]
    return rng.choices(population, weights=weights, k=1)[0]


def fmt_amount(value: int) -> str:
    return f"{int(value):,}".replace(",", ".")


class GameError(Exception):
    pass


class GameEngine:
    def __init__(self, db: Database, rng: random.Random | None = None):
        self.db = db
        self.rng = rng or random.Random()
        self._player_locks: dict[str, threading.RLock] = {}
        self._player_locks_guard = threading.Lock()
        self._sect_locks: dict[str, threading.RLock] = {}
        self._sect_locks_guard = threading.Lock()
        self.db.seed_redeem_codes(REDEEM_CODES)
        self._migrate_technique_bonuses()

    TECHNIQUE_STAT_LABELS = {
        "root": "căn cơ", "insight": "ngộ tính", "luck": "khí vận",
        "fate": "thiên mệnh", "mind": "tâm tính",
    }

    def _apply_technique_bonus(self, player: Player, item_id: str) -> tuple[str, int]:
        item = ITEMS.get(item_id, {})
        stat = item.get("technique_stat")
        bonus = int(item.get("technique_bonus", 0))
        if stat not in self.TECHNIQUE_STAT_LABELS or bonus <= 0:
            return "", 0
        current = int(getattr(player, stat))
        actual = self._soft_capped_stat_gain(current, bonus)
        updated = min(100, current + actual)
        setattr(player, stat, updated)
        return self.TECHNIQUE_STAT_LABELS[stat], actual

    def _migrate_technique_bonuses(self) -> None:
        # Give the new passive bonus to techniques learned by older saves exactly once.
        for user_id in self.db.list_player_ids():
            player = self.db.get_player(user_id)
            if not player:
                continue
            changed = False
            for key in self.db.list_discoveries(user_id, "technique:"):
                item_id = key.split(":", 1)[1]
                marker = f"technique_bonus:{item_id}"
                if self.db.get_discovery(user_id, marker):
                    continue
                item = ITEMS.get(item_id, {})
                if item.get("type") != "technique":
                    continue
                _, actual = self._apply_technique_bonus(player, item_id)
                self.db.add_discovery(user_id, marker)
                changed = changed or actual > 0
            if changed:
                self.db.save_player(player)

    def _player_lock(self, user_id: str) -> threading.RLock:
        key = str(user_id)
        with self._player_locks_guard:
            lock = self._player_locks.get(key)
            if lock is None:
                lock = threading.RLock()
                self._player_locks[key] = lock
            return lock

    def _sect_lock(self, sect_id: str) -> threading.RLock:
        key = str(sect_id)
        with self._sect_locks_guard:
            lock = self._sect_locks.get(key)
            if lock is None:
                lock = threading.RLock()
                self._sect_locks[key] = lock
            return lock

    # ---------- character ----------
    def exists(self, user_id: str) -> bool:
        return self.db.get_player(user_id) is not None

    def roll_stat(self, low: int = 35, high: int = 92) -> int:
        value = int(self.rng.triangular(low, high, 70))
        if self.rng.random() < 0.03:
            value = self.rng.randint(max(75, value), 100)
        return min(value, 100)

    def roll_destiny(self) -> str:
        return weighted_pick(self.rng, DESTINIES)

    def roll_talent(self, path: str) -> str:
        return weighted_pick(self.rng, PATH_TALENTS[path])

    def create_character(self, user_id: str, display_name: str, path: str) -> Player:
        if path not in {"tien", "ma"}:
            raise GameError("Đạo không hợp lệ. Hãy chọn `.tutien` rồi chọn Tiên hoặc Ma.")
        if self.exists(user_id):
            raise GameError("Ngươi đã có nhân vật rồi. Dùng `.info` để xem thiên mệnh.")

        destiny = self.roll_destiny()
        talent = self.roll_talent(path)
        root, insight, luck, fate, mind = [self.roll_stat() for _ in range(5)]

        if destiny == "Thiên Mệnh Chi Tử":
            luck = min(100, luck + 10); fate = min(100, fate + 10)
        elif destiny == "Đại Khí Vãn Thành":
            root = min(100, root + 4); insight = min(100, insight + 4)
        elif destiny == "Sát Phạt Chi Mệnh":
            mind = min(100, mind + 6)
        elif destiny == "Thiên Sát Cô Tinh":
            fate = min(100, fate + 7)
        elif destiny == "Phúc Tinh":
            luck = min(100, luck + 6); fate = min(100, fate + 5)
        elif destiny == "Kiếm Tu Chi Mệnh":
            insight = min(100, insight + 5)

        talent_bonus = {
            "Thanh Vân Đạo Thể": (5, 0, 0, 0, 0), "Kiếm Tâm Sơ Thành": (0, 5, 0, 0, 0),
            "Tử Khí Đông Lai": (0, 0, 7, 0, 0), "Dược Linh Thân": (3, 0, 0, 0, 0),
            "Huyết Ma Chi Thể": (0, 0, 0, 0, 5), "Thôn Thiên Ma Cốt": (6, 0, 0, 0, 0),
            "Ma Diễm Tâm": (0, 5, 0, 0, 0), "Hắc Nhật Ma Thai": (0, 0, 0, 5, 0),
        }.get(talent, (0, 0, 0, 0, 0))
        root = min(100, root + talent_bonus[0]); insight = min(100, insight + talent_bonus[1])
        luck = min(100, luck + talent_bonus[2]); fate = min(100, fate + talent_bonus[3]); mind = min(100, mind + talent_bonus[4])

        now = int(time.time())
        player = Player(
            user_id=str(user_id), display_name=display_name[:64], path=path,
            realm_idx=0, layer=0, cultivation=0, root=root, insight=insight,
            luck=luck, fate=fate, mind=mind, karma=10 if path == "ma" else 0,
            merit=0, destiny=destiny, talent=talent, spirit_stones=STARTING_STONES,
            pity=0, equipped=None, last_cultivate=0, last_explore=0, last_hunt=0,
            last_daily=0, daily_streak=0, created_at=now, updated_at=now, injury=0, be_quan_active=0, be_quan_last_tick=0, be_quan_prepaid=0,
            foundation=max(30, min(100, int(root * 0.65 + insight * 0.20 + mind * 0.15))), dao_type=None, dao_stage=0, dao_progress=0,
            explore_zone="hoangnguyen", trial_best=0, trial_attempts=0, trial_day=0, last_trial=0, tribulation_ready=0, loadout="{}",
        )
        self.db.create_player(player)
        return player

    # ---------- derived stats ----------
    def realm_name(self, player: Player) -> str:
        return REALMS[min(player.realm_idx, len(REALMS) - 1)][0]

    def minor_realm(self, player: Player) -> str:
        realm = REALMS[min(player.realm_idx, len(REALMS) - 1)]
        return minor_realm_name(player.layer, realm[1])

    def realm_text(self, player: Player) -> str:
        name = self.realm_name(player)
        minor = self.minor_realm(player)
        if player.layer == 0:
            return f"{name} · {minor}"
        return f"{name} · {minor} (tầng {player.layer})"

    def is_max_realm(self, player: Player) -> bool:
        return player.realm_idx >= len(REALMS) - 1 and player.layer >= REALMS[-1][1]

    def cultivation_requirement(self, player: Player) -> int:
        # Requirement grows super-linearly: every higher realm is materially harder.
        if player.realm_idx == 0:
            return 1000
        realm_base = 1400 * (1.34 ** max(0, player.realm_idx - 1))
        layer_factor = 1.0 + max(0, player.layer - 1) * 0.16
        return max(1000, int(realm_base * layer_factor))

    def cultivation_headroom(self, player: Player) -> int:
        return max(0, self.cultivation_requirement(player) - player.cultivation)

    def add_cultivation(self, player: Player, amount: int) -> int:
        """Apply cultivation through one canonical, cap-safe path."""
        if amount <= 0 or self.is_max_realm(player):
            return 0
        cap = self.cultivation_requirement(player)
        gain = max(0, min(int(amount), max(0, cap - player.cultivation)))
        player.cultivation += gain
        if (
            player.realm_idx in TRIBULATION_REALMS
            and player.realm_idx == 9
            and player.layer == REALMS[9][1]
            and player.cultivation >= cap
        ):
            player.tribulation_ready = 1
        return gain

    @staticmethod
    def _soft_capped_stat_gain(current: int, requested: int) -> int:
        """Diminishing-return growth for permanent stats; hard cap at 100."""
        current = max(0, min(100, int(current)))
        requested = max(0, int(requested))
        if requested <= 0 or current >= 100:
            return 0
        if current < 70:
            effective = requested
        elif current < 90:
            effective = max(1, int(requested * 0.60))
        else:
            effective = max(1, int(requested * 0.35))
        return min(effective, 100 - current)

    def _gain_dao_insight_locked(self, player: Player, amount: int = 1) -> int:
        if not player.dao_type or amount <= 0:
            return 0
        info = DAO_PATHS[player.dao_type]
        before = int(player.dao_progress)
        player.dao_progress = min(DAO_STAGE_THRESHOLD[-1], before + int(amount))
        while player.dao_stage < len(info["stages"]) - 1 and player.dao_progress >= DAO_STAGE_THRESHOLD[player.dao_stage + 1]:
            player.dao_stage += 1
        return player.dao_progress - before

    def _dao_combat_progress_locked(self, player: Player, *, skill: bool = False, damage_taken: bool = False) -> int:
        if not player.dao_type:
            return 0
        equipped = ITEMS.get(player.equipped or {}, {}) if player.equipped else {}
        weapon_name = str(equipped.get("name", ""))
        gain = 0
        if player.dao_type == "kiem" and "Kiếm" in weapon_name:
            gain = 7 if skill else 5
        elif player.dao_type == "dao" and "Đao" in weapon_name:
            gain = 7 if skill else 5
        elif player.dao_type == "phap" and skill:
            gain = 8
        elif player.dao_type == "the":
            gain = 6 if damage_taken else 4
        return self._gain_dao_insight_locked(player, gain)

    def stat_contributions(self, player: Player) -> dict:
        """Named contributions. Core totals match v1.16.4 battle_stats."""
        equipment_attack = equipment_defense = 0
        loadout = self._parse_loadout(player)
        for _slot, eid in loadout.items():
            if not eid:
                continue
            piece = ITEMS.get(eid, {})
            equipment_attack += int(piece.get("attack", 0))
            equipment_defense += int(piece.get("defense", 0))
        # legacy single equipped if loadout empty
        if not any(loadout.values()) and player.equipped:
            item = ITEMS.get(player.equipped, {})
            equipment_attack = int(item.get("attack", 0))
            equipment_defense = int(item.get("defense", 0))
        dao_stage = int(getattr(player, "dao_stage", 0) or 0)
        dao_hp = dao_atk = dao_def = 0
        if player.dao_type == "kiem":
            dao_atk += dao_stage * 18
        elif player.dao_type == "dao":
            dao_atk += dao_stage * 14
            dao_def += dao_stage * 8
        elif player.dao_type == "the":
            dao_hp += dao_stage * 180
            dao_def += dao_stage * 18
        return {
            "realm_hp": 1000 + player.realm_idx * 900 + player.layer * 120,
            "foundation_hp": player.root * 25,
            "equipment_hp": equipment_defense * 5,
            "dao_hp": dao_hp,
            "realm_attack": 80 + player.realm_idx * 120 + player.layer * 20,
            "foundation_attack": player.insight * 3,
            "equipment_attack": equipment_attack,
            "dao_attack": dao_atk,
            "realm_defense": 60 + player.realm_idx * 100 + player.layer * 18,
            "foundation_defense": player.root * 2,
            "equipment_defense": equipment_defense * 2,
            "dao_defense": dao_def,
            "dao_stage": dao_stage,
        }

    def mental_state(self, player: Player) -> str:
        if int(player.injury or 0) >= 35 or int(player.mind) <= 25:
            return "Tâm ma"
        if int(player.injury or 0) >= 15 or int(player.mind) <= 45:
            return "Bất ổn"
        if int(player.mind) >= 80:
            return "Ổn định"
        return "Bình thường"

    def battle_stats(self, player: Player) -> dict:
        parts = self.stat_contributions(player)
        hp = parts["realm_hp"] + parts["foundation_hp"] + parts["equipment_hp"] + parts["dao_hp"]
        attack = parts["realm_attack"] + parts["foundation_attack"] + parts["equipment_attack"] + parts["dao_attack"]
        defense = parts["realm_defense"] + parts["foundation_defense"] + parts["equipment_defense"] + parts["dao_defense"]
        injury_factor = max(0.45, 1.0 - min(55, player.injury) / 100.0)
        hp = max(1, int(hp * injury_factor))
        dao_stage = parts["dao_stage"]
        crit_chance = min(0.18, 0.05 + player.insight * 0.0008 + player.fate * 0.0004 + (dao_stage * 0.012 if player.dao_type == "phap" else 0.0))
        crit_multiplier = min(1.65, 1.50 + player.mind * 0.001)
        rating = int((hp / 100.0) * 20 + (attack / 10.0) * 35 + (defense / 10.0) * 25 + player.insight * 0.1 + player.root * 0.1)
        speed = 40 + player.realm_idx * 4 + player.layer + int(player.insight * 0.12)
        accuracy = 72 + min(18, player.insight // 6)
        evasion = 6 + min(16, player.luck // 7)
        return {
            "hp": hp,
            "attack": attack,
            "defense": defense,
            "rating": max(1, rating),
            "crit_chance": crit_chance,
            "crit_multiplier": crit_multiplier,
            "speed": speed,
            "accuracy": accuracy,
            "evasion": evasion,
            "phys_res": min(35, defense // 50),
            "magic_res": min(35, int(player.mind) // 4),
            "control_res": min(30, int(player.mind) // 5),
            "spirit": 100 + player.realm_idx * 40 + player.insight,
            "stamina": 100 + player.realm_idx * 30 + player.root,
            "mental_state": self.mental_state(player),
            "contributions": parts,
        }


    # ---------- status effects (lightweight Discord turn combat) ----------
    def _new_status(self, effect_id: str, duration: int | None = None) -> dict | None:
        spec = STATUS_EFFECTS.get(effect_id)
        if not spec:
            return None
        return {
            "id": effect_id,
            "name": spec["name"],
            "kind": spec["kind"],
            "duration": int(duration if duration is not None else spec["duration"]),
            "power": float(spec["power"]),
        }

    def _status_list(self, container: dict, side: str) -> list:
        key = f"{side}_statuses"
        if key not in container or container[key] is None:
            container[key] = []
        return container[key]

    def apply_status(self, container: dict, side: str, effect_id: str, duration: int | None = None) -> dict | None:
        """Apply or refresh a status on player/enemy side of an encounter or duel state."""
        st = self._new_status(effect_id, duration)
        if not st:
            return None
        statuses = self._status_list(container, side)
        for existing in statuses:
            if existing["id"] == effect_id:
                existing["duration"] = max(int(existing["duration"]), st["duration"])
                existing["power"] = st["power"]
                return existing
        statuses.append(st)
        return st

    def has_status(self, container: dict, side: str, effect_id: str) -> bool:
        return any(s["id"] == effect_id and int(s["duration"]) > 0 for s in self._status_list(container, side))

    def tick_statuses(self, container: dict, side: str, max_hp: int) -> dict:
        """Process start-of-turn statuses. Returns {damage, blocked, logs, skip_action, speed_factor, shield_factor}."""
        statuses = self._status_list(container, side)
        logs = []
        damage = 0
        skip_action = False
        speed_factor = 1.0
        shield_factor = 0.0
        remaining = []
        for st in statuses:
            kind = st.get("kind")
            power = float(st.get("power", 0))
            if kind == "dot" and int(st["duration"]) > 0:
                tick = max(1, int(max_hp * power))
                damage += tick
                logs.append(f"{st['name']} gây **{tick}** sát thương.")
            if kind == "control" and int(st["duration"]) > 0:
                skip_action = True
                logs.append(f"Bị **{st['name']}**, không thể hành động.")
            if kind == "debuff" and st.get("id") == "slow" and int(st["duration"]) > 0:
                speed_factor *= max(0.4, 1.0 - power)
                logs.append(f"**{st['name']}**: tốc độ giảm.")
            if kind == "buff" and st.get("id") == "shield" and int(st["duration"]) > 0:
                shield_factor = max(shield_factor, power)
            st["duration"] = int(st["duration"]) - 1
            if int(st["duration"]) > 0:
                remaining.append(st)
            else:
                logs.append(f"**{st['name']}** đã hết hiệu lực.")
        container[f"{side}_statuses"] = remaining
        return {
            "damage": damage,
            "logs": logs,
            "skip_action": skip_action,
            "speed_factor": speed_factor,
            "shield_factor": shield_factor,
        }

    def mitigate_with_shield(self, damage: int, shield_factor: float) -> int:
        if shield_factor <= 0 or damage <= 0:
            return int(damage)
        return max(0, int(damage * (1.0 - min(0.6, shield_factor))))

    def _technique_bonus_from_mastery(self, mastery: int) -> float:
        """Bounded combat bonus from mastery stage (max ~12%)."""
        mastery = max(0, min(12, int(mastery)))
        return 0.01 * mastery  # 1% per point, hard cap 12%

    def gain_technique_mastery(self, user_id: str, technique_id: str, amount: int = 1) -> dict | None:
        """Increase mastery for a learned technique. No-op if never learned."""
        amount = max(0, int(amount))
        if amount <= 0:
            return None
        key = f"technique:{technique_id}"
        if not self.db.get_discovery(user_id, key):
            # backward compat: create mastery row if discovery exists under technique_bonus only
            if not self.db.get_discovery(user_id, f"technique_bonus:{technique_id}"):
                return None
        row = self.db.get_technique_mastery(user_id, technique_id)
        current = int(row["mastery"]) if row else 0
        if current <= 0 and row is None:
            current = 1  # ensure learned techniques start at least at Nhập môn
        new_val = min(12, current + amount)
        stage = self._mastery_stage(new_val)
        self.db.upsert_technique_mastery(user_id, technique_id, new_val, stage)
        return {"technique_id": technique_id, "mastery": new_val, "stage": stage, "gained": new_val - current}

    def mastery_combat_multiplier(self, user_id: str, technique_id: str | None = None) -> float:
        """Return the bounded mastery multiplier for one specific technique.

        ``technique_id`` is the gameplay path: combat must use the mastery of the
        technique actually selected, not the average mastery of the character.
        For backward compatibility, omitting ``technique_id`` keeps the old
        aggregate read-only behavior, but combat code never uses that fallback.
        """
        if technique_id:
            row = self.db.get_technique_mastery(user_id, technique_id)
            if not row:
                return 1.0
            return 1.0 + self._technique_bonus_from_mastery(int(row["mastery"]))
        try:
            rows = self.db.conn.execute(
                "SELECT mastery FROM technique_mastery WHERE user_id=?",
                (str(user_id),),
            ).fetchall()
        except Exception:
            return 1.0
        if not rows:
            return 1.0
        avg = sum(int(r[0]) for r in rows) / max(1, len(rows))
        return 1.0 + self._technique_bonus_from_mastery(int(avg))

    def calculate_damage(
        self,
        attack: int,
        defense: int,
        *,
        multiplier: float = 1.0,
        crit_chance: float = 0.0,
        crit_multiplier: float = 1.5,
        variance: float = 0.10,
        minimum_ratio: float = 0.08,
        accuracy: float | None = None,
        evasion: float | None = None,
        status_on_hit: str | None = None,
    ) -> dict:
        """Unified PvE/PvP damage formula.

        Defense uses diminishing returns. Optional accuracy/evasion only apply when
        provided so legacy callers keep identical hit rate (always hit).
        """
        attack = max(1, int(attack))
        defense = max(0, int(defense))
        multiplier = max(0.1, float(multiplier))
        variance = max(0.0, min(0.35, float(variance)))
        hit = True
        if accuracy is not None and evasion is not None:
            # Stable but meaningful hit curve: ordinary builds land most attacks,
            # while a real Accuracy/Evasion gap measurably changes miss chance.
            acc = max(0.0, min(150.0, float(accuracy)))
            eva = max(0.0, min(100.0, float(evasion)))
            hit_chance = 0.82 + ((acc - eva - 50.0) * 0.003)
            hit_chance = max(0.35, min(0.97, hit_chance))
            hit = self.rng.random() < hit_chance
        if not hit:
            return {"damage": 0, "crit": False, "mitigation": 0.0, "hit": False, "status": None}
        mitigation = defense / (defense + 200.0)
        roll = self.rng.uniform(1.0 - variance, 1.0 + variance)
        raw = attack * multiplier * roll
        crit = crit_chance > 0 and self.rng.random() < min(0.95, max(0.0, crit_chance))
        if crit:
            raw *= max(1.0, crit_multiplier)
        damage = int(raw * (1.0 - mitigation))
        minimum = max(1, int(attack * max(0.01, minimum_ratio)))
        applied = None
        if status_on_hit and self.rng.random() < 0.18:
            applied = status_on_hit
        return {
            "damage": max(minimum, damage),
            "crit": crit,
            "mitigation": mitigation,
            "hit": True,
            "status": applied,
        }


    def combat_power(self, player: Player) -> int:
        return self.battle_stats(player)["rating"]

    def event_bonus(self, player: Player) -> float:
        bonus = 0.0
        if player.destiny == "Thiên Mệnh Chi Tử": bonus += 0.12
        elif player.destiny == "Phúc Tinh": bonus += 0.08
        if player.talent == "Tử Khí Đông Lai": bonus += 0.08
        return bonus

    # ---------- shared progression helpers ----------
    def _progress_sect_mission(self, user_id: str, mission_key: str, amount: int = 1) -> None:
        membership = self.db.get_sect_membership(str(user_id))
        if membership:
            self.db.add_mission_progress(str(user_id), str(membership["sect_id"]), mission_key, int(amount), time.strftime("%Y%m%d"))

    def sect_info(self, user_id: str) -> dict | None:
        row = self.db.get_sect_membership(user_id)
        return dict(row) if row else None

    def list_sects(self) -> list[dict]:
        # Keep legacy/system sects available to old saves and tests.
        return [dict(r) for r in self.db._all_sects()]

    def list_custom_sects(self) -> list[dict]:
        return [dict(r) for r in self.db.list_custom_sects()]

    def list_all_sects(self) -> list[dict]:
        return [dict(r) for r in self.db.list_sects()]

    def create_sect(self, user_id: str, name: str, description: str) -> dict:
        with self._player_lock(user_id):
            return self._create_sect_locked(user_id, name, description)

    def _create_sect_locked(self, user_id: str, name: str, description: str) -> dict:
        player = self._require_player(user_id)
        if self.db.get_sect_membership(user_id):
            raise GameError("Ngươi đã thuộc một Tông Môn. Hãy rời Tông Môn hiện tại trước khi sáng lập đạo thống riêng.")
        name = " ".join(name.strip().split())
        description = " ".join(description.strip().split())
        if len(name) < 2 or len(name) > 30:
            raise GameError("Tên Tông Môn phải dài từ 2 đến 30 ký tự.")
        if len(description) < 4 or len(description) > 180:
            raise GameError("Tông quy/mô tả phải dài từ 4 đến 180 ký tự.")
        sect_id = f"player_{user_id}"
        try:
            row = self.db.create_sect(sect_id, user_id, name, player.path, player.realm_idx, description, bonus_percent=2)
        except ValueError as exc:
            messages = {
                "already_has_sect": "Ngươi đã sáng lập một Tông Môn.",
                "sect_name_taken": "Tên Tông Môn này đã có người sử dụng.",
            }
            raise GameError(messages.get(str(exc), "Không thể sáng lập Tông Môn.")) from exc
        return dict(row)

    def dissolve_sect(self, user_id: str) -> None:
        with self._player_lock(user_id):
            member = self.db.get_sect_membership(user_id)
            if not member:
                raise GameError("Ngươi chưa thuộc Tông Môn nào.")
            sect = self.db.get_sect(str(member["sect_id"]))
            if not sect or str(sect["owner_id"] or "") != str(user_id):
                raise GameError("Chỉ Tông Chủ mới có thể giải tán Tông Môn.")
            try:
                self.db.delete_sect(str(member["sect_id"]), user_id)
            except ValueError as exc:
                raise GameError("Không thể giải tán Tông Môn này.") from exc

    def sect_is_owner(self, user_id: str) -> bool:
        member = self.db.get_sect_membership(user_id)
        if not member:
            return False
        sect = self.db.get_sect(str(member["sect_id"]))
        return bool(sect and str(sect["owner_id"] or "") == str(user_id))

    def _sect_eligible(self, player: Player, sect: dict) -> bool:
        path = str(sect.get("path", "both"))
        return player.realm_idx >= int(sect.get("min_realm", 0)) and (path == "both" or path == player.path)

    def join_sect(self, user_id: str, sect_id: str) -> dict:
        with self._player_lock(user_id):
            player = self._require_player(user_id)
            sect = self.db.get_sect(sect_id)
            if not sect:
                raise GameError("Tông môn không tồn tại.")
            sect_d = dict(sect)
            if not self._sect_eligible(player, sect_d):
                realm_name = REALMS[int(sect_d["min_realm"])][0]
                path_text = "cả hai đạo" if sect_d["path"] == "both" else ("Tiên đạo" if sect_d["path"] == "tien" else "Ma đạo")
                raise GameError(f"Chưa đủ điều kiện. Cần từ **{realm_name}** và thuộc **{path_text}**.")
            try:
                self.db.join_sect(user_id, sect_id)
            except ValueError as exc:
                msg = {"already_member": "Ngươi đã thuộc một Tông Môn.", "sect_not_found": "Tông Môn không tồn tại."}
                raise GameError(msg.get(str(exc), "Không thể gia nhập Tông Môn.")) from exc
            return sect_d

    def leave_sect(self, user_id: str) -> None:
        with self._player_lock(user_id):
            try:
                self.db.leave_sect(user_id)
            except ValueError as exc:
                if str(exc) == "not_member":
                    raise GameError("Ngươi hiện chưa thuộc Tông Môn.") from exc
                raise

    def sect_contribute(self, user_id: str, amount: int) -> dict:
        with self._player_lock(user_id):
            self._require_player(user_id)
            if amount < 100 or amount % 100 != 0:
                raise GameError("Cống hiến phải từ 100 Linh Thạch và theo bội số 100.")
            try:
                row = self.db.add_sect_contribution(user_id, amount)
            except ValueError as exc:
                messages = {
                    "not_member": "Ngươi chưa gia nhập Tông Môn.",
                    "not_enough_stones": "Ngươi không đủ Linh Thạch để cống hiến.",
                    "player_not_found": "Không tìm thấy nhân vật.",
                }
                raise GameError(messages.get(str(exc), "Cống hiến thất bại.")) from exc
            return dict(row)

    def sect_rank(self, contribution: int) -> str:
        if contribution >= 5000: return "Chân Truyền"
        if contribution >= 2000: return "Nội Môn"
        return "Ngoại Môn"

    def pvp_challenge(self, challenger_id: str, target_id: str, bet_type: str, item_id: str | None, amount: int) -> dict:
        challenger_id = str(challenger_id)
        target_id = str(target_id)
        first, second = sorted((challenger_id, target_id))
        with self._player_lock(first), self._player_lock(second):
            challenger = self._require_player(challenger_id)
            target = self._require_player(target_id)
            if challenger_id == target_id:
                raise GameError("Không thể tự đấu với chính mình.")
            if amount <= 0:
                raise GameError("Mức cược phải lớn hơn 0.")
            if bet_type == "stones":
                if challenger.spirit_stones < amount or target.spirit_stones < amount:
                    raise GameError("Cả hai bên phải đủ Linh Thạch cho mức cược này.")
            elif bet_type == "item":
                if not item_id or item_id not in ITEMS:
                    raise GameError("Vật phẩm cược không tồn tại.")
                if self.db.get_item_count(challenger_id, item_id) < amount:
                    raise GameError("Ngươi không đủ vật phẩm để đặt cược.")
                if self.db.get_item_count(target_id, item_id) < amount:
                    raise GameError("Đối thủ không đủ vật phẩm cùng loại để đối cược.")
            else:
                raise GameError("Loại cược chỉ gồm `lt` hoặc `item`.")
            try:
                challenge_id = self.db.create_pvp_challenge(challenger_id, target_id, bet_type, item_id, amount)
            except ValueError as exc:
                if str(exc) == "target_busy":
                    raise GameError("Đối thủ đang có một lời thách đấu khác chưa xử lý.") from exc
                raise GameError("Không thể tạo lời thách đấu PvP.") from exc
            return {"id": challenge_id, "challenger": challenger, "target": target, "bet_type": bet_type, "item_id": item_id, "amount": amount}

    def pvp_preview(self, challenger_id: str, target_id: str) -> dict:
        challenger = self._require_player(str(challenger_id))
        target = self._require_player(str(target_id))
        c_stats = self.battle_stats(challenger)
        t_stats = self.battle_stats(target)
        c_rating = max(1, int(c_stats["rating"]))
        t_rating = max(1, int(t_stats["rating"]))
        c_chance = max(10.0, min(90.0, 50.0 + (c_rating - t_rating) * 0.06))
        return {"challenger": challenger, "target": target, "challenger_stats": c_stats, "target_stats": t_stats, "challenger_chance": c_chance, "target_chance": 100.0 - c_chance}

    def get_pvp_challenge(self, challenge_id: int) -> dict | None:
        row = self.db.get_pvp_challenge(challenge_id)
        return dict(row) if row else None

    def decline_pvp(self, challenge_id: int, user_id: str) -> None:
        with self._player_lock(user_id):
            row = self.db.get_pvp_challenge(challenge_id)
            if not row or str(row["target_id"]) != str(user_id):
                raise GameError("Lời đấu này không còn hiệu lực.")
            self.db.close_pvp_challenge(challenge_id)

    def resolve_pvp(self, challenge_id: int, user_id: str) -> dict:
        row = self.db.get_pvp_challenge(challenge_id)
        if not row or str(row["target_id"]) != str(user_id):
            raise GameError("Lời đấu này không còn hiệu lực.")
        first, second = sorted((str(row["challenger_id"]), str(row["target_id"])))
        with self._player_lock(first), self._player_lock(second):
            # Re-read after acquiring locks so the settlement uses current balances/stats.
            row = self.db.get_pvp_challenge(challenge_id)
            if not row or str(row["target_id"]) != str(user_id):
                raise GameError("Lời đấu này không còn hiệu lực.")
            challenger = self._require_player(str(row["challenger_id"]))
            target = self._require_player(str(row["target_id"]))
            c_stats = self.battle_stats(challenger)
            t_stats = self.battle_stats(target)
            c_weight = max(10.0, min(90.0, 50.0 + (c_stats["rating"] - t_stats["rating"]) * 0.06))
            # Short deterministic-feeling duel simulation for PvP presentation.
            # It uses the same unified damage formula as PvE and never grants combat buffs.
            c_hp, t_hp = c_stats["hp"], t_stats["hp"]
            rounds = []
            # Lightweight duel status container
            duel = {"player_statuses": [], "enemy_statuses": []}
            # Higher speed acts first
            attacker = "c" if c_stats.get("speed", 40) >= t_stats.get("speed", 40) else "t"
            if abs(c_stats.get("speed", 40) - t_stats.get("speed", 40)) < 3:
                attacker = "c" if self.rng.random() * 100 < c_weight else "t"
            for round_no in range(1, 13):
                if c_hp <= 0 or t_hp <= 0:
                    break
                if attacker == "c":
                    tick = self.tick_statuses(duel, "player", c_stats["hp"])
                    c_hp = max(0, c_hp - tick["damage"])
                    if c_hp <= 0:
                        rounds.append({"round": round_no, "attacker": "c", "damage": 0, "crit": False, "miss": False, "c_hp": c_hp, "t_hp": t_hp, "status_logs": tick["logs"]})
                        break
                    if tick["skip_action"]:
                        rounds.append({"round": round_no, "attacker": "c", "damage": 0, "crit": False, "miss": False, "stunned": True, "c_hp": c_hp, "t_hp": t_hp})
                    else:
                        hit = self.calculate_damage(
                            c_stats["attack"], t_stats["defense"],
                            crit_chance=c_stats["crit_chance"], crit_multiplier=c_stats["crit_multiplier"],
                            variance=0.08,
                            accuracy=float(c_stats.get("accuracy", 75)) * (0.85 if tick["speed_factor"] < 1.0 else 1.0),
                            evasion=float(t_stats.get("evasion", 8)),
                        )
                        dmg = 0 if not hit.get("hit", True) else hit["damage"]
                        # target shield
                        sh = 0.0
                        for st in duel.get("enemy_statuses") or []:
                            if st.get("id") == "shield" and int(st.get("duration", 0)) > 0:
                                sh = max(sh, float(st.get("power", 0)))
                        dmg = self.mitigate_with_shield(dmg, sh)
                        t_hp = max(0, t_hp - dmg)
                        if hit.get("hit") and self.rng.random() < 0.08:
                            self.apply_status(duel, "enemy", self.rng.choice(["bleed", "slow"]))
                        rounds.append({"round": round_no, "attacker": "c", "damage": dmg, "crit": hit.get("crit", False), "miss": not hit.get("hit", True), "c_hp": c_hp, "t_hp": t_hp})
                    attacker = "t"
                else:
                    tick = self.tick_statuses(duel, "enemy", t_stats["hp"])
                    t_hp = max(0, t_hp - tick["damage"])
                    if t_hp <= 0:
                        rounds.append({"round": round_no, "attacker": "t", "damage": 0, "crit": False, "miss": False, "c_hp": c_hp, "t_hp": t_hp, "status_logs": tick["logs"]})
                        break
                    if tick["skip_action"]:
                        rounds.append({"round": round_no, "attacker": "t", "damage": 0, "crit": False, "miss": False, "stunned": True, "c_hp": c_hp, "t_hp": t_hp})
                    else:
                        hit = self.calculate_damage(
                            t_stats["attack"], c_stats["defense"],
                            crit_chance=t_stats["crit_chance"], crit_multiplier=t_stats["crit_multiplier"],
                            variance=0.08,
                            accuracy=float(t_stats.get("accuracy", 75)) * (0.85 if tick["speed_factor"] < 1.0 else 1.0),
                            evasion=float(c_stats.get("evasion", 8)),
                        )
                        dmg = 0 if not hit.get("hit", True) else hit["damage"]
                        sh = 0.0
                        for st in duel.get("player_statuses") or []:
                            if st.get("id") == "shield" and int(st.get("duration", 0)) > 0:
                                sh = max(sh, float(st.get("power", 0)))
                        dmg = self.mitigate_with_shield(dmg, sh)
                        c_hp = max(0, c_hp - dmg)
                        if hit.get("hit") and self.rng.random() < 0.08:
                            self.apply_status(duel, "player", self.rng.choice(["bleed", "slow"]))
                        rounds.append({"round": round_no, "attacker": "t", "damage": dmg, "crit": hit.get("crit", False), "miss": not hit.get("hit", True), "c_hp": c_hp, "t_hp": t_hp})
                    attacker = "c"
            # A tiny amount of luck prevents stalemates without overpowering weaker builds.
            if c_hp == t_hp:
                winner_id = str(row["challenger_id"]) if self.rng.random() * 100 < c_weight else str(row["target_id"])
            else:
                winner_id = str(row["challenger_id"]) if c_hp > t_hp else str(row["target_id"])
            try:
                settlement = self.db.settle_pvp_challenge(challenge_id, winner_id)
            except ValueError as exc:
                messages = {
                    "challenge_not_found": "Lời đấu đã hết hiệu lực.",
                    "stake_unavailable": "Một bên không còn đủ tài sản để đặt cược.",
                    "player_not_found": "Một nhân vật không còn tồn tại.",
                    "invalid_winner": "Kết quả PvP không hợp lệ.",
                }
                raise GameError(messages.get(str(exc), "PvP không thể hoàn tất.")) from exc
            return {"challenger": challenger, "target": target, "challenger_power": c_stats["rating"], "target_power": t_stats["rating"], "challenger_stats": c_stats, "target_stats": t_stats, "rounds": rounds, "challenger_chance": c_weight, **settlement}

    # ---------- bế quan ----------
    def start_be_quan(self, user_id: str) -> dict:
        with self._player_lock(user_id):
            player = self._require_player(user_id)
            now = int(time.time())
            if player.be_quan_active:
                # Refresh due cycles before reporting status so the command never
                # shows stale cultivation/stone values.
                processed = self.process_be_quan(now=now)
                player = self._require_player(user_id)
                remaining = max(0, BE_QUAN_INTERVAL - (now - player.be_quan_last_tick)) if player.be_quan_active else 0
                return {
                    "active": bool(player.be_quan_active),
                    "remaining": remaining,
                    "player": player,
                    "processed": next((r for r in processed if r["user_id"] == str(user_id)), None),
                }
            if player.spirit_stones < BE_QUAN_COST:
                raise GameError(f"Cần {BE_QUAN_COST} Linh Thạch để bắt đầu Bế Quan.")
            # The first payment reserves the first cycle; cultivation is awarded
            # when that five-minute cycle completes.
            player.spirit_stones -= BE_QUAN_COST
            player.be_quan_active = 1
            player.be_quan_prepaid = 1
            player.be_quan_last_tick = now
            self.db.save_player(player)
            return {"active": True, "remaining": BE_QUAN_INTERVAL, "player": player, "first_cycle_paid": True}

    def stop_be_quan(self, user_id: str) -> dict:
        with self._player_lock(user_id):
            player = self._require_player(user_id)
            if not player.be_quan_active:
                raise GameError("Ngươi hiện không ở trạng thái Bế Quan.")
            results = self.process_be_quan(now=int(time.time()))
            player = self._require_player(user_id)
            player.be_quan_active = 0
            player.be_quan_prepaid = 0
            player.be_quan_last_tick = int(time.time())
            self.db.save_player(player)
            processed = next((r for r in results if r["user_id"] == str(user_id)), None)
            return {"player": player, "processed": processed}

    def be_quan_status(self, user_id: str) -> dict:
        now = int(time.time())
        # Process matured cycles first so status is authoritative.
        self.process_be_quan(now=now)
        player = self._require_player(user_id)
        remaining = max(0, BE_QUAN_INTERVAL - (now - player.be_quan_last_tick)) if player.be_quan_active else 0
        return {"player": player, "remaining": remaining}

    def _auto_cultivation_gain(self, player: Player) -> int:
        base = self.rng.randint(60, 110)
        multiplier = 0.70 + player.root / 240.0
        if player.path == "ma": multiplier += 0.10
        if player.talent in {"Thanh Vân Đạo Thể", "Dược Linh Thân"}: multiplier += 0.06
        if player.talent == "Thôn Thiên Ma Cốt": multiplier += 0.10
        sect = self.db.get_sect_membership(player.user_id)
        if sect:
            multiplier += int(sect["bonus_percent"]) / 100.0
        return max(10, int(base * multiplier))

    def process_be_quan(self, now: int | None = None, max_cycles: int = 288) -> list[dict]:
        now = int(time.time()) if now is None else int(now)
        results: list[dict] = []
        drop_pool = [item_id for item_id, item in ITEMS.items() if item.get("category") == "Linh vật" and item.get("rarity") in {"Phàm", "Hoàng", "Huyền"}]
        for row in self.db.list_active_be_quan():
            user_id = str(row["user_id"])
            with self._player_lock(user_id):
                fresh = self.db.get_player(user_id)
                if not fresh or not fresh.be_quan_active:
                    continue
                player = fresh
                elapsed = max(0, now - player.be_quan_last_tick)
                full_cycles = elapsed // BE_QUAN_INTERVAL
                cycles = min(max_cycles, full_cycles)
                if cycles <= 0:
                    continue
                total_gain = 0
                drops: list[str] = []
                stopped = False
                cycles_done = 0
                for _ in range(cycles):
                    if player.be_quan_prepaid:
                        # The fee paid when Bế Quan starts covers the first
                        # completed cycle; do not charge the player twice.
                        player.be_quan_prepaid = 0
                    elif player.spirit_stones >= BE_QUAN_COST:
                        player.spirit_stones -= BE_QUAN_COST
                    else:
                        stopped = True
                        player.be_quan_active = 0
                        break
                    gain = self.add_cultivation(player, self._auto_cultivation_gain(player))
                    total_gain += gain
                    cycles_done += 1
                    if gain <= 0:
                        stopped = True
                        player.be_quan_active = 0
                        break
                    if drop_pool and self.rng.random() < 0.20:
                        item_id = self.rng.choice(drop_pool)
                        self.db.add_item(player.user_id, item_id, 1)
                        drops.append(ITEMS[item_id]["name"])
                    player.be_quan_last_tick += BE_QUAN_INTERVAL
                if stopped:
                    # No funds remain. Mark the player stopped and consume all
                    # elapsed time so the next command cannot re-run stale cycles.
                    player.be_quan_last_tick = now
                    player.be_quan_prepaid = 0
                else:
                    # The loop already advanced last_tick by every completed cycle.
                    # If downtime exceeded the catch-up cap, discard extra cycles
                    # but preserve the current partial-cycle remainder.
                    if full_cycles > max_cycles:
                        player.be_quan_last_tick = now - (elapsed % BE_QUAN_INTERVAL)
                player.updated_at = now
                self.db.save_player(player)
                results.append({"user_id": player.user_id, "cycles": cycles_done, "gain": total_gain, "drops": drops, "stopped": stopped, "player": player})
        return results

    def cooldown_remaining(self, last_timestamp: int, kind: str) -> int:
        return max(0, COOLDOWNS[kind] - (int(time.time()) - last_timestamp))

    def daily_remaining(self, player: Player) -> int:
        return max(0, DAILY_COOLDOWN - (int(time.time()) - player.last_daily))

    def _require_player(self, user_id: str) -> Player:
        player = self.db.get_player(user_id)
        if not player:
            raise GameError("Ngươi chưa khai đạo. Dùng `.tutien` hoặc `.tamuontutien` để bắt đầu.")
        return player

    # ---------- cultivation ----------
    def cultivate(self, user_id: str) -> dict:
        with self._player_lock(user_id):
            player = self._require_player(user_id)
            remaining = self.cooldown_remaining(player.last_cultivate, "cultivate")
            if remaining:
                raise GameError(f"Thiên cơ chưa ổn định. Còn **{remaining}s** trước khi có thể tu luyện tiếp.")

            base = self.rng.randint(80, 150)
            multiplier = 0.72 + player.root / 220.0
            if player.path == "ma": multiplier += 0.12; player.karma += 1
            if player.talent in {"Thanh Vân Đạo Thể", "Dược Linh Thân"}: multiplier += 0.08
            if player.talent == "Thôn Thiên Ma Cốt": multiplier += 0.14
            if player.destiny == "Đại Khí Vãn Thành" and player.realm_idx >= 2: multiplier += 0.20
            sect = self.db.get_sect_membership(player.user_id)
            if sect:
                multiplier += int(sect["bonus_percent"]) / 100.0

            if player.cultivation >= self.cultivation_requirement(player):
                raise GameError("Tu vi đã đạt cực hạn của tầng này. Hãy `.dotpha` trước khi tiếp tục tu luyện.")
            raw_gain = max(10, int(base * multiplier))
            gain = self.add_cultivation(player, raw_gain)
            player.last_cultivate = int(time.time())
            result = {"player": player, "gain": gain, "event": None, "event_text": None}

            chance = min(0.30, 0.02 + player.luck / 1000.0 + player.fate / 1400.0 + self.event_bonus(player))
            if self.rng.random() < chance:
                roll = self.rng.random()
                if roll < 0.55:
                    extra = self.add_cultivation(player, self.rng.randint(50, 140)); player.fate = min(100, player.fate + 1)
                    result.update(event="linh_khi_don", event_text=f"Linh khí hội tụ! +{extra} tu vi bonus.")
                elif roll < 0.85:
                    stones = self.rng.randint(60, 180); player.spirit_stones += stones
                    result.update(event="linh_thach", event_text=f"Nhặt được một mạch linh khí nhỏ: +{stones} linh thạch.")
                else:
                    extra = self.add_cultivation(player, self.rng.randint(150, 300)); player.insight = min(100, player.insight + 1)
                    result.update(event="don_ngo", event_text=f"Đốn ngộ! +{extra} tu vi và +1 ngộ tính.")
            self._progress_sect_mission(user_id, "cultivate", 1)
            self.db.save_player(player)
            return result

    def breakthrough_chance(self, player: Player) -> float:
        chance = 58.0 + (player.root - 50) * 0.34 + (player.insight - 50) * 0.28 + (player.mind - 50) * 0.22 + player.fate * 0.08
        chance += 2.0 if player.path == "tien" else 5.0
        if player.destiny == "Đại Khí Vãn Thành": chance += 4.0 if player.realm_idx >= 2 else -6.0
        if player.destiny == "Thiên Mệnh Chi Tử": chance += 6.0
        # Phase 1: preparation modifiers. Still clamped so important breaks are not free.
        chance += max(-6.0, min(8.0, (int(player.foundation or 0) - 50) * 0.08))
        if player.dao_type and int(player.dao_stage or 0) >= 2:
            chance += 3.0
        if self.mental_state(player) == "Tâm ma":
            chance -= 8.0
        elif self.mental_state(player) == "Ổn định":
            chance += 3.0
        return max(12.0, min(92.0, chance))

    def breakthrough_preview(self, user_id: str) -> dict:
        player = self._require_player(user_id)
        if self.is_max_realm(player):
            raise GameError("Ngươi đã chạm đỉnh Tiên Đế. Hành trình hiện tại chưa mở cảnh giới tiếp theo.")
        required = self.cultivation_requirement(player)
        if player.cultivation < required:
            raise GameError(f"Tu vi chưa đủ. Hiện có **{player.cultivation}**, cần **{required}** để đột phá.")
        if player.realm_idx == 9 and player.layer >= REALMS[9][1]:
            raise GameError("Ngươi đã tới Độ Kiếp tầng 3. Muốn tiến vào Chân Tiên, phải vượt **Thiên Kiếp** bằng `.thienkiep`.")
        return {
            "player": player,
            "required": required,
            "chance": self.breakthrough_chance(player),
            "mental_state": self.mental_state(player),
            "minor_realm": self.minor_realm(player),
            "old_text": self.realm_text(player),
            "next_realm_hint": REALMS[player.realm_idx][0] if player.layer < REALMS[player.realm_idx][1] else REALMS[min(player.realm_idx + 1, len(REALMS) - 1)][0],
        }

    def breakthrough(self, user_id: str) -> dict:
        with self._player_lock(user_id):
            player = self._require_player(user_id)
            preview = self.breakthrough_preview(user_id)
            required = preview["required"]
            chance = preview["chance"]

            if player.path == "ma":
                player.karma += 3

            success = self.rng.random() * 100 <= chance
            result = {"player": player, "required": required, "chance": chance, "success": success, "major": False}
            if success:
                old_text = self.realm_text(player)
                old_realm = player.realm_idx
                max_layer = REALMS[player.realm_idx][1]
                if player.realm_idx == 0:
                    player.realm_idx = 1; player.layer = 1
                elif player.layer < max_layer:
                    player.layer += 1
                else:
                    player.realm_idx += 1; player.layer = 1; result["major"] = True
                # Breakthrough consumes the entire current-floor cultivation pool.
                # This also cleans up any legacy over-cap value from older versions.
                player.cultivation = 0
                if result["major"] or player.realm_idx != old_realm:
                    player.mind = min(100, player.mind + 2)
                    player.foundation = min(100, player.foundation + (3 if result["major"] else 1))
                player.tribulation_ready = 0
                self.db.save_player(player)
                result.update(old_text=old_text, new_text=self.realm_text(player))
            else:
                loss = max(50, int(required * 0.12))
                player.cultivation = max(0, player.cultivation - loss)
                player.mind = max(1, player.mind - 2)
                if player.path == "ma":
                    player.karma += 4
                self.db.save_player(player)
                result["loss"] = loss
            return result

    # ---------- daily ----------
    def claim_daily(self, user_id: str) -> dict:
        with self._player_lock(user_id):
            player = self._require_player(user_id)
            remaining = self.daily_remaining(player)
            if remaining:
                hours, rem = divmod(remaining, 3600); minutes = rem // 60
                raise GameError(f"Đạo hữu đã nhận quà hôm nay. Còn **{hours}h {minutes}m**.")
            now = int(time.time())
            if player.last_daily and now - player.last_daily <= DAILY_COOLDOWN * 2:
                player.daily_streak += 1
            else:
                player.daily_streak = 1
            streak = player.daily_streak
            reward = 500 + player.realm_idx * 200 + player.layer * 75 + min(streak, 7) * 75
            player.spirit_stones += reward
            player.last_daily = now
            if streak >= 7:
                self.db.add_item(user_id, "hoi_khi_dan", 1)
                bonus = "; nhận thêm Hồi Khí Đan"
            else:
                bonus = ""
            self.db.save_player(player)
            return {"player": player, "reward": reward, "streak": streak, "bonus": bonus}

    # ---------- exploration / encounters ----------

    def _enemy_rating(self, hp: int, attack: int, defense: int) -> int:
        return int((hp / 100.0) * 20 + (attack / 10.0) * 35 + (defense / 10.0) * 25 + 10)

    def _new_encounter(self, player: Player, boss: bool = False) -> dict:
        player_rating = max(1, self.combat_power(player))
        if boss:
            enemy = dict(self.rng.choice(BOSS_MONSTERS))
            base_rating = self._enemy_rating(enemy["hp"], enemy["attack"], enemy["defense"])
            target_rating = int(player_rating * self.rng.uniform(1.05, 1.35))
            kind_label = "👑 BOSS"
        else:
            monster_name, base_hp, reward_roll, stones = self.rng.choice(MONSTERS)
            attack = max(50, int(base_hp * 0.58))
            defense = max(35, int(base_hp * 0.40))
            enemy = {
                "name": monster_name, "hp": base_hp, "attack": attack, "defense": defense,
                "reward": stones, "cultivation": reward_roll, "kind": "monster",
            }
            base_rating = self._enemy_rating(enemy["hp"], enemy["attack"], enemy["defense"])
            target_rating = int(player_rating * self.rng.uniform(0.62, 0.88))
            kind_label = "⚔️ Yêu thú"

        scale = max(0.5, target_rating / max(1, base_rating))
        enemy["hp"] = max(80, int(enemy["hp"] * scale ** 0.72))
        enemy["attack"] = max(35, int(enemy["attack"] * scale ** 0.38))
        enemy["defense"] = max(25, int(enemy["defense"] * scale ** 0.38))
        if enemy.get("reward"):
            enemy["reward"] = max(1, int(enemy["reward"] * min(2.5, max(0.75, scale ** 0.28))))
        if enemy.get("cultivation"):
            enemy["cultivation"] = max(1, int(enemy["cultivation"] * min(2.8, max(0.75, scale ** 0.30))))
        enemy["kind"] = "boss" if boss else "monster"
        enemy["kind_label"] = kind_label
        enemy["rating"] = self._enemy_rating(enemy["hp"], enemy["attack"], enemy["defense"])
        enemy["max_hp"] = enemy["hp"]
        enemy["accuracy"] = 68 + (8 if boss else 0)
        enemy["evasion"] = 6 + (4 if boss else 0)
        enemy["player_statuses"] = []
        enemy["enemy_statuses"] = []
        return enemy

    def start_encounter(self, user_id: str) -> dict:
        player = self._require_player(user_id)
        return {"player": player, "encounter": self._new_encounter(player, boss=(self.rng.random() < 0.25))}

    def _learned_combat_skills(self, user_id: str) -> list[dict]:
        skills = []
        for key in self.db.list_discoveries(user_id, prefix="technique:"):
            item_id = key.split(":", 1)[1]
            item = ITEMS.get(item_id)
            if item and item.get("type") == "technique":
                mult = self.SKILL_MULTIPLIERS.get(item.get("rarity", "Phàm"), 1.20)
                skills.append({
                    "id": item_id,
                    "name": item["name"],
                    "item": item,
                    "rarity": item.get("rarity", "Phàm"),
                    "multiplier": mult,
                    "description": item.get("description", ""),
                })
        return skills

    def combat_skills(self, user_id: str) -> list[dict]:
        self._require_player(user_id)
        return self._learned_combat_skills(user_id)

    SKILL_MULTIPLIERS = {
        "Phàm": 1.10, "Hoàng": 1.22, "Huyền": 1.35, "Địa": 1.50,
        "Thiên": 1.65, "Tiên": 1.82, "Thần": 2.00,
    }

    def battle_skill(self, user_id: str, encounter: dict, player_hp: int, enemy_hp: int, skill_id: str) -> dict:
        with self._player_lock(user_id):
            player = self._require_player(user_id)
            skills = self._learned_combat_skills(user_id)
            skill = next((x for x in skills if x["id"] == skill_id), None)
            if not skill:
                raise GameError("Ngươi chưa học kỹ năng này.")
            item = skill["item"]
            stats = self.battle_stats(player)
            # Process player-side statuses at the start of every combat action,
            # not only on normal attacks. This keeps stun/DoT/slow consistent
            # across normal attacks, skills, and combat items.
            ptick = self.tick_statuses(encounter, "player", max(1, int(stats["hp"])))
            player_hp = max(0, int(player_hp) - int(ptick["damage"]))
            if player_hp <= 0:
                injury = self.rng.randint(8, 14)
                player.injury = min(55, player.injury + injury)
                self.db.save_player(player)
                return {
                    "player": player, "player_hp": 0, "enemy_hp": enemy_hp, "ended": True, "victory": False,
                    "damage": 0, "enemy_damage": 0, "crit": False,
                    "text": "\n".join(ptick["logs"] + [f"<:hp:1556722270918152344> HP cạn vì hiệu ứng · thương thế +{injury}%."]),
                }
            multiplier = self.SKILL_MULTIPLIERS.get(item.get("rarity", "Phàm"), 1.20)
            if player.path == "tien":
                multiplier += 0.05
            else:
                multiplier += 0.08
            if player.talent in {"Kiếm Tâm Sơ Thành", "Ma Diễm Tâm", "Huyết Ma Chi Thể"}:
                multiplier += 0.10
            # Technique mastery is specific to the skill actually selected.
            multiplier *= self.mastery_combat_multiplier(user_id, skill_id)
            enemy_eva = float(encounter.get("evasion", 8))
            if ptick["skip_action"]:
                turn = self._battle_enemy_turn(
                    user_id, encounter, player_hp, enemy_hp, 0,
                    "🌀 Kỹ năng — **BỊ KHỐNG CHẾ**", player, extra_lines=ptick["logs"],
                )
                return turn
            damage_info = self.calculate_damage(
                stats["attack"], encounter["defense"], multiplier=multiplier,
                crit_chance=stats["crit_chance"], crit_multiplier=stats["crit_multiplier"],
                accuracy=float(stats["accuracy"]), evasion=enemy_eva,
            )
            label = f"🌀 **{skill['name']}**"
            if not damage_info.get("hit", True):
                label += " · **TRƯỢT**"
            elif damage_info["crit"]:
                label += " · 💥 **BẠO KÍCH**"
            turn = self._battle_enemy_turn(
                user_id, encounter, player_hp, enemy_hp,
                damage_info["damage"] if damage_info.get("hit", True) else 0,
                label, player,
            )
            # Mastery is earned from actually using the selected technique
            # successfully, never from a random technique on victory.
            if damage_info.get("hit", True):
                mastery = self.gain_technique_mastery(user_id, skill_id, 1)
                turn["technique_id"] = skill_id
                turn["technique_mastery"] = mastery
            return turn

    def combat_use_item(self, user_id: str, item_id: str, player_hp: int, max_hp: int) -> dict:
        with self._player_lock(user_id):
            player = self._require_player(user_id)
            item = ITEMS.get(item_id)
            if not item or item.get("type") != "consumable":
                raise GameError("Chỉ có Đan dược và Bùa chú có thể sử dụng trực tiếp trong chiến đấu.")
            category = item.get("category", "")
            if category not in {"Đan dược", "Bùa chú"}:
                raise GameError("Vật phẩm này không thể dùng trong chiến đấu.")
            owned = self.db.get_item_count(user_id, item_id)
            if owned < 1:
                raise GameError("Ngươi không có vật phẩm này trong túi.")
            result = self.use_item(user_id, item_id)
            # Recalculate max HP after item effects (stats may have changed).
            max_hp = max(int(max_hp), self.battle_stats(result["player"])["hp"])
            heal_ratio = 0.28 if category == "Đan dược" else 0.18
            heal = max(1, int(max_hp * heal_ratio))
            new_hp = min(max_hp, int(player_hp) + heal)
            return {
                "player": result["player"],
                "player_hp": new_hp,
                "max_hp": max_hp,
                "heal": new_hp - int(player_hp),
                "text": (
                    f"{('💊' if category == 'Đan dược' else '📜')} Dùng **{item['name']}** · "
                    f"<:hp:1556722270918152344> hồi **{new_hp - int(player_hp)} HP**. {result['text']}"
                ),
            }

    def combat_item_turn(
        self,
        user_id: str,
        encounter: dict,
        player_hp: int,
        enemy_hp: int,
        item_id: str,
    ) -> dict:
        """Atomic combat turn: consume item + heal + enemy retaliation under one player lock."""
        with self._player_lock(user_id):
            player = self._require_player(user_id)
            max_hp = self.battle_stats(player)["hp"]
            ptick = self.tick_statuses(encounter, "player", max(1, int(max_hp)))
            player_hp = max(0, int(player_hp) - int(ptick["damage"]))
            if player_hp <= 0:
                injury = self.rng.randint(8, 14)
                player.injury = min(55, player.injury + injury)
                self.db.save_player(player)
                return {
                    "player": player, "player_hp": 0, "enemy_hp": enemy_hp, "ended": True, "victory": False,
                    "damage": 0, "enemy_damage": 0, "crit": False, "heal": 0,
                    "text": "\n".join(ptick["logs"] + [f"<:hp:1556722270918152344> HP cạn vì hiệu ứng · thương thế +{injury}%."]),
                }
            if ptick["skip_action"]:
                turn = self._battle_enemy_turn(
                    user_id, encounter, player_hp, enemy_hp, 0,
                    "🧪 Sử dụng vật phẩm — **BỊ KHỐNG CHẾ**", player, extra_lines=ptick["logs"],
                )
                turn["item_text"] = ""
                turn["heal"] = 0
                return turn
            used = self.combat_use_item(user_id, item_id, player_hp, max_hp)
            turn = self._battle_enemy_turn(
                user_id,
                encounter,
                used["player_hp"],
                enemy_hp,
                0,
                "🧪 Sử dụng vật phẩm",
                used["player"],
            )
            turn["item_text"] = used["text"]
            turn["heal"] = used["heal"]
            turn["text"] = used["text"] + "\n\n" + turn["text"]
            return turn

    def skill_preview(self, user_id: str, skill_id: str) -> dict:
        """Return display stats for a learned combat skill (no side effects)."""
        skills = self._learned_combat_skills(user_id)
        skill = next((x for x in skills if x["id"] == skill_id), None)
        if not skill:
            raise GameError("Ngươi chưa học kỹ năng này.")
        item = skill["item"]
        multiplier = self.SKILL_MULTIPLIERS.get(item.get("rarity", "Phàm"), 1.20)
        mastery_row = self.db.get_technique_mastery(user_id, skill_id)
        mastery = int(mastery_row["mastery"]) if mastery_row else 1
        return {
            "id": skill_id,
            "name": skill["name"],
            "rarity": item.get("rarity", "Phàm"),
            "multiplier": multiplier * self.mastery_combat_multiplier(user_id, skill_id),
            "mastery": mastery,
            "stage": self._mastery_stage(mastery),
            "description": item.get("description", ""),
        }

    def _battle_enemy_turn(self, user_id: str, encounter: dict, player_hp: int, enemy_hp: int, damage: int, action_label: str, player: Player | None = None, extra_lines: list | None = None) -> dict:
        # The whole turn is serialized for this player. Reload the latest player state
        # so another command cannot overwrite rewards/injury between item/skill and retaliation.
        with self._player_lock(user_id):
            player = self._require_player(user_id)
            stats = self.battle_stats(player)
            player_hp = max(0, min(int(player_hp), stats["hp"]))
            enemy = dict(encounter)
            damage = max(0, int(damage))
            enemy_hp = max(0, int(enemy_hp) - damage)
            lines = list(extra_lines or [])
            if damage > 0:
                lines.append(f"{action_label} · <:att:1556722389973213294> gây **{damage}** sát thương lên **{enemy['name']}**.")
            else:
                lines.append(f"{action_label} · Không gây sát thương.")
            # Enemy start-of-turn statuses (DoT on enemy before they act)
            etick = self.tick_statuses(encounter, "enemy", max(1, int(enemy.get("max_hp", enemy_hp or 1))))
            if etick["damage"]:
                enemy_hp = max(0, enemy_hp - etick["damage"])
            lines.extend(etick["logs"])
            # Keep status lists on the shared encounter object
            enemy["player_statuses"] = encounter.get("player_statuses", [])
            enemy["enemy_statuses"] = encounter.get("enemy_statuses", [])
            dao_gain = self._dao_combat_progress_locked(
                player,
                skill=("Đánh thường" not in action_label and "Sử dụng vật phẩm" not in action_label),
            )
            if enemy_hp <= 0:
                reward = int(enemy["reward"] * (1.0 + player.fate / 300.0))
                player.spirit_stones += reward
                gain = self.add_cultivation(player, int(enemy.get("cultivation", 100)))
                self.db.add_discovery(user_id, f"defeat:{enemy['name']}")
                # Technique mastery is awarded by battle_skill for the technique
                # actually used. Normal attacks never grant random technique mastery.
                self.db.save_player(player)
                extra = f" · +{dao_gain} Đạo ngộ" if dao_gain else ""
                return {
                    "player": player, "player_hp": player_hp, "enemy_hp": 0, "ended": True, "victory": True,
                    "damage": damage, "enemy_damage": 0, "crit": "BẠO KÍCH" in action_label,
                    "text": "\n".join(lines + [f"\n🏆 Hạ **{enemy['name']}**! +**{fmt_amount(reward)}** linh thạch · +**{fmt_amount(gain)}** tu vi{extra}."]),
                }
            # Player shield from active player statuses
            player_shield = 0.0
            for st in encounter.get("player_statuses") or []:
                if st.get("id") == "shield" and int(st.get("duration", 0)) > 0:
                    player_shield = max(player_shield, float(st.get("power", 0)))
            if etick["skip_action"]:
                enemy_info = {"damage": 0, "crit": False, "hit": False}
                enemy_damage = 0
                lines.append(f"{enemy['name']} bị khống chế, không thể phản kích.")
            else:
                enemy_acc = float(enemy.get("accuracy", 70)) * (0.85 if etick["speed_factor"] < 1.0 else 1.0)
                enemy_info = self.calculate_damage(
                    enemy["attack"], stats["defense"],
                    multiplier=0.82 if enemy.get("kind") == "boss" else 0.75,
                    crit_chance=0.10 if enemy.get("kind") == "boss" else 0.05,
                    crit_multiplier=1.50,
                    variance=0.08,
                    minimum_ratio=0.06,
                    accuracy=enemy_acc,
                    evasion=float(stats.get("evasion", 8)),
                    status_on_hit=self.rng.choice([None, None, None, "poison", "slow"]),
                )
                if not enemy_info.get("hit", True):
                    # Near-death: graze still connects so low-HP finishes stay readable in Discord.
                    if player_hp <= max(1, stats["hp"] // 25):
                        enemy_damage = max(1, int(enemy.get("attack", 1) * 0.15))
                        lines.append(f"{enemy['name']} sát khí vẫn vương · **trầy** **{enemy_damage}** sát thương.")
                    else:
                        enemy_damage = 0
                        lines.append(f"{enemy['name']} tấn công · **TRƯỢT**.")
                else:
                    enemy_damage = self.mitigate_with_shield(enemy_info["damage"], player_shield)
                    if enemy_info.get("status"):
                        self.apply_status(encounter, "player", enemy_info["status"])
            player_hp = max(0, player_hp - enemy_damage)
            if enemy_damage > 0 and player.dao_type == "the":
                dao_gain += self._dao_combat_progress_locked(player, damage_taken=True)
            if enemy_damage > 0:
                reaction = f"{enemy['name']} phản kích · <:att:1556722389973213294> gây **{enemy_damage}** sát thương."
                if enemy_info.get("crit"):
                    reaction += " 💥 **Bạo kích!**"
                lines.append(reaction)
            if player_hp <= 0:
                injury = self.rng.randint(10, 18)
                player.injury = min(55, player.injury + injury)
                loss = min(player.spirit_stones, self.rng.randint(80, 220))
                player.spirit_stones -= loss
                self.db.save_player(player)
                if dao_gain:
                    lines.append(f"🧭 Lĩnh ngộ Đạo: +{dao_gain} tiến độ.")
                lines.append(f"<:hp:1556722270918152344> HP cạn kiệt · trọng thương (+{injury}% thương thế), mất {loss} linh thạch.")
                return {
                    "player": player, "player_hp": 0, "enemy_hp": enemy_hp, "ended": True, "victory": False,
                    "damage": damage, "enemy_damage": enemy_damage, "crit": "BẠO KÍCH" in action_label,
                    "text": "\n".join(lines),
                }
            if dao_gain:
                lines.append(f"🧭 Lĩnh ngộ Đạo: +{dao_gain} tiến độ.")
            self.db.save_player(player)
            return {
                "player": player, "player_hp": player_hp, "enemy_hp": enemy_hp, "ended": False, "victory": False,
                "damage": damage, "enemy_damage": enemy_damage, "crit": "BẠO KÍCH" in action_label,
                "text": "\n".join(lines),
            }

    def battle_step(self, user_id: str, encounter: dict, player_hp: int, enemy_hp: int, action: str) -> dict:
        if action != "normal":
            raise GameError("Hành động chiến đấu không hợp lệ. Hãy chọn kỹ năng từ nút Kỹ năng.")
        with self._player_lock(user_id):
            player = self._require_player(user_id)
            stats = self.battle_stats(player)
            lines = []
            # Start of player turn: DoT / stun / slow
            ptick = self.tick_statuses(encounter, "player", max(1, int(stats["hp"])))
            if ptick["damage"]:
                player_hp = max(0, player_hp - ptick["damage"])
            lines.extend(ptick["logs"])
            if player_hp <= 0:
                injury = self.rng.randint(8, 14)
                player.injury = min(55, player.injury + injury)
                self.db.save_player(player)
                return {
                    "player": player, "player_hp": 0, "enemy_hp": enemy_hp, "ended": True, "victory": False,
                    "damage": 0, "enemy_damage": 0, "crit": False, "statuses": encounter,
                    "text": "\n".join(lines + [f"<:hp:1556722270918152344> HP cạn vì hiệu ứng · thương thế +{injury}%."]),
                }
            damage = 0
            crit = False
            if ptick["skip_action"]:
                label = "⚡ Bị khống chế — bỏ lượt"
            else:
                mult = 1.0 * self.mastery_combat_multiplier(user_id)
                enemy_eva = int(encounter.get("evasion", 8))
                # slow reduces effective accuracy slightly via speed factor
                acc = float(stats["accuracy"]) * (0.85 if ptick["speed_factor"] < 1.0 else 1.0)
                damage_info = self.calculate_damage(
                    stats["attack"], encounter["defense"], multiplier=mult,
                    crit_chance=stats["crit_chance"], crit_multiplier=stats["crit_multiplier"],
                    accuracy=acc, evasion=enemy_eva,
                )
                if not damage_info.get("hit", True):
                    label = "⚔️ Đánh thường · **TRƯỢT**"
                    damage = 0
                    crit = False
                else:
                    # enemy shield mitigation if active
                    etick_preview_shield = 0.0
                    for st in encounter.get("enemy_statuses") or []:
                        if st.get("id") == "shield" and int(st.get("duration", 0)) > 0:
                            etick_preview_shield = max(etick_preview_shield, float(st.get("power", 0)))
                    damage = self.mitigate_with_shield(damage_info["damage"], etick_preview_shield)
                    crit = damage_info["crit"]
                    label = "⚔️ Đánh thường" + (" · 💥 **BẠO KÍCH**" if crit else "")
                    if damage_info.get("status"):
                        self.apply_status(encounter, "enemy", damage_info["status"])
                    elif self.rng.random() < 0.10:
                        self.apply_status(encounter, "enemy", self.rng.choice(["burn", "bleed", "slow"]))
            return self._battle_enemy_turn(
                user_id, encounter, player_hp, enemy_hp, damage, label, player, extra_lines=lines,
            )

    def flee_encounter(self, user_id: str, encounter: dict) -> dict:
        with self._player_lock(user_id):
            player = self._require_player(user_id)
            player_rating = self.combat_power(player)
            if player_rating < int(encounter["rating"]):
                injury = self.rng.randint(5, 10)
                player.injury = min(55, player.injury + injury)
                self.db.save_player(player)
                return {"injury": injury, "text": f"🏃 Ngươi cưỡng ép rút lui khỏi **{encounter['name']}**. Vì thực lực yếu hơn, nhận **{injury}% thương thế**."}
            return {"injury": 0, "text": f"🏃 Ngươi bình yên rút khỏi chiến trường của **{encounter['name']}**."}

    def hunt(self, user_id: str) -> dict:
        # Backward-compatible alias: hunting is now part of exploration encounters.
        result = self.explore(user_id)
        self._progress_sect_mission(user_id, "hunt_beast", 1)
        return result

    # ---------- economy / inventory ----------
    def shop(self, category: str = "all") -> list[tuple[str, dict]]:
        """Return shop stock filtered by a Discord shop category."""
        category = category.strip()
        if category not in {"all", *(name for name, _label, _desc in SHOP_CATEGORIES if name != "all")}:
            raise GameError("Danh mục Tiên Phường không tồn tại.")
        items = [(item_id, ITEMS[item_id]) for item_id in SHOP_ORDER if item_id in ITEMS]
        if category == "all":
            return items
        return [(item_id, item) for item_id, item in items if item.get("category") == category]

    def shop_categories(self) -> list[tuple[str, str, str]]:
        return list(SHOP_CATEGORIES)

    def buy(self, user_id: str, item_id: str, qty: int = 1) -> tuple[Player, dict, int]:
        with self._player_lock(user_id):
            self._require_player(user_id)
            if item_id not in ITEMS or item_id not in SHOP_ORDER:
                raise GameError("Vật phẩm này không bán trong Tiên Phường.")
            if qty <= 0 or qty > 50:
                raise GameError("Số lượng phải từ 1 đến 50.")
            item = ITEMS[item_id]
            total = int(item["price"]) * qty
            try:
                player, total = self.db.purchase_shop_item(user_id, item_id, qty, int(item["price"]))
            except ValueError as exc:
                if str(exc) == "not_enough_stones":
                    current = self.db.get_player(user_id)
                    raise GameError(f"Không đủ linh thạch. Cần **{total:,}**, hiện có **{current.spirit_stones:,}**.") from exc
                raise GameError("Mua vật phẩm thất bại.") from exc
            return player, item, total

    def use_item(self, user_id: str, item_id: str, qty: int = 1) -> dict:
        with self._player_lock(user_id):
            player = self._require_player(user_id)
            qty = int(qty)
            if qty < 1 or qty > 100:
                raise GameError("Số lượng sử dụng phải từ 1 đến 100.")
            item = ITEMS.get(item_id)
            if not item:
                raise GameError("Không tìm thấy vật phẩm này.")
            if self.db.get_item_count(user_id, item_id) < 1:
                raise GameError("Ngươi không có vật phẩm này trong túi.")
            if item.get("type") != "consumable":
                if item.get("type") == "equipment":
                    raise GameError("Vật phẩm này là trang bị. Dùng `.trangbi <item>` để trang bị.")
                if item.get("type") == "technique":
                    raise GameError("Vật phẩm này là công pháp. Dùng `.hoc <item>` để học.")
                raise GameError("Vật phẩm này không thể sử dụng trực tiếp.")

            bonus = 1.08 if player.talent == "Dược Linh Thân" else 1.0
            changes: list[str] = []

            base = int(item.get("cultivation", 0))
            if base:
                gain = self.add_cultivation(player, int(base * bonus) * qty)
                if gain:
                    changes.append(f"+{gain} tu vi")

            stat_labels = {
                "root": "căn cơ", "insight": "ngộ tính", "luck": "khí vận",
                "fate": "thiên mệnh", "mind": "tâm tính",
            }
            all_stats = int(item.get("all_stats", 0))
            for stat, label in stat_labels.items():
                amount = (all_stats + int(item.get(stat, 0))) * qty
                if amount:
                    current = int(getattr(player, stat))
                    actual = self._soft_capped_stat_gain(current, amount)
                    updated = min(100, current + actual)
                    setattr(player, stat, updated)
                    if actual:
                        changes.append(f"+{actual} {label}")

            injury_reduction = int(item.get("injury_reduction", 0)) * qty
            if injury_reduction:
                old_injury = player.injury
                player.injury = max(0, player.injury - injury_reduction)
                reduced = old_injury - player.injury
                changes.append(f"- {reduced}% thương thế" if reduced else "thương thế không đổi")

            if not changes:
                raise GameError("Vật phẩm này chưa có hiệu ứng sử dụng.")
            if not self.db.remove_item(user_id, item_id, qty):
                raise GameError("Vật phẩm vừa được sử dụng ở một thao tác khác. Hãy thử lại.")
            self.db.save_player(player)
            return {"player": player, "text": f"Dùng {item['name']} ×{qty}: " + " · ".join(changes) + "."}


    @staticmethod
    def _mastery_stage(mastery: int) -> str:
        if mastery >= 12:
            return "Viên mãn"
        if mastery >= 8:
            return "Đại thành"
        if mastery >= 4:
            return "Tiểu thành"
        return "Nhập môn"

    def learn_technique(self, user_id: str, item_id: str) -> dict:
        with self._player_lock(user_id):
            player = self._require_player(user_id)
            item = ITEMS.get(item_id)
            if not item or item.get("type") != "technique":
                raise GameError("Vật phẩm này không phải công pháp có thể học.")
            if self.db.get_item_count(user_id, item_id) < 1:
                raise GameError("Ngươi không có công pháp này trong túi.")
            key = f"technique:{item_id}"
            if self.db.get_discovery(user_id, key):
                raise GameError("Ngươi đã học công pháp này rồi.")
            if not self.db.remove_item(user_id, item_id, 1):
                raise GameError("Không thể tiêu hao công pháp. Hãy thử lại.")
            self.db.add_discovery(user_id, key)
            stat_label, actual = self._apply_technique_bonus(player, item_id)
            self.db.add_discovery(user_id, f"technique_bonus:{item_id}")
            mastery = 1 + min(2, int(player.insight) // 40)
            stage = self._mastery_stage(mastery)
            self.db.upsert_technique_mastery(user_id, item_id, mastery, stage)
            self.db.save_player(player)
            return {"player": player, "item": item, "stat": stat_label, "bonus": actual, "mastery": mastery, "stage": stage}


    def _parse_loadout(self, player: Player) -> dict:
        import json
        raw = getattr(player, "loadout", None) or "{}"
        try:
            data = json.loads(raw) if isinstance(raw, str) else dict(raw or {})
        except Exception:
            data = {}
        out = {slot: None for slot in EQUIP_SLOTS}
        for k, v in data.items():
            if k in out and v:
                out[k] = str(v)
        # migrate legacy single equipped into weapon/artifact
        if player.equipped and not any(out.values()):
            slot = item_slot(player.equipped) or "weapon"
            if slot in out:
                out[slot] = player.equipped
        return out

    def _save_loadout(self, player: Player, loadout: dict) -> None:
        import json
        clean = {k: v for k, v in loadout.items() if v}
        player.loadout = json.dumps(clean, ensure_ascii=False)
        # keep equipped as primary weapon or first piece for backward compatibility
        player.equipped = loadout.get("weapon") or loadout.get("artifact") or loadout.get("armor") or loadout.get("accessory") or None

    def equip(self, user_id: str, item_id: str) -> dict:
        with self._player_lock(user_id):
            player = self._require_player(user_id)
            item = ITEMS.get(item_id)
            if not item or item.get("type") != "equipment":
                raise GameError("Đây không phải trang bị.")
            if self.db.get_item_count(user_id, item_id) < 1:
                raise GameError("Ngươi không có trang bị này.")
            required_path = item.get("path")
            if required_path and required_path != player.path:
                raise GameError("Trang bị này không cộng hưởng với con đường ngươi đang tu.")
            slot = item_slot(item_id) or item.get("slot") or "artifact"
            if slot not in EQUIP_SLOTS:
                slot = "artifact"
            loadout = self._parse_loadout(player)
            # unequip same item from other slots if any
            for s, v in list(loadout.items()):
                if v == item_id:
                    loadout[s] = None
            loadout[slot] = item_id
            self._save_loadout(player, loadout)
            if item.get("category") == "Binh khí" and player.dao_type:
                name = str(item.get("name", ""))
                if (player.dao_type == "kiem" and "Kiếm" in name) or (player.dao_type == "dao" and "Đao" in name):
                    self._gain_dao_insight_locked(player, 10)
            self.db.save_player(player)
            return {"player": player, "item": item, "slot": slot, "loadout": loadout}

    def unequip(self, user_id: str, slot: str | None = None) -> Player:
        with self._player_lock(user_id):
            player = self._require_player(user_id)
            loadout = self._parse_loadout(player)
            if slot:
                if slot not in EQUIP_SLOTS:
                    raise GameError("Ô trang bị không hợp lệ.")
                loadout[slot] = None
            else:
                loadout = {s: None for s in EQUIP_SLOTS}
            self._save_loadout(player, loadout)
            self.db.save_player(player)
            return player

    def transfer_spirit_stones(self, sender_id: str, target_id: str, amount: int) -> dict:
        sender_id = str(sender_id)
        target_id = str(target_id)
        amount = int(amount)
        if sender_id == target_id:
            raise GameError("Không thể chuyển Linh Thạch cho chính mình.")
        if amount <= 0:
            raise GameError("Số Linh Thạch phải lớn hơn 0.")
        first, second = sorted((sender_id, target_id))
        with self._player_lock(first), self._player_lock(second):
            self._require_player(sender_id)
            self._require_player(target_id)
            try:
                sender, target = self.db.transfer_spirit_stones(sender_id, target_id, amount)
            except ValueError as exc:
                messages = {
                    "sender_not_found": "Không tìm thấy nhân vật người gửi.",
                    "target_not_found": "Đạo hữu nhận chưa khai đạo.",
                    "not_enough_stones": "Ngươi không đủ Linh Thạch.",
                    "invalid_amount": "Số Linh Thạch không hợp lệ.",
                    "self_transfer": "Không thể chuyển Linh Thạch cho chính mình.",
                }
                raise GameError(messages.get(str(exc), "Chuyển Linh Thạch thất bại.")) from exc
            return {"sender": sender, "target": target, "amount": amount}

    # ---------- market ----------
    def market_list(self, user_id: str, item_id: str, quantity: int, unit_price: int) -> int:
        with self._player_lock(user_id):
                    self._require_player(user_id)
                    item = ITEMS.get(item_id)
                    if not item: raise GameError("Không tìm thấy vật phẩm này.")
                    if not item.get("marketable", False): raise GameError("Vật phẩm này không thể giao dịch trên chợ.")
                    if quantity < 1 or quantity > 50: raise GameError("Số lượng đăng bán phải từ 1 đến 50.")
                    if unit_price < 1 or unit_price > 10_000_000: raise GameError("Đơn giá phải từ 1 đến 10.000.000 linh thạch.")
                    try: return self.db.create_market_listing(user_id, item_id, quantity, unit_price)
                    except ValueError as exc:
                        if str(exc) == "not_enough_items": raise GameError("Ngươi không đủ vật phẩm để đăng bán.") from exc
                        raise
            
    def market(self, item_id: str | None = None, limit: int = 12): return self.db.get_market_listings(item_id=item_id, limit=limit)

    def market_cancel(self, user_id: str, listing_id: int) -> dict:
        with self._player_lock(user_id):
                    self._require_player(user_id)
                    listing = self.db.cancel_market_listing(user_id, listing_id)
                    if not listing: raise GameError("Không tìm thấy gian hàng của ngươi.")
                    return dict(listing)
            
    def market_buy(self, user_id: str, listing_id: int) -> dict:
        with self._player_lock(user_id):
                    self._require_player(user_id)
                    try: return dict(self.db.buy_market_listing(user_id, listing_id))
                    except ValueError as exc:
                        messages = {
                            "listing_not_found": "Gian hàng không còn tồn tại hoặc đã được mua.",
                            "self_purchase": "Không thể tự mua đồ của chính mình.",
                            "buyer_not_found": "Không tìm thấy nhân vật người mua.",
                            "not_enough_stones": "Không đủ linh thạch để mua gian hàng này.",
                        }
                        raise GameError(messages.get(str(exc), "Giao dịch thất bại.")) from exc
            
    # ---------- redeem codes ----------
    def redeem_code(self, user_id: str, code: str) -> dict:
        with self._player_lock(user_id):
                    self._require_player(user_id)
                    normalized = code.strip().lower()
                    config = REDEEM_CODES.get(normalized)
                    if not config:
                        raise GameError("Mã code không tồn tại hoặc đã bị thu hồi.")
                    try:
                        reward = self.db.redeem_code(user_id, normalized, config["rewards"])
                    except ValueError as exc:
                        messages = {
                            "invalid_code": "Mã code không tồn tại.",
                            "inactive_code": "Mã code đã bị khóa.",
                            "expired_code": "Mã code đã hết hạn.",
                            "code_exhausted": "Mã code đã hết lượt sử dụng.",
                            "already_redeemed": "Ngươi đã nhận mã code này rồi.",
                        }
                        raise GameError(messages.get(str(exc), "Không thể nhận code.")) from exc
                    return {"code": normalized, "description": config.get("description", ""), **reward}
            
    # ---------- gacha / legacy progression ----------
    def gacha_once(self, user_id: str) -> dict:
        with self._player_lock(user_id):
            player = self._require_player(user_id)
            if not self.db.remove_item(user_id, GACHA_TICKET_ID, 1):
                raise GameError("Ngươi không có Thiên Cơ Lệnh.")
            player.pity += 1
            rarity_names = [row[0] for row in GACHA_TABLE]
            weights = [row[1] for row in GACHA_TABLE]
            rarity = self.rng.choices(rarity_names, weights=weights, k=1)[0]
            if player.pity >= 50 and rarity in {"Phàm", "Hoàng", "Huyền"}:
                rarity = "Địa"
                player.pity = 0
            elif rarity in {"Địa", "Thiên", "Tiên", "Thần"}:
                player.pity = 0
            row = next(x for x in GACHA_TABLE if x[0] == rarity)
            reward_type, value, extra = self.rng.choice(row[2])
            text = ""
            if reward_type == "item":
                qty = int(extra or 1)
                self.db.add_item(user_id, value, qty)
                text = f"Nhận {ITEMS[value]['name']} ×{qty}"
            elif reward_type == "stones":
                player.spirit_stones += int(value)
                text = f"Nhận {int(value):,} linh thạch"
            elif reward_type == "cultivation":
                gain = self.add_cultivation(player, int(value))
                text = f"Nhận {int(gain):,} tu vi"
            self.db.save_player(player)
            return {"player": player, "rarity": rarity, "text": text}

    # ---------- Dao Lu ----------
    def dao_lu_info(self, user_id: str) -> dict | None:
        self._require_player(user_id)
        row = self.db.get_dao_lu(user_id)
        return dict(row) if row else None

    def request_dao_lu(self, user_id: str, target_id: str) -> None:
        requester = str(user_id)
        target = str(target_id)
        if requester == target:
            raise GameError("Không thể kết duyên với chính mình.")
        first, second = sorted((requester, target))
        with self._player_lock(first), self._player_lock(second):
            self._require_player(requester); self._require_player(target)
            if self.db.get_dao_lu(requester) or self.db.get_dao_lu(target):
                raise GameError("Một trong hai người đã có Đạo Lữ.")
            self.db.create_dao_lu_request(requester, target)

    def accept_dao_lu(self, user_id: str) -> dict:
        with self._player_lock(user_id):
            self._require_player(user_id)
            req = self.db.get_dao_lu_request(user_id)
            if not req:
                raise GameError("Không có lời kết duyên đang chờ.")
            requester = str(req["requester_id"])
            first, second = sorted((requester, str(user_id)))
            with self._player_lock(first), self._player_lock(second):
                if self.db.get_dao_lu(requester) or self.db.get_dao_lu(str(user_id)):
                    raise GameError("Một trong hai người đã có Đạo Lữ.")
                self.db.create_dao_lu(requester, str(user_id))
            return {"partner_id": requester}

    def reject_dao_lu(self, user_id: str) -> None:
        with self._player_lock(user_id):
            req = self.db.get_dao_lu_request(user_id)
            if not req:
                raise GameError("Không có lời kết duyên đang chờ.")
            self.db.delete_dao_lu_request(req["requester_id"])

    def break_dao_lu(self, user_id: str) -> dict:
        with self._player_lock(user_id):
            row = self.db.break_dao_lu(user_id)
            if not row:
                raise GameError("Ngươi hiện chưa có Đạo Lữ.")
            return {"partner_id": str(row["partner_id"])}

    def dao_lu_song_tu(self, user_id: str) -> dict:
        uid = str(user_id)
        initial = self.db.get_dao_lu(uid)
        if not initial:
            raise GameError("Ngươi hiện chưa có Đạo Lữ.")
        partner_id = str(initial["partner_id"])
        first, second = sorted((uid, partner_id))
        with self._player_lock(first), self._player_lock(second):
            row = self.db.get_dao_lu(uid)
            if not row:
                raise GameError("Ngươi hiện chưa có Đạo Lữ.")
            remaining = self.cooldown_remaining(int(row["last_song_tu"]), "song_tu")
            if remaining:
                minutes, seconds = divmod(remaining, 60)
                time_left = f"{minutes}m {seconds}s" if minutes else f"{seconds}s"
                raise GameError(f"Song tu chưa thể tiến hành lần nữa. Còn **{time_left}**.")
            player = self.db.get_player(uid)
            partner = self.db.get_player(partner_id)
            if not player or not partner:
                raise GameError("Đạo Lữ không còn tồn tại.")
            raw_gain = self.rng.randint(120, 260) + int((player.root + partner.root) / 8)
            gain_a = self.add_cultivation(player, raw_gain)
            gain_b = self.add_cultivation(partner, raw_gain)
            now = int(time.time())
            self.db.save_player(player)
            self.db.save_player(partner)
            self.db.update_dao_lu(uid, intimacy_delta=3, last_song_tu=now)
            return {"gain": gain_a, "partner_gain": gain_b, "raw_gain": raw_gain, "intimacy": int(row["intimacy"]) + 3, "partner": partner}

    def dao_lu_gift(self, user_id: str, item_id: str, qty: int = 1) -> dict:
        with self._player_lock(user_id):
            self._require_player(user_id)
            qty = int(qty)
            if qty <= 0:
                raise GameError("Số lượng quà tặng phải lớn hơn 0.")
            if not self.db.get_dao_lu(user_id):
                raise GameError("Ngươi hiện chưa có Đạo Lữ.")
            item = ITEMS.get(item_id)
            if not item or not self.db.remove_item(user_id, item_id, qty):
                raise GameError("Không đủ vật phẩm để tặng.")
            self.db.update_dao_lu(user_id, intimacy_delta=max(1, qty))
            return {"item": item, "qty": qty}

    # ---------- exploration / dao / towers / sect ----------
    def set_explore_zone(self, user_id: str, zone_key: str) -> dict:
        with self._player_lock(user_id):
            player = self._require_player(user_id)
            zone = EXPLORE_ZONES.get(zone_key)
            if not zone or not zone.get("enabled"):
                raise GameError("Khu vực này chưa được khai mở.")
            if player.realm_idx < int(zone["min_realm"]):
                raise GameError(f"Cần đạt {REALMS[int(zone['min_realm'])][0]} mới có thể tiến vào khu vực này.")
            player.explore_zone = zone_key
            self.db.save_player(player)
            return zone

    def list_explore_zones(self) -> list[dict]:
        return [dict(key=k, **v) for k, v in EXPLORE_ZONES.items() if v.get("enabled")]

    def explore(self, user_id: str, zone_key: str | None = None) -> dict:
        with self._player_lock(user_id):
            player = self._require_player(user_id)
            chosen_key = zone_key or player.explore_zone or "hoangnguyen"
            zone = EXPLORE_ZONES.get(chosen_key)
            if not zone or not zone.get("enabled"):
                raise GameError("Khu vực này chưa được khai mở.")
            if player.realm_idx < int(zone["min_realm"]):
                raise GameError(f"Cần đạt {REALMS[int(zone['min_realm'])][0]} mới có thể tiến vào khu vực này.")
            remaining = self.cooldown_remaining(player.last_explore, "explore")
            if remaining:
                raise GameError(f"Còn **{remaining}s** trước khi có thể khám phá tiếp.")
            player.explore_zone = chosen_key
            player.last_explore = int(time.time())
            event = self.rng.choice(zone["events"])
            result = {"player": player, "zone": zone, "event": event, "text": "", "encounter": None, "reward": {}}
            if event in {"monster", "boss"}:
                foe = self._new_encounter(player, boss=event == "boss")
                scale = float(zone["danger"])
                foe["hp"] = int(foe["hp"] * scale)
                foe["max_hp"] = foe["hp"]
                foe["attack"] = int(foe["attack"] * scale)
                foe["defense"] = int(foe["defense"] * scale)
                result["encounter"] = foe
                result["text"] = f"{zone['name']}: {foe['kind_label']} **{foe['name']}** xuất hiện!"
            elif event == "linh_mach":
                amount = self.rng.randint(*zone["reward"])
                player.spirit_stones += amount
                result["text"] = f"Phát hiện linh mạch, thu được **{amount} Linh Thạch**."
            elif event == "linh_thao":
                item_pool = ("tu_van_linh_qua", "huyet_linh_hoa", "thien_linh_qua") if chosen_key == "hoangnguyen" else ("long_huyet_qua", "huyet_linh_hoa", "tu_van_linh_qua")
                item_id = self.rng.choice(item_pool)
                qty = self.rng.randint(1, 2)
                self.db.add_item(user_id, item_id, qty)
                self._progress_sect_mission(user_id, "collect_spirit", qty)
                result["text"] = f"Hái được **{ITEMS[item_id]['name']} ×{qty}**."
            elif event == "merchant":
                stones = self.rng.randint(120, 420)
                player.spirit_stones += stones
                result["text"] = f"Gặp một tán tu giữa Hoang Nguyên. Giao thương thuận lợi, +**{stones} Linh Thạch**."
            elif event == "ancient_cave":
                result["inheritance"] = self.roll_inheritance(user_id)
                result["text"] = result["inheritance"]["text"]
            elif event == "epiphany":
                gain = self.add_cultivation(player, self.rng.randint(250, 700))
                player.insight = min(100, player.insight + 2)
                result["text"] = f"Đốn ngộ giữa thiên địa: **+{gain} tu vi**, +2 Ngộ Tính."
            elif event == "beast_cache":
                item_id = self.rng.choice(("long_huyet_qua", "huyet_linh_hoa", "thanh_phong_kiem"))
                if self.rng.random() < 0.35:
                    item_id = "long_huyet_qua"
                self.db.add_item(user_id, item_id, 1)
                stones = self.rng.randint(150, 500)
                player.spirit_stones += stones
                result["text"] = f"Đào được yêu tàng! Nhận **{ITEMS[item_id]['name']}** và **{stones} Linh Thạch**."
                self.db.add_discovery(user_id, f"zone:{chosen_key}:beast_cache:{item_id}")
            elif event == "bloodline":
                player.root = min(100, player.root + 2)
                player.fate = min(100, player.fate + 1)
                gain = self.add_cultivation(player, self.rng.randint(400, 900))
                result["text"] = f"Chạm vào huyết mạch yêu thú cổ, căn cốt **+2**, khí vận **+1**, tu vi **+{gain}**."
                self.db.add_discovery(user_id, f"zone:{chosen_key}:bloodline")
            else:
                loss = min(player.spirit_stones, self.rng.randint(100, 450))
                player.spirit_stones -= loss
                player.injury = min(100, player.injury + self.rng.randint(3, 10))
                result["text"] = f"Trận pháp cổ phản phệ: mất **{loss} Linh Thạch**, thương thế tăng."
            self._progress_sect_mission(user_id, "explore", 1)
            self.db.save_player(player)
            return result

    # ---------- Đăng Thăng Thiên ----------
    def ascension_tower_status(self, user_id: str) -> dict:
        player = self._require_player(user_id)
        day = int(time.strftime("%Y%m%d"))
        row = self.db.get_ascension_tower_progress(user_id)
        if not row:
            return {"best": 0, "attempts": 0, "remaining": ASCENSION_TOWER["daily_attempts"], "next_floor": 1}
        attempts = int(row["attempts"]) if int(row["day_key"]) == day else 0
        best = int(row["best_floor"])
        return {"best": best, "attempts": attempts, "remaining": max(0, ASCENSION_TOWER["daily_attempts"] - attempts), "next_floor": min(ASCENSION_TOWER["max_floor"], best + 1), "max_floor": ASCENSION_TOWER["max_floor"]}

    def ascension_tower_climb(self, user_id: str) -> dict:
        with self._player_lock(user_id):
            player = self._require_player(user_id)
            day = int(time.strftime("%Y%m%d"))
            now = int(time.time())
            row = self.db.get_ascension_tower_progress(user_id)
            best = int(row["best_floor"]) if row else 0
            attempts = int(row["attempts"]) if row and int(row["day_key"]) == day else 0
            if attempts >= ASCENSION_TOWER["daily_attempts"]:
                raise GameError("Hôm nay đã hết lượt Đăng Thăng Thiên.")
            if best >= ASCENSION_TOWER["max_floor"]:
                raise GameError("Ngươi đã chạm đỉnh Đăng Thăng Thiên.")
            floor = best + 1
            score = player.root + player.insight + player.mind + player.foundation + player.realm_idx * 15 + player.layer * 5 + int(getattr(player, "dao_stage", 0)) * 10
            difficulty = 120 + floor * 3.2
            chance = max(0.08, min(0.93, 0.52 + (score - difficulty) / 210.0))
            success = self.rng.random() < chance
            attempts += 1
            reward = ASCENSION_TOWER["base_reward"] + floor * 220 + self.rng.randint(0, 240) if success else 0
            drops = None
            if success:
                best = floor
                player.spirit_stones += reward
                gain = self.add_cultivation(player, 180 + floor * 12)
                if floor % 5 == 0:
                    drop = self.rng.choice(("tu_van_linh_qua", "hoi_khi_dan", "long_huyet_qua"))
                    self.db.add_item(user_id, drop, 1)
                    drops = ITEMS[drop]["name"]
                text = f"🌌 Đăng Thăng Thiên: vượt **tầng {floor}**. +{reward} Linh Thạch, +{gain} tu vi."
                if drops:
                    text += f" Nhận thêm **{drops}**."
            else:
                player.injury = min(100, player.injury + 2)
                text = f"🌌 Đăng Thăng Thiên: thất bại tại **tầng {floor}**. Đạo tâm chưa đủ vững."
            self.db.upsert_ascension_tower_progress(user_id, best_floor=best, attempts=attempts, day_key=day, last_attempt=now)
            self.db.log_ascension_tower(user_id, floor, success, reward, time.time_ns())
            self.db.save_player(player)
            return {"success": success, "floor": floor, "reward": reward, "chance": chance, "text": text, "status": self.ascension_tower_status(user_id)}

    def ascension_tower_leaderboard(self, limit: int = 10) -> list[dict]:
        return [dict(r) for r in self.db.ascension_tower_leaderboard(limit)]

    # ---------- Tháp Tông Môn ----------
    def sect_tower_status(self, user_id: str) -> dict:
        membership = self.db.get_sect_membership(user_id)
        if not membership:
            raise GameError("Ngươi chưa thuộc Tông Môn nào.")
        sect_id = str(membership["sect_id"])
        row = self.db.get_sect_tower_progress(sect_id)
        day = int(time.strftime("%Y%m%d"))
        best = int(row["best_floor"]) if row else 0
        attempts = int(row["attempts"]) if row and int(row["day_key"]) == day else 0
        return {"sect_id": sect_id, "sect_name": str(membership["name"]), "best": best, "attempts": attempts, "remaining": max(0, SECT_TOWER["daily_attempts"] - attempts), "next_floor": min(SECT_TOWER["max_floor"], best + 1), "max_floor": SECT_TOWER["max_floor"]}

    def sect_tower_climb(self, user_id: str) -> dict:
        with self._player_lock(user_id):
            player = self._require_player(user_id)
            membership = self.db.get_sect_membership(user_id)
            if not membership:
                raise GameError("Ngươi chưa thuộc Tông Môn nào.")
            sect_id = str(membership["sect_id"])
            with self._sect_lock(sect_id):
                sect = self.db.get_sect(sect_id)
                day = int(time.strftime("%Y%m%d"))
                now = int(time.time())
                row = self.db.get_sect_tower_progress(sect_id)
                best = int(row["best_floor"]) if row else 0
                attempts = int(row["attempts"]) if row and int(row["day_key"]) == day else 0
                if attempts >= SECT_TOWER["daily_attempts"]:
                    raise GameError("Hôm nay Tông Môn đã hết lượt Tháp Tông Môn.")
                if best >= SECT_TOWER["max_floor"]:
                    raise GameError("Tông Môn đã chạm đỉnh Tháp Tông Môn.")
                floor = best + 1
                members = self.db.list_sect_members(sect_id)
                member_count = len(members)
                top_contribution = max((int(r["contribution"]) for r in members), default=0)
                sect_level = int(sect["level"]) if sect else 1
                score = player.root + player.insight + player.foundation + sect_level * 18 + min(20, member_count) * 5 + min(100, top_contribution / 800.0)
                difficulty = 110 + floor * 3.4
                chance = max(0.08, min(0.90, 0.46 + (score - difficulty) / 230.0))
                success = self.rng.random() < chance
                attempts += 1
                reward = SECT_TOWER["base_reward"] + floor * 280 + self.rng.randint(0, 320) if success else 0
                if success:
                    best = floor
                    personal_reward = max(150, reward // 4)
                    player.spirit_stones += personal_reward
                    self.db.add_sect_treasury(sect_id, reward)
                    self.db.add_member_contribution(user_id, max(20, floor * 8))
                    gain = self.add_cultivation(player, 180 + floor * 10)
                    text = f"🏯 Tháp Tông Môn: Tông Môn vượt **tầng {floor}**. Tông khố +{reward} Linh Thạch, ngươi +{personal_reward} Linh Thạch, +{gain} tu vi."
                else:
                    player.injury = min(100, player.injury + 2)
                    text = f"🏯 Tháp Tông Môn: thất bại tại **tầng {floor}**. Tông Môn cần mạnh hơn trước khi thử lại."
                self.db.upsert_sect_tower_progress(sect_id, best_floor=best, attempts=attempts, day_key=day, last_attempt=now)
                self.db.log_sect_tower(sect_id, user_id, floor, success, reward, time.time_ns())
                self.db.save_player(player)
                return {"success": success, "floor": floor, "reward": reward, "chance": chance, "text": text, "status": self.sect_tower_status(user_id)}

    def sect_tower_leaderboard(self, limit: int = 10) -> list[dict]:
        return [dict(r) for r in self.db.sect_tower_leaderboard(limit)]

    def choose_dao(self,user_id:str,dao_type:str)->dict:
        with self._player_lock(user_id):
            player=self._require_player(user_id)
            if player.dao_type and player.dao_type!=dao_type: raise GameError("Đạo đã định. Muốn đổi Đạo phải chờ một cơ duyên đặc biệt.")
            if dao_type not in DAO_PATHS: raise GameError("Đạo này chưa tồn tại.")
            if not player.dao_type: player.dao_type=dao_type; player.dao_stage=0; player.dao_progress=0; self.db.save_player(player)
            return self.dao_info(user_id)

    def gain_dao_insight(self,user_id:str,amount:int=1)->dict:
        with self._player_lock(user_id):
            player=self._require_player(user_id)
            if not player.dao_type: raise GameError("Ngươi chưa chọn Đạo. Dùng `.dao` để chọn con đường.")
            self._gain_dao_insight_locked(player, max(1, int(amount)))
            self.db.save_player(player); return self.dao_info(user_id)

    def dao_info(self,user_id:str)->dict|None:
        p=self._require_player(user_id)
        if not p.dao_type: return None
        info=DAO_PATHS[p.dao_type]; return {"key":p.dao_type,"name":info["name"],"icon":info["icon"],"stage":p.dao_stage,"stage_name":info["stages"][p.dao_stage],"progress":p.dao_progress,"next":DAO_STAGE_THRESHOLD[p.dao_stage+1] if p.dao_stage+1<len(DAO_STAGE_THRESHOLD) else None}

    def trial_status(self,user_id:str)->dict:
        p=self._require_player(user_id)
        day=int(time.strftime("%Y%m%d"))
        attempts=p.trial_attempts if p.trial_day==day else 0
        best=max(0,int(p.trial_best))
        return {
            "best": best,
            "attempts": attempts,
            "remaining": max(0,TRIAL_TOWER["daily_attempts"]-attempts),
            "next_floor": min(TRIAL_TOWER["max_floor"], best+1),
            "day": day,
            "max_floor": TRIAL_TOWER["max_floor"],
        }

    def trial_challenge(self,user_id:str)->dict:
        with self._player_lock(user_id):
            p=self._require_player(user_id)
            day=int(time.strftime("%Y%m%d"))
            if p.trial_day!=day:
                p.trial_day=day
                p.trial_attempts=0
            if p.trial_attempts>=TRIAL_TOWER["daily_attempts"]:
                raise GameError("Hôm nay đã hết lượt Thí Luyện Tháp.")
            best=max(0,int(p.trial_best))
            if best>=TRIAL_TOWER["max_floor"]:
                raise GameError("Ngươi đã chạm đỉnh Thí Luyện Tháp.")
            floor=best+1
            p.trial_attempts+=1

            # Public tower: progression challenge only. No permanent stat/DAO buffs.
            training_score=(
                p.root*1.10 + p.insight*1.00 + p.foundation*1.15 + p.mind*0.45
                + p.realm_idx*18 + p.layer*3
            )
            floor_penalty=(floor-1)*TRIAL_TOWER["floor_penalty"]
            realm_pressure=1.0 + p.realm_idx*0.012
            chance=(training_score/220.0 + 0.36*realm_pressure) - floor_penalty
            chance=max(0.10,min(0.90,chance))
            success=self.rng.random()<chance

            if success:
                p.trial_best=floor
                reward=(
                    TRIAL_TOWER["base_reward"]
                    + floor*TRIAL_TOWER["floor_reward"]
                    + self.rng.randint(0,120)
                )
                p.spirit_stones+=reward
                gain=self.add_cultivation(p, 90 + floor*8)
                text=f"🗼 Thí Luyện Tháp: vượt **tầng {floor}**. +**{reward} Linh Thạch**"
                if gain:
                    text+=f", +**{gain} tu vi**."
                else:
                    text+="."
            else:
                reward=0
                p.injury=min(100,p.injury+1)
                text=f"🗼 Thí Luyện Tháp: thất bại tại **tầng {floor}**. Thương thế +1%."
            p.last_trial=int(time.time())
            self.db.save_player(p)
            with self.db.lock, self.db.conn:
                self.db.conn.execute(
                    "INSERT INTO trial_logs(user_id,floor,reward,created_at) VALUES(?,?,?,?)",
                    (str(user_id),floor,reward,time.time_ns()),
                )
            return {"success":success,"floor":floor,"reward":reward,"chance":chance,"text":text,"status":self.trial_status(user_id)}

    def trial_leaderboard(self,limit:int=10)->list[Player]:
        rows=self.db.conn.execute("SELECT * FROM players WHERE trial_best>0 ORDER BY trial_best DESC,realm_idx DESC,layer DESC,cultivation DESC LIMIT ?",(int(limit),)).fetchall(); return [Player.from_row(r) for r in rows]

    def sect_overview(self,user_id:str)->dict:
        m=self.db.get_sect_membership(user_id)
        if not m: raise GameError("Ngươi chưa thuộc Tông Môn nào.")
        sect=self.db.get_sect(str(m["sect_id"])); return {"member":dict(m),"sect":dict(sect),"treasury":self.db.get_sect_treasury(str(m["sect_id"])),"members":[dict(r) for r in self.db.list_sect_members(str(m["sect_id"]))]}

    def sect_leaderboard(self,limit:int=10)->list[dict]: return [dict(r) for r in self.db.sect_leaderboard(limit)]

    def sect_change_role(self,actor_id:str,target_id:str,role:str)->None:
        try: self.db.change_sect_role(actor_id,target_id,role)
        except ValueError as exc: raise GameError("Chỉ Tông Chủ có thể trao chức và người được trao phải cùng Tông Môn.") from exc

    def upgrade_sect_linh_mach(self,user_id:str)->dict:
        try:
            return self.db.upgrade_sect_linh_mach(user_id)
        except ValueError as exc:
            messages={"not_owner":"Chỉ Tông Chủ có thể nâng cấp Linh Mạch.","facility_max":"Linh Mạch đã đạt cấp tối đa.","not_enough_treasury":"Tông Khố không đủ Linh Thạch cho lần nâng cấp này."}
            raise GameError(messages.get(str(exc),"Không thể nâng cấp Linh Mạch.")) from exc

    def sect_mission_list(self,user_id:str)->list[dict]:
        self._require_player(user_id)
        membership=self.db.get_sect_membership(user_id)
        if not membership:
            raise GameError("Ngươi chưa thuộc Tông Môn nào.")
        sect_id=str(membership["sect_id"]); day=time.strftime("%Y%m%d"); out=[]
        for key,data in SECT_MISSIONS.items():
            row=self.db.get_mission_progress(user_id,sect_id,key)
            progress=0 if not row or row.get("day_key")!=day else int(row["progress"])
            completed=bool(row and row.get("day_key")==day and row.get("completed_at"))
            out.append({"key":key,**data,"progress":min(progress,int(data["target"])),"completed":completed})
        return out

    def sect_mission_claim(self,user_id:str,mission_key:str)->dict:
        with self._player_lock(user_id):
            membership=self.db.get_sect_membership(user_id)
            if not membership: raise GameError("Chỉ môn nhân mới có thể nhận nhiệm vụ Tông Môn.")
            data=SECT_MISSIONS.get(mission_key)
            if not data: raise GameError("Nhiệm vụ không tồn tại.")
            sect_id=str(membership["sect_id"]); day=time.strftime("%Y%m%d"); row=self.db.get_mission_progress(user_id,sect_id,mission_key)
            if not row or row.get("day_key")!=day or int(row["progress"])<int(data["target"]): raise GameError("Nhiệm vụ chưa hoàn thành.")
            if not self.db.complete_mission(user_id,sect_id,mission_key,day): raise GameError("Nhiệm vụ hôm nay đã nhận thưởng.")
            p=self._require_player(user_id)
            p.spirit_stones += int(data["reward"])
            self.db.save_player(p)
            # Mission contribution is earned progress, not a second currency donation.
            self.db.grant_sect_contribution(user_id, int(data["contribution"]))
            return {"reward":data["reward"],"contribution":data["contribution"]}

    def roll_inheritance(self,user_id:str)->dict:
        p=self._require_player(user_id); candidates=[e for e in INHERITANCE_EVENTS if p.realm_idx>=1 or e["key"]=="dan_vuong"]; event=self.rng.choice(candidates)
        if self.rng.random()<=float(event["chance"]):
            reward=event["reward"]
            if reward=="kiem_y_fragment":
                self.db.add_discovery(user_id,"dao:kiem:fragment")
                if p.dao_type == "kiem":
                    self._gain_dao_insight_locked(p, 80)
                    self.db.save_player(p)
            else: self.db.add_item(user_id,reward,1)
            return {"success":True,"text":f"✨ Cơ duyên mở ra: **{event['name']}**. Ngươi nhận được truyền thừa!"}
        return {"success":False,"text":f"🏚️ Gặp **{event['name']}**, nhưng truyền thừa đã tàn. Chỉ còn dấu vết để lĩnh ngộ."}

    def face_tribulation(self,user_id:str)->dict:
        with self._player_lock(user_id):
            p=self._require_player(user_id)
            required=self.cultivation_requirement(p)
            if not (p.realm_idx == 9 and p.layer == REALMS[9][1]):
                raise GameError("Thiên Kiếp chỉ mở tại **Độ Kiếp tầng 3**.")
            if p.cultivation < required:
                raise GameError(f"Tu vi chưa đủ để ứng kiếp. Cần **{required}**, hiện có **{p.cultivation}**.")
            # Old exact-cap saves may not have the readiness flag; normalize once.
            if not p.tribulation_ready and p.cultivation >= required:
                p.tribulation_ready = 1
            if not p.tribulation_ready:
                raise GameError("Chưa đủ điều kiện ứng kiếp.")
            chance=max(25,min(90,42+p.foundation*0.34+p.fate*0.14+p.mind*0.10))
            success=self.rng.random()*100<=chance
            if success:
                p.realm_idx=10
                p.layer=1
                p.cultivation=0
                p.foundation=min(100,p.foundation+2)
                p.merit+=100
                p.tribulation_ready=0
                text="⚡ Vượt qua Thiên Kiếp! Đại Đạo mở lối, ngươi chính thức bước vào **Chân Tiên tầng 1**."
            else:
                loss=max(100,int(required*0.15))
                p.injury=min(100,p.injury+20)
                p.cultivation=max(0,p.cultivation-loss)
                p.tribulation_ready=0
                text=f"⚡ Thiên Kiếp phản phệ! Thương thế +20%, tổn thất **{loss} tu vi**. Hãy tu luyện lại rồi ứng kiếp."
            self.db.save_player(p)
            return {"success":success,"chance":chance,"text":text,"player":p}

    # ---------- Admin core ----------
    def add_admin_user(self, user_id: str, actor_id: str) -> None:
        self.db.add_admin_user(user_id, actor_id)
        self.db.add_admin_audit(actor_id, "add_admin", user_id, "Granted admin access")

    def remove_admin_user(self, user_id: str, actor_id: str) -> None:
        self.db.remove_admin_user(user_id)
        self.db.add_admin_audit(actor_id, "remove_admin", user_id, "Revoked admin access")

    def admin_audit(self, actor_id: str, action: str, target_id: str | None, details: str = "") -> None:
        self.db.add_admin_audit(actor_id, action, target_id, details)

    # ---------- display ----------
    def info(self, user_id: str) -> Player: return self._require_player(user_id)

    def inventory(self, user_id: str) -> list[tuple[str, dict, int]]:
        self._require_player(user_id)
        return [(item_id, ITEMS[item_id], count) for item_id, count in self.db.list_inventory(user_id) if item_id in ITEMS]

    def leaderboard(self, limit: int = 10, path: str | None = None) -> list[Player]:
        return self.db.leaderboard(limit, path=path)

    def foundation_grade(self, player: Player) -> str:
        return "Phàm" if player.foundation < 50 else "Ổn" if player.foundation < 70 else "Tốt" if player.foundation < 85 else "Thượng phẩm" if player.foundation < 95 else "Cực phẩm"

    def public_profile(self, user_id: str) -> dict:
        player = self._require_player(user_id)
        inventory = self.inventory(user_id)
        return {"player": player, "inventory": inventory, "discoveries": self.discovery_count(user_id), "foundation_grade": self.foundation_grade(player), "dao": self.dao_info(user_id) if player.dao_type else None}

    def discovery_count(self, user_id: str) -> int:
        self._require_player(user_id); return self.db.count_discoveries(user_id)

    def destiny_description(self, player: Player) -> str: return DESTINY_DESCRIPTIONS.get(player.destiny, "Thiên mệnh chưa rõ.")
    def talent_description(self, player: Player) -> str: return TALENT_DESCRIPTIONS.get(player.talent, "Thiên phú chưa rõ.")
