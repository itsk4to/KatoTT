# Kato Tu Tiên v1.16.3 — UI & Command Guide

## UX rule
- Menu/Select: lựa chọn, điều hướng, duyệt dữ liệu.
- Button/emoji: hành động nhanh, xác nhận, leo tháp, chiến đấu, mua.
- Prefix command: thao tác có tham số hoặc đường tắt cho người chơi lâu năm.

## Main entry
- `.menu`, `.mm`, `.trangchu` mở Đại Điện.

## Current GUI-first surfaces
- Tu Vi: `.tuvi`
- Khám phá: `.khampha`
- Tông Môn: `.tongmon`
- Túi: `.tui`, `.kho`
- Chợ: `.cho`
- Đạo: `.dao`
- BXH: `.bxh`, `.top`
- Đạo Lữ: `.daolu`
- Thí Luyện Tháp: `.thap`, `.leothap`
- Đăng Thiên Lộ: `.thangthien`
- Tháp Tông Môn: `.thaptong`
- Thiên Kiếp: `.thienkiep`

## Command authoring
Tạo command mới bằng cách:
1. Viết `async def command_xxx(...)`.
2. Thêm đúng một `CommandSpec(...)` vào `COMMAND_SPECS`.
3. Chọn `takes_args=True` nếu handler nhận `args`.
4. Có thể thêm aliases ngay trong cùng record.
5. Không sửa một dispatch map thứ hai.

`COMMAND_LOOKUP` được tạo tự động từ registry.
