# Kato Tu Tiên v1.15.0 — Complete Tu Chân Update

## Core progression
- Tu vi requirement now grows non-linearly with realm/layer.
- Reaching the current cultivation cap forces breakthrough before further cultivation.
- Consumable use is capped and supports batch usage: `.dung <item> <so_luong>`.
- Added Căn Cơ (foundation quality) as a progression attribute.
- Public UI/leaderboards no longer use the old Lực Chiến number as progression.
- Internal combat rating remains private for PvE/PvP calculations.
- Tiên Đạo and Ma Đạo have separate leaderboards.

## Đạo
- Added Kiếm Đạo, Đao Đạo, Pháp Đạo, Thể Đạo.
- Progression: Khí → Ý → Thế → Tâm.
- Dao progression affects combat expression without becoming a public power score.
- Weapon affinity can advance the relevant Dao progression.

## Exploration
- Added selectable exploration zones: Hoang Nguyên, Yêu Thú Sơn Mạch, Cổ Động Phủ, Vạn Lý Hải Vực, Cửu U Ma Vực.
- Added inheritance/cơ duyên events.
- Existing encounters remain backward compatible.

## Thí Luyện Tháp
- Daily limited attempts.
- Best floor is stored per player.
- Tower rewards and leaderboard are independent of public combat power.

## Tông Môn
- `.tongmon` now opens the normal discovery/join GUI for non-members.
- Existing members enter the dedicated **Nội Vụ Tông Môn** GUI.
- Added top contribution, member list, missions, role management, sect leaderboard, leave, dissolve.
- Added roles: Đệ Tử, Hộ Pháp, Trưởng Lão, Phó Tông Chủ, Tông Chủ.
- Added Tông Khố, sect level/EXP and mission progress tables.

## Chợ
- Existing Tiên Phường remains available.
- `.cho` now opens a dedicated market GUI with listing selection, purchase and refresh controls.
- Existing `.dangban`, `.muacho`, `.huyban` commands remain available.

## Thiên Kiếp
- Added a safe `.thienkiep` foundation for late-realm tribulation.
- Phase is not used as a hard lock on normal cultivation before the required realms.

## Compatibility
- Player migrations are idempotent.
- Existing inventory, stones, sect, market and progression data are preserved.
- Existing `public_profile['power']` remains available internally for backward compatibility, but it is no longer shown in public UI.

## Validation
- Python source compile check: PASS.
- Existing + v1.15 tests: **70 passed**.
