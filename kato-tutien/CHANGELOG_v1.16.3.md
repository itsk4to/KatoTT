# Kato Tu Tiên v1.16.3 — GUI-first UX + Command Registry

## UI/UX
- Added `.menu` / `.mm` / `.trangchu` Đại Điện navigation hub.
- Tu Vi now opens directly on the player's chosen path; quick buttons for Tu luyện, Đột phá, Bế quan and refresh.
- BXH now has Tiên Đạo, Ma Đạo and Tông Môn tabs.
- `.dao` now opens a Select-based Con Đường Đạo menu; command arguments remain supported as a fast path.
- `.tui` / `.kho` now opens a category + item selection inventory with Dùng x1/x5/x10/custom, Trang bị/Học and refresh actions.
- `.daolu` now opens a dashboard with Song Tu, Tặng Đạo, Hủy Duyên and navigation actions.
- `.thangthien` now opens a dedicated Ascension Route panel.
- `.thaptong` now opens a dedicated Sect Tower panel with climb/BXH/home actions.
- `.thienkiep` now uses an explicit confirmation screen before the irreversible roll.

## Command authoring
- Added a `CommandSpec` registry as the single source of truth for command names, aliases, usage, descriptions and handlers.
- New commands/aliases can be added by defining one `CommandSpec`; no second dispatcher map is required.
- Existing quick commands remain available for experienced players.

## Compatibility
- Existing prefix commands remain backward compatible.
- Existing engine/database systems are unchanged by the UI refactor.
- 92 existing tests continue to pass; additional static checks cover the new command registry and UI classes.
