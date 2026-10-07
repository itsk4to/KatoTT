# Kato Tu Tiên v1.16.0 — Large Exploration & Tower Update

## Tu Vi
- Added `.tuvi`: a two-button menu for viewing Tu Vi Tiên Đạo and Ma Đạo separately.
- `.info` no longer duplicates the Linh Thạch icon.
- Existing Tiên/Ma progression remains unchanged.

## Bế Quan — fixed
- Fixed the first-cycle fee being charged twice.
- The 50 Linh Thạch paid when entering Bế Quan now covers the first completed cycle.
- Fixed cycle timestamp advancement being doubled after processing.
- Status refreshes completed offline cycles before showing the next tick.
- Bế Quan continues to process persistent state after restart and stops cleanly when future cycles can no longer be paid.

## Khám Phá — region selection
- `.khampha` now opens a region-selection menu before rolling an encounter.
- v1.16.0 opens the first two regions:
  - 🌲 Hoang Nguyên
  - 🐉 Yêu Thú Sơn Mạch
- Each region has its own encounter/cơ duyên pool and reward flavor.
- Hoang Nguyên focuses on linh mạch, linh thảo, merchant encounters, ancient cave inheritances and epiphany.
- Yêu Thú Sơn Mạch focuses on monsters, bosses, beast caches and bloodline opportunities.
- Future regions remain data-driven and locked for later updates.
- `.khu` remains available for setting the selected exploration region.

## BXH Tiên / Ma
- `.bxh` is now a GUI menu with two separate buttons:
  - 🪽 Tiên Đạo
  - 😈 Ma Đạo
- Selecting one button shows only that path's ranking.
- A home button returns to the selection menu.

## Đăng Thăng Thiên
- Added `.thangthien` for persistent personal tower progression.
- Best floor is stored in SQLite.
- 3 attempts per day.
- Next floor is based on the player's highest cleared floor.
- Rewards include Linh Thạch, tu vi and milestone item drops.
- Added tower leaderboard data.

## Tháp Tông Môn
- Added `.thaptong` / `.thaptongmon`.
- Progress is shared by the Tông Môn rather than an individual player.
- 2 attempts per day per Tông Môn.
- Successful clears reward the Tông Khố and the participating player.
- Best floor and logs are persistent.
- Added Tông Môn tower leaderboard data.

## Database migration
- Added `be_quan_prepaid` to persist the first-cycle reservation state.
- Added personal tower progress/log tables.
- Added Tông Môn tower progress/log tables.
- Existing player, inventory, market, sect and progression data is preserved.
- Migrations are idempotent.

## Validation
- Python compile checks: PASS.
- Test suite: **73 passed, 0 failed**.
