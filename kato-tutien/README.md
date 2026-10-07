# Kato Tu Tiên v2.0.0

Discord cultivation MMORPG bot (Python + SQLite).

# Kato Tu Tiên v1.16.2

> Complete Tu Chân Update — tu vi, căn cơ, Tiên/Ma, Đạo, khám phá, Thí Luyện Tháp, Tông Môn Nội Vụ và Chợ GUI.

## v1.16.2 highlights

- **Tu vi:** ngưỡng tăng dần theo cảnh giới/tầng; đầy tu vi phải đột phá.
- **Căn Cơ:** phẩm chất nền tảng ảnh hưởng progression và độ ổn định.
- **Tiên/Ma:** BXH tách riêng, không còn dùng Lực Chiến làm chỉ số công khai.
- **Đạo:** Kiếm/Đao/Pháp/Thể với Khí → Ý → Thế → Tâm.
- **Khám phá:** nhiều khu vực, yêu thú, động phủ và cơ duyên.
- **Thí Luyện Tháp Ngoại Môn:** `.thap` / `.leothap`, leo tầng tuần tự, 5 lượt/ngày, GUI trạng thái/BXH; không cấp buff chỉ số vĩnh viễn.
- **Tông Môn:** thành viên vào thẳng Nội Vụ; top cống hiến, môn nhân, trao chức, nhiệm vụ, Tông Khố, BXH, rời/giải tán.
- **Chợ:** GUI chọn gian hàng và mua trực tiếp.
- **Vật phẩm:** `.dung <item> [so_luong]`, tối đa 100 mỗi lần.
- **Thiên Kiếp:** chỉ mở tại Độ Kiếp tầng 3 khi đủ tu vi; vượt kiếp mới tiến Chân Tiên, không thể farm lặp.

Xem `CHANGELOG_v1.16.1.md` và `CHANGELOG_v1.16.0.md` để biết chi tiết bugfix, migration và gameplay.

---

# Kato Tu Tiên v1.16.0

Discord cultivation RPG dùng prefix `.`. Core game chạy bằng Python + SQLite và không cần AI key. Bản cập nhật hiện tại: **v1.16.2 — Comprehensive Gameplay/UI Fix**.

## Chạy trên Replit

1. Tạo Python Repl/project.
2. Upload toàn bộ project.
3. Install:

```bash
python -m pip install -r requirements.txt
```

4. Thêm Secret `DISCORD_TOKEN`.
5. Đặt `KATO_OWNER_IDS` = Discord User ID của Owner; nhiều ID ngăn cách bằng dấu phẩy.
6. **Bắt buộc production:** đặt `KATO_ADMIN_PASSWORD` (mật khẩu Thiên Đạo). Bot sẽ từ chối khởi động nếu secret này thiếu.
7. Tùy chọn: `KATO_CUSTOM_EMOJI=0` để dùng emoji Unicode thay vì custom emoji server (tránh icon vỡ khi bot không cùng server có emoji).
8. Bật **Message Content Intent** trong Discord Developer Portal.
9. Run:

```bash
python bot.py
```

Database SQLite tự tạo thành `kato_tutien.db`.

`/thien-dao` dùng Modal/ephemeral để xác minh mật khẩu; không yêu cầu Owner/Admin/User ID. Phiên Admin chỉ lưu **RAM** (5 phút, mất khi restart). `.filedb` / `/filedb`: nếu đã có session thì xuất DB luôn; nếu chưa thì hỏi mật khẩu. Backup gửi **chỉ qua DM**.

## Gameplay

