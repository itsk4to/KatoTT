# Implementation Report — v2.0.0 Revision Pass

**Status:** IMPLEMENTATION COMPLETE — WAITING FOR REVIEW

## Fixes in this pass
1. **Combat status system** — `apply_status`, `tick_statuses`, `mitigate_with_shield` on encounter/duel containers; burn/poison/bleed DoT; stun skip; slow speed factor; shield mitigation; accuracy/evasion in PvE and PvP.
2. **Technique mastery progression** — `gain_technique_mastery` now advances the technique actually selected in `battle_skill`; combat uses that technique's own mastery multiplier, capped at +12%, while discovery-only legacy learns remain compatible.
3. **Market tax** — `seller_gain = int(total * 0.98)`; `tax = total - seller_gain`.
4. **Duplicate methods removed** — single `GameEngine.explore`, single `Database.add_sect_treasury`.
5. **Accuracy/Evasion balance** — removed the old 90% minimum hit floor; the new bounded hit curve keeps normal combat stable while making Evasion measurably affect miss rate.
6. **Docs** updated for actual v2.0.0 architecture.

## Files changed
- game/engine.py
- game/database.py
- game/content.py (STATUS_EFFECTS already present)
- tests/test_v200_revision.py (new)
- TEST_REPORT.md, IMPLEMENTATION_REPORT.md, MIGRATION.md, CHANGELOG_MAJOR_UPDATE.md, ARCHITECTURE_REPORT.md, README.md

## Compatibility
- No data wipe; loadout/equipped dual-write; technique discoveries remain valid.

## Known limitations
- Status application chance is modest (~8–18%); not every hit applies a status.
- Higher explore zones remain staged `enabled=False`.
- Sect diplomacy / faction war still not implemented.

## Final Balance / Integration Pass

- `battle_skill()` applies the selected technique's own mastery multiplier.
- Successful use of a selected technique grants +1 mastery to that same technique; normal attacks no longer grant random technique mastery.
- Accuracy/Evasion uses a bounded curve of 35%–97% and no longer floors normal hits at 90%.
- Added regression coverage proving higher Evasion increases miss rate and proving mastery isolation between two learned techniques.
- Final full test run: **127/127 PASS**.
