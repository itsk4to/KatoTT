# Kato Tu Tiên v1.16.2 — Comprehensive Gameplay/UI/Security Fix

## Fixed
- PvP challenge UI (`PvpChallengeView`) with accept/decline/timeout flow.
- `.admin` Thiên Đạo panel and fail-closed `KATO_ADMIN_PASSWORD`.
- Cultivation cap bypasses from Bế Quan, combat, towers, consumables and Song Tu.
- Song Tu now grants cultivation to both partners through the same cap-safe path.
- Sect mission progress is scoped by `sect_id`; switching sects cannot carry progress.
- Sect level/EXP progression and Linh Mạch treasury spending are now functional.
- Tông Môn role and contribution rank are displayed separately.
- Dao equipment progression uses the same central Dao insight helper.
- Permanent stat items use diminishing returns and hard cap 100.
- Tower naming/UI clarified to distinguish personal trial, ascension route and sect tower.
- Public profile remains free of the deprecated public `power` field.

## Security
- No packaged/default admin password fallback.
- Startup requires `KATO_ADMIN_PASSWORD`.

## Compatibility
- Existing SQLite saves are migrated idempotently.
- Existing player progress, inventory, sect membership, market and relationship data are preserved.