- Tạo nhân vật: Tiên đạo / Ma đạo.
- Random căn cốt, ngộ tính, khí vận, phúc duyên, tâm cảnh, mệnh cách, thiên phú.
- Tu luyện có cooldown **25 giây**; `.khampha` trước tiên mở menu chọn vùng. v1.16.0 mở **Hoang Nguyên** và **Yêu Thú Sơn Mạch**, mỗi vùng có pool cơ duyên riêng; gặp giao tranh vẫn mở 4 nút <:att:1556722389973213294> Tấn công, 🌀 Kỹ năng, <:vatpham:1556658044954214481> Túi đồ và 🏃 Rút lui.
- Combat dùng công thức damage thống nhất: damage nền theo ATK + multiplier, giảm sát thương bằng diminishing returns của DEF, có random variance và bạo kích; Boss và quái vật scale theo **chỉ số chiến đấu nội bộ**; chỉ số này không được hiển thị như một đơn vị Lực Chiến cho người chơi.
- Đạo Lữ: kết duyên, chấp nhận, tặng quà, song tu, hủy duyên.
- Thiên Đạo: `/thien-dao` xác minh bằng mật khẩu qua Modal; phiên 5 phút và audit log. `.filedb` cũng yêu cầu mật khẩu, tạo SQLite backup nhất quán và gửi riêng qua DM.
- Daily reward có streak để tạo nhịp chơi hằng ngày.
- Tiên Phường GUI phân mục dạng thanh cuộn: Pháp bảo, Bùa chú, Đan dược, Binh khí, Linh vật và Công pháp. Chọn vật phẩm để xem chi tiết rồi mua ×1/×5.
- Hồ sơ công khai: `.xem @nguoi` để xem cảnh giới, căn cơ, Đạo và hành trang; **không hiển thị Lực Chiến**.
- Chợ đạo hữu: đăng bán, xem chợ, mua và hủy gian hàng. `.chuyen @người <số_linh_thạch>` chuyển Linh Thạch an toàn giữa người chơi.
- `.tuvi` mở menu xem Tu Vi Tiên Đạo / Ma Đạo; `.bxh` mở menu chọn BXH Tiên / Ma / Tông. Đột Phá dùng **một message + 2 nút emoji Đồng ý/Từ chối**, chỉ người gọi được bấm và timeout tự khóa.
- SQLite bật WAL, foreign keys và busy timeout; các thao tác engine/database từ Discord chạy ngoài event loop, có khóa theo người chơi cho các thao tác cạnh tranh.

## Lệnh chính

```text
.tutien
.tamuontutien
.info
.xem @nguoi
.daily
.tuluyen
.dotpha
.khampha
.san
.shop
.mua tu_khi_dan 3
.tui
.dung tu_khi_dan
.trangbi thanh_phong_kiem
.thao
.cho
.dangban tu_khi_dan 3 120
.muacho 1
.huyban 1
.tuvi
.bxh
.thangthien
.thaptong
.chuyen @nguoi 5000
```

Prefix không phân biệt hoa thường: `.tuluyen`, `.TULUYEN` đều hoạt động.

## v1.16 content

- **Bế Quan:** sửa lỗi phí chu kỳ đầu bị tính hai lần và lỗi tăng thời gian chu kỳ gấp đôi. Trạng thái được lưu persistent.
- **Đăng Thiên Lộ:** thử thách cột mốc cá nhân, 3 lượt/ngày, lưu tầng cao nhất; không phải nguồn buff vĩnh viễn.
- **Thí Luyện Tháp Ngoại Môn:** leo từng tầng theo tiến độ cá nhân, 5 lượt/ngày, có GUI và BXH; không phụ thuộc Tông Môn.
- **Tháp Tông Môn:** leo tháp chung cho cả Tông, 2 lượt/ngày, lưu tầng cao nhất và thưởng vào Tông Khố.
- **Khám Phá:** vùng quyết định pool sự kiện/cơ duyên; hai vùng đầu tiên đã mở.

## Kiến trúc

`bot.py` chịu trách nhiệm Discord transport và command routing.

`game/content.py` chứa dữ liệu thế giới, item, mệnh cách và bảng nội dung.

`game/database.py` quản lý SQLite persistent state, migration nhỏ cho schema cũ và giao dịch chợ.

`game/engine.py` chứa gameplay logic, progression, economy, public profile và market.

`tests/test_engine.py` có test cho core progression, economy, daily và market.

## Điểm đã tối ưu

