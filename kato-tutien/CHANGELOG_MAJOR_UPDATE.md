# Kato Tu Tiên v2.0.0 — Major Update

## Phase 0 — Safety
- Baseline 99 tests green on v1.16.4.
- Original backup retained.

## Phase 1 — Character Core
- Minor realms: Sơ/Trung/Hậu/Viên mãn (display only).
- `stat_contributions()` + `battle_stats()` (legacy totals preserved).
- Derived spirit/stamina/speed/accuracy/evasion/resists + mental state.
- Breakthrough modifiers (foundation, Dao, mental). Clamp 12–92.
- `technique_mastery` table on learn.

## Phase 2 — Items / Equipment
- Multi-slot loadout: weapon / artifact / armor / accessory (`loadout` JSON).
- `equipped` kept for backward compatibility (primary piece).
- New armor/accessory items in content.
- Stats sum all equipped pieces.

## Phase 3 — World / Exploration
- Zone data for Cổ Động Phủ, Hải Vực, Ma Vực (staged `enabled=False` until content pass).
- Realm gates on `set_explore_zone` / `explore` unchanged.
- Fortune continues to influence events via existing luck/fate.

## Phase 4 — Combat
- Unified `calculate_damage` extended with optional accuracy/evasion and status_on_hit.
- `STATUS_EFFECTS` table (burn, poison, stun, slow, shield, bleed).
- PvE/PvP still share core formula; legacy callers remain always-hit.

## Phase 5 — Sect
- Existing roles, treasury, missions, tower preserved (no destructive rewrite).

## Phase 6 — Economy
- Market 2% tax sink (buyer pays full, seller receives 98%).
- Transfer remains 1:1 and atomic.

## Phase 7 — Endgame
- Existing Đăng Thiên Lộ / Thí Luyện Tháp / Thiên Kiếp retained.
- Breakthrough/mental state feed higher difficulty indirectly.

## Phase 8 — World expansion (architecture)
- `WORLD_REGIONS` maps Phàm Giới / Ma Vực to zone keys for future open.
- Zones remain data-driven; enable flag flips without schema change.

## Compatibility
- No player/market/sect data wipe.
- Commands and aliases preserved.

## Revision Pass (post-architect review)
- Real status combat pipeline (DoT/stun/slow/shield) + accuracy/evasion in PvE/PvP.
- Technique mastery progression through combat, hard cap 12.
- Market tax uses int(total*0.98).
- Removed duplicate explore/add_sect_treasury.
- Selected technique mastery is now isolated per skill; normal attacks no longer award random technique mastery.
- Accuracy/Evasion hit curve rebalanced with meaningful but stable miss rates.
- Added regression coverage for both behaviors.
- Tests: 127 passed.
