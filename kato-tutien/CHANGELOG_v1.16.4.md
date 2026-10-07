# Kato Tu Tiên v1.16.4 — PvP Duel Update

- Nâng cấp PvP từ lời thách đấu + quyết toán thành duel có preview chỉ số và diễn biến từng hiệp.
- Thêm `engine.pvp_preview()` để xem HP/Công/Thủ và xác suất cân bằng trước khi chấp nhận.
- PvP dùng chung `battle_stats()` và `calculate_damage()` với combat, không cộng buff vĩnh viễn khi đấu.
- Kết quả PvP hiển thị tối đa 8 hiệp gần nhất, có bạo kích và sát thương.
- Giữ cược Linh Thạch/vật phẩm, timeout 10 phút và chống double-settlement hiện tại.
- Thêm test preview không làm thay đổi dữ liệu nhân vật.