- Sửa duplicate key trong bảng combat power.
- Chặn lỗi vượt khỏi cảnh giới cuối gây `IndexError`.
- Cho phép schema cũ tự thêm `last_daily` và `daily_streak`.
- Luồng khai đạo dùng GUI thanh cuộn `.tutien` / `.tamuontutien`; `.tao` giữ alias cũ để tương thích.
- Thêm giao dịch market theo transaction để tránh mất item/tiền khi mua bán đồng thời. Thêm transfer Linh Thạch cũng dùng transaction nguyên tử.
- Tách hồ sơ công khai khỏi lệnh `.info` để dễ mở rộng UI xã hội.
- Chuẩn hóa lại thông báo lỗi và prefix trong engine.
- Xác minh Admin qua Modal/ephemeral, phiên 5 phút, giới hạn thử sai và audit log.
- Chuẩn hóa emoji custom cho Linh Thạch và các nút combat/Đột Phá.
- Public profile/leaderboard không còn expose trường `power`; combat rating nội bộ chỉ phục vụ PvE/PvP và không phải chỉ số progression.
- Khóa trạng thái Tháp Tông Môn theo `sect_id` để tránh race condition trong cùng Tông.
- Mọi nguồn tu vi (Bế Quan, combat, Song Tu, tháp, đan dược) đều qua `add_cultivation()` nên không thể vượt cap.
- Nhiệm vụ Tông Môn gắn với `sect_id`; đổi Tông không thể mang tiến độ cũ sang Tông mới.
- Cống hiến tự đưa Linh Thạch vào Tông Khố và tự tích EXP/Cấp Tông; Tông Chủ có thể nâng Linh Mạch tối đa cấp 5.
- Permanent stat consumables dùng diminishing returns ở mốc 70/90 để chống farm buff vô hạn.

## Kiểm thử

```bash
python -m pytest -q
```

Bản hiện tại gồm test cho core game, economy, redeem code, Tiên Phường và transfer Linh Thạch.


## v9
- Shop/Boss interaction hardening to avoid Discord interaction hangs.
- Tông Môn menu, gia nhập/rời tông, cống hiến, rank và buff tu luyện nhẹ.
- PvP đối chiến với cược Linh Thạch hoặc vật phẩm trong game.
- `.tu` là lệnh tu luyện chính; `.tuluyen` giữ làm bí danh tương thích.
- Bế Quan: 50 Linh Thạch / 5 phút, tự động tu luyện và có cơ hội thu thập vật phẩm; có thể tiếp tục xử lý qua restart nhờ dữ liệu SQLite.
- `.help` được viết lại theo nhóm chức năng.


## v14
- Combat GUI hardened: mọi interaction dài đều defer/acknowledge đúng cách; lỗi sau defer chỉnh vào response gốc thay vì để spinner treo.
- Damage engine thống nhất cho đánh thường, kỹ năng và phản kích; thêm bạo kích, variance và mitigation theo DEF.
- Yêu thú/Boss scale theo chỉ số chiến đấu nội bộ để tránh giao tranh quá dễ hoặc quá vô lý ở đầu/cuối game.
- Khóa trạng thái theo người chơi cho progression, item, gacha, PvP, giao dịch, Đạo Lữ và Tông Môn để giảm race-condition.
- Worker Bế Quan chạy ngoài Discord event loop; `.filedb` backup cũng chạy ngoài event loop.
- Dọn code combat chết sau `return`, loại bỏ các response Discord lặp sau `defer`, và giảm query DB thừa trong combat/Tông Môn.
- Bộ test core hiện tại: **48/48 PASS**.

## Known limitations / hardening notes

- Phiên Thiên Đạo (`/thien-dao`) **chỉ lưu trong RAM** (TTL 5 phút). Restart bot → toàn bộ session mất.
- Rate-limit thử sai mật khẩu (5 lần/60s) vẫn in-memory — reset khi process restart.
- Exception trong interaction/command được log đầy đủ (`logger.exception`) thay vì nuốt im.
- Custom emoji ID chỉ hiện đúng khi bot cùng server có emoji; set `KATO_CUSTOM_EMOJI=0` để fallback Unicode.
- Production **bắt buộc** đặt `KATO_ADMIN_PASSWORD`; bot từ chối khởi động nếu secret này thiếu.

## v14.1 polish

- Logging thay cho bare `except Exception`.
- (v14.1 tạm thời persist SQLite; v14.2+ đã chuyển lại RAM-only.)
- Emoji Unicode fallback (`KATO_CUSTOM_EMOJI`).
- Thêm yêu thú / Boss đa dạng hơn (scale theo chỉ số chiến đấu nội bộ, không hiển thị thành đơn vị Lực Chiến).
- `.gitignore`, `requirements-dev.txt`, `.env.example` cập nhật.

## v14.2 interaction & Thiên Đạo hardening

