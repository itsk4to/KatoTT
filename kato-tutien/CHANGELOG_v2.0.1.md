# Kato Tu Tiên v2.0.1

## Bugfix
- Khôi phục command registry cho `.tutien`.
- Thêm aliases `.tamuontutien` và `.tao` để luồng Khai Đạo trong README/UI hoạt động đúng.
- Giữ nguyên handler `command_create` và GUI chọn con đường tu hành.
- Thêm regression test để ngăn lỗi command registry này tái diễn.

## Revision 2 review fixes
- Guarded `EncounterView` message access with `getattr(...)` so view timeout callbacks cannot raise `AttributeError` when no bound message is present.
- Combat skills and combat items now process player-side DoT/control/slow statuses at the start of the action, matching normal attacks.
