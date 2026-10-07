# Kato Tu Tiên v2.0.1 — Revision 2 Review

## Validation
- `pytest -q`: **130 passed**
- `python -m compileall -q .`: OK
- No duplicate methods found in production classes `GameEngine` / `Database`.
- Command registry contains `.tutien`, `.tamuontutien`, `.tao` mapped to `command_create`.
- Market tax remains 2% implicit burn (`seller_gain = floor(total * 0.98)`).
- Technique mastery remains capped at +12% and is tied to the selected technique.

## Runtime issues found and fixed
1. `EncounterView.on_timeout()` could raise `AttributeError: 'EncounterView' object has no attribute 'message'`. The same unsafe access existed in combat skill/item update paths. Message access is now guarded with `getattr(..., None)`.
2. Player-side combat statuses were processed for normal attacks but could be skipped when using a skill or combat item. This meant `stun` could fail to stop a skill and DoT duration/damage could be skipped on those actions. Skill/item turns now process player statuses at the start of the action.

## Regression coverage
- Added a test proving a stunned player cannot cast a skill and the stun is consumed.
- Added a test proving poison ticks during a combat-item turn.
