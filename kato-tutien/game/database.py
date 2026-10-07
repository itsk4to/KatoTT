from __future__ import annotations

import sqlite3
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class Player:
    user_id: str
    display_name: str
    path: str
    realm_idx: int
    layer: int
    cultivation: int
    root: int
    insight: int
    luck: int
    fate: int
    mind: int
    karma: int
    merit: int
    destiny: str
    talent: str
    spirit_stones: int
    pity: int
    equipped: str | None
    last_cultivate: int
    last_explore: int
    last_hunt: int
    last_daily: int
    daily_streak: int
    created_at: int
    updated_at: int
    injury: int = 0
    be_quan_active: int = 0
    be_quan_last_tick: int = 0
    be_quan_prepaid: int = 0
    foundation: int = 50
    dao_type: str | None = None
    dao_stage: int = 0
    dao_progress: int = 0
    explore_zone: str = "hoangnguyen"
    trial_best: int = 0
    trial_attempts: int = 0
    trial_day: int = 0
    last_trial: int = 0
    tribulation_ready: int = 0
    loadout: str = "{}"

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Player":
        return cls(**dict(row))


class Database:
    def __init__(self, path: str | Path = "kato_tutien.db"):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, check_same_thread=False, timeout=5)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.execute("PRAGMA synchronous = NORMAL")
        self.conn.execute("PRAGMA busy_timeout = 5000")
        self.lock = threading.RLock()
        self.initialize()

    def initialize(self) -> None:
        with self.lock, self.conn:
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS players (
                    user_id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    path TEXT NOT NULL,
                    realm_idx INTEGER NOT NULL DEFAULT 0,
                    layer INTEGER NOT NULL DEFAULT 0,
                    cultivation INTEGER NOT NULL DEFAULT 0,
                    root INTEGER NOT NULL,
                    insight INTEGER NOT NULL,
                    luck INTEGER NOT NULL,
                    fate INTEGER NOT NULL,
                    mind INTEGER NOT NULL,
                    karma INTEGER NOT NULL DEFAULT 0,
                    merit INTEGER NOT NULL DEFAULT 0,
                    destiny TEXT NOT NULL,
                    talent TEXT NOT NULL,
                    spirit_stones INTEGER NOT NULL DEFAULT 1000,
                    pity INTEGER NOT NULL DEFAULT 0,
                    equipped TEXT,
                    last_cultivate INTEGER NOT NULL DEFAULT 0,
                    last_explore INTEGER NOT NULL DEFAULT 0,
                    last_hunt INTEGER NOT NULL DEFAULT 0,
                    last_daily INTEGER NOT NULL DEFAULT 0,
                    daily_streak INTEGER NOT NULL DEFAULT 0,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    be_quan_active INTEGER NOT NULL DEFAULT 0,
                    be_quan_last_tick INTEGER NOT NULL DEFAULT 0,
                    be_quan_prepaid INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS inventory (
                    user_id TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    count INTEGER NOT NULL DEFAULT 0 CHECK(count >= 0),
                    PRIMARY KEY (user_id, item_id),
                    FOREIGN KEY (user_id) REFERENCES players(user_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS discoveries (
                    user_id TEXT NOT NULL,
                    event_key TEXT NOT NULL,
                    discovered_at INTEGER NOT NULL,
                    PRIMARY KEY (user_id, event_key),
                    FOREIGN KEY (user_id) REFERENCES players(user_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS market_listings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    seller_id TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    quantity INTEGER NOT NULL CHECK(quantity > 0),
                    unit_price INTEGER NOT NULL CHECK(unit_price > 0),
                    created_at INTEGER NOT NULL,
                    FOREIGN KEY (seller_id) REFERENCES players(user_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_market_active ON market_listings(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_market_item ON market_listings(item_id, created_at DESC);

                CREATE TABLE IF NOT EXISTS redeem_codes (
                    code TEXT PRIMARY KEY,
                    max_uses INTEGER NOT NULL DEFAULT 0 CHECK(max_uses >= 0),
                    used_count INTEGER NOT NULL DEFAULT 0 CHECK(used_count >= 0),
                    created_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL DEFAULT 0,
                    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1))
                );

                CREATE TABLE IF NOT EXISTS code_redemptions (
                    code TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    redeemed_at INTEGER NOT NULL,
                    PRIMARY KEY (code, user_id),
                    FOREIGN KEY (code) REFERENCES redeem_codes(code) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES players(user_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_code_redemptions_user ON code_redemptions(user_id);

                CREATE TABLE IF NOT EXISTS dao_lu (
                    user_id TEXT PRIMARY KEY,
                    partner_id TEXT NOT NULL UNIQUE,
                    intimacy INTEGER NOT NULL DEFAULT 0,
                    created_at INTEGER NOT NULL,
                    last_song_tu INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES players(user_id) ON DELETE CASCADE,
                    FOREIGN KEY (partner_id) REFERENCES players(user_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS dao_lu_requests (
                    requester_id TEXT PRIMARY KEY,
                    target_id TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    FOREIGN KEY (requester_id) REFERENCES players(user_id) ON DELETE CASCADE,
                    FOREIGN KEY (target_id) REFERENCES players(user_id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_dao_lu_requests_target ON dao_lu_requests(target_id, created_at DESC);

                CREATE TABLE IF NOT EXISTS sects (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    path TEXT NOT NULL DEFAULT 'both',
                    min_realm INTEGER NOT NULL DEFAULT 0,
                    description TEXT NOT NULL DEFAULT '',
                    bonus_percent INTEGER NOT NULL DEFAULT 0,
                    owner_id TEXT,
                    created_at INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY (owner_id) REFERENCES players(user_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS sect_members (
                    user_id TEXT PRIMARY KEY,
                    sect_id TEXT NOT NULL,
                    contribution INTEGER NOT NULL DEFAULT 0,
                    joined_at INTEGER NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES players(user_id) ON DELETE CASCADE,
                    FOREIGN KEY (sect_id) REFERENCES sects(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_sect_members_sect ON sect_members(sect_id, contribution DESC);

                CREATE TABLE IF NOT EXISTS pvp_challenges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    challenger_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    bet_type TEXT NOT NULL CHECK(bet_type IN ('stones','item')),
                    item_id TEXT,
                    amount INTEGER NOT NULL CHECK(amount > 0),
                    created_at INTEGER NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
                    FOREIGN KEY (challenger_id) REFERENCES players(user_id) ON DELETE CASCADE,
                    FOREIGN KEY (target_id) REFERENCES players(user_id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_pvp_target_active ON pvp_challenges(target_id, active, created_at DESC);

                CREATE TABLE IF NOT EXISTS admin_users (
                    user_id TEXT PRIMARY KEY,
                    added_by TEXT NOT NULL,
                    added_at INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS admin_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    actor_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    target_id TEXT,
                    details TEXT NOT NULL DEFAULT '',
                    created_at INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_admin_audit_time ON admin_audit(created_at DESC);

                CREATE TABLE IF NOT EXISTS admin_sessions (
                    user_id TEXT PRIMARY KEY,
                    expires_at REAL NOT NULL
                );
                """
            )
            self._ensure_player_columns()
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS technique_mastery (
                    user_id TEXT NOT NULL,
                    technique_id TEXT NOT NULL,
                    mastery INTEGER NOT NULL DEFAULT 0,
                    stage TEXT NOT NULL DEFAULT 'Nhập môn',
                    updated_at INTEGER NOT NULL,
                    PRIMARY KEY (user_id, technique_id),
                    FOREIGN KEY (user_id) REFERENCES players(user_id) ON DELETE CASCADE
                )
            """)

    def _ensure_player_columns(self) -> None:
        columns = {row[1] for row in self.conn.execute("PRAGMA table_info(players)").fetchall()}
        if "last_daily" not in columns:
            self.conn.execute("ALTER TABLE players ADD COLUMN last_daily INTEGER NOT NULL DEFAULT 0")
        if "daily_streak" not in columns:
            self.conn.execute("ALTER TABLE players ADD COLUMN daily_streak INTEGER NOT NULL DEFAULT 0")
        if "injury" not in columns:
            self.conn.execute("ALTER TABLE players ADD COLUMN injury INTEGER NOT NULL DEFAULT 0")
        if "be_quan_active" not in columns:
            self.conn.execute("ALTER TABLE players ADD COLUMN be_quan_active INTEGER NOT NULL DEFAULT 0")
        if "be_quan_last_tick" not in columns:
            self.conn.execute("ALTER TABLE players ADD COLUMN be_quan_last_tick INTEGER NOT NULL DEFAULT 0")
        if "be_quan_prepaid" not in columns:
            self.conn.execute("ALTER TABLE players ADD COLUMN be_quan_prepaid INTEGER NOT NULL DEFAULT 0")
        additions = {
            "foundation": "INTEGER NOT NULL DEFAULT 50",
            "dao_type": "TEXT",
            "dao_stage": "INTEGER NOT NULL DEFAULT 0",
            "dao_progress": "INTEGER NOT NULL DEFAULT 0",
            "explore_zone": "TEXT NOT NULL DEFAULT 'hoangnguyen'",
            "trial_best": "INTEGER NOT NULL DEFAULT 0",
            "trial_attempts": "INTEGER NOT NULL DEFAULT 0",
            "trial_day": "INTEGER NOT NULL DEFAULT 0",
            "last_trial": "INTEGER NOT NULL DEFAULT 0",
            "tribulation_ready": "INTEGER NOT NULL DEFAULT 0",
            "loadout": "TEXT NOT NULL DEFAULT '{}'",
        }
        for name, definition in additions.items():
            if name not in columns:
                self.conn.execute(f"ALTER TABLE players ADD COLUMN {name} {definition}")
        self._migrate_sect_schema()
        self._ensure_expansion_tables()
        self._seed_sects()

    def _ensure_expansion_tables(self) -> None:
        with self.lock, self.conn:
            cols = {r[1] for r in self.conn.execute("PRAGMA table_info(sect_members)").fetchall()}
            if "role" not in cols:
                self.conn.execute("ALTER TABLE sect_members ADD COLUMN role TEXT NOT NULL DEFAULT 'Đệ Tử'")
            cols = {r[1] for r in self.conn.execute("PRAGMA table_info(sects)").fetchall()}
            if "level" not in cols:
                self.conn.execute("ALTER TABLE sects ADD COLUMN level INTEGER NOT NULL DEFAULT 1")
            if "exp" not in cols:
                self.conn.execute("ALTER TABLE sects ADD COLUMN exp INTEGER NOT NULL DEFAULT 0")
            if "linh_mach_level" not in cols:
                self.conn.execute("ALTER TABLE sects ADD COLUMN linh_mach_level INTEGER NOT NULL DEFAULT 0")
            self.conn.execute("CREATE TABLE IF NOT EXISTS sect_treasury (sect_id TEXT PRIMARY KEY, spirit_stones INTEGER NOT NULL DEFAULT 0, FOREIGN KEY(sect_id) REFERENCES sects(id) ON DELETE CASCADE)")
            mission_cols = {r[1] for r in self.conn.execute("PRAGMA table_info(sect_mission_progress)").fetchall()}
            if "sect_id" not in mission_cols:
                if mission_cols:
                    self.conn.execute("ALTER TABLE sect_mission_progress RENAME TO sect_mission_progress_legacy")
                    self.conn.execute("CREATE TABLE sect_mission_progress (user_id TEXT NOT NULL, sect_id TEXT NOT NULL, mission_key TEXT NOT NULL, progress INTEGER NOT NULL DEFAULT 0, completed_at INTEGER NOT NULL DEFAULT 0, day_key TEXT NOT NULL DEFAULT '', PRIMARY KEY(user_id, sect_id, mission_key), FOREIGN KEY(user_id) REFERENCES players(user_id) ON DELETE CASCADE, FOREIGN KEY(sect_id) REFERENCES sects(id) ON DELETE CASCADE)")
                    self.conn.execute("INSERT OR IGNORE INTO sect_mission_progress(user_id,sect_id,mission_key,progress,completed_at,day_key) SELECT l.user_id,sm.sect_id,l.mission_key,l.progress,l.completed_at,l.day_key FROM sect_mission_progress_legacy l JOIN sect_members sm ON sm.user_id=l.user_id")
                    self.conn.execute("DROP TABLE sect_mission_progress_legacy")
                else:
                    self.conn.execute("CREATE TABLE sect_mission_progress (user_id TEXT NOT NULL, sect_id TEXT NOT NULL, mission_key TEXT NOT NULL, progress INTEGER NOT NULL DEFAULT 0, completed_at INTEGER NOT NULL DEFAULT 0, day_key TEXT NOT NULL DEFAULT '', PRIMARY KEY(user_id, sect_id, mission_key), FOREIGN KEY(user_id) REFERENCES players(user_id) ON DELETE CASCADE, FOREIGN KEY(sect_id) REFERENCES sects(id) ON DELETE CASCADE)")
            self.conn.execute("CREATE TABLE IF NOT EXISTS trial_logs (user_id TEXT NOT NULL, floor INTEGER NOT NULL, reward INTEGER NOT NULL, created_at INTEGER NOT NULL, PRIMARY KEY(user_id, created_at), FOREIGN KEY(user_id) REFERENCES players(user_id) ON DELETE CASCADE)")
            self.conn.execute("CREATE TABLE IF NOT EXISTS dao_events (user_id TEXT NOT NULL, event_key TEXT NOT NULL, amount INTEGER NOT NULL DEFAULT 0, created_at INTEGER NOT NULL, PRIMARY KEY(user_id,event_key), FOREIGN KEY(user_id) REFERENCES players(user_id) ON DELETE CASCADE)")
            self.conn.execute("CREATE TABLE IF NOT EXISTS ascension_tower_progress (user_id TEXT PRIMARY KEY, best_floor INTEGER NOT NULL DEFAULT 0, attempts INTEGER NOT NULL DEFAULT 0, day_key INTEGER NOT NULL DEFAULT 0, last_attempt INTEGER NOT NULL DEFAULT 0, FOREIGN KEY(user_id) REFERENCES players(user_id) ON DELETE CASCADE)")
            self.conn.execute("CREATE TABLE IF NOT EXISTS ascension_tower_logs (user_id TEXT NOT NULL, floor INTEGER NOT NULL, success INTEGER NOT NULL, reward INTEGER NOT NULL DEFAULT 0, created_at INTEGER NOT NULL, PRIMARY KEY(user_id, created_at), FOREIGN KEY(user_id) REFERENCES players(user_id) ON DELETE CASCADE)")
            self.conn.execute("CREATE TABLE IF NOT EXISTS sect_tower_progress (sect_id TEXT PRIMARY KEY, best_floor INTEGER NOT NULL DEFAULT 0, attempts INTEGER NOT NULL DEFAULT 0, day_key INTEGER NOT NULL DEFAULT 0, last_attempt INTEGER NOT NULL DEFAULT 0, FOREIGN KEY(sect_id) REFERENCES sects(id) ON DELETE CASCADE)")
            self.conn.execute("CREATE TABLE IF NOT EXISTS sect_tower_logs (sect_id TEXT NOT NULL, user_id TEXT NOT NULL, floor INTEGER NOT NULL, success INTEGER NOT NULL, reward INTEGER NOT NULL DEFAULT 0, created_at INTEGER NOT NULL, PRIMARY KEY(sect_id, created_at), FOREIGN KEY(sect_id) REFERENCES sects(id) ON DELETE CASCADE, FOREIGN KEY(user_id) REFERENCES players(user_id) ON DELETE CASCADE)")
            self.conn.execute("INSERT OR IGNORE INTO sect_treasury(sect_id, spirit_stones) SELECT id,0 FROM sects")

    def sect_leaderboard(self, limit: int = 10) -> list[sqlite3.Row]:
        with self.lock:
            return self.conn.execute("SELECT s.id,s.name,s.path,s.level,s.exp,COALESCE(SUM(sm.contribution),0) AS contribution,COUNT(sm.user_id) AS members FROM sects s LEFT JOIN sect_members sm ON sm.sect_id=s.id WHERE s.owner_id IS NOT NULL GROUP BY s.id ORDER BY contribution DESC,s.level DESC,s.exp DESC LIMIT ?", (int(limit),)).fetchall()

    def list_sect_members(self, sect_id: str, limit: int = 50) -> list[sqlite3.Row]:
        with self.lock:
            return self.conn.execute("SELECT sm.*,p.display_name,p.realm_idx,p.layer,p.path FROM sect_members sm JOIN players p ON p.user_id=sm.user_id WHERE sm.sect_id=? ORDER BY sm.contribution DESC LIMIT ?", (str(sect_id),int(limit))).fetchall()

    def change_sect_role(self, actor_id: str, target_id: str, role: str) -> None:
        allowed={"Đệ Tử","Hộ Pháp","Trưởng Lão","Phó Tông Chủ","Tông Chủ"}
        if role not in allowed: raise ValueError("invalid_role")
        with self.lock, self.conn:
            actor=self.conn.execute("SELECT s.id FROM sect_members sm JOIN sects s ON s.id=sm.sect_id WHERE sm.user_id=? AND s.owner_id=?",(str(actor_id),str(actor_id))).fetchone()
            target=self.conn.execute("SELECT sect_id FROM sect_members WHERE user_id=?",(str(target_id),)).fetchone()
            if not actor or not target or str(actor["id"])!=str(target["sect_id"]): raise ValueError("not_owner")
            if role == "Tông Chủ":
                self.conn.execute("UPDATE sects SET owner_id=? WHERE id=?",(str(target_id),str(actor["id"])))
            self.conn.execute("UPDATE sect_members SET role=? WHERE user_id=? AND sect_id=?",(role,str(target_id),str(actor["id"])))
            if role == "Tông Chủ":
                self.conn.execute("UPDATE sect_members SET role='Phó Tông Chủ' WHERE user_id=? AND sect_id=?",(str(actor_id),str(actor["id"])))

    @staticmethod
    def _sect_level_threshold(level: int) -> int:
        return 1000 + max(0, int(level) - 1) * 750

    def _apply_sect_exp_locked(self, sect_id: str, amount: int) -> sqlite3.Row:
        row = self.conn.execute("SELECT * FROM sects WHERE id=?", (str(sect_id),)).fetchone()
        if not row:
            raise ValueError("sect_not_found")
        level = max(1, int(row["level"] or 1))
        exp = max(0, int(row["exp"] or 0)) + max(0, int(amount))
        bonus = int(row["bonus_percent"] or 0)
        while level < 20 and exp >= self._sect_level_threshold(level):
            exp -= self._sect_level_threshold(level)
            level += 1
            bonus = min(10, bonus + 1)
        self.conn.execute("UPDATE sects SET level=?,exp=?,bonus_percent=? WHERE id=?", (level, exp, bonus, str(sect_id)))
        return self.conn.execute("SELECT * FROM sects WHERE id=?", (str(sect_id),)).fetchone()

    def grant_sect_contribution(self, user_id: str, amount: int) -> sqlite3.Row:
        with self.lock, self.conn:
            member=self.conn.execute("SELECT * FROM sect_members WHERE user_id=?",(str(user_id),)).fetchone()
            if not member: raise ValueError("not_member")
            self.conn.execute("UPDATE sect_members SET contribution=contribution+? WHERE user_id=?",(int(amount),str(user_id)))
            self._apply_sect_exp_locked(str(member["sect_id"]), max(1,int(amount)//5))
            return self.conn.execute("SELECT sm.*,s.name,s.bonus_percent,s.level,s.exp,s.linh_mach_level,COALESCE(st.spirit_stones,0) AS treasury FROM sect_members sm JOIN sects s ON s.id=sm.sect_id LEFT JOIN sect_treasury st ON st.sect_id=s.id WHERE sm.user_id=?",(str(user_id),)).fetchone()

    def add_sect_treasury(self, sect_id: str, amount: int) -> int:
        with self.lock, self.conn:
            self.conn.execute("INSERT INTO sect_treasury(sect_id,spirit_stones) VALUES(?,?) ON CONFLICT(sect_id) DO UPDATE SET spirit_stones=spirit_stones+excluded.spirit_stones",(str(sect_id),int(amount)))
            row=self.conn.execute("SELECT spirit_stones FROM sect_treasury WHERE sect_id=?",(str(sect_id),)).fetchone()
            return int(row[0])

    def get_sect_treasury(self, sect_id: str) -> int:
        with self.lock:
            row=self.conn.execute("SELECT spirit_stones FROM sect_treasury WHERE sect_id=?",(str(sect_id),)).fetchone()
            return int(row[0]) if row else 0

    def upgrade_sect_linh_mach(self, user_id: str) -> dict:
        with self.lock, self.conn:
            row = self.conn.execute("SELECT s.* FROM sects s JOIN sect_members sm ON sm.sect_id=s.id WHERE sm.user_id=? AND s.owner_id=?", (str(user_id), str(user_id))).fetchone()
            if not row:
                raise ValueError("not_owner")
            level = int(row["linh_mach_level"] or 0)
            if level >= 5:
                raise ValueError("facility_max")
            cost = 15000 * (level + 1)
            treasury = self.conn.execute("SELECT spirit_stones FROM sect_treasury WHERE sect_id=?", (str(row["id"]),)).fetchone()
            current = int(treasury[0]) if treasury else 0
            if current < cost:
                raise ValueError("not_enough_treasury")
            self.conn.execute("UPDATE sect_treasury SET spirit_stones=spirit_stones-? WHERE sect_id=?", (cost, str(row["id"])))
            new_level = level + 1
            new_bonus = min(10, int(row["bonus_percent"]) + 1)
            self.conn.execute("UPDATE sects SET linh_mach_level=?,bonus_percent=? WHERE id=?", (new_level, new_bonus, str(row["id"])))
            return dict(self.conn.execute("SELECT * FROM sects WHERE id=?", (str(row["id"]),)).fetchone())

    def add_mission_progress(self,user_id:str,sect_id:str,mission_key:str,amount:int,day_key:str)->dict:
        with self.lock,self.conn:
            row=self.conn.execute("SELECT progress,completed_at,day_key FROM sect_mission_progress WHERE user_id=? AND sect_id=? AND mission_key=?",(str(user_id),str(sect_id),mission_key)).fetchone()
            if not row or row["day_key"]!=day_key:
                self.conn.execute("INSERT OR REPLACE INTO sect_mission_progress(user_id,sect_id,mission_key,progress,completed_at,day_key) VALUES(?,?,?,?,?,?)",(str(user_id),str(sect_id),mission_key,int(amount),0,day_key))
            elif int(row["completed_at"]):
                pass
            else:
                self.conn.execute("UPDATE sect_mission_progress SET progress=progress+? WHERE user_id=? AND sect_id=? AND mission_key=?",(int(amount),str(user_id),str(sect_id),mission_key))
            row=self.conn.execute("SELECT * FROM sect_mission_progress WHERE user_id=? AND sect_id=? AND mission_key=?",(str(user_id),str(sect_id),mission_key)).fetchone()
            return dict(row)

    def get_mission_progress(self,user_id:str,sect_id:str,mission_key:str)->dict|None:
        with self.lock:
            row=self.conn.execute("SELECT * FROM sect_mission_progress WHERE user_id=? AND sect_id=? AND mission_key=?",(str(user_id),str(sect_id),mission_key)).fetchone()
            return dict(row) if row else None

    def complete_mission(self,user_id:str,sect_id:str,mission_key:str,day_key:str)->bool:
        with self.lock,self.conn:
            row=self.conn.execute("SELECT completed_at,day_key FROM sect_mission_progress WHERE user_id=? AND sect_id=? AND mission_key=?",(str(user_id),str(sect_id),mission_key)).fetchone()
            if not row or row["day_key"]!=day_key or int(row["completed_at"]): return False
            self.conn.execute("UPDATE sect_mission_progress SET completed_at=? WHERE user_id=? AND sect_id=? AND mission_key=?",(int(time.time()),str(user_id),str(sect_id),mission_key))
            return True

    def clear_mission_progress(self,user_id:str)->None:
        with self.lock,self.conn:
            self.conn.execute("DELETE FROM sect_mission_progress WHERE user_id=?",(str(user_id),))

    def get_player(self, user_id: str) -> Player | None:
        with self.lock:
            row = self.conn.execute("SELECT * FROM players WHERE user_id = ?", (str(user_id),)).fetchone()
        return Player.from_row(row) if row else None

    def get_players_by_ids(self, user_ids: list[str]) -> dict[str, Player]:
        ids = [str(x) for x in user_ids]
        if not ids:
            return {}
        placeholders = ",".join("?" for _ in ids)
        with self.lock:
            rows = self.conn.execute(f"SELECT * FROM players WHERE user_id IN ({placeholders})", ids).fetchall()
        return {str(row["user_id"]): Player.from_row(row) for row in rows}

    def create_player(self, player: Player) -> None:
        data = asdict(player)
        with self.lock, self.conn:
            self.conn.execute(
                """
                INSERT INTO players (
                    user_id, display_name, path, realm_idx, layer, cultivation,
                    root, insight, luck, fate, mind, karma, merit, destiny, talent,
                    spirit_stones, pity, equipped, last_cultivate, last_explore,
                    last_hunt, last_daily, daily_streak, created_at, updated_at, injury,
                    be_quan_active, be_quan_last_tick, be_quan_prepaid, foundation, dao_type, dao_stage, dao_progress,
                    explore_zone, trial_best, trial_attempts, trial_day, last_trial, tribulation_ready, loadout
                ) VALUES (
                    :user_id, :display_name, :path, :realm_idx, :layer, :cultivation,
                    :root, :insight, :luck, :fate, :mind, :karma, :merit, :destiny, :talent,
                    :spirit_stones, :pity, :equipped, :last_cultivate, :last_explore,
                    :last_hunt, :last_daily, :daily_streak, :created_at, :updated_at, :injury,
                    :be_quan_active, :be_quan_last_tick, :be_quan_prepaid, :foundation, :dao_type, :dao_stage, :dao_progress,
                    :explore_zone, :trial_best, :trial_attempts, :trial_day, :last_trial, :tribulation_ready, :loadout
                )
                """,
                data,
            )

    def save_player(self, player: Player) -> None:
        player.updated_at = int(time.time())
        data = asdict(player)
        with self.lock, self.conn:
            self.conn.execute(
                """
                UPDATE players SET
                    display_name=:display_name, path=:path, realm_idx=:realm_idx, layer=:layer,
                    cultivation=:cultivation, root=:root, insight=:insight, luck=:luck,
                    fate=:fate, mind=:mind, karma=:karma, merit=:merit, destiny=:destiny,
                    talent=:talent, spirit_stones=:spirit_stones, pity=:pity,
                    equipped=:equipped, last_cultivate=:last_cultivate,
                    last_explore=:last_explore, last_hunt=:last_hunt,
                    last_daily=:last_daily, daily_streak=:daily_streak, injury=:injury,
                    be_quan_active=:be_quan_active, be_quan_last_tick=:be_quan_last_tick, be_quan_prepaid=:be_quan_prepaid,
                    foundation=:foundation, dao_type=:dao_type, dao_stage=:dao_stage, dao_progress=:dao_progress,
                    explore_zone=:explore_zone, trial_best=:trial_best, trial_attempts=:trial_attempts,
                    trial_day=:trial_day, last_trial=:last_trial, tribulation_ready=:tribulation_ready, loadout=:loadout, updated_at=:updated_at
                WHERE user_id=:user_id
                """,
                data,
            )

    def purchase_shop_item(self, user_id: str, item_id: str, qty: int, unit_price: int) -> tuple[Player, int]:
        """Atomically charge stones and grant a shop item."""
        user_id = str(user_id)
        qty = int(qty)
        unit_price = int(unit_price)
        if qty <= 0 or unit_price < 0:
            raise ValueError("invalid_purchase")
        total = qty * unit_price
        now = int(time.time())
        with self.lock:
            self.conn.execute("BEGIN IMMEDIATE")
            try:
                row = self.conn.execute(
                    "SELECT * FROM players WHERE user_id=?", (user_id,)
                ).fetchone()
                if not row:
                    raise ValueError("player_not_found")
                if int(row["spirit_stones"]) < total:
                    raise ValueError("not_enough_stones")
                self.conn.execute(
                    "UPDATE players SET spirit_stones=spirit_stones-?, updated_at=? WHERE user_id=?",
                    (total, now, user_id),
                )
                self.conn.execute(
                    """INSERT INTO inventory(user_id,item_id,count) VALUES(?,?,?)
                       ON CONFLICT(user_id,item_id) DO UPDATE SET count=count+excluded.count""",
                    (user_id, item_id, qty),
                )
                updated = self.conn.execute("SELECT * FROM players WHERE user_id=?", (user_id,)).fetchone()
                self.conn.commit()
                return Player.from_row(updated), total
            except Exception:
                self.conn.rollback()
                raise

    def add_item(self, user_id: str, item_id: str, count: int = 1) -> int:
        if count <= 0:
            return self.get_item_count(user_id, item_id)
        with self.lock, self.conn:
            self.conn.execute(
                """
                INSERT INTO inventory(user_id, item_id, count) VALUES(?, ?, ?)
                ON CONFLICT(user_id, item_id) DO UPDATE SET count = count + excluded.count
                """,
                (str(user_id), item_id, count),
            )
        return self.get_item_count(user_id, item_id)

    def remove_item(self, user_id: str, item_id: str, count: int = 1) -> bool:
        if count <= 0:
            return True
        with self.lock, self.conn:
            row = self.conn.execute(
                "SELECT count FROM inventory WHERE user_id=? AND item_id=?",
                (str(user_id), item_id),
            ).fetchone()
            if not row or row["count"] < count:
                return False
            new_count = row["count"] - count
            if new_count:
                self.conn.execute(
                    "UPDATE inventory SET count=? WHERE user_id=? AND item_id=?",
                    (new_count, str(user_id), item_id),
                )
            else:
                self.conn.execute(
                    "DELETE FROM inventory WHERE user_id=? AND item_id=?",
                    (str(user_id), item_id),
                )
        return True

    def get_item_count(self, user_id: str, item_id: str) -> int:
        with self.lock:
            row = self.conn.execute(
                "SELECT count FROM inventory WHERE user_id=? AND item_id=?",
                (str(user_id), item_id),
            ).fetchone()
        return int(row["count"]) if row else 0

    def list_inventory(self, user_id: str) -> list[tuple[str, int]]:
        with self.lock:
            rows = self.conn.execute(
                "SELECT item_id, count FROM inventory WHERE user_id=? AND count>0 ORDER BY item_id",
                (str(user_id),),
            ).fetchall()
        return [(row["item_id"], int(row["count"])) for row in rows]

    def get_discovery(self, user_id: str, event_key: str) -> bool:
        with self.lock:
            row = self.conn.execute(
                "SELECT 1 FROM discoveries WHERE user_id=? AND event_key=? LIMIT 1",
                (str(user_id), event_key),
            ).fetchone()
        return row is not None

    def add_discovery(self, user_id: str, event_key: str) -> bool:
        with self.lock, self.conn:
            cur = self.conn.execute(
                "INSERT OR IGNORE INTO discoveries(user_id, event_key, discovered_at) VALUES(?, ?, ?)",
                (str(user_id), event_key, int(time.time())),
            )
        return cur.rowcount > 0

    def list_discoveries(self, user_id: str, prefix: str | None = None) -> list[str]:
        with self.lock:
            if prefix is None:
                rows = self.conn.execute(
                    "SELECT event_key FROM discoveries WHERE user_id=? ORDER BY discovered_at",
                    (str(user_id),),
                ).fetchall()
            else:
                rows = self.conn.execute(
                    "SELECT event_key FROM discoveries WHERE user_id=? AND event_key LIKE ? ORDER BY discovered_at",
                    (str(user_id), f"{prefix}%"),
                ).fetchall()
        return [str(row["event_key"]) for row in rows]

    def list_player_ids(self) -> list[str]:
        with self.lock:
            rows = self.conn.execute("SELECT user_id FROM players").fetchall()
        return [str(row["user_id"]) for row in rows]

    def count_discoveries(self, user_id: str) -> int:
        with self.lock:
            row = self.conn.execute(
                "SELECT COUNT(*) AS c FROM discoveries WHERE user_id=?",
                (str(user_id),),
            ).fetchone()
        return int(row["c"])

    def leaderboard(self, limit: int = 10, path: str | None = None) -> list[Player]:
        with self.lock:
            if path in {"tien", "ma"}:
                rows = self.conn.execute(
                    "SELECT * FROM players WHERE path=? ORDER BY (realm_idx * 1000000 + layer * 10000 + cultivation) DESC, foundation DESC, user_id ASC LIMIT ?",
                    (path, int(limit)),
                ).fetchall()
            else:
                rows = self.conn.execute(
                    "SELECT * FROM players ORDER BY (realm_idx * 1000000 + layer * 10000 + cultivation) DESC, foundation DESC, user_id ASC LIMIT ?",
                    (int(limit),),
                ).fetchall()
        return [Player.from_row(row) for row in rows]

    # ---------- Dao Lu ----------
    def get_dao_lu(self, user_id: str) -> sqlite3.Row | None:
        with self.lock:
            return self.conn.execute("SELECT * FROM dao_lu WHERE user_id=?", (str(user_id),)).fetchone()

    def create_dao_lu_request(self, requester_id: str, target_id: str) -> None:
        with self.lock, self.conn:
            self.conn.execute(
                "INSERT INTO dao_lu_requests(requester_id, target_id, created_at) VALUES(?, ?, ?) "
                "ON CONFLICT(requester_id) DO UPDATE SET target_id=excluded.target_id, created_at=excluded.created_at",
                (str(requester_id), str(target_id), int(time.time())),
            )

    def get_dao_lu_request(self, target_id: str) -> sqlite3.Row | None:
        with self.lock:
            return self.conn.execute(
                "SELECT * FROM dao_lu_requests WHERE target_id=? ORDER BY created_at DESC LIMIT 1",
                (str(target_id),),
            ).fetchone()

    def delete_dao_lu_request(self, requester_id: str) -> None:
        with self.lock, self.conn:
            self.conn.execute("DELETE FROM dao_lu_requests WHERE requester_id=?", (str(requester_id),))

    def create_dao_lu(self, user_a: str, user_b: str) -> None:
        now = int(time.time())
        with self.lock, self.conn:
            self.conn.execute("BEGIN IMMEDIATE")
            try:
                self.conn.execute("DELETE FROM dao_lu_requests WHERE requester_id=? OR target_id=?", (str(user_a), str(user_a)))
                self.conn.execute("DELETE FROM dao_lu_requests WHERE requester_id=? OR target_id=?", (str(user_b), str(user_b)))
                self.conn.execute("INSERT INTO dao_lu(user_id, partner_id, intimacy, created_at, last_song_tu) VALUES(?,?,?,?,0)", (str(user_a), str(user_b), 0, now))
                self.conn.execute("INSERT INTO dao_lu(user_id, partner_id, intimacy, created_at, last_song_tu) VALUES(?,?,?,?,0)", (str(user_b), str(user_a), 0, now))
                self.conn.commit()
            except Exception:
                self.conn.rollback()
                raise

    def update_dao_lu(self, user_id: str, *, intimacy_delta: int = 0, last_song_tu: int | None = None) -> None:
        with self.lock, self.conn:
            row = self.conn.execute("SELECT partner_id FROM dao_lu WHERE user_id=?", (str(user_id),)).fetchone()
            if not row:
                return
            partner = str(row["partner_id"])
            if last_song_tu is None:
                self.conn.execute("UPDATE dao_lu SET intimacy=intimacy+? WHERE user_id IN (?,?)", (int(intimacy_delta), str(user_id), partner))
            else:
                self.conn.execute("UPDATE dao_lu SET intimacy=intimacy+?, last_song_tu=? WHERE user_id IN (?,?)", (int(intimacy_delta), int(last_song_tu), str(user_id), partner))

    def break_dao_lu(self, user_id: str) -> sqlite3.Row | None:
        with self.lock, self.conn:
            self.conn.execute("BEGIN IMMEDIATE")
            try:
                row = self.conn.execute("SELECT * FROM dao_lu WHERE user_id=?", (str(user_id),)).fetchone()
                if not row:
                    self.conn.rollback()
                    return None
                partner = str(row["partner_id"])
                self.conn.execute("DELETE FROM dao_lu WHERE user_id IN (?,?)", (str(user_id), partner))
                self.conn.commit()
                return row
            except Exception:
                self.conn.rollback()
                raise

    # ---------- Sect & PvP ----------
    def _migrate_sect_schema(self) -> None:
        """Migrate old fixed-sect databases to player-created sects."""
        with self.lock, self.conn:
            columns = {row[1] for row in self.conn.execute("PRAGMA table_info(sects)").fetchall()}
            if "owner_id" not in columns:
                self.conn.execute("ALTER TABLE sects ADD COLUMN owner_id TEXT")
            if "created_at" not in columns:
                self.conn.execute("ALTER TABLE sects ADD COLUMN created_at INTEGER NOT NULL DEFAULT 0")
            self.conn.execute("UPDATE sects SET created_at=? WHERE created_at=0", (int(time.time()),))

    def create_sect(self, sect_id: str, owner_id: str, name: str, path: str, min_realm: int, description: str, bonus_percent: int = 2) -> sqlite3.Row:
        with self.lock, self.conn:
            if self.conn.execute("SELECT 1 FROM sects WHERE owner_id=?", (str(owner_id),)).fetchone():
                raise ValueError("already_has_sect")
            if self.conn.execute("SELECT 1 FROM sects WHERE lower(name)=lower(?)", (name,)).fetchone():
                raise ValueError("sect_name_taken")
            now = int(time.time())
            self.conn.execute(
                "INSERT INTO sects(id,name,path,min_realm,description,bonus_percent,owner_id,created_at,exp) VALUES(?,?,?,?,?,?,?,?,?)",
                (str(sect_id), name, path, int(min_realm), description, int(bonus_percent), str(owner_id), now, 500),
            )
            self.conn.execute(
                "INSERT INTO sect_members(user_id,sect_id,contribution,joined_at,role) VALUES(?,?,5000,?,?)",
                (str(owner_id), str(sect_id), now, "Tông Chủ"),
            )
            self.conn.execute("INSERT OR IGNORE INTO sect_treasury(sect_id,spirit_stones) VALUES(?,0)",(str(sect_id),))
            return self.conn.execute("SELECT * FROM sects WHERE id=?", (str(sect_id),)).fetchone()

    def delete_sect(self, sect_id: str, owner_id: str) -> None:
        with self.lock, self.conn:
            row = self.conn.execute("SELECT owner_id FROM sects WHERE id=?", (str(sect_id),)).fetchone()
            if not row or str(row["owner_id"] or "") != str(owner_id):
                raise ValueError("not_sect_owner")
            self.conn.execute("DELETE FROM sects WHERE id=?", (str(sect_id),))

    def list_custom_sects(self) -> list[sqlite3.Row]:
        with self.lock:
            return self.conn.execute("SELECT * FROM sects WHERE owner_id IS NOT NULL ORDER BY created_at DESC, id ASC").fetchall()

    def _seed_sects(self) -> None:
        rows = [
            ("thanh_van", "Thanh Vân Tông", "tien", 0, "Chính đạo thanh nhã, thiên về tu luyện ổn định.", 2),
            ("kiem_ho", "Kiếm Hồ Sơn Trang", "both", 2, "Kiếm tu trọng chiến, thiên về công kích.", 3),
            ("dan_dinh", "Đan Đỉnh Cốc", "both", 1, "Luyện đan và linh dược, tu hành bền bỉ.", 2),
            ("van_ma", "Vạn Ma Điện", "ma", 1, "Ma đạo hung lệ, tu luyện nhanh nhưng hiểm.", 3),
            ("thai_hu", "Thái Hư Các", "both", 4, "Tàng kinh lâu đời, dành cho người có căn cơ vững.", 5),
        ]
        with self.lock, self.conn:
            self.conn.executemany(
                "INSERT OR IGNORE INTO sects(id,name,path,min_realm,description,bonus_percent) VALUES(?,?,?,?,?,?)",
                rows,
            )

    def _all_sects(self) -> list[sqlite3.Row]:
        with self.lock:
            return self.conn.execute("SELECT * FROM sects ORDER BY min_realm ASC, id ASC").fetchall()

    def list_sects(self) -> list[sqlite3.Row]:
        return self._all_sects()

    def get_sect(self, sect_id: str) -> sqlite3.Row | None:
        with self.lock:
            return self.conn.execute("SELECT * FROM sects WHERE id=?", (str(sect_id),)).fetchone()

    def get_sect_membership(self, user_id: str) -> sqlite3.Row | None:
        with self.lock:
            return self.conn.execute(
                "SELECT sm.*, s.name, s.path, s.min_realm, s.description, s.bonus_percent, s.owner_id, s.level, s.exp, s.linh_mach_level "
                "FROM sect_members sm JOIN sects s ON s.id=sm.sect_id WHERE sm.user_id=?",
                (str(user_id),),
            ).fetchone()

    def join_sect(self, user_id: str, sect_id: str) -> None:
        with self.lock, self.conn:
            if self.conn.execute("SELECT 1 FROM sect_members WHERE user_id=?", (str(user_id),)).fetchone():
                raise ValueError("already_member")
            if not self.conn.execute("SELECT 1 FROM sects WHERE id=?", (str(sect_id),)).fetchone():
                raise ValueError("sect_not_found")
            self.conn.execute(
                "INSERT INTO sect_members(user_id,sect_id,contribution,joined_at) VALUES(?,?,0,?)",
                (str(user_id), str(sect_id), int(time.time())),
            )
            self.conn.execute("DELETE FROM sect_mission_progress WHERE user_id=?", (str(user_id),))

    def leave_sect(self, user_id: str) -> None:
        with self.lock, self.conn:
            cur = self.conn.execute("DELETE FROM sect_members WHERE user_id=?", (str(user_id),))
            if cur.rowcount == 0:
                raise ValueError("not_member")
            self.conn.execute("DELETE FROM sect_mission_progress WHERE user_id=?", (str(user_id),))

    def add_sect_contribution(self, user_id: str, amount: int) -> sqlite3.Row:
        with self.lock:
            self.conn.execute("BEGIN IMMEDIATE")
            try:
                member = self.conn.execute("SELECT * FROM sect_members WHERE user_id=?", (str(user_id),)).fetchone()
                if not member:
                    raise ValueError("not_member")
                player = self.conn.execute("SELECT * FROM players WHERE user_id=?", (str(user_id),)).fetchone()
                if not player:
                    raise ValueError("player_not_found")
                if int(player["spirit_stones"]) < amount:
                    raise ValueError("not_enough_stones")
                now = int(time.time())
                self.conn.execute("UPDATE players SET spirit_stones=spirit_stones-?, updated_at=? WHERE user_id=?", (amount, now, str(user_id)))
                self.conn.execute("UPDATE sect_members SET contribution=contribution+? WHERE user_id=?", (amount, str(user_id)))
                sect_id = str(member["sect_id"])
                self.conn.execute("INSERT INTO sect_treasury(sect_id,spirit_stones) VALUES(?,?) ON CONFLICT(sect_id) DO UPDATE SET spirit_stones=spirit_stones+excluded.spirit_stones", (sect_id, amount))
                self._apply_sect_exp_locked(sect_id, max(1, amount // 5))
                result = self.conn.execute(
                    "SELECT sm.*, s.name, s.bonus_percent, s.level, s.exp, s.linh_mach_level FROM sect_members sm JOIN sects s ON s.id=sm.sect_id WHERE sm.user_id=?",
                    (str(user_id),),
                ).fetchone()
                self.conn.commit()
                return result
            except Exception:
                self.conn.rollback()
                raise

    def create_pvp_challenge(self, challenger_id: str, target_id: str, bet_type: str, item_id: str | None, amount: int) -> int:
        challenger_id, target_id = str(challenger_id), str(target_id)
        with self.lock:
            self.conn.execute("BEGIN IMMEDIATE")
            try:
                # Prevent a user from being spammed with multiple simultaneous challenges.
                existing = self.conn.execute(
                    "SELECT 1 FROM pvp_challenges WHERE target_id=? AND active=1 LIMIT 1",
                    (target_id,),
                ).fetchone()
                if existing:
                    raise ValueError("target_busy")
                cur = self.conn.execute(
                    "INSERT INTO pvp_challenges(challenger_id,target_id,bet_type,item_id,amount,created_at,active) VALUES(?,?,?,?,?,?,1)",
                    (challenger_id, target_id, str(bet_type), item_id, int(amount), int(time.time())),
                )
                self.conn.commit()
                return int(cur.lastrowid)
            except Exception:
                self.conn.rollback()
                raise

    def get_pvp_challenge(self, challenge_id: int, active_only: bool = True) -> sqlite3.Row | None:
        sql = "SELECT * FROM pvp_challenges WHERE id=?"
        params = [int(challenge_id)]
        if active_only:
            sql += " AND active=1"
        with self.lock:
            row = self.conn.execute(sql, params).fetchone()
            if row and active_only and int(time.time()) - int(row["created_at"]) >= 10 * 60:
                self.conn.execute("UPDATE pvp_challenges SET active=0 WHERE id=?", (int(challenge_id),))
                self.conn.commit()
                return None
            return row

    def close_pvp_challenge(self, challenge_id: int) -> None:
        with self.lock, self.conn:
            self.conn.execute("UPDATE pvp_challenges SET active=0 WHERE id=?", (int(challenge_id),))

    def settle_pvp_challenge(self, challenge_id: int, winner_id: str) -> dict:
        with self.lock:
            self.conn.execute("BEGIN IMMEDIATE")
            try:
                row = self.conn.execute("SELECT * FROM pvp_challenges WHERE id=? AND active=1", (int(challenge_id),)).fetchone()
                if not row:
                    raise ValueError("challenge_not_found")
                challenger = self.conn.execute("SELECT * FROM players WHERE user_id=?", (str(row["challenger_id"]),)).fetchone()
                target = self.conn.execute("SELECT * FROM players WHERE user_id=?", (str(row["target_id"]),)).fetchone()
                if not challenger or not target:
                    raise ValueError("player_not_found")
                bet_type = str(row["bet_type"]); item_id = row["item_id"]; amount = int(row["amount"])
                loser_id = str(row["target_id"] if str(winner_id) == str(row["challenger_id"]) else row["challenger_id"])
                if winner_id not in {str(row["challenger_id"]), str(row["target_id"])}:
                    raise ValueError("invalid_winner")
                if bet_type == "stones":
                    for p in (challenger, target):
                        if int(p["spirit_stones"]) < amount:
                            raise ValueError("stake_unavailable")
                    self.conn.execute("UPDATE players SET spirit_stones=spirit_stones-? WHERE user_id IN (?,?)", (amount, str(row["challenger_id"]), str(row["target_id"])))
                    self.conn.execute("UPDATE players SET spirit_stones=spirit_stones+? WHERE user_id=?", (amount * 2, str(winner_id)))
                    won = {"type": "stones", "amount": amount * 2}
                else:
                    for uid in (str(row["challenger_id"]), str(row["target_id"])):
                        count_row = self.conn.execute("SELECT count FROM inventory WHERE user_id=? AND item_id=?", (uid, item_id)).fetchone()
                        if not count_row or int(count_row["count"]) < amount:
                            raise ValueError("stake_unavailable")
                    for uid in (str(row["challenger_id"]), str(row["target_id"])):
                        self.conn.execute("UPDATE inventory SET count=count-? WHERE user_id=? AND item_id=?", (amount, uid, item_id))
                        self.conn.execute("DELETE FROM inventory WHERE user_id=? AND item_id=? AND count<=0", (uid, item_id))
                    self.conn.execute(
                        "INSERT INTO inventory(user_id,item_id,count) VALUES(?,?,?) ON CONFLICT(user_id,item_id) DO UPDATE SET count=count+excluded.count",
                        (str(winner_id), str(item_id), amount * 2),
                    )
                    won = {"type": "item", "item_id": str(item_id), "amount": amount * 2}
                self.conn.execute("UPDATE pvp_challenges SET active=0 WHERE id=?", (int(challenge_id),))
                self.conn.commit()
                return {"winner_id": str(winner_id), "loser_id": loser_id, "stake": won}
            except Exception:
                self.conn.rollback()
                raise

    def list_active_be_quan(self) -> list[sqlite3.Row]:
        with self.lock:
            return self.conn.execute("SELECT * FROM players WHERE be_quan_active=1 AND be_quan_last_tick>0").fetchall()

    # ---------- Tower persistence ----------
    def get_ascension_tower_progress(self, user_id: str) -> sqlite3.Row | None:
        with self.lock:
            return self.conn.execute("SELECT * FROM ascension_tower_progress WHERE user_id=?", (str(user_id),)).fetchone()

    def upsert_ascension_tower_progress(self, user_id: str, *, best_floor: int, attempts: int, day_key: int, last_attempt: int) -> None:
        with self.lock, self.conn:
            self.conn.execute(
                "INSERT INTO ascension_tower_progress(user_id,best_floor,attempts,day_key,last_attempt) VALUES(?,?,?,?,?) "
                "ON CONFLICT(user_id) DO UPDATE SET best_floor=excluded.best_floor, attempts=excluded.attempts, day_key=excluded.day_key, last_attempt=excluded.last_attempt",
                (str(user_id), int(best_floor), int(attempts), int(day_key), int(last_attempt)),
            )

    def log_ascension_tower(self, user_id: str, floor: int, success: bool, reward: int, created_at: int) -> None:
        with self.lock, self.conn:
            self.conn.execute("INSERT INTO ascension_tower_logs(user_id,floor,success,reward,created_at) VALUES(?,?,?,?,?)", (str(user_id), int(floor), int(bool(success)), int(reward), int(created_at)))

    def ascension_tower_leaderboard(self, limit: int = 10) -> list[sqlite3.Row]:
        with self.lock:
            return self.conn.execute(
                "SELECT p.*, a.best_floor FROM ascension_tower_progress a JOIN players p ON p.user_id=a.user_id "
                "WHERE a.best_floor>0 ORDER BY a.best_floor DESC, p.realm_idx DESC, p.layer DESC, p.cultivation DESC LIMIT ?",
                (int(limit),),
            ).fetchall()

    def get_sect_tower_progress(self, sect_id: str) -> sqlite3.Row | None:
        with self.lock:
            return self.conn.execute("SELECT * FROM sect_tower_progress WHERE sect_id=?", (str(sect_id),)).fetchone()

    def upsert_sect_tower_progress(self, sect_id: str, *, best_floor: int, attempts: int, day_key: int, last_attempt: int) -> None:
        with self.lock, self.conn:
            self.conn.execute(
                "INSERT INTO sect_tower_progress(sect_id,best_floor,attempts,day_key,last_attempt) VALUES(?,?,?,?,?) "
                "ON CONFLICT(sect_id) DO UPDATE SET best_floor=excluded.best_floor, attempts=excluded.attempts, day_key=excluded.day_key, last_attempt=excluded.last_attempt",
                (str(sect_id), int(best_floor), int(attempts), int(day_key), int(last_attempt)),
            )

    def add_member_contribution(self, user_id: str, amount: int) -> None:
        with self.lock, self.conn:
            row = self.conn.execute("SELECT sect_id FROM sect_members WHERE user_id=?", (str(user_id),)).fetchone()
            if not row:
                raise ValueError("not_member")
            self.conn.execute("UPDATE sect_members SET contribution=contribution+? WHERE user_id=?", (int(amount), str(user_id)))
            self._apply_sect_exp_locked(str(row["sect_id"]), max(1, int(amount)//5))

    def log_sect_tower(self, sect_id: str, user_id: str, floor: int, success: bool, reward: int, created_at: int) -> None:
        with self.lock, self.conn:
            self.conn.execute("INSERT INTO sect_tower_logs(sect_id,user_id,floor,success,reward,created_at) VALUES(?,?,?,?,?,?)", (str(sect_id), str(user_id), int(floor), int(bool(success)), int(reward), int(created_at)))

    def sect_tower_leaderboard(self, limit: int = 10) -> list[sqlite3.Row]:
        with self.lock:
            return self.conn.execute(
                "SELECT s.id,s.name,s.level,s.owner_id,st.best_floor FROM sect_tower_progress st JOIN sects s ON s.id=st.sect_id "
                "WHERE st.best_floor>0 ORDER BY st.best_floor DESC, s.level DESC, s.exp DESC, s.name ASC LIMIT ?",
                (int(limit),),
            ).fetchall()

    # ---------- Admin ----------
    def is_admin_user(self, user_id: str) -> bool:
        with self.lock:
            return self.conn.execute("SELECT 1 FROM admin_users WHERE user_id=?", (str(user_id),)).fetchone() is not None

    def add_admin_user(self, user_id: str, added_by: str) -> None:
        with self.lock, self.conn:
            self.conn.execute("INSERT OR REPLACE INTO admin_users(user_id, added_by, added_at) VALUES(?,?,?)", (str(user_id), str(added_by), int(time.time())))

    def remove_admin_user(self, user_id: str) -> None:
        with self.lock, self.conn:
            self.conn.execute("DELETE FROM admin_users WHERE user_id=?", (str(user_id),))

    def list_admin_users(self) -> list[str]:
        with self.lock:
            rows = self.conn.execute("SELECT user_id FROM admin_users ORDER BY added_at ASC").fetchall()
        return [str(r["user_id"]) for r in rows]

    def add_admin_audit(self, actor_id: str, action: str, target_id: str | None = None, details: str = "") -> None:
        with self.lock, self.conn:
            self.conn.execute("INSERT INTO admin_audit(actor_id, action, target_id, details, created_at) VALUES(?,?,?,?,?)", (str(actor_id), action, None if target_id is None else str(target_id), details[:1000], int(time.time())))

    def get_admin_audit(self, limit: int = 20) -> list[sqlite3.Row]:
        with self.lock:
            return self.conn.execute("SELECT * FROM admin_audit ORDER BY id DESC LIMIT ?", (int(limit),)).fetchall()

    def set_admin_session(self, user_id: str, expires_at: float) -> None:
        with self.lock, self.conn:
            self.conn.execute(
                "INSERT INTO admin_sessions(user_id, expires_at) VALUES(?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET expires_at=excluded.expires_at",
                (str(user_id), float(expires_at)),
            )

    def get_admin_session_expiry(self, user_id: str) -> float:
        with self.lock:
            row = self.conn.execute(
                "SELECT expires_at FROM admin_sessions WHERE user_id=?", (str(user_id),)
            ).fetchone()
            return float(row["expires_at"]) if row else 0.0

    def clear_admin_session(self, user_id: str) -> None:
        with self.lock, self.conn:
            self.conn.execute("DELETE FROM admin_sessions WHERE user_id=?", (str(user_id),))

    def purge_expired_admin_sessions(self, now: float | None = None) -> int:
        now = time.time() if now is None else float(now)
        with self.lock, self.conn:
            cur = self.conn.execute("DELETE FROM admin_sessions WHERE expires_at <= ?", (now,))
            return int(cur.rowcount or 0)

    def transfer_spirit_stones(self, sender_id: str, target_id: str, amount: int) -> tuple[Player, Player]:
        sender_id = str(sender_id)
        target_id = str(target_id)
        amount = int(amount)
        if sender_id == target_id:
            raise ValueError("self_transfer")
        if amount <= 0:
            raise ValueError("invalid_amount")
        now = int(time.time())
        with self.lock:
            self.conn.execute("BEGIN IMMEDIATE")
            try:
                sender = self.conn.execute("SELECT * FROM players WHERE user_id=?", (sender_id,)).fetchone()
                target = self.conn.execute("SELECT * FROM players WHERE user_id=?", (target_id,)).fetchone()
                if not sender:
                    raise ValueError("sender_not_found")
                if not target:
                    raise ValueError("target_not_found")
                if int(sender["spirit_stones"]) < amount:
                    raise ValueError("not_enough_stones")
                self.conn.execute(
                    "UPDATE players SET spirit_stones=spirit_stones-?, updated_at=? WHERE user_id=?",
                    (amount, now, sender_id),
                )
                self.conn.execute(
                    "UPDATE players SET spirit_stones=spirit_stones+?, updated_at=? WHERE user_id=?",
                    (amount, now, target_id),
                )
                sender_after = self.conn.execute("SELECT * FROM players WHERE user_id=?", (sender_id,)).fetchone()
                target_after = self.conn.execute("SELECT * FROM players WHERE user_id=?", (target_id,)).fetchone()
                self.conn.commit()
                return Player.from_row(sender_after), Player.from_row(target_after)
            except Exception:
                self.conn.rollback()
                raise

    def create_market_listing(self, seller_id: str, item_id: str, quantity: int, unit_price: int) -> int:
        seller_id = str(seller_id)
        quantity = int(quantity)
        unit_price = int(unit_price)
        now = int(time.time())
        with self.lock:
            self.conn.execute("BEGIN IMMEDIATE")
            try:
                row = self.conn.execute(
                    "SELECT count FROM inventory WHERE user_id=? AND item_id=?",
                    (seller_id, item_id),
                ).fetchone()
                if not row or int(row["count"]) < quantity:
                    raise ValueError("not_enough_items")

                new_count = int(row["count"]) - quantity
                if new_count:
                    self.conn.execute(
                        "UPDATE inventory SET count=? WHERE user_id=? AND item_id=?",
                        (new_count, seller_id, item_id),
                    )
                else:
                    self.conn.execute(
                        "DELETE FROM inventory WHERE user_id=? AND item_id=?",
                        (seller_id, item_id),
                    )

                cur = self.conn.execute(
                    """
                    INSERT INTO market_listings(seller_id, item_id, quantity, unit_price, created_at)
                    VALUES(?, ?, ?, ?, ?)
                    """,
                    (seller_id, item_id, quantity, unit_price, now),
                )
                self.conn.commit()
                return int(cur.lastrowid)
            except Exception:
                self.conn.rollback()
                raise

    def get_market_listings(self, *, item_id: str | None = None, limit: int = 12) -> list[sqlite3.Row]:
        with self.lock:
            if item_id:
                return self.conn.execute(
                    """
                    SELECT m.*, p.display_name AS seller_name
                    FROM market_listings m
                    JOIN players p ON p.user_id = m.seller_id
                    WHERE m.item_id = ?
                    ORDER BY m.unit_price ASC, m.created_at ASC
                    LIMIT ?
                    """,
                    (item_id, int(limit)),
                ).fetchall()
            return self.conn.execute(
                """
                SELECT m.*, p.display_name AS seller_name
                FROM market_listings m
                JOIN players p ON p.user_id = m.seller_id
                ORDER BY m.created_at DESC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()

    def cancel_market_listing(self, seller_id: str, listing_id: int) -> sqlite3.Row | None:
        seller_id = str(seller_id)
        with self.lock:
            self.conn.execute("BEGIN IMMEDIATE")
            try:
                listing = self.conn.execute(
                    "SELECT * FROM market_listings WHERE id=? AND seller_id=?",
                    (int(listing_id), seller_id),
                ).fetchone()
                if not listing:
                    self.conn.rollback()
                    return None
                self.conn.execute("DELETE FROM market_listings WHERE id=?", (int(listing_id),))
                self.conn.execute(
                    """
                    INSERT INTO inventory(user_id, item_id, count) VALUES(?, ?, ?)
                    ON CONFLICT(user_id, item_id) DO UPDATE SET count = count + excluded.count
                    """,
                    (seller_id, listing["item_id"], listing["quantity"]),
                )
                self.conn.commit()
                return listing
            except Exception:
                self.conn.rollback()
                raise

    def buy_market_listing(self, buyer_id: str, listing_id: int) -> sqlite3.Row:
        buyer_id = str(buyer_id)
        with self.lock:
            self.conn.execute("BEGIN IMMEDIATE")
            try:
                listing = self.conn.execute(
                    "SELECT * FROM market_listings WHERE id=?",
                    (int(listing_id),),
                ).fetchone()
                if not listing:
                    raise ValueError("listing_not_found")
                if listing["seller_id"] == buyer_id:
                    raise ValueError("self_purchase")

                buyer = self.conn.execute(
                    "SELECT spirit_stones FROM players WHERE user_id=?",
                    (buyer_id,),
                ).fetchone()
                if not buyer:
                    raise ValueError("buyer_not_found")

                total = int(listing["quantity"]) * int(listing["unit_price"])
                if int(buyer["spirit_stones"]) < total:
                    raise ValueError("not_enough_stones")
                # Phase 6 money sink: seller receives floor(total * 0.98); remainder burned.
                seller_gain = int(total * 0.98)
                tax = total - seller_gain

                self.conn.execute(
                    "UPDATE players SET spirit_stones = spirit_stones - ?, updated_at=? WHERE user_id=?",
                    (total, int(time.time()), buyer_id),
                )
                self.conn.execute(
                    "UPDATE players SET spirit_stones = spirit_stones + ?, updated_at=? WHERE user_id=?",
                    (seller_gain, int(time.time()), listing["seller_id"]),
                )
                self.conn.execute("DELETE FROM market_listings WHERE id=?", (int(listing_id),))
                self.conn.execute(
                    """
                    INSERT INTO inventory(user_id, item_id, count) VALUES(?, ?, ?)
                    ON CONFLICT(user_id, item_id) DO UPDATE SET count = count + excluded.count
                    """,
                    (buyer_id, listing["item_id"], listing["quantity"]),
                )
                self.conn.commit()
                return listing
            except Exception:
                self.conn.rollback()
                raise

    def seed_redeem_codes(self, codes: dict[str, dict]) -> None:
        now = int(time.time())
        with self.lock, self.conn:
            for code, data in codes.items():
                self.conn.execute(
                    """
                    INSERT INTO redeem_codes(code, max_uses, used_count, created_at, expires_at, active)
                    VALUES(?, ?, 0, ?, ?, 1)
                    ON CONFLICT(code) DO UPDATE SET max_uses=excluded.max_uses
                    """,
                    (code, int(data.get("max_uses", 0)), now, int(data.get("expires_at", 0))),
                )

    def redeem_code(self, user_id: str, code: str, rewards: dict) -> dict:
        user_id = str(user_id)
        code = code.strip().lower()
        now = int(time.time())
        with self.lock:
            self.conn.execute("BEGIN IMMEDIATE")
            try:
                row = self.conn.execute("SELECT * FROM redeem_codes WHERE code=?", (code,)).fetchone()
                if not row:
                    raise ValueError("invalid_code")
                if not int(row["active"]):
                    raise ValueError("inactive_code")
                if int(row["expires_at"]) and now >= int(row["expires_at"]):
                    raise ValueError("expired_code")
                if int(row["max_uses"]) and int(row["used_count"]) >= int(row["max_uses"]):
                    raise ValueError("code_exhausted")
                exists = self.conn.execute(
                    "SELECT 1 FROM code_redemptions WHERE code=? AND user_id=?", (code, user_id)
                ).fetchone()
                if exists:
                    raise ValueError("already_redeemed")

                stones = int(rewards.get("spirit_stones", 0))
                if stones:
                    self.conn.execute(
                        "UPDATE players SET spirit_stones=spirit_stones+?, updated_at=? WHERE user_id=?",
                        (stones, now, user_id),
                    )
                for item_id, quantity in rewards.get("items", {}).items():
                    quantity = int(quantity)
                    if quantity <= 0:
                        continue
                    self.conn.execute(
                        """INSERT INTO inventory(user_id,item_id,count) VALUES(?,?,?)
                           ON CONFLICT(user_id,item_id) DO UPDATE SET count=count+excluded.count""",
                        (user_id, item_id, quantity),
                    )
                self.conn.execute(
                    "INSERT INTO code_redemptions(code,user_id,redeemed_at) VALUES(?,?,?)",
                    (code, user_id, now),
                )
                self.conn.execute(
                    "UPDATE redeem_codes SET used_count=used_count+1 WHERE code=?", (code,)
                )
                self.conn.commit()
                return {"spirit_stones": stones, "items": dict(rewards.get("items", {}))}
            except Exception:
                self.conn.rollback()
                raise


    def get_technique_mastery(self, user_id: str, technique_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM technique_mastery WHERE user_id = ? AND technique_id = ?",
            (str(user_id), technique_id),
        ).fetchone()
        return dict(row) if row else None

    def upsert_technique_mastery(self, user_id: str, technique_id: str, mastery: int, stage: str) -> None:
        now = int(__import__("time").time())
        self.conn.execute(
            """
            INSERT INTO technique_mastery (user_id, technique_id, mastery, stage, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, technique_id) DO UPDATE SET
                mastery = excluded.mastery,
                stage = excluded.stage,
                updated_at = excluded.updated_at
            """,
            (str(user_id), technique_id, int(mastery), stage, now),
        )

    def close(self) -> None:
        with self.lock:
            self.conn.close()
