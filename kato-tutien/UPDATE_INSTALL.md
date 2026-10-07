# v1.16.2 Complete Fix / Install

## Safe update
1. Back up `kato_tutien.db` before replacing source files.
2. Replace the project source with this v1.16.2 package.
3. Keep existing `DISCORD_TOKEN` and add/set `KATO_ADMIN_PASSWORD` as a strong Secret.
4. Do not copy an old/default admin password hash into the project.
5. Start the bot normally.
6. SQLite migrations are idempotent and preserve existing player/inventory/sect/market/relationship data.

## Important v1.16.2 fixes
- PvP challenge buttons are implemented and challenge timeouts close stale challenges.
- `.admin` / Thiên Đạo panel is available; startup fails closed if `KATO_ADMIN_PASSWORD` is missing.
- All cultivation sources use the same hard-cap path; no over-cap carry from Bế Quan, combat, towers, items or Song Tu.
- Song Tu grants cultivation to both partners, each capped independently.
- Sect mission progress is scoped to the current `sect_id`; leaving/joining a new sect cannot carry old progress.
- Sect EXP now levels the sect; Treasury can be spent on Linh Mạch upgrades.
- Role and contribution rank are displayed as separate concepts.
- Dao progression uses a shared progression helper and has combat/inheritance routes.
- Permanent stat consumables use diminishing returns and hard cap 100.
- Tower names/UI are separated into Thí Luyện Tháp · Cá Nhân, Đăng Thiên Lộ, and Tháp Tông Môn.
- NPC/system sects are visible in the sect browser.

## New / key commands
- `.bxh` — Tiên / Ma / Tông rankings.
- `.dao` — choose and inspect Dao progression.
- `.khampha` / `.khu <zone>` — exploration.
- `.thap` / `.leothap` — personal trial tower.
- `.thangthien` — Đăng Thiên Lộ.
- `.thaptong` — shared sect tower.
- `.thienkiep` — final Độ Kiếp tribulation.
- `.linhmach` — inspect sect Linh Mạch.
- `.admin` / `/thien-dao` / `.filedb` — Thiên Đạo admin tools.

## Validation
The release was checked with:
- `python -m compileall -q .`
- `pytest -q`

Current test suite: **92 passing**.