- Admin session chuyển về **RAM-only** (đúng yêu cầu restart = mất session).
- `/filedb` và `.filedb`: nếu đã có Admin Session thì **không hỏi lại mật khẩu**; chưa có thì Modal mật khẩu.
- FileDB luôn `defer()` trước backup; backup chạy `asyncio.to_thread`; gửi **chỉ qua DM**; xóa file tạm.
- Combat: item turn atomic (`combat_item_turn`), busy flag cho rút lui/skill/túi đồ, skill list chỉ skill đã học + hiện multiplier.
- Thêm test combat thắng/thua/rút lui/skill/item concurrent + SQLite backup.

## v1.14.4 interaction / combat safety

- PathChoice (khai đạo): `defer()` trước khi tạo nhân vật — không để interaction treo.
- AdminPasswordModal: `defer()` trước PBKDF2 verify.
- EncounterView không còn gọi SQLite trên event loop khi khởi tạo.
- Combat skill/item: claim `busy` **trước** `await defer` để chặn double-cast.
- Test mở rộng: admin session RAM TTL/restart, concurrent battle_step, skill learned/unlearned, password verify env override.
- Bộ test: **61/61 PASS**.


## v1.16.2 fixes

- PvP có GUI chấp nhận/từ chối và tự khóa lời đấu hết hạn.
- `.admin` có bảng Thiên Đạo; mật khẩu `KATO_ADMIN_PASSWORD` là bắt buộc, không còn mật khẩu mặc định đóng gói.
- Mọi nguồn tu vi đều đi qua `add_cultivation()` để không vượt trần: tu luyện, đan dược, bế quan, combat, tháp và song tu.
- Song tu cộng tu vi cho **cả hai** đạo lữ, mỗi bên vẫn chịu cap riêng.
- Nhiệm vụ Tông Môn gắn với `sect_id`, tránh đổi Tông để mang tiến độ sang Tông mới.
- Cấp Tông thực sự nhận EXP và level-up; Tông Khố được dùng để nâng Linh Mạch.
- Chức vụ Tông Môn và hạng cống hiến hiển thị tách biệt.
- Đạo tiến triển thống nhất qua helper chung; Kiếm/Đao/Pháp/Thể đều có đường lĩnh ngộ trong combat, truyền thừa hoặc build tương ứng.
- Ba loại Tháp được phân biệt: **Thí Luyện Tháp · Cá Nhân**, **Đăng Thiên Lộ**, **Tháp Tông Môn**.
- Các vật phẩm tăng chỉ số vĩnh viễn dùng diminishing returns + hard cap 100.


- Nhiệm vụ Tông Môn trao **cống hiến miễn phí**, không trừ lại Linh Thạch của phần thưởng nhiệm vụ.

## v1.16.4 — GUI-first UX

- `.menu` / `.mm` / `.trangchu`: Đại Điện điều hướng bằng nút/emoji.
- `.tuvi`: mở thẳng Tu Vi của con đường đã chọn; có nút Tu luyện / Đột phá / Bế quan / Làm mới.
- `.tui` / `.kho`: menu phân loại + chọn vật phẩm + Dùng ×1/×5/×10/Số khác + Trang bị/Học.
- `.dao`: menu Select chọn Kiếm/Đao/Pháp/Thể; lệnh `.dao <type>` vẫn là fast path.
- `.bxh`: tabs Tiên / Ma / Tông Môn.
- `.daolu`: dashboard Song Tu / Tặng Đạo / Hủy Duyên / Đại Điện.
- `.thangthien`, `.thaptong`, `.thienkiep`: menu + nút xác nhận/thao tác.

### Command Registry

Prefix commands được khai báo trong `bot.py` bằng `CommandSpec`. Mỗi lệnh chỉ cần một bản ghi gồm tên chính, aliases, nhóm, cú pháp, mô tả và handler. Dispatcher tự động tra registry; không cần sửa thêm một dictionary dispatch riêng.

Ví dụ:

```python
CommandSpec(
    "mycommand",
    ("mc",),
    "advanced",
    ".mycommand <arg>",
    "Mô tả lệnh.",
    "command_mycommand",
    True,
)
```

Các lệnh nhanh vẫn tồn tại để người chơi quen gõ, còn GUI là đường thao tác mặc định cho các hệ thống nhiều lựa chọn.
