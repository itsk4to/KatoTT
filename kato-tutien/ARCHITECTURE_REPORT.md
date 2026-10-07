# Architecture Report — Kato Tu Tiên v2.0.0

## Stack
Discord (bot.py) → GameEngine → Database (SQLite WAL) → content.py

## Character / stats
- Storage: realm_idx, layer, cultivation, foundation stats, dao_*, loadout JSON, equipped (compat).
- `stat_contributions()` → `battle_stats()` (hp/atk/def/crit + speed/accuracy/evasion/resists/spirit/stamina/mental_state).

## Equipment
- Slots: weapon, artifact, armor, accessory via `loadout`.
- Stats sum all equipped pieces; `equipped` mirrors primary piece.

## Exploration
- EXPLORE_ZONES data-driven; min_realm gate; staged higher zones enabled=False.
- WORLD_REGIONS maps Phàm Giới / Ma Vực.

## Combat / status
- Unified `calculate_damage` (optional accuracy/evasion/status_on_hit).
- Encounter carries `player_statuses` / `enemy_statuses`.
- `tick_statuses`: DoT damage, stun skip, slow speed_factor, shield factor.
- PvP duel uses same accuracy/evasion and light status container.

## Technique mastery
- Table technique_mastery; stages Nhập môn→Viên mãn (thresholds 1/4/8/12).
- Gain on learn + combat victory; combat multiplier ≤ +12%.

## Sect / market / towers
- Sect roles, treasury, missions, towers unchanged in structure.
- Market buy: seller_gain = int(total * 0.98), atomic transaction.
- Towers + Thiên Kiếp retained.

## Concurrency
- RLock on DB; per-player locks on competing engine ops; market/PvP settle atomic.
