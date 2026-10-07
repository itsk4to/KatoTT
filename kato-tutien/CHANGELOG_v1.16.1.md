# Kato Tu Tiên v1.16.1

## Bugfix
- Fix Thiên Kiếp có thể bị farm lặp ở cùng cảnh giới.
- `.dotpha` không thể bỏ qua cửa Thiên Kiếp tại Độ Kiếp tầng 3.
- Vượt Thiên Kiếp thành công sẽ tiến sang **Chân Tiên tầng 1** và reset tu vi về 0.
- Save cũ ở Độ Kiếp vẫn có thể tu luyện bình thường đến đúng ngưỡng ứng kiếp.
- Khóa theo Tông Môn khi leo Tháp Tông Môn để tránh hai môn nhân đồng thời xử lý cùng một tầng.
- `public_profile()` không còn trả trường `power`; combat rating nội bộ vẫn được giữ cho PvE/PvP.

## 🗼 Thí Luyện Tháp Ngoại Môn
- `.thap` / `.leothap` mở chế độ **Leo Tháp cá nhân**, không cần thuộc Tông Môn.
- Tầng tăng tuần tự theo `best_floor + 1`, đúng nghĩa leo tháp.
- 5 lượt/ngày, có GUI **Leo 1 tầng / Trạng thái / BXH**.
- Phần thưởng chỉ gồm **Linh Thạch + tu vi**; không cấp buff chỉ số hoặc tăng Đạo vĩnh viễn.
- Tỷ lệ và phần thưởng đã hạ/cân lại để Tháp là hoạt động progression, không phải máy farm buff.
- Thương thế chỉ tăng nhẹ khi thất bại.

## Kiểm thử
- Thêm regression test cho Thiên Kiếp, public profile, Leo Tháp ngoài và daily limit.
- Compile toàn bộ Python: PASS.
- Toàn bộ test suite: PASS.
