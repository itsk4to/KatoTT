from __future__ import annotations

import hmac
import logging
import os
import re
import time
import sqlite3
import tempfile
from dataclasses import dataclass

import asyncio
import discord
from discord import app_commands
from discord.ext import tasks

from game.database import Database
from game.engine import GameEngine, GameError, ITEMS
from game.content import REALMS, SHOP_CATEGORIES, TRIAL_TOWER

logger = logging.getLogger("kato")

TOKEN_ENV = "DISCORD_TOKEN"
DB_PATH = os.getenv("KATO_DB_PATH", "kato_tutien.db")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)
ADMIN_SESSION_TTL = 300
ADMIN_SESSIONS: dict[str, float] = {}  # RAM-only: wiped on process restart
ADMIN_FAILS: dict[str, list[float]] = {}  # rate-limit; also RAM-only

db = Database(DB_PATH)
engine = GameEngine(db)

COLOR_MAIN = 0x5865F2
COLOR_SUCCESS = 0x57F287
COLOR_INFO = 0x5DADE2
COLOR_WARN = 0xFEE75C
COLOR_ERROR = 0xED4245

def _icon(custom: str, fallback: str) -> str:
    """Prefer custom server emoji when enabled; always fall back to Unicode."""
    if os.getenv("KATO_CUSTOM_EMOJI", "1").strip() in {"0", "false", "False", "no", "off"}:
        return fallback
    return custom


# Custom Discord emojis (same server) with Unicode fallbacks for portability.
LINH_THACH_ICON = _icon("<:linhthach:1556648801471701053>", "💎")
DONG_Y_ICON = _icon("<:dongy:1556653535037366292>", "✅")
TU_CHOI_ICON = _icon("<:tuchoi:1556653578649731092>", "❌")
TAN_CONG_ICON = _icon("<:tancong:1556657986028568656>", "⚔️")
KI_NANG_ICON = _icon("<:kinang:1556658019188613150>", "🌀")
VAT_PHAM_ICON = _icon("<:vatpham:1556658044954214481>", "🎒")
BO_CHAY_ICON = _icon("<:bochay:1556658072850792528>", "🏃")

CONG_PHAP_ICON = _icon("<:congphap:1556722479492243538>", "📜")
BUA_CHU_ICON = _icon("<:buachu:1556722564502655076>", "🔮")
DAN_DUOC_ICON = _icon("<:danduoc:1556722510962106459>", "💊")
DEF_ICON = _icon("<:def:1556722328425992242>", "🛡️")
HP_ICON = _icon("<:hp:1556722270918152344>", "❤️")
ATT_ICON = _icon("<:att:1556722389973213294>", "🗡️")

CATEGORY_ICONS = {
    "all": VAT_PHAM_ICON,
    "Pháp bảo": VAT_PHAM_ICON,
    "Bùa chú": BUA_CHU_ICON,
    "Đan dược": DAN_DUOC_ICON,
    "Binh khí": ATT_ICON,
    "Linh vật": VAT_PHAM_ICON,
    "Công pháp": CONG_PHAP_ICON,
}


def category_icon(category: str) -> str:
    return CATEGORY_ICONS.get(category, VAT_PHAM_ICON)


def decorate_currency(text: str) -> str:
    """Add the Linh Thạch icon once, without duplicating an icon already in the UI."""
    pattern = re.compile(r"(?i)\blinh\s+thạch\b")
    def repl(match: re.Match) -> str:
        prefix = text[max(0, match.start() - len(LINH_THACH_ICON) - 1):match.start()]
        if prefix.endswith(LINH_THACH_ICON + " "):
            return match.group(0)
        return LINH_THACH_ICON + " " + match.group(0)
    return pattern.sub(repl, text)


def clean_ui_text(text: str) -> str:
    # Keep markdown readable while avoiding emoji noise in compact embeds.
    return re.sub(r"[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F]", "", text).strip()


def split_ui(text: str) -> tuple[str, str]:
    text = clean_ui_text(text)
    lines = [line.rstrip() for line in text.splitlines()]
    while lines and not lines[0].strip():
        lines.pop(0)
    title = lines[0].strip() if lines else "Kato Tu Tiên"
    if title.startswith("**") and title.endswith("**"):
        title = title[2:-2]
    return title[:256], "\n".join(lines[1:]).strip()[:4000]


def make_embed(text: str, *, color: int = COLOR_MAIN, footer: str = "Kato Tu Tiên") -> discord.Embed:
    text = decorate_currency(text)
    title, description = split_ui(text)
    embed = discord.Embed(title=title, description=description or "\u200b", color=color)
    embed.set_footer(text=footer)
    return embed


def make_plain_embed(title: str, description: str, *, color: int = COLOR_MAIN, footer: str = "Kato Tu Tiên") -> discord.Embed:
    embed = discord.Embed(title=title[:256], description=description[:4000] or "\u200b", color=color)
    embed.set_footer(text=footer)
    return embed


async def reply_ui(message: discord.Message, text: str, *, color: int = COLOR_MAIN) -> None:
    await message.reply(embed=make_embed(text, color=color), mention_author=False)


async def run_engine(func, /, *args, **kwargs):
    """Run synchronous engine/SQLite work off Discord's event loop."""
    return await asyncio.to_thread(func, *args, **kwargs)


def fmt(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def path_name(path: str) -> str:
    return "Tiên đạo" if path == "tien" else "Ma đạo"


def rarity_icon(rarity: str) -> str:
    return {"Phàm": "⚪", "Hoàng": "🟢", "Huyền": "🔵", "Địa": "🟣", "Thiên": "🟡", "Tiên": "🔴", "Thần": "🌈"}.get(rarity, "▫️")


def ui_section(title: str, icon: str = "") -> str:
    return f"{icon} **{title.upper()}**" if icon else f"**{title.upper()}**"


def ui_stat(label: str, value: object, icon: str = "") -> str:
    return f"{icon} **{label}:** `{value}`" if icon else f"**{label}:** `{value}`"


@dataclass(frozen=True)
class CommandSpec:
    name: str
    aliases: tuple[str, ...]
    category: str
    usage: str
    description: str
    handler: str
    takes_args: bool = False


# Single source of truth for prefix commands. Add a new CommandSpec to create a
# command + aliases without having to edit the dispatcher in a second place.
COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec("tutien", ("tamuontutien", "tao"), "start", ".tutien", "Khai đạo và tạo nhân vật tu luyện.", "command_create", True),
    CommandSpec("help", ("h",), "start", ".help", "Mở sổ tay giao diện và lệnh.", "command_help"),
    CommandSpec("menu", ("mm", "trangchu", "home"), "start", ".menu", "Mở Đại Điện điều hướng các hệ thống.", "command_menu"),
    CommandSpec("info", (), "start", ".info", "Xem nhân vật và chỉ số.", "command_info"),
    CommandSpec("xem", (), "start", ".xem [@người]", "Xem hồ sơ công khai.", "command_show", True),
    CommandSpec("tu", ("tuluyen",), "cultivation", ".tu", "Tu luyện một lượt.", "command_cultivate"),
    CommandSpec("tuvi", (), "cultivation", ".tuvi", "Mở đại điện Tu Vi.", "command_tuvi"),
    CommandSpec("dotpha", (), "cultivation", ".dotpha", "Mở nghi thức Đột Phá.", "command_breakthrough"),
    CommandSpec("bequan", (), "cultivation", ".bequan", "Mở Động Phủ Bế Quan.", "command_be_quan"),
    CommandSpec("xuatquan", (), "cultivation", ".xuatquan", "Xuất quan.", "command_xuat_quan"),
    CommandSpec("daily", (), "cultivation", ".daily", "Nhận thưởng hằng ngày.", "command_daily"),
    CommandSpec("khampha", ("phieuluu", "san"), "explore", ".khampha", "Mở Bản Đồ Khám Phá.", "command_explore", True),
    CommandSpec("khu", (), "explore", ".khu <mã>", "Chọn khu khám phá nhanh.", "command_explore_zone", True),
    CommandSpec("thap", ("leothap",), "explore", ".thap", "Mở Thí Luyện Tháp cá nhân.", "command_trial"),
    CommandSpec("thangthien", ("thangthiên",), "explore", ".thangthien", "Mở Đăng Thiên Lộ.", "command_thang_thien"),
    CommandSpec("thaptong", ("thaptongmon",), "sect", ".thaptong", "Mở Tháp Tông Môn.", "command_thap_tong"),
    CommandSpec("dao", (), "dao", ".dao", "Mở đại điện Con Đường Đạo.", "command_dao", True),
    CommandSpec("thienkiep", (), "cultivation", ".thienkiep", "Ứng Thiên Kiếp khi đủ điều kiện.", "command_tribulation"),
    CommandSpec("tongmon", ("tm",), "sect", ".tongmon", "Mở Đại Điện Tông Môn/Nội Vụ.", "command_sect"),
    CommandSpec("congtong", (), "sect", ".congtong <linh_thach>", "Đóng góp nhanh vào Tông Khố.", "command_sect_contribute", True),
    CommandSpec("linhmach", (), "sect", ".linhmach", "Xem nâng cấp Linh Mạch.", "command_linh_mach"),
    CommandSpec("nhiemvutong", ("nvtong_list",), "sect", ".nhiemvutong", "Mở nhiệm vụ Tông Môn.", "command_sect_missions"),
    CommandSpec("nvtong", (), "sect", ".nvtong <mã>", "Nhận thưởng nhiệm vụ.", "command_sect_mission_claim", True),
    CommandSpec("pvp", (), "combat", ".pvp @người ...", "Tạo lời thách đấu PvP.", "command_pvp", True),
    CommandSpec("tui", ("kho", "inventory"), "items", ".tui", "Mở Túi Càn Khôn.", "command_inventory"),
    CommandSpec("dung", ("use",), "items", ".dung <item> [sl]", "Dùng một hoặc nhiều vật phẩm.", "command_use", True),
    CommandSpec("hoc", ("learn",), "items", ".hoc <công_pháp>", "Học công pháp.", "command_learn", True),
    CommandSpec("trangbi", ("equip",), "items", ".trangbi <item>", "Trang bị pháp bảo/binh khí.", "command_equip", True),
    CommandSpec("thao", (), "items", ".thao", "Tháo trang bị.", "command_unequip"),
    CommandSpec("shop", (), "trade", ".shop", "Mở Tiên Phường.", "command_shop"),
    CommandSpec("mua", (), "trade", ".mua <item> [sl]", "Mua nhanh từ Tiên Phường.", "command_buy", True),
    CommandSpec("cho", (), "trade", ".cho [lọc]", "Mở Chợ Đạo Hữu.", "command_market", True),
    CommandSpec("dangban", (), "trade", ".dangban <item> <sl> <gia>", "Đăng bán nhanh.", "command_market_list", True),
    CommandSpec("huyban", (), "trade", ".huyban <id>", "Hủy tin bán.", "command_market_cancel", True),
    CommandSpec("muacho", (), "trade", ".muacho <id>", "Mua tin đăng nhanh.", "command_market_buy", True),
    CommandSpec("chuyen", (), "trade", ".chuyen @người <số>", "Chuyển Linh Thạch.", "command_transfer", True),
    CommandSpec("bxh", ("top",), "advanced", ".bxh", "Mở BXH Tiên/Ma/Tông Môn.", "command_leaderboard"),
    CommandSpec("thienco", ("gacha",), "advanced", ".thienco [sl]", "Mở Thiên Cơ Các.", "command_gacha", True),
    CommandSpec("code", ("redeem",), "advanced", ".code <mã>", "Nhập mã thưởng.", "command_code", True),
    CommandSpec("daolu", (), "social", ".daolu", "Mở bảng Đạo Lữ.", "command_daolu"),
    CommandSpec("ketduyen", (), "social", ".ketduyen @người", "Gửi lời kết duyên.", "command_request_daolu"),
    CommandSpec("chapnhan", (), "social", ".chapnhan", "Chấp nhận lời kết duyên đang chờ.", "command_accept_daolu"),
    CommandSpec("tuchoi", (), "social", ".tuchoi", "Từ chối lời kết duyên.", "command_reject_daolu"),
    CommandSpec("huyduyen", (), "social", ".huyduyen", "Hủy Đạo Duyên.", "command_break_daolu"),
    CommandSpec("songtu", (), "social", ".songtu", "Song Tu với Đạo Lữ.", "command_songtu"),
    CommandSpec("tangdao", (), "social", ".tangdao <item> [sl]", "Tặng vật phẩm cho Đạo Lữ.", "command_daolu_gift", True),
    CommandSpec("admin", (), "advanced", ".admin", "Mở Thiên Đạo quản trị.", "command_admin", True),
    CommandSpec("filedb", (), "advanced", ".filedb", "Xuất database qua DM.", "command_filedb"),
)
COMMAND_LOOKUP = {alias: spec for spec in COMMAND_SPECS for alias in (spec.name, *spec.aliases)}


def command_registry_lines(category: str | None = None) -> list[str]:
    rows = [s for s in COMMAND_SPECS if category is None or s.category == category]
    seen = set()
    lines = []
    for spec in rows:
        if spec.name in seen:
            continue
        seen.add(spec.name)
        alias = f" · `.{spec.aliases[0]}`" if spec.aliases else ""
        lines.append(f"`{spec.usage}`{alias} — {spec.description}")
    return lines


class MainMenuView(discord.ui.View):
    def __init__(self, owner_id: int):
        super().__init__(timeout=240)
        self.owner_id = owner_id

    async def guard(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Chỉ người mở Đại Điện mới điều khiển được menu này.", ephemeral=True)
            return False
        return True

    async def _edit(self, interaction: discord.Interaction, embed: discord.Embed, view: discord.ui.View | None = None):
        await interaction.response.edit_message(embed=embed, view=view or self)

    @discord.ui.button(label="Tu Luyện", emoji="🧘", style=discord.ButtonStyle.primary, row=0)
    async def cultivation(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.guard(interaction): return
        player = await run_engine(engine.info, str(self.owner_id))
        await self._edit(interaction, tuvi_embed(player), TuViView(self.owner_id))

    @discord.ui.button(label="Khám Phá", emoji="🗺️", style=discord.ButtonStyle.primary, row=0)
    async def explore(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.guard(interaction): return
        await self._edit(interaction, make_plain_embed("🗺️ KHÁM PHÁ", "Chọn khu vực để bắt đầu hành trình."), ExploreZoneView(self.owner_id))

    @discord.ui.button(label="Tông Môn", emoji="🏯", style=discord.ButtonStyle.primary, row=0)
    async def sect(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.guard(interaction): return
        dashboard = await run_engine(sect_dashboard, self.owner_id)
        if dashboard["member"]:
            o = await run_engine(engine.sect_overview, str(self.owner_id))
            m, sct = o["member"], o["sect"]
            text = f"🏯 **{sct['name']} — NỘI VỤ**\n\n👑 Chức vụ: **{m.get('role') or 'Đệ Tử'}**\n🏅 Hạng cống hiến: **{engine.sect_rank(int(m['contribution']))}**\n✨ Cống hiến: **{fmt(int(m['contribution']))}**\n👥 Môn nhân: **{len(o['members'])}**\n💎 Tông Khố: **{fmt(int(o['treasury']))}**\n🌿 Linh Mạch: **cấp {sct.get('linh_mach_level',0)} · +{sct.get('bonus_percent',0)}%**"
            await self._edit(interaction, make_embed(text, footer="Tông Môn · Nội Vụ"), SectManageView(self.owner_id))
        else:
            await self._edit(interaction, sect_embed(self.owner_id, member=dashboard["member"], owner=dashboard["owner"], sects=dashboard["sects"]), SectView(self.owner_id, dashboard))

    @discord.ui.button(label="Túi", emoji="🎒", style=discord.ButtonStyle.secondary, row=1)
    async def inventory(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.guard(interaction): return
        view = InventoryView(self.owner_id)
        await view.rebuild()
        await self._edit(interaction, await view.embed(), view)

    @discord.ui.button(label="Chợ", emoji="🛍️", style=discord.ButtonStyle.secondary, row=1)
    async def market(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.guard(interaction): return
        view = MarketView(self.owner_id)
        await view.rebuild()
        await self._edit(interaction, await view.embed(), view)

    @discord.ui.button(label="Đạo", emoji="🧭", style=discord.ButtonStyle.secondary, row=1)
    async def dao(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.guard(interaction): return
        view = DaoView(self.owner_id)
        await self._edit(interaction, await view.embed(), view)

    @discord.ui.button(label="BXH", emoji="🏆", style=discord.ButtonStyle.secondary, row=1)
    async def leaderboard(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.guard(interaction): return
        await self._edit(interaction, make_plain_embed("🏆 BẢNG XẾP HẠNG TU CHÂN", "Chọn bảng muốn xem."), LeaderboardView(self.owner_id))

    @discord.ui.button(label="Đạo Lữ", emoji="💞", style=discord.ButtonStyle.secondary, row=1)
    async def daolu(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.guard(interaction): return
        view = DaoLuView(self.owner_id)
        await self._edit(interaction, await view.embed(), view)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True


async def command_menu(message: discord.Message) -> None:
    await message.reply(embed=make_plain_embed("🌌 ĐẠI ĐIỆN KATO TU TIÊN", "Chọn một hệ thống để tiếp tục. Emoji + nút là cách thao tác nhanh; lệnh vẫn được giữ cho đạo hữu thích gõ."), view=MainMenuView(message.author.id), mention_author=False)


HELP_CATEGORIES = {
    "start": ("Khởi đầu", "🌱", "Tạo nhân vật và xem hành trình tu luyện.", "🌱 **KHỞI ĐẦU**\n\n`.tamuontutien`\n→ Tạo nhân vật và chọn con đường tu hành.\n\n`.xem`\n→ Xem thông tin nhân vật và chỉ số.\n\n`.info`\n→ Xem trạng thái tu luyện chi tiết."),
    "cultivation": ("Tu luyện", "⚡", "Tăng tu vi, đột phá, bế quan và Đăng Thiên Lộ.", "⚡ **TU LUYỆN**\n\n`.tu`\n→ Tu luyện để tăng tu vi.\n\n`.tuvi`\n→ Mở menu xem Tu Vi Tiên Đạo / Ma Đạo.\n\n`.dotpha`\n→ Khi đủ điều kiện, thử đột phá cảnh giới.\n\n`.daily`\n→ Nhận phần thưởng hằng ngày.\n\n`.bequan`\n→ Bế quan tu luyện tự động, kể cả khi offline.\n\n`.xuatquan`\n→ Kết thúc bế quan.\n\n`.thangthien`\n→ Leo Đăng Thiên Lộ, lưu tầng cao nhất và nhận thưởng."),
    "explore": ("Khám phá", "🗺️", "Chọn vùng rồi mới bắt đầu khám phá; mỗi vùng có pool cơ duyên riêng.", "🗺️ **KHÁM PHÁ**\n\n`.khampha`\n→ Mở menu chọn vùng để bắt đầu khám phá.\n\n🌲 **Hoang Nguyên** → linh mạch, linh thảo, tán tu, cổ động phủ, đốn ngộ.\n🐉 **Yêu Thú Sơn Mạch** → yêu thú, Boss, yêu tàng và huyết mạch cơ duyên.\n\nGặp giao tranh sẽ chuyển sang giao diện chiến đấu 4 nút."),
    "combat": ("Chiến đấu", "⚔️", "Các hành động khi gặp yêu thú hoặc Boss.", "⚔️ **CHIẾN ĐẤU**\n\n{att} **Tấn công** → Đánh thường.\n\n{skill} **Kỹ năng** → Chọn kỹ năng đã học.\n\n{bag} **Túi đồ** → Dùng vật phẩm phù hợp.\n\n{run} **Rút lui** → Rời khỏi giao tranh.\n\n{hp} HP · {att_stat} Công · {def} Phòng thủ."),
    "items": ("Vật phẩm", "🎒", "Xem, dùng, trang bị và học vật phẩm/công pháp.", "🎒 **VẬT PHẨM**\n\n`.tui` → Mở túi đồ.\n`.dung <item> [sl]` → Sử dụng nhiều vật phẩm cùng lúc.\n`.trangbi <item>` → Trang bị.\n`.thao` → Tháo trang bị.\n`.hoc <công_pháp>` → Học công pháp.\n\n{pill} Đan dược · {talisman} Bùa chú · {artifact} Vật phẩm/Pháp bảo · {manual} Công pháp."),
    "sect": ("Tông Môn", "🏯", "Sáng lập, quản lý Tông Môn, Tông Khố và Tháp Tông Môn.", "🏯 **TÔNG MÔN**\n\n`.tongmon` → Nội Vụ nếu đã gia nhập.\n`.congtong <linh_thach>` → Đóng góp vào Tông Khố.\n`.thaptong` → Tháp Tông Môn chung.\n`.nhiemvutong` / `.nvtong <mã>` → Nhiệm vụ.\n`.linhmach` → Xem chi phí nâng Linh Mạch.\n\nNội Vụ gồm Top cống hiến, Môn nhân, chức vụ, BXH, Tông Khố và Linh Mạch."),
    "social": ("Đạo Lữ", "💞", "Kết duyên, song tu và tương tác với đạo hữu.", "💞 **ĐẠO LỮ**\n\n`.daolu` → Xem trạng thái đạo lữ.\n`.ketduyen @người` → Gửi lời cầu duyên.\n`.songtu` → Song tu.\n`.tangdao <item> [sl]` → Tặng vật phẩm.\n`.huyduyen` → Kết thúc quan hệ."),
    "trade": ("Giao dịch", "🛍️", "Tiên Phường, chợ và chuyển Linh Thạch.", "🛍️ **GIAO DỊCH**\n\n`.shop` → Xem Tiên Phường.\n`.mua <item> [sl]` → Mua vật phẩm.\n`.cho` → Xem chợ.\n`.dangban <item> <sl> <gia>` → Đăng bán.\n`.muacho <id>` → Mua tin đăng.\n`.huyban <id>` → Hủy tin bán.\n`.chuyen @người <số>` → Chuyển Linh Thạch."),
    "advanced": ("Hệ thống khác", "🔮", "Thiên Cơ, Đạo, ba loại Tháp, Thiên Kiếp và quản trị.", "🔮 **HỆ THỐNG KHÁC**\n\n`.thienco` / `.gacha` → Thiên Cơ.\n`.code <mã>` → Nhập mã thưởng.\n`.bxh` / `.top` → BXH Tiên / Ma / Tông Môn.\n`.dao` → Mở menu chọn/kiểm tra Đạo; tiến trình Khí → Ý → Thế → Tâm.\n`.thap` / `.leothap` → Thí Luyện Tháp · Cá Nhân, 5 lượt/ngày.\n`.thangthien` → Đăng Thiên Lộ · thử thách cột mốc cá nhân, không phải farm buff.\n`.thaptong` → Tháp Tông Môn · tiến độ chung cả Tông.\n`.thienkiep` → Mở màn xác nhận Ứng Thiên Kiếp tại Độ Kiếp tầng 3.\n`.admin`, `/thien-dao`, `.filedb` → quản trị Thiên Đạo."),
}

def help_menu_embed() -> discord.Embed:
    lines = ["🌌 **KATO TU TIÊN**", "", "Chọn một mục để xem lệnh và công dụng.", ""]
    for label, emoji, desc, _ in HELP_CATEGORIES.values():
        lines.append(f"{emoji} **{label}** — {desc}")
    lines.append("\n💡 `.help` để mở lại bảng tra cứu.")
    return make_embed("\n".join(lines), footer="Kato Tu Tiên · Sổ tay lệnh")

def help_category_text(key: str) -> str:
    label, emoji, desc, body = HELP_CATEGORIES[key]
    return body.format(att=TAN_CONG_ICON, skill=KI_NANG_ICON, bag=VAT_PHAM_ICON, run=BO_CHAY_ICON, hp=HP_ICON, att_stat=ATT_ICON, **{"def": DEF_ICON}, pill=DAN_DUOC_ICON, talisman=BUA_CHU_ICON, artifact=VAT_PHAM_ICON, manual=CONG_PHAP_ICON)

class HelpSelect(discord.ui.Select):
    def __init__(self, owner_id: int):
        self.owner_id = owner_id
        options = [discord.SelectOption(label=v[0], value=k, emoji=v[1], description=v[2][:100]) for k, v in HELP_CATEGORIES.items()]
        super().__init__(placeholder="📖 Chọn mục muốn xem...", min_values=1, max_values=1, options=options)
    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Chỉ người mở Help mới điều khiển được menu này.", ephemeral=True)
            return
        await interaction.response.edit_message(embed=make_embed(help_category_text(self.values[0]), footer="Kato Tu Tiên · Help"), view=self.view)

class HelpView(discord.ui.View):
    def __init__(self, owner_id: int):
        super().__init__(timeout=180)
        self.owner_id = owner_id
        self.add_item(HelpSelect(owner_id))
    @discord.ui.button(label="Trang chính", style=discord.ButtonStyle.secondary, emoji="📖")
    async def home(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Chỉ người mở Help mới điều khiển được menu này.", ephemeral=True)
            return
        await interaction.response.edit_message(embed=help_menu_embed(), view=self)
    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True

def help_text() -> str:
    return "Chọn một mục trong menu Help để xem các lệnh và công dụng."

async def command_help(message: discord.Message) -> None:
    await message.reply(embed=help_menu_embed(), view=HelpView(message.author.id), mention_author=False)


async def send_error(message: discord.Message, error: Exception) -> None:
    await reply_ui(message, f"Lỗi\n{error}", color=COLOR_ERROR)


# Custom Discord emojis used by the faction picker.
TU_TIEN_ICON = discord.PartialEmoji(name="tutien", id=1556700775982305350)
TU_MA_ICON = discord.PartialEmoji(name="tuma", id=1556700734748233749)


class PathChoiceSelect(discord.ui.Select):
    def __init__(self, owner_id: int):
        self.owner_id = owner_id
        options = [
            discord.SelectOption(label="Tu Tiên", value="tien", emoji=TU_TIEN_ICON, description="Chính đạo, truy cầu trường sinh."),
            discord.SelectOption(label="Tu Ma", value="ma", emoji=TU_MA_ICON, description="Ma đạo, nghịch thiên mà hành."),
        ]
        super().__init__(placeholder="☯️ Chọn con đường tu hành...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Thiên cơ chỉ thuộc về người mở giao diện này.", ephemeral=True)
            return
        await interaction.response.defer()
        try:
            if await run_engine(engine.exists, str(interaction.user.id)):
                raise GameError("Ngươi đã có đạo thống rồi.")
            player = await run_engine(engine.create_character, str(interaction.user.id), interaction.user.display_name, self.values[0])
            await interaction.edit_original_response(embed=make_embed(
                f"🌌 **NGƯƠI MUỐN BƯỚC LÊN CON ĐƯỜNG NÀO?**\n\nĐã chọn **{path_name(player.path)}**.\n\nCăn cốt: **{player.root}** · Ngộ tính: **{player.insight}**\nKhí vận: **{player.luck}** · Tâm cảnh: **{player.mind}**\n\nMệnh cách: **{player.destiny}**\nThiên phú: **{player.talent}**\n_{engine.destiny_description(player)}_\n_{engine.talent_description(player)}_\n\nVốn khởi đầu: **{fmt(player.spirit_stones)} linh thạch**\n\nDùng `.info` để bước tiếp trên tiên lộ.", color=COLOR_SUCCESS, footer="Thiên Đạo đã ghi nhận đạo thống"), view=None)
        except GameError as exc:
            await interaction.edit_original_response(content=decorate_currency(str(exc)), view=None)
        except Exception as exc:
            logger.exception("path choice failed: %s", exc)
            await interaction.edit_original_response(content="Đã xảy ra lỗi khi khai đạo. Hãy thử lại.", view=None)


class PathChoiceView(discord.ui.View):
    def __init__(self, owner_id: int):
        super().__init__(timeout=180)
        self.add_item(PathChoiceSelect(owner_id))


async def command_create(message: discord.Message, args: list[str]) -> None:
    uid = str(message.author.id)
    if await run_engine(engine.exists, uid):
        await reply_ui(message, "Ngươi đã có đạo thống rồi. Dùng `.info` để xem thiên mệnh.", color=COLOR_WARN)
        return
    await message.reply(
        embed=make_embed("🌌 **NGƯƠI MUỐN BƯỚC LÊN CON ĐƯỜNG NÀO?**\n\n*Một niệm định tiên ma, một bước định cả con đường tu hành.*\n\nChọn một đạo trong thanh cuộn bên dưới.", footer="Khai đạo · Tu Tiên hoặc Tu Ma"),
        view=PathChoiceView(message.author.id),
        mention_author=False,
    )

async def send_character_origin(message: discord.Message, player) -> None:
    text = (
        "KHAI ĐẠO THÀNH CÔNG\n"
        f"{player.display_name} · {path_name(player.path)}\n\n"
        f"Căn cốt: **{player.root}** · Ngộ tính: **{player.insight}**\n"
        f"Khí vận: **{player.luck}** · Phúc duyên: **{player.fate}**\n"
        f"Tâm cảnh: **{player.mind}**\n\n"
        f"Mệnh cách: **{player.destiny}**\n"
        f"Thiên phú: **{player.talent}**\n"
        f"_{engine.destiny_description(player)}_\n"
        f"_{engine.talent_description(player)}_\n\n"
        f"Vốn khởi đầu: **{fmt(player.spirit_stones)} linh thạch**\n\n"
        "Dùng `.info` để xem nhân vật."
    )
    await reply_ui(message, text, color=COLOR_SUCCESS)


def tuvi_embed(player) -> discord.Embed:
    path = path_name(player.path)
    icon = "🪽" if player.path == "tien" else "😈"
    title = f"{icon} TU VI {path.upper()}"
    req = engine.cultivation_requirement(player)
    desc = (
        f"{icon} **Con đường:** {path}\n"
        f"🌌 **Cảnh giới:** {engine.realm_text(player)}\n"
        f"⚡ **Tu vi:** `{fmt(player.cultivation)} / {fmt(req)}`\n"
        f"🏛️ **Căn Cơ:** `{player.foundation}/100` · **{engine.foundation_grade(player)}**\n"
        f"✨ **Mệnh cách:** {player.destiny}\n"
        f"🔮 **Thiên phú:** {player.talent}\n\n"
        "Tu vi đầy thì dùng `.dotpha` để thử đột phá cảnh giới."
    )
    return make_plain_embed(title, desc, color=COLOR_SUCCESS if player.path == "tien" else COLOR_WARN, footer="Tu Vi · Tiên / Ma")


class TuViView(discord.ui.View):
    def __init__(self, owner_id: int):
        super().__init__(timeout=180)
        self.owner_id = owner_id
        self.busy = False

    async def guard(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Chỉ người mở Tu Vi mới điều khiển được menu này.", ephemeral=True)
            return False
        if self.busy:
            await interaction.response.send_message("Hệ thống đang xử lý lượt tu luyện.", ephemeral=True)
            return False
        return True

    async def refresh(self, interaction: discord.Interaction):
        player = await run_engine(engine.info, str(self.owner_id))
        await interaction.response.edit_message(embed=tuvi_embed(player), view=self)

    @discord.ui.button(label="Tu luyện", emoji="🧘", style=discord.ButtonStyle.primary, row=0)
    async def cultivate(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.guard(interaction): return
        self.busy = True
        try:
            result = await run_engine(engine.cultivate, str(self.owner_id))
            player = result["player"]
            text = f"{tuvi_embed(player).description}\n\n🧘 **Lĩnh hội +{fmt(result['gain'])} tu vi.**"
            if result.get("event_text"):
                text += f"\n{result['event_text']}"
            await interaction.response.edit_message(embed=make_plain_embed(tuvi_embed(player).title, text, color=COLOR_SUCCESS), view=self)
        except GameError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
        finally:
            self.busy = False

    @discord.ui.button(label="Đột phá", emoji="⚡", style=discord.ButtonStyle.success, row=0)
    async def breakthrough(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.guard(interaction): return
        preview = await run_engine(engine.breakthrough_preview, str(self.owner_id))
        text = (f"**{preview['old_text']}** → thử mở cảnh giới kế tiếp\n\n"
                f"Ngưỡng tu vi: **{fmt(preview['required'])}**\n"
                f"Tỷ lệ dự kiến: **{preview['chance']:.1f}%**\n\n⚠️ Thất bại sẽ phản phệ tu vi.")
        await interaction.response.send_message(embed=make_embed(text, color=COLOR_WARN, footer="Đột Phá · Xác nhận"), view=BreakthroughView(self.owner_id), ephemeral=True)

    @discord.ui.button(label="Bế quan", emoji="🧘‍♂️", style=discord.ButtonStyle.secondary, row=0)
    async def be_quan(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.guard(interaction): return
        try:
            result = await run_engine(engine.start_be_quan, str(self.owner_id))
            await interaction.response.send_message(f"🧘‍♂️ **Đã nhập Động Phủ.** Chu kỳ: **{result.get('cycles', result.get('cycle_minutes', '?'))}** · Trạng thái sẽ được cập nhật tự động.", ephemeral=True)
        except GameError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)

    @discord.ui.button(label="Làm mới", emoji="🔄", style=discord.ButtonStyle.secondary, row=0)
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.guard(interaction): return
        await self.refresh(interaction)

    @discord.ui.button(label="Đại Điện", emoji="🏠", style=discord.ButtonStyle.secondary, row=1)
    async def home(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.guard(interaction): return
        await interaction.response.edit_message(embed=make_plain_embed("🌌 ĐẠI ĐIỆN KATO TU TIÊN", "Chọn hệ thống để tiếp tục."), view=MainMenuView(self.owner_id))

    async def on_timeout(self):
        for child in self.children: child.disabled = True


async def command_tuvi(message: discord.Message) -> None:
    player = await run_engine(engine.info, str(message.author.id))
    await message.reply(embed=tuvi_embed(player), view=TuViView(message.author.id), mention_author=False)


def leaderboard_embed(path: str) -> discord.Embed:
    players = []
    label = "Tiên Đạo" if path == "tien" else "Ma Đạo"
    icon = "🪽" if path == "tien" else "😈"
    # This helper is filled asynchronously by command_leaderboard_view.
    return make_plain_embed(f"🏆 {icon} BXH {label.upper()}", "Đang tải...", footer="BXH · Tiên / Ma")


class LeaderboardView(discord.ui.View):
    def __init__(self, owner_id: int):
        super().__init__(timeout=180)
        self.owner_id = owner_id

    async def guard(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Chỉ người mở BXH mới điều khiển được menu này.", ephemeral=True)
            return False
        return True

    async def show_path(self, interaction: discord.Interaction, path: str):
        rows = await run_engine(engine.leaderboard, 10, path)
        label = "Tiên Đạo" if path == "tien" else "Ma Đạo"
        icon = "🪽" if path == "tien" else "😈"
        lines = [f"{icon} **TOP {label.upper()}**", ""]
        if not rows: lines.append("Chưa có tu sĩ trên bảng xếp hạng.")
        else:
            for idx, player in enumerate(rows, 1):
                medal = {1:"🥇",2:"🥈",3:"🥉"}.get(idx, f"`#{idx}`")
                lines.append(f"{medal} **{player.display_name}** · {engine.realm_text(player)} · Tu vi `{fmt(player.cultivation)}` · Căn Cơ `{player.foundation}`")
        await interaction.response.edit_message(embed=make_plain_embed(f"🏆 {icon} BXH {label.upper()}", "\n".join(lines), footer="BXH · Tu Chân"), view=self)

    @discord.ui.button(label="Tiên Đạo", emoji="🪽", style=discord.ButtonStyle.success, row=0)
    async def tien(self, interaction: discord.Interaction, button: discord.ui.Button):
        if await self.guard(interaction): await self.show_path(interaction, "tien")

    @discord.ui.button(label="Ma Đạo", emoji="😈", style=discord.ButtonStyle.danger, row=0)
    async def ma(self, interaction: discord.Interaction, button: discord.ui.Button):
        if await self.guard(interaction): await self.show_path(interaction, "ma")

    @discord.ui.button(label="Tông Môn", emoji="🏯", style=discord.ButtonStyle.primary, row=0)
    async def sect(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.guard(interaction): return
        rows = await run_engine(engine.sect_leaderboard, 10)
        lines = ["🏯 **TOP TÔNG MÔN**", ""]
        if not rows: lines.append("Chưa có Tông Môn trên bảng xếp hạng.")
        else:
            for idx, row in enumerate(rows, 1):
                medal = {1:"🥇",2:"🥈",3:"🥉"}.get(idx, f"`#{idx}`")
                lines.append(f"{medal} **{row['name']}** · Cấp {row.get('level',1)} · {fmt(int(row.get('contribution',0)))} cống hiến · {row.get('members',0)} môn nhân")
        await interaction.response.edit_message(embed=make_plain_embed("🏆 BXH TÔNG MÔN", "\n".join(lines), footer="BXH · Tông Môn"), view=self)

    @discord.ui.button(label="Đại Điện", emoji="🏠", style=discord.ButtonStyle.secondary, row=1)
    async def home(self, interaction: discord.Interaction, button: discord.ui.Button):
        if await self.guard(interaction):
            await interaction.response.edit_message(embed=make_plain_embed("🌌 ĐẠI ĐIỆN KATO TU TIÊN", "Chọn hệ thống để tiếp tục."), view=MainMenuView(self.owner_id))

    async def on_timeout(self):
        for child in self.children: child.disabled = True


async def command_leaderboard(message: discord.Message) -> None:
    await message.reply(embed=make_plain_embed("🏆 BẢNG XẾP HẠNG TU CHÂN", "Chọn: 🪽 Tiên Đạo · 😈 Ma Đạo · 🏯 Tông Môn"), view=LeaderboardView(message.author.id), mention_author=False)


async def command_info(message: discord.Message) -> None:
    player = await run_engine(engine.info, str(message.author.id))
    equip_name = ITEMS[player.equipped]["name"] if player.equipped in ITEMS else "Chưa có"
    req = engine.cultivation_requirement(player)
    discoveries = await run_engine(engine.discovery_count, str(message.author.id))
    daily = "Sẵn sàng" if engine.daily_remaining(player) == 0 else "Đã nhận hôm nay"
    stats = engine.battle_stats(player)
    text = (
        f"{ui_section(player.display_name, '🌌')}\n"
        f"{path_name(player.path)} · **{engine.realm_text(player)}**\n\n"
        f"{HP_ICON} **HP:** `{fmt(stats['hp'])}`   {ATT_ICON} **Công:** `{fmt(stats['attack'])}`   {DEF_ICON} **Phòng:** `{fmt(stats['defense'])}`\n"
        f"⚡ **Tu vi:** `{fmt(player.cultivation)} / {fmt(req)}`\n"
        f"{LINH_THACH_ICON} **Linh Thạch:** `{fmt(player.spirit_stones)}`\n\n"
        f"**Căn cốt** `{player.root}` · **Ngộ tính** `{player.insight}`\n"
        f"**Khí vận** `{player.luck}` · **Phúc duyên** `{player.fate}`\n"
        f"**Tâm cảnh** `{player.mind}` · **Nghiệp lực** `{player.karma}` · **Công đức** `{player.merit}`\n"
        f"🏛️ **Căn Cơ:** `{player.foundation}/100` · **{engine.foundation_grade(player)}**\n\n"
        f"🌟 **Mệnh cách:** {player.destiny}\n"
        f"✨ **Thiên phú:** {player.talent}\n"
        f"{VAT_PHAM_ICON} **Trang bị:** {equip_name}\n"
        f"🗺️ **Khám phá:** `{discoveries}` · 📅 **Daily:** {daily}\n"
        f"💥 **Bạo kích:** `{stats['crit_chance'] * 100:.1f}%` · **Chí mạng:** `×{stats['crit_multiplier']:.2f}`"
    )
    await reply_ui(message, text)


async def command_daily(message: discord.Message) -> None:
    result = await run_engine(engine.claim_daily, str(message.author.id))
    await reply_ui(message, f"NHẬN THƯỞNG HẰNG NGÀY\n+**{fmt(result['reward'])} linh thạch**\nStreak: **{result['streak']} ngày**{result['bonus']}", color=COLOR_SUCCESS)


async def command_show(message: discord.Message) -> None:
    target = message.mentions[0] if message.mentions else message.author
    try:
        profile = await run_engine(engine.public_profile, str(target.id))
    except GameError:
        raise GameError("Đạo hữu này chưa khai đạo.")
    player = profile["player"]
    items = profile["inventory"]
    equipped = ITEMS[player.equipped]["name"] if player.equipped in ITEMS else "Chưa có"
    item_lines = [category_icon(item.get("category", "")) + f" {item['name']} ×{count}" for _item_id, item, count in items[:6]]
    if len(items) > 6:
        item_lines.append(f"... và {len(items) - 6} loại khác")
    text = (
        f"HÀNH TRANG CỦA {player.display_name}\n"
        f"{path_name(player.path)} · **{engine.realm_text(player)}**\n"
        f"Cảnh giới: **{engine.realm_text(player)}** · Căn Cơ: **{profile['foundation_grade']}** · Khám phá: **{profile['discoveries']}**\n"
        f"Trang bị: **{equipped}**\n\n"
        "Vật phẩm:\n" + ("\n".join(item_lines) if item_lines else "Túi đồ trống.")
    )
    await reply_ui(message, text)


async def command_cultivate(message: discord.Message) -> None:
    result = await run_engine(engine.cultivate, str(message.author.id)); player = result["player"]
    text = f"VẬN CHUYỂN CÔNG PHÁP\n+**{fmt(result['gain'])}** tu vi\nHiện tại: **{fmt(player.cultivation)} / {fmt(engine.cultivation_requirement(player))}**"
    if result["event_text"]:
        text += f"\n\n{result['event_text']}"
    await reply_ui(message, text, color=COLOR_SUCCESS)


class BreakthroughView(discord.ui.View):
    def __init__(self, owner_id: int):
        super().__init__(timeout=90)
        self.owner_id = owner_id
        self.busy = False

    async def ensure_owner(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Thiên cơ này chỉ thuộc về người mở Đột Phá.", ephemeral=True)
            return False
        return True

    def disable_all(self) -> None:
        for child in self.children:
            child.disabled = True

    @discord.ui.button(label=None, emoji=DONG_Y_ICON, style=discord.ButtonStyle.success, row=0)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.ensure_owner(interaction):
            return
        if self.busy:
            await interaction.response.send_message("Đột phá đang được xử lý.", ephemeral=True)
            return
        self.busy = True
        await interaction.response.defer()
        try:
            result = await run_engine(engine.breakthrough, str(self.owner_id))
        except GameError as exc:
            self.disable_all()
            await interaction.edit_original_response(embed=make_embed(str(exc), color=COLOR_ERROR, footer="Đột Phá · Không thể thực hiện"), view=self)
            return
        except Exception as exc:
            logger.exception("Unhandled error: %s", exc)
            self.disable_all()
            await interaction.edit_original_response(content="Đã xảy ra lỗi khi đột phá. Trạng thái nhân vật được giữ nguyên; hãy thử lại.", view=self)
            return
        self.disable_all()
        if result["success"]:
            text = f"ĐỘT PHÁ THÀNH CÔNG\n{result['old_text']} → **{result['new_text']}**\nTỷ lệ lúc đột phá: **{result['chance']:.1f}%**"
            if result["major"]:
                text += "\n\nMột đại cảnh mới đã mở ra."
            await interaction.edit_original_response(embed=make_embed(text, color=COLOR_SUCCESS, footer="Đột Phá · Thành công"), view=self)
        else:
            await interaction.edit_original_response(embed=make_embed(
                f"ĐỘT PHÁ THẤT BẠI\nPhản phệ: **-{fmt(result['loss'])}** tu vi.\nTỷ lệ lúc đột phá: **{result['chance']:.1f}%**",
                color=COLOR_WARN, footer="Đột Phá · Thất bại"), view=self)

    @discord.ui.button(label=None, emoji=TU_CHOI_ICON, style=discord.ButtonStyle.secondary, row=0)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.ensure_owner(interaction):
            return
        self.disable_all()
        await interaction.response.edit_message(embed=make_embed("ĐỘT PHÁ ĐÃ HỦY\nNgươi đã giữ lại cơ hội đột phá cho lần sau.", color=COLOR_WARN, footer="Đột Phá · Đã hủy"), view=self)

    async def on_timeout(self) -> None:
        self.disable_all()


async def command_breakthrough(message: discord.Message) -> None:
    preview = await run_engine(engine.breakthrough_preview, str(message.author.id))
    text = (
        "ĐỘT PHÁ?\n"
        f"Cảnh giới hiện tại: **{preview['old_text']}**\n"
        f"Ngưỡng tu vi: **{fmt(preview['required'])}**\n"
        f"Tỷ lệ thành công dự kiến: **{preview['chance']:.1f}%**\n"
        "\n⚠️ Đột phá thất bại sẽ bị phản phệ tu vi.\n"
        "Xác nhận quyết định của ngươi bằng hai nút bên dưới."
    )
    await message.reply(embed=make_embed(text, color=COLOR_WARN, footer="Đột Phá · Xác nhận"), view=BreakthroughView(message.author.id), mention_author=False)


class CombatSkillView(discord.ui.View):
    def __init__(self, combat_view: "EncounterView", skills: list[dict]):
        super().__init__(timeout=60)
        self.combat_view = combat_view
        self.skills = skills
        options = []
        for x in skills[:25]:
            mult = float(x.get("multiplier", 1.2))
            rarity = x.get("rarity", "?")
            desc = f"{ATT_ICON} x{mult:.2f} · {rarity} · 1 lượt combat"[:100]
            options.append(discord.SelectOption(label=x["name"][:100], value=x["id"], description=desc))
        self.select = discord.ui.Select(placeholder="Chọn kỹ năng đã học...", options=options)
        self.select.callback = self._select
        self.add_item(self.select)

    async def _select(self, interaction: discord.Interaction):
        if interaction.user.id != self.combat_view.owner_id:
            await interaction.response.send_message("Chỉ người đang giao chiến mới có thể hành động.", ephemeral=True)
            return
        if self.combat_view.busy or self.combat_view.ended:
            await interaction.response.send_message("Lượt này đang được xử lý hoặc trận chiến đã kết thúc.", ephemeral=True)
            return
        # Claim the turn before any await so concurrent selects cannot double-cast.
        self.combat_view.busy = True
        self.combat_view.update_buttons()
        await interaction.response.defer()
        await self.combat_view._skill_action(interaction, self.select.values[0], already_busy=True)

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True


class CombatInventoryView(discord.ui.View):
    def __init__(self, combat_view: "EncounterView", inventory_rows: list[tuple[str, dict, int]]):
        super().__init__(timeout=60)
        self.combat_view = combat_view
        self.category = "Đan dược"
        self.inventory_rows = inventory_rows
        self._refresh()

    def _refresh(self):
        self.clear_items()
        for label, category, emoji in [
            ("Đan dược", "Đan dược", DAN_DUOC_ICON),
            ("Bùa chú", "Bùa chú", BUA_CHU_ICON),
            ("Pháp bảo", "Pháp bảo", VAT_PHAM_ICON),
            ("Công pháp", "Công pháp", CONG_PHAP_ICON),
        ]:
            button = discord.ui.Button(label=label, emoji=emoji, style=discord.ButtonStyle.primary if category == self.category else discord.ButtonStyle.secondary, row=0)
            async def callback(interaction: discord.Interaction, cat=category):
                if interaction.user.id != self.combat_view.owner_id:
                    await interaction.response.send_message("Chỉ người đang giao chiến mới có thể hành động.", ephemeral=True)
                    return
                await interaction.response.defer()
                try:
                    self.category = cat
                    self.inventory_rows = await run_engine(engine.inventory, str(self.combat_view.owner_id))
                    self._refresh()
                    await interaction.edit_original_response(embed=make_embed(self.text(), color=COLOR_INFO, footer="Đang giao chiến · Túi đồ"), view=self)
                except Exception as exc:
                    logger.exception("Unhandled error: %s", exc)
                    await interaction.edit_original_response(content="Không thể tải túi đồ lúc này. Hãy thử lại.", view=self)
            button.callback = callback
            self.add_item(button)
        if self.category in {"Đan dược", "Bùa chú"}:
            items = [x for x in self.inventory_rows if x[1].get("category") == self.category and x[1].get("type") == "consumable"]
            options = [discord.SelectOption(label=f"{item['name']} ×{count}"[:100], value=item_id, description=item.get("description", "")[:100]) for item_id, item, count in items[:25]]
            if options:
                select = discord.ui.Select(placeholder=f"Chọn {self.category.lower()} để sử dụng...", options=options, row=1)
                async def use_callback(interaction: discord.Interaction):
                    if interaction.user.id != self.combat_view.owner_id:
                        await interaction.response.send_message("Chỉ người đang giao chiến mới có thể hành động.", ephemeral=True)
                        return
                    if self.combat_view.busy or self.combat_view.ended:
                        await interaction.response.send_message("Lượt này đang được xử lý hoặc trận chiến đã kết thúc.", ephemeral=True)
                        return
                    self.combat_view.busy = True
                    self.combat_view.update_buttons()
                    await interaction.response.defer()
                    await self.combat_view._item_action(interaction, select.values[0], already_busy=True)
                select.callback = use_callback
                self.add_item(select)
        else:
            # Equipment/technique remain view-only here; they are not silently consumed during combat.
            pass

    def text(self) -> str:
        items = [x for x in self.inventory_rows if x[1].get("category") == self.category]
        icon = category_icon(self.category)
        if not items:
            return f"{icon} **{self.category.upper()}**\n\nKhông có vật phẩm trong túi."
        lines = [f"{icon} **{self.category.upper()}**", ""]
        for item_id, item, count in items[:12]:
            lines.append(f"{icon} **{item['name']}** ×{count}\n> {item.get('description', '')}")
        if self.category in {"Pháp bảo", "Công pháp"}:
            lines.append("\n*Nhóm này không sử dụng trực tiếp trong lượt combat.*")
        return "\n".join(lines)


class EncounterView(discord.ui.View):
    """Combat GUI: attack, learned skills, combat inventory, retreat."""
    def __init__(self, owner_id: int, encounter: dict, player_hp: int | None = None, player=None, stats: dict | None = None):
        super().__init__(timeout=180)
        self.owner_id = owner_id
        self.encounter = encounter
        self._cached_player = player
        # Never touch SQLite on the Discord event loop here. Callers must pass
        # player/stats snapshots obtained via run_engine / asyncio.to_thread.
        if stats is None:
            if player is not None:
                stats = engine.battle_stats(player)  # pure compute on player object
            else:
                stats = {
                    "hp": int(encounter.get("max_hp", encounter.get("hp", 1000))),
                    "attack": 0,
                    "defense": 0,
                    "crit_chance": 0.05,
                    "crit_multiplier": 1.5,
                }
        self.player_hp = int(stats["hp"]) if player_hp is None else int(player_hp)
        self.enemy_hp = int(encounter["hp"])
        self.busy = False
        self.ended = False
        self.update_buttons()

    def update_buttons(self):
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = self.busy or self.ended

    def status_text(self, player=None) -> str:
        # Prefer player snapshot from the last engine call; avoid SQLite on the event loop.
        if player is not None:
            self._cached_player = player
        player = player or self._cached_player
        if player is not None:
            stats = engine.battle_stats(player)
        else:
            stats = {"hp": max(1, self.player_hp), "attack": 0, "defense": 0, "crit_chance": 0.0, "crit_multiplier": 1.5}
            class _P:
                injury = 0
            player = _P()
        enemy_pct = max(0, min(100, round(self.enemy_hp / max(1, self.encounter['max_hp']) * 100)))
        player_pct = max(0, min(100, round(self.player_hp / max(1, stats['hp']) * 100)))
        return (
            f"👹 **{self.encounter['kind_label']} · {self.encounter['name']}**\n"
            f"{HP_ICON} **{self.enemy_hp}/{self.encounter['max_hp']} HP** · `{enemy_pct}%`\n"
            f"{ATT_ICON} **Công {self.encounter['attack']}** · {DEF_ICON} **Phòng {self.encounter['defense']}**\n\n"
            f"🧑 **Đạo hữu**\n"
            f"{HP_ICON} **{self.player_hp}/{stats['hp']} HP** · `{player_pct}%`\n"
            f"{ATT_ICON} **Công {stats['attack']}** · {DEF_ICON} **Phòng {stats['defense']}**\n"
            f"💥 **Crit {stats['crit_chance'] * 100:.1f}%** · `×{stats['crit_multiplier']:.2f}` · **Thương thế {player.injury}%**"
        )

    async def ensure_owner(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Chỉ người đang giao chiến mới có thể hành động.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Tấn công", emoji=TAN_CONG_ICON, style=discord.ButtonStyle.danger, row=0)
    async def normal(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.ensure_owner(interaction): return
        await self._act(interaction, "normal")

    @discord.ui.button(label="Kỹ năng", emoji=KI_NANG_ICON, style=discord.ButtonStyle.primary, row=0)
    async def skill(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.ensure_owner(interaction):
            return
        if self.busy or self.ended:
            await interaction.response.send_message("Lượt này đang được xử lý hoặc trận chiến đã kết thúc.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            skills = await run_engine(engine.combat_skills, str(self.owner_id))
        except Exception as exc:
            logger.exception("combat_skills failed: %s", exc)
            await interaction.edit_original_response(content="Không tải được danh sách kỹ năng. Hãy thử lại.")
            return
        if not skills:
            await interaction.edit_original_response(
                content=f"{CONG_PHAP_ICON} Ngươi chưa học công pháp nào có thể dùng làm kỹ năng chiến đấu."
            )
            return
        skill_lines = [
            f"{KI_NANG_ICON} **KỸ NĂNG ĐÃ HỌC**",
            "",
            "Chỉ kỹ năng đã học mới xuất hiện. Mỗi lần dùng tốn **1 lượt** combat.",
            f"{ATT_ICON} Damage theo multiplier · {HP_ICON}/{DEF_ICON} theo chỉ số nhân vật.",
            "",
        ]
        for s in skills[:8]:
            skill_lines.append(
                f"• **{s['name']}** ({s.get('rarity', '?')}) · {ATT_ICON} ×**{float(s.get('multiplier', 1.2)):.2f}**"
            )
        await interaction.edit_original_response(
            embed=make_embed("\n".join(skill_lines), color=COLOR_INFO, footer="Combat · Chọn kỹ năng"),
            view=CombatSkillView(self, skills),
        )

    @discord.ui.button(label="Túi đồ", emoji=VAT_PHAM_ICON, style=discord.ButtonStyle.secondary, row=0)
    async def inventory(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.ensure_owner(interaction):
            return
        if self.busy or self.ended:
            await interaction.response.send_message("Lượt này đang được xử lý hoặc trận chiến đã kết thúc.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            inventory_rows = await run_engine(engine.inventory, str(self.owner_id))
            view = CombatInventoryView(self, inventory_rows)
            await interaction.edit_original_response(
                embed=make_embed(view.text(), color=COLOR_INFO, footer="Đang giao chiến · Túi đồ"),
                view=view,
            )
        except Exception as exc:
            logger.exception("combat inventory failed: %s", exc)
            await interaction.edit_original_response(content="Không tải được túi đồ. Hãy thử lại.")

    @discord.ui.button(label="Rút lui", emoji=BO_CHAY_ICON, style=discord.ButtonStyle.secondary, row=0)
    async def flee(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.ensure_owner(interaction):
            return
        if self.busy or self.ended:
            await interaction.response.send_message("Lượt này đang được xử lý hoặc trận chiến đã kết thúc.", ephemeral=True)
            return
        self.busy = True
        self.update_buttons()
        await interaction.response.defer()
        try:
            result = await run_engine(engine.flee_encounter, str(self.owner_id), self.encounter)
            self.ended = True
            self.busy = False
            self.update_buttons()
            await interaction.edit_original_response(
                embed=make_embed(
                    f"🏃 **RÚT KHỎI CHIẾN TRƯỜNG**\n\n{result['text']}",
                    color=COLOR_WARN,
                    footer="Khám phá · Giao tranh kết thúc",
                ),
                view=self,
            )
        except GameError as exc:
            self.busy = False
            self.update_buttons()
            await interaction.edit_original_response(content=decorate_currency(str(exc)), view=self)
        except Exception as exc:
            logger.exception("Unhandled error: %s", exc)
            self.busy = False
            self.update_buttons()
            await interaction.edit_original_response(content="Đã xảy ra lỗi khi rút lui. Hãy thử lại.", view=self)

    async def _skill_action(self, interaction: discord.Interaction, skill_id: str, *, already_busy: bool = False):
        if self.ended or (self.busy and not already_busy):
            await interaction.edit_original_response(content="Lượt này đang được xử lý hoặc trận chiến đã kết thúc.", view=None)
            return
        if not already_busy:
            self.busy = True
            self.update_buttons()
        try:
            result = await run_engine(engine.battle_skill, str(self.owner_id), self.encounter, self.player_hp, self.enemy_hp, skill_id)
            self.player_hp, self.enemy_hp = result["player_hp"], result["enemy_hp"]
            self.ended = bool(result["ended"]); self.busy = False; self.update_buttons()
            message = getattr(self, "message", None)
            if message:
                await message.edit(embed=make_embed(f"⚔️ **GIAO CHIẾN**\n\n{self.status_text(result.get('player'))}\n\n{result['text']}", color=COLOR_SUCCESS if self.ended and result['victory'] else (COLOR_ERROR if self.ended else COLOR_INFO), footer="Giao tranh kết thúc" if self.ended else "Quyết định lượt tiếp theo"), view=self)
            await interaction.edit_original_response(content="Kỹ năng đã được sử dụng.", view=None)
        except GameError as exc:
            self.busy = False; self.update_buttons()
            await interaction.edit_original_response(content=decorate_currency(str(exc)), view=None)
        except Exception as exc:
            logger.exception("Unhandled error: %s", exc)
            self.busy = False; self.update_buttons()
            await interaction.edit_original_response(content="Đã xảy ra lỗi khi thi triển kỹ năng. Trạng thái trận chiến được giữ nguyên; hãy thử lại.", view=None)

    async def _item_action(self, interaction: discord.Interaction, item_id: str, *, already_busy: bool = False):
        if self.ended or (self.busy and not already_busy):
            await interaction.edit_original_response(content="Lượt này đang được xử lý hoặc trận chiến đã kết thúc.", view=None)
            return
        if not already_busy:
            self.busy = True
            self.update_buttons()
        try:
            result = await run_engine(
                engine.combat_item_turn,
                str(self.owner_id),
                self.encounter,
                self.player_hp,
                self.enemy_hp,
                item_id,
            )
            self.player_hp, self.enemy_hp = result["player_hp"], result["enemy_hp"]
            self.ended = bool(result["ended"])
            self.busy = False
            self.update_buttons()
            message = getattr(self, "message", None)
            if message:
                color = (
                    COLOR_SUCCESS if self.ended and result.get("victory")
                    else (COLOR_ERROR if self.ended else COLOR_INFO)
                )
                await message.edit(
                    embed=make_embed(
                        f"⚔️ **GIAO CHIẾN**\n\n{self.status_text(result.get('player'))}\n\n{result['text']}",
                        color=color,
                        footer="Giao tranh kết thúc" if self.ended else "Quyết định lượt tiếp theo",
                    ),
                    view=self,
                )
            await interaction.edit_original_response(content="Vật phẩm đã được sử dụng.", view=None)
        except GameError as exc:
            self.busy = False
            self.update_buttons()
            await interaction.edit_original_response(content=decorate_currency(str(exc)), view=None)
        except Exception as exc:
            logger.exception("Unhandled error: %s", exc)
            self.busy = False
            self.update_buttons()
            await interaction.edit_original_response(
                content="Đã xảy ra lỗi khi sử dụng vật phẩm. Trạng thái trận chiến được giữ nguyên; hãy thử lại.",
                view=None,
            )

    async def on_timeout(self) -> None:
        self.ended = True
        self.update_buttons()
        message = getattr(self, "message", None)
        if message:
            try:
                await message.edit(view=self)
            except discord.HTTPException:
                pass

    async def _act(self, interaction: discord.Interaction, action: str):
        if self.busy or self.ended:
            if not interaction.response.is_done(): await interaction.response.send_message("Lượt này đang được xử lý hoặc trận chiến đã kết thúc.", ephemeral=True)
            return
        self.busy = True; self.update_buttons()
        try:
            await interaction.response.defer()
            result = await run_engine(engine.battle_step, str(self.owner_id), self.encounter, self.player_hp, self.enemy_hp, action)
            self.player_hp, self.enemy_hp = result["player_hp"], result["enemy_hp"]
            self.ended = bool(result["ended"]); self.busy = False; self.update_buttons()
            color = COLOR_SUCCESS if result["victory"] else (COLOR_ERROR if self.ended else COLOR_INFO)
            await interaction.edit_original_response(embed=make_embed(f"⚔️ **GIAO CHIẾN**\n\n{self.status_text(result.get('player'))}\n\n{result['text']}", color=color, footer="Giao tranh kết thúc" if self.ended else "Quyết định lượt tiếp theo"), view=self)
        except GameError as exc:
            self.busy = False; self.update_buttons()
            await interaction.edit_original_response(content=decorate_currency(str(exc)), view=self)
        except Exception as exc:
            logger.exception("Unhandled error: %s", exc)
            self.busy = False; self.update_buttons()
            await interaction.edit_original_response(content="Đã xảy ra lỗi khi xử lý lượt đánh. Trạng thái trận chiến được giữ nguyên; hãy thử lại.", view=self)


async def send_explore_result_from_message(message_or_interaction, owner_id: int, result: dict, *, edit: bool = False) -> None:
    if result.get("encounter"):
        foe = result["encounter"]
        player = result["player"]
        stats = engine.battle_stats(player)
        text = (
            f"👹 **{foe['kind_label']} · {foe['name']}**\n"
            f"{HP_ICON} HP `{fmt(foe['hp'])}` · {ATT_ICON} Công `{fmt(foe['attack'])}` · {DEF_ICON} Phòng `{fmt(foe['defense'])}`\n\n"
            f"🧑 **Đạo hữu**\n"
            f"{HP_ICON} HP `{fmt(stats['hp'])}` · {ATT_ICON} Công `{fmt(stats['attack'])}` · {DEF_ICON} Phòng `{fmt(stats['defense'])}`\n\n"
            f"{TAN_CONG_ICON} Tấn công · {KI_NANG_ICON} Kỹ năng · {VAT_PHAM_ICON} Túi đồ · {BO_CHAY_ICON} Rút lui"
        )
        embed = make_embed(f"⚔️ **GIAO TRANH**\n\n🗺️ **{result['zone']['name']}**\n{text}", color=COLOR_WARN, footer="Khám phá · Giao tranh")
        view = EncounterView(owner_id, foe, player=player, stats=stats)
    else:
        embed = make_embed(f"🗺️ **{result['zone']['name']}**\n\n✨ **CƠ DUYÊN**\n{result['text']}", color=COLOR_INFO, footer="Khám phá · Khu vực")
        view = None
    if edit:
        await message_or_interaction.edit_original_response(embed=embed, view=view, content=None)
    else:
        await message_or_interaction.reply(embed=embed, view=view, mention_author=False)


class ExploreZoneView(discord.ui.View):
    def __init__(self, owner_id: int):
        super().__init__(timeout=180)
        self.owner_id = owner_id
        self.busy = False

    async def _choose(self, interaction: discord.Interaction, zone_key: str) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Chỉ người mở Khám Phá mới điều khiển được menu này.", ephemeral=True)
            return
        if self.busy:
            await interaction.response.send_message("Đang xử lý lượt khám phá...", ephemeral=True)
            return
        self.busy = True
        try:
            await interaction.response.defer()
            result = await run_engine(engine.explore, str(self.owner_id), zone_key)
            await send_explore_result_from_message(interaction, self.owner_id, result, edit=True)
            self.clear_items()
        except GameError as exc:
            await interaction.edit_original_response(content=decorate_currency(str(exc)), embed=None, view=self)
            self.busy = False
        except Exception as exc:
            logger.exception("Explore zone failed: %s", exc)
            await interaction.edit_original_response(content="Không thể khám phá khu vực lúc này.", view=self)
            self.busy = False

    @discord.ui.button(label="Hoang Nguyên", style=discord.ButtonStyle.primary, emoji="🌲", row=0)
    async def hoangnguyen(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._choose(interaction, "hoangnguyen")

    @discord.ui.button(label="Yêu Thú Sơn Mạch", style=discord.ButtonStyle.danger, emoji="🐉", row=0)
    async def yeuthusonmach(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._choose(interaction, "yeuthusonmach")

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True


async def command_explore(message: discord.Message, args: list[str] | None = None) -> None:
    args = args or []
    if args:
        result = await run_engine(engine.explore, str(message.author.id), args[0].lower())
        await send_explore_result_from_message(message, message.author.id, result)
        return
    await message.reply(
        embed=make_plain_embed(
            "🗺️ KHÁM PHÁ",
            "Chọn khu vực để bắt đầu một lượt khám phá.\n\n🌲 **Hoang Nguyên**\n→ Linh mạch, linh thảo, tán tu, cổ động phủ và đốn ngộ.\n\n🐉 **Yêu Thú Sơn Mạch**\n→ Yêu thú, Boss, yêu tàng, cổ động phủ và huyết mạch cơ duyên.",
            footer="Khám phá · Chọn vùng",
        ),
        view=ExploreZoneView(message.author.id),
        mention_author=False,
    )


async def command_hunt(message: discord.Message) -> None:
    await command_explore(message)


class AscensionView(discord.ui.View):
    def __init__(self, owner_id:int): super().__init__(timeout=180); self.owner_id=owner_id; self.busy=False
    async def guard(self,i):
        if i.user.id!=self.owner_id: await i.response.send_message("Chỉ người mở Đăng Thiên Lộ mới điều khiển được menu.",ephemeral=True); return False
        if self.busy: await i.response.send_message("Đang xử lý lượt leo tháp.",ephemeral=True); return False
        return True
    async def climb_now(self,i):
        if not await self.guard(i): return
        self.busy=True
        try:
            r=await run_engine(engine.ascension_tower_climb,str(self.owner_id)); s=r['status']
            await i.response.edit_message(embed=make_embed(f"🌌 **ĐĂNG THIÊN LỘ**\n\n{r['text']}\n\n🏆 Cao nhất: **{s['best']}**\n🎫 Lượt còn: **{s['remaining']}**\n🌠 Tầng kế tiếp: **{s['next_floor']}",color=COLOR_SUCCESS if r['success'] else COLOR_WARN,footer="Đăng Thiên Lộ"),view=self)
        except GameError as exc: await i.response.send_message(str(exc),ephemeral=True)
        finally: self.busy=False
    @discord.ui.button(label="Leo 1 tầng",emoji="🌌",style=discord.ButtonStyle.primary,row=0)
    async def climb(self,i:discord.Interaction,b:discord.ui.Button): await self.climb_now(i)
    @discord.ui.button(label="Trạng thái",emoji="📜",style=discord.ButtonStyle.secondary,row=0)
    async def status(self,i:discord.Interaction,b:discord.ui.Button):
        if await self.guard(i):
            p=await run_engine(engine.info,str(self.owner_id)); await i.response.send_message(f"🌌 **ĐĂNG THIÊN LỘ**\n\nDùng nút **Leo 1 tầng** để tiếp tục. Hiện tại: **{engine.realm_text(p)}**.",ephemeral=True)
    @discord.ui.button(label="Đại Điện",emoji="🏠",style=discord.ButtonStyle.secondary,row=0)
    async def home(self,i:discord.Interaction,b:discord.ui.Button):
        if await self.guard(i): await i.response.edit_message(embed=make_plain_embed("🌌 ĐẠI ĐIỆN KATO TU TIÊN","Chọn hệ thống để tiếp tục."),view=MainMenuView(self.owner_id))
    async def on_timeout(self):
        for c in self.children:c.disabled=True


class SectTowerView(discord.ui.View):
    def __init__(self,owner_id:int): super().__init__(timeout=180); self.owner_id=owner_id; self.busy=False
    async def guard(self,i):
        if i.user.id!=self.owner_id: await i.response.send_message("Chỉ người mở Tháp Tông Môn mới điều khiển được menu.",ephemeral=True); return False
        if self.busy: await i.response.send_message("Đang xử lý lượt leo Tháp Tông Môn.",ephemeral=True); return False
        return True
    @discord.ui.button(label="Leo 1 tầng",emoji="🏯",style=discord.ButtonStyle.primary,row=0)
    async def climb(self,i:discord.Interaction,b:discord.ui.Button):
        if not await self.guard(i): return
        self.busy=True
        try:
            r=await run_engine(engine.sect_tower_climb,str(self.owner_id)); s=r['status']
            await i.response.edit_message(embed=make_embed(f"🏯 **THÁP TÔNG MÔN · {s['sect_name']}**\n\n{r['text']}\n\n🏆 Cao nhất: **{s['best']}**\n🎫 Lượt còn: **{s['remaining']}**\n🌠 Tầng kế tiếp: **{s['next_floor']}",color=COLOR_SUCCESS if r['success'] else COLOR_WARN,footer="Tháp Tông Môn"),view=self)
        except GameError as exc: await i.response.send_message(str(exc),ephemeral=True)
        finally:self.busy=False
    @discord.ui.button(label="BXH Tông",emoji="🏆",style=discord.ButtonStyle.secondary,row=0)
    async def rank(self,i:discord.Interaction,b:discord.ui.Button):
        if await self.guard(i):
            rows=await run_engine(engine.sect_tower_leaderboard,10); lines=["🏆 **BXH THÁP TÔNG MÔN**"]
            for n,r in enumerate(rows,1): lines.append(f"#{n} **{r.get('name','Tông Môn')}** · tầng {r.get('best_floor',0)}")
            await i.response.send_message(embed=make_embed("\n".join(lines)),ephemeral=True)
    @discord.ui.button(label="Đại Điện",emoji="🏠",style=discord.ButtonStyle.secondary,row=0)
    async def home(self,i:discord.Interaction,b:discord.ui.Button):
        if await self.guard(i): await i.response.edit_message(embed=make_plain_embed("🌌 ĐẠI ĐIỆN KATO TU TIÊN","Chọn hệ thống để tiếp tục."),view=MainMenuView(self.owner_id))
    async def on_timeout(self):
        for c in self.children:c.disabled=True


async def command_thang_thien(message: discord.Message) -> None:
    status = await run_engine(engine.ascension_tower_status, str(message.author.id)) if hasattr(engine, "ascension_tower_status") else None
    text = "Đây là Đăng Thiên Lộ: thử thách cột mốc cá nhân, không phải nơi farm buff vĩnh viễn."
    if status: text += f"\n\n🏆 Cao nhất: **{status.get('best',0)}** · 🎫 Lượt còn: **{status.get('remaining','?')}** · 🌠 Kế tiếp: **{status.get('next_floor','?')}**"
    await message.reply(embed=make_embed("🌌 **ĐĂNG THIÊN LỘ**\n\n"+text),view=AscensionView(message.author.id),mention_author=False)

async def command_thap_tong(message: discord.Message) -> None:
    status = await run_engine(engine.sect_tower_status, str(message.author.id))
    await message.reply(embed=make_embed(f"🏯 **THÁP TÔNG MÔN · {status['sect_name']}**\n\nTông Môn cùng tiến độ một tháp chung.\n🏆 Tầng cao nhất: **{status['best']}**\n🎫 Lượt còn hôm nay: **{status['remaining']}**\n🌠 Tầng kế tiếp: **{status['next_floor']}"),view=SectTowerView(message.author.id),mention_author=False)

class DaoGiftModal(discord.ui.Modal, title="🎁 Tặng Đạo Lữ"):
    item_id = discord.ui.TextInput(label="Mã vật phẩm", placeholder="vi_du: truc_co_dan", required=True, max_length=64)
    quantity = discord.ui.TextInput(label="Số lượng", placeholder="1", required=True, max_length=4)
    def __init__(self, owner_id: int):
        super().__init__(); self.owner_id = owner_id
    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Không thuộc phiên Đạo Lữ này.", ephemeral=True); return
        try:
            qty = int(str(self.quantity.value).strip())
            result = await run_engine(engine.dao_lu_gift, str(self.owner_id), str(self.item_id.value).strip().lower(), qty)
            await interaction.response.send_message(f"🎁 Đã tặng **{result['item']['name']} ×{result['qty']}** cho Đạo Lữ.", ephemeral=True)
        except (ValueError, TypeError):
            await interaction.response.send_message("Số lượng không hợp lệ.", ephemeral=True)
        except GameError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)


class DaoLuView(discord.ui.View):
    def __init__(self, owner_id: int):
        super().__init__(timeout=180); self.owner_id = owner_id

    async def guard(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Chỉ người mở bảng Đạo Lữ mới điều khiển được menu.", ephemeral=True); return False
        return True

    async def embed(self):
        info = await run_engine(engine.dao_lu_info, str(self.owner_id))
        if not info:
            req = await run_engine(engine.db.get_dao_lu_request, str(self.owner_id))
            extra = f"\n💌 Đang có lời kết duyên từ <@{req['requester_id']}>." if req else ""
            return make_embed("💞 **ĐẠO LỮ**\n\nNgươi hiện đang độc hành." + extra, footer="Đạo Lữ · Thiên duyên")
        partner = await run_engine(engine.info, str(info['partner_id']))
        return make_embed(
            f"💞 **ĐẠO LỮ**\n\n💞 Đạo hữu: <@{partner.user_id}>\n✨ Độ thân mật: **{info['intimacy']}**\n\nChọn một hành động bên dưới.",
            footer="Đạo Lữ · Thiên duyên",
        )

    @discord.ui.button(label="Song Tu", emoji="☯️", style=discord.ButtonStyle.success, row=0)
    async def songtu(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.guard(interaction): return
        try:
            result = await run_engine(engine.dao_lu_song_tu, str(self.owner_id))
            await interaction.response.edit_message(
                embed=make_embed(
                    f"☯️ **SONG TU THÀNH CÔNG**\n\nNgươi +**{fmt(result['gain'])}** tu vi\nĐạo Lữ +**{fmt(result['partner_gain'])}** tu vi\n✨ Thân mật: **{result['intimacy']}**",
                    color=COLOR_SUCCESS,
                    footer="Đạo Lữ · Song Tu",
                ),
                view=self,
            )
        except GameError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)

    @discord.ui.button(label="Tặng Đạo", emoji="🎁", style=discord.ButtonStyle.primary, row=0)
    async def gift(self, interaction: discord.Interaction, button: discord.ui.Button):
        if await self.guard(interaction):
            await interaction.response.send_modal(DaoGiftModal(self.owner_id))

    @discord.ui.button(label="Làm mới", emoji="🔄", style=discord.ButtonStyle.secondary, row=0)
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        if await self.guard(interaction):
            await interaction.response.edit_message(embed=await self.embed(), view=self)

    @discord.ui.button(label="Hủy Duyên", emoji="💔", style=discord.ButtonStyle.danger, row=1)
    async def breakup(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.guard(interaction): return
        try:
            result = await run_engine(engine.break_dao_lu, str(self.owner_id))
            await interaction.response.edit_message(
                embed=make_embed(f"💔 Đạo duyên với <@{result['partner_id']}> đã chấm dứt.", color=COLOR_WARN, footer="Đạo Lữ · Đã chia tay"),
                view=None,
            )
        except GameError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)

    @discord.ui.button(label="Đại Điện", emoji="🏠", style=discord.ButtonStyle.secondary, row=1)
    async def home(self, interaction: discord.Interaction, button: discord.ui.Button):
        if await self.guard(interaction):
            await interaction.response.edit_message(embed=make_plain_embed("🌌 ĐẠI ĐIỆN KATO TU TIÊN", "Chọn hệ thống để tiếp tục."), view=MainMenuView(self.owner_id))

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True


async def command_daolu(message: discord.Message) -> None:
    view=DaoLuView(message.author.id)
    await message.reply(embed=await view.embed(),view=view,mention_author=False)


class DaoLuRequestView(discord.ui.View):
    def __init__(self, requester_id: int, target_id: int):
        super().__init__(timeout=180)
        self.requester_id = requester_id
        self.target_id = target_id
        self.done = False

    async def ensure_target(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.target_id:
            await interaction.response.send_message("Lời kết duyên này không thuộc về ngươi.", ephemeral=True)
            return False
        return True

    def disable_all(self):
        for child in self.children: child.disabled = True

    @discord.ui.button(label="Đồng ý", emoji=DONG_Y_ICON, style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.ensure_target(interaction): return
        if self.done: return
        self.done = True; self.disable_all()
        await interaction.response.defer()
        try:
            result = await run_engine(engine.accept_dao_lu, str(self.target_id))
            await interaction.edit_original_response(embed=make_embed(
                f"💞 **KẾT DUYÊN THÀNH CÔNG**\n\n<@{self.requester_id}> và <@{self.target_id}> đã trở thành Đạo Lữ.",
                color=COLOR_SUCCESS, footer="Đạo Lữ · Thiên duyên đã định"), view=self)
        except GameError as exc:
            self.done = False
            for child in self.children: child.disabled = False
            await interaction.edit_original_response(content=str(exc), view=self)
        except Exception as exc:
            logger.exception("Unhandled error: %s", exc)
            self.done = False
            for child in self.children: child.disabled = False
            await interaction.edit_original_response(content="Đã xảy ra lỗi khi kết duyên. Lời cầu duyên vẫn được giữ; hãy thử lại.", view=self)

    @discord.ui.button(label="Từ chối", emoji=TU_CHOI_ICON, style=discord.ButtonStyle.secondary)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.ensure_target(interaction): return
        if self.done: return
        self.done = True; self.disable_all()
        await run_engine(engine.reject_dao_lu, str(self.target_id))
        await interaction.response.edit_message(embed=make_embed(
            f"💞 **LỜI KẾT DUYÊN ĐÃ BỊ TỪ CHỐI**\n\n<@{self.target_id}> đã từ chối lời kết duyên.",
            color=COLOR_WARN, footer="Đạo Lữ · Đã từ chối"), view=self)


async def command_request_daolu(message: discord.Message) -> None:
    if not message.mentions: raise GameError("Cú pháp: `.ketduyen @người`")
    target = message.mentions[0]
    await run_engine(engine.request_dao_lu, str(message.author.id), str(target.id))
    await message.reply(
        content=f"<@{target.id}>",
        embed=make_embed(f"💞 **LỜI KẾT DUYÊN**\n\n**{message.author.display_name}** muốn kết thành Đạo Lữ với ngươi.\n\nHãy quyết định như khi Đột Phá: **Đồng ý** hoặc **Từ chối**.", color=COLOR_WARN, footer="Đạo Lữ · Chờ quyết định"),
        view=DaoLuRequestView(message.author.id, target.id), mention_author=False
    )


async def command_accept_daolu(message: discord.Message) -> None:
    result = await run_engine(engine.accept_dao_lu, str(message.author.id))
    await reply_ui(message, f"💞 **KẾT DUYÊN THÀNH CÔNG**\nNgươi và <@{result['partner_id']}> đã trở thành Đạo Lữ.", color=COLOR_SUCCESS)


async def command_reject_daolu(message: discord.Message) -> None:
    await run_engine(engine.reject_dao_lu, str(message.author.id)); await reply_ui(message, "Lời kết duyên đã được khước từ.", color=COLOR_WARN)


async def command_break_daolu(message: discord.Message) -> None:
    result = await run_engine(engine.break_dao_lu, str(message.author.id)); await reply_ui(message, f"Đạo duyên với <@{result['partner_id']}> đã chấm dứt.", color=COLOR_WARN)


async def command_songtu(message: discord.Message) -> None:
    result = await run_engine(engine.dao_lu_song_tu, str(message.author.id)); await reply_ui(message, f"☯️ **SONG TU**\nNgươi nhận **+{fmt(result['gain'])} tu vi** · <@{result['partner'].user_id}> nhận **+{fmt(result['partner_gain'])} tu vi**.\nĐộ thân mật +3 → **{result['intimacy']}**.", color=COLOR_SUCCESS)


async def command_daolu_gift(message: discord.Message, args: list[str]) -> None:
    if not args: raise GameError("Cú pháp: `.tangdao <item> [sl]`")
    qty = int(args[1]) if len(args) > 1 else 1
    result = await run_engine(engine.dao_lu_gift, str(message.author.id), args[0].lower(), qty)
    await reply_ui(message, f"🎁 Đã tặng Đạo Lữ **{result['item']['name']} ×{qty}**. Độ thân mật tăng thêm **{max(1, qty)}**.", color=COLOR_SUCCESS)




def sect_dashboard(owner_id: int | str) -> dict:
    """Load the complete sect screen state in one synchronous DB batch."""
    uid = str(owner_id)
    member = engine.sect_info(uid)
    owner = engine.sect_is_owner(uid) if member else False
    return {"member": member, "owner": owner, "sects": engine.list_all_sects()}


class SectCreateModal(discord.ui.Modal, title="🏯 Sáng Lập Tông Môn"):
    name = discord.ui.TextInput(label="Tên Tông Môn", placeholder="Ví dụ: Cửu Thiên Kiếm Tông", min_length=2, max_length=30)
    description = discord.ui.TextInput(label="Tông quy / giới thiệu", placeholder="Đạo thống của ngươi theo đuổi điều gì?", style=discord.TextStyle.paragraph, min_length=4, max_length=180)

    def __init__(self, owner_id: int):
        super().__init__()
        self.owner_id = owner_id

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Thiên cơ này không thuộc về ngươi.", ephemeral=True)
            return
        await interaction.response.defer()
        try:
            sect = await run_engine(engine.create_sect, str(self.owner_id), str(self.name.value), str(self.description.value))
            dashboard = await run_engine(sect_dashboard, self.owner_id)
            await interaction.edit_original_response(
                embed=sect_embed(self.owner_id, sect["id"], member=dashboard["member"], owner=dashboard["owner"], sects=dashboard["sects"]),
                view=SectView(self.owner_id, dashboard),
            )
        except GameError as exc:
            await interaction.edit_original_response(content=str(exc))
        except Exception as exc:
            logger.exception("Unhandled error: %s", exc)
            await interaction.edit_original_response(content="Đã xảy ra lỗi khi sáng lập Tông Môn. Dữ liệu nhân vật được giữ nguyên; hãy thử lại.")


class SectSelect(discord.ui.Select):
    def __init__(self, view: "SectView", sects: list[dict]):
        self.sect_view = view
        options = []
        for sect in sects[:25]:
            path_text = "Tiên đạo" if sect["path"] == "tien" else ("Ma đạo" if sect["path"] == "ma" else "Lưỡng đạo")
            owner_text = f"Tông chủ <@{sect['owner_id']}>" if sect.get("owner_id") else "Tông Môn NPC / hệ thống"
            options.append(discord.SelectOption(label=sect["name"][:100], value=sect["id"], description=f"{path_text} · {owner_text}"[:100], emoji="🏯"))
        if not options:
            options = [discord.SelectOption(label="Chưa có Tông Môn khả dụng", value="__empty__", description="Hãy trở thành Tông Chủ đầu tiên", emoji="🌌")]
        super().__init__(placeholder="🏯 Chọn Tông Môn của đạo hữu...", min_values=1, max_values=1, options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.sect_view.owner_id:
            await interaction.response.send_message("Chỉ người mở bảng Tông Môn mới có thể dùng menu này.", ephemeral=True)
            return
        value = self.values[0]
        if value == "__empty__":
            await interaction.response.edit_message()
            return
        self.sect_view.selected = value
        self.sect_view.refresh_buttons()
        await interaction.response.edit_message(
            embed=sect_embed(self.sect_view.owner_id, value, member=self.sect_view.member, owner=self.sect_view.is_owner, sects=self.sect_view.sects),
            view=self.sect_view,
        )


class SectView(discord.ui.View):
    def __init__(self, owner_id: int, dashboard: dict):
        super().__init__(timeout=180)
        self.owner_id = owner_id
        self.member = dashboard.get("member")
        self.is_owner = bool(dashboard.get("owner"))
        self.sects = list(dashboard.get("sects", []))
        self.selected = None
        self.select = SectSelect(self, self.sects)
        self.join_button = discord.ui.Button(label="Gia nhập", emoji=DONG_Y_ICON, style=discord.ButtonStyle.success, row=1)
        self.create_button = discord.ui.Button(label="Sáng lập", emoji="🏯", style=discord.ButtonStyle.primary, row=1)
        self.manage_button = discord.ui.Button(label="Giải tán", emoji="🗑️", style=discord.ButtonStyle.danger, row=1)
        self.join_button.callback = self.join_callback
        self.create_button.callback = self.create_callback
        self.manage_button.callback = self.dissolve_callback
        self.add_item(self.select); self.add_item(self.join_button); self.add_item(self.create_button); self.add_item(self.manage_button)
        self.refresh_buttons()

    def refresh_buttons(self):
        self.join_button.disabled = not self.selected or bool(self.member)
        self.create_button.disabled = bool(self.member)
        self.manage_button.disabled = not self.is_owner

    async def create_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Chỉ người mở bảng Tông Môn mới có thể thao tác.", ephemeral=True)
            return
        await interaction.response.send_modal(SectCreateModal(self.owner_id))

    async def join_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Chỉ người mở bảng Tông Môn mới có thể thao tác.", ephemeral=True)
            return
        await interaction.response.defer()
        try:
            sect = await run_engine(engine.join_sect, str(self.owner_id), self.selected)
            dashboard = await run_engine(sect_dashboard, self.owner_id)
            await interaction.edit_original_response(
                embed=sect_embed(self.owner_id, sect["id"], member=dashboard["member"], owner=dashboard["owner"], sects=dashboard["sects"]),
                view=SectView(self.owner_id, dashboard),
            )
        except GameError as exc:
            await interaction.edit_original_response(content=str(exc), view=self)
        except Exception as exc:
            logger.exception("Unhandled error: %s", exc)
            await interaction.edit_original_response(content="Đã xảy ra lỗi khi gia nhập Tông Môn. Hãy thử lại.", view=self)

    async def dissolve_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Chỉ người mở bảng Tông Môn mới có thể thao tác.", ephemeral=True)
            return
        await interaction.response.defer()
        try:
            await run_engine(engine.dissolve_sect, str(self.owner_id))
            dashboard = await run_engine(sect_dashboard, self.owner_id)
            await interaction.edit_original_response(
                embed=sect_embed(self.owner_id, member=dashboard["member"], owner=dashboard["owner"], sects=dashboard["sects"]),
                view=SectView(self.owner_id, dashboard),
            )
        except GameError as exc:
            await interaction.edit_original_response(content=str(exc), view=self)
        except Exception as exc:
            logger.exception("Unhandled error: %s", exc)
            await interaction.edit_original_response(content="Đã xảy ra lỗi khi giải tán Tông Môn. Hãy thử lại.", view=self)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True


def sect_embed(owner_id: int, sect_id: str | None = None, *, member=None, owner: bool | None = None, sects: list[dict] | None = None) -> discord.Embed:
    if member is None or owner is None or sects is None:
        dashboard = sect_dashboard(owner_id)
        member = dashboard["member"]
        owner = dashboard["owner"]
        sects = dashboard["sects"]
    if not sect_id:
        lines = ["🏯 **TÔNG MÔN**", "", "Có Tông Môn người chơi và Tông Môn NPC/hệ thống. Mỗi đạo hữu chỉ thuộc một Tông Môn tại một thời điểm."]
        if member:
            actual_role = member.get("role") or ("Tông Chủ" if owner else "Đệ Tử")
            lines += ["", f"Tông Môn hiện tại: **{member['name']}**", f"Chức vụ: **{actual_role}**", f"Hạng cống hiến: **{engine.sect_rank(int(member['contribution']))}** · Cống hiến: **{fmt(int(member['contribution']))}"]
        return make_embed("\n".join(lines), footer="Tông Môn · Đạo thống")
    sect = next((x for x in sects if x["id"] == sect_id), None)
    if not sect:
        return make_embed("Tông Môn không tồn tại hoặc đã giải tán.", color=COLOR_ERROR)
    path_text = "Tiên đạo" if sect["path"] == "tien" else ("Ma đạo" if sect["path"] == "ma" else "Lưỡng đạo")
    owner_text = f"<@{sect['owner_id']}>" if sect.get("owner_id") else "Hệ thống / NPC"
    lines = [f"🏯 **{sect['name']}**", "", sect["description"], "", f"👑 Tông Chủ: {owner_text}", f"☯️ Đạo thống: **{path_text}**", f"🌿 Linh Mạch: **cấp {sect.get('linh_mach_level', 0)}** · Buff tu luyện **+{sect.get('bonus_percent', 0)}%**", f"📈 Cấp Tông: **{sect.get('level', 1)}** · EXP **{sect.get('exp', 0)}**"]
    if member and member["sect_id"] == sect_id:
        actual_role = member.get("role") or ("Tông Chủ" if str(sect.get("owner_id") or "") == str(owner_id) else "Đệ Tử")
        lines += ["", f"Chức vụ: **{actual_role}**", f"Hạng cống hiến: **{engine.sect_rank(int(member['contribution']))}** · Cống hiến: **{fmt(int(member['contribution']))}"]
    return make_embed("\n".join(lines), footer="Tông Môn · Thông tin đạo thống")


class SectManageView(discord.ui.View):
    def __init__(self, owner_id:int):
        super().__init__(timeout=180); self.owner_id=owner_id
        for label,emoji,style,cb in [("Top cống hiến","🏆",discord.ButtonStyle.primary,self.top), ("Môn nhân","👥",discord.ButtonStyle.secondary,self.members), ("Nhiệm vụ","📜",discord.ButtonStyle.secondary,self.missions), ("Rời Tông","🚪",discord.ButtonStyle.danger,self.leave)]:
            b=discord.ui.Button(label=label,emoji=emoji,style=style,row=0); b.callback=cb; self.add_item(b)
        self.role_button=discord.ui.Button(label="Trao chức",emoji="👑",style=discord.ButtonStyle.success,row=1); self.role_button.callback=self.role; self.add_item(self.role_button)
        rank_button=discord.ui.Button(label="BXH Tông Môn",emoji="🏆",style=discord.ButtonStyle.primary,row=1); rank_button.callback=self.sect_rank; self.add_item(rank_button)
        self.linh_mach_button=discord.ui.Button(label="Nâng Linh Mạch",emoji="🌿",style=discord.ButtonStyle.success,row=1); self.linh_mach_button.callback=self.linh_mach; self.add_item(self.linh_mach_button)
        self.dissolve_button=discord.ui.Button(label="Giải tán",emoji="🗑️",style=discord.ButtonStyle.danger,row=1); self.dissolve_button.callback=self.dissolve; self.add_item(self.dissolve_button)
        self.refresh_owner_state()

    def refresh_owner_state(self):
        try: is_owner = engine.sect_is_owner(str(self.owner_id))
        except Exception: is_owner = False
        for b in (self.role_button,self.linh_mach_button,self.dissolve_button): b.disabled = not is_owner

    async def guard(self,i):
        if i.user.id!=self.owner_id: await i.response.send_message("Chỉ người mở Nội Vụ mới có thể thao tác.",ephemeral=True); return False
        return True
    async def top(self,i):
        if not await self.guard(i): return
        o=await run_engine(engine.sect_overview,str(self.owner_id)); ms=sorted(o['members'],key=lambda x:int(x['contribution']),reverse=True)[:10]; text="🏆 **TOP CỐNG HIẾN**\n"+"\n".join(f"#{n} <@{m['user_id']}> · {fmt(int(m['contribution']))}" for n,m in enumerate(ms,1)); await i.response.send_message(embed=make_embed(text,footer="Nội Vụ Tông Môn"),ephemeral=True)
    async def members(self,i):
        if not await self.guard(i): return
        o=await run_engine(engine.sect_overview,str(self.owner_id)); text="👥 **MÔN NHÂN**\n"+"\n".join(f"<@{m['user_id']}> · {m.get('role','Đệ Tử')} · {engine.sect_rank(int(m.get('contribution',0)))} · {engine.realm_text(await run_engine(engine.info,str(m['user_id'])))}" for m in o['members'][:25]); await i.response.send_message(embed=make_embed(text,footer="Nội Vụ Tông Môn"),ephemeral=True)
    async def missions(self,i):
        if not await self.guard(i): return
        ms=await run_engine(engine.sect_mission_list,str(self.owner_id)); text="📜 **NHIỆM VỤ**\n"+"\n".join(f"`{m['key']}` {m['name']} · {m['progress']}/{m['target']}" for m in ms); await i.response.send_message(embed=make_embed(text+"\n\nDùng `.nvtong <mã>` để nhận thưởng."),ephemeral=True)
    async def leave(self,i):
        if not await self.guard(i): return
        if await run_engine(engine.sect_is_owner,str(self.owner_id)): await i.response.send_message("Tông Chủ phải chuyển quyền hoặc giải tán Tông Môn trước.",ephemeral=True); return
        await run_engine(engine.leave_sect,str(self.owner_id)); await i.response.edit_message(embed=make_embed("🚪 Đã rời Tông Môn."),view=None)
    async def role(self,i):
        if not await self.guard(i): return
        if not await run_engine(engine.sect_is_owner,str(self.owner_id)): await i.response.send_message("Chỉ Tông Chủ mới có thể trao chức.",ephemeral=True); return
        await i.response.send_modal(SectRoleModal(self.owner_id))
    async def sect_rank(self,i):
        if not await self.guard(i): return
        rows=await run_engine(engine.sect_leaderboard,10); text="🏆 **BXH TÔNG MÔN**\n"+"\n".join(f"#{n} **{r['name']}** · cấp {r['level']} · {fmt(int(r['contribution']))} cống hiến · {r['members']} môn nhân" for n,r in enumerate(rows,1)); await i.response.send_message(embed=make_embed(text),ephemeral=True)
    async def linh_mach(self,i):
        if not await self.guard(i): return
        if not await run_engine(engine.sect_is_owner,str(self.owner_id)): await i.response.send_message("Chỉ Tông Chủ mới có thể nâng cấp Linh Mạch.",ephemeral=True); return
        try:
            result=await run_engine(engine.upgrade_sect_linh_mach,str(self.owner_id))
            await i.response.send_message(f"🌿 **LINH MẠCH NÂNG CẤP**\nCấp mới: **{result.get('linh_mach_level',0)}/5**\nBuff toàn Tông: **+{result.get('bonus_percent',0)}%** tu luyện.",ephemeral=True)
        except GameError as exc: await i.response.send_message(str(exc),ephemeral=True)
    async def dissolve(self,i):
        if not await self.guard(i): return
        if not await run_engine(engine.sect_is_owner,str(self.owner_id)): await i.response.send_message("Chỉ Tông Chủ mới có thể giải tán Tông Môn.",ephemeral=True); return
        await run_engine(engine.dissolve_sect,str(self.owner_id)); await i.response.edit_message(embed=make_embed("🗑️ Tông Môn đã giải tán."),view=None)

class SectRoleModal(discord.ui.Modal,title="👑 Trao Chức Tông Môn"):
    target_id=discord.ui.TextInput(label="Discord User ID",placeholder="ID môn nhân",min_length=1,max_length=30)
    role=discord.ui.TextInput(label="Chức vụ",placeholder="Đệ Tử / Hộ Pháp / Trưởng Lão / Phó Tông Chủ / Tông Chủ",min_length=3,max_length=20)
    def __init__(self,owner_id:int): super().__init__(); self.owner_id=owner_id
    async def on_submit(self,interaction:discord.Interaction):
        if interaction.user.id!=self.owner_id: await interaction.response.send_message("Không thuộc phiên Nội Vụ này.",ephemeral=True); return
        try:
            await run_engine(engine.sect_change_role,str(self.owner_id),str(self.target_id.value).strip(),str(self.role.value).strip()); await interaction.response.send_message("👑 Đã cập nhật chức vụ môn nhân.",ephemeral=True)
        except GameError as exc: await interaction.response.send_message(str(exc),ephemeral=True)

async def command_sect(message: discord.Message) -> None:
    dashboard = await run_engine(sect_dashboard, message.author.id)
    if dashboard["member"]:
        o=await run_engine(engine.sect_overview,str(message.author.id)); m=o["member"]; sct=o["sect"]; actual_role=m.get("role") or ("Tông Chủ" if dashboard["owner"] else "Đệ Tử"); contribution_rank=engine.sect_rank(int(m["contribution"]))
        text=f"🏯 **{sct['name']} — NỘI VỤ**\n\n{str(sct['description'])}\n\n👑 Chức vụ: **{actual_role}**\n🏅 Hạng cống hiến: **{contribution_rank}**\n✨ Cống hiến: **{fmt(int(m['contribution']))}**\n👥 Môn nhân: **{len(o['members'])}**\n💎 Tông Khố: **{fmt(int(o['treasury']))}**\n🌿 Linh Mạch: **cấp {sct.get('linh_mach_level',0)} · +{sct.get('bonus_percent',0)}%**\n📈 Cấp Tông: **{sct.get('level',1)}** · EXP **{sct.get('exp',0)}**"
        await message.reply(embed=make_embed(text,footer="Tông Môn · Nội Vụ"),view=SectManageView(message.author.id),mention_author=False); return
    await message.reply(embed=sect_embed(message.author.id, member=dashboard["member"], owner=dashboard["owner"], sects=dashboard["sects"]),view=SectView(message.author.id,dashboard),mention_author=False)


async def command_sect_contribute(message: discord.Message, args: list[str]) -> None:
    if not args:
        raise GameError("Cú pháp: `.congtong <linh_thach>`")
    result = await run_engine(engine.sect_contribute, str(message.author.id), int(args[0]))
    actual_role = str(result.get("role") or ("Tông Chủ" if await run_engine(engine.sect_is_owner, str(message.author.id)) else "Đệ Tử"))
    contribution_rank = await run_engine(engine.sect_rank, int(result['contribution']))
    await reply_ui(message, f"🏯 **CỐNG HIẾN TÔNG MÔN**\n\n{LINH_THACH_ICON} -`{fmt(int(args[0]))}`\n✨ Cống hiến: **{fmt(int(result['contribution']))}**\n👑 Chức vụ: **{actual_role}**\n🏅 Hạng cống hiến: **{contribution_rank}**\n💎 Tông Khố: **{fmt(int(result.get('treasury', 0)))}**", color=COLOR_SUCCESS)


async def command_linh_mach(message: discord.Message) -> None:
    overview = await run_engine(engine.sect_overview, str(message.author.id))
    sect = overview["sect"]
    level = int(sect.get("linh_mach_level", 0))
    if level >= 5:
        await reply_ui(message, f"🌿 Linh Mạch đã đạt **cấp {level}/5** · Buff tu luyện **+{sect.get('bonus_percent',0)}%**.", color=COLOR_INFO)
        return
    cost = 15000 * (level + 1)
    await reply_ui(message, f"🌿 **LINH MẠCH TÔNG MÔN**\nCấp hiện tại: **{level}/5**\nCấp tiếp theo: **{level+1}**\nChi phí: **{fmt(cost)} Linh Thạch Tông Khố**\nChỉ **Tông Chủ** có thể nâng cấp bằng nút trong Nội Vụ.")

class PvpChallengeView(discord.ui.View):
    def __init__(self, challenge_id: int, target_id: int):
        super().__init__(timeout=600); self.challenge_id=challenge_id; self.target_id=target_id; self.busy=False
    async def guard_target(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.target_id:
            await interaction.response.send_message("Chỉ người bị thách đấu mới có thể quyết định.", ephemeral=True); return False
        if self.busy:
            await interaction.response.send_message("Lời đấu đang được xử lý.", ephemeral=True); return False
        return True
    @discord.ui.button(label="Chấp nhận", emoji="⚔️", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.guard_target(interaction): return
        self.busy=True
        for child in self.children: child.disabled=True
        await interaction.response.defer()
        try:
            result=await run_engine(engine.resolve_pvp,self.challenge_id,str(self.target_id))
            winner=int(result['winner_id']); loser=int(result['loser_id']); stake=result['stake']
            rounds=result.get('rounds', [])
            log=[]
            for r in rounds[-8:]:
                actor = result['challenger'].name if r['attacker']=='c' else result['target'].name
                crit = ' 💥' if r.get('crit') else ''
                log.append(f"**R{r['round']}** · ⚔️ {actor} -{fmt(int(r['damage']))}{crit}")
            if stake.get('type')=='stones': reward=f"{fmt(int(stake['amount']))} Linh Thạch"
            else: reward=f"{ITEMS.get(stake['item_id'],{}).get('name',stake['item_id'])} ×{stake['amount']}"
            text=(f"⚔️ **KẾT QUẢ PVP**\n\n🏆 Người thắng: <@{winner}>\n💠 Người thua: <@{loser}>\n"
                  f"📜 **Diễn biến:**\n" + ("\n".join(log) if log else "Trận đấu kết thúc trong thế giằng co.") +
                  f"\n\n🎁 Người thắng nhận: **{reward}**.")
            await interaction.edit_original_response(embed=make_embed(text,color=COLOR_SUCCESS,footer="PvP · Quyết đấu hoàn tất"),view=None)
        except GameError as exc:
            await interaction.edit_original_response(content=f"❌ {exc}",embed=None,view=None)

    @discord.ui.button(label="Từ chối", emoji="✖️", style=discord.ButtonStyle.secondary)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.guard_target(interaction): return
        self.busy=True
        await run_engine(engine.decline_pvp,self.challenge_id,str(self.target_id))
        await interaction.response.edit_message(embed=make_embed("✖️ **LỜI THÁCH ĐẤU ĐÃ BỊ TỪ CHỐI**",color=COLOR_WARN,footer="PvP · Đã từ chối"),view=None)
    async def on_timeout(self):
        try: await run_engine(db.close_pvp_challenge,self.challenge_id)
        except Exception: pass
        for child in self.children: child.disabled=True

async def command_pvp(message: discord.Message, args: list[str]) -> None:
    if not message.mentions or len(args) < 2:
        raise GameError("Cú pháp: `.pvp @người lt <số>` hoặc `.pvp @người item <item> <sl>`")
    target = message.mentions[0]
    mode = args[1].lower()
    if mode in {"lt", "linhthach", "linh"}:
        if len(args) < 3:
            raise GameError("Cú pháp: `.pvp @người lt <số>`")
        bet_type, item_id, amount = "stones", None, int(args[2])
    elif mode == "item":
        if len(args) < 4:
            raise GameError("Cú pháp: `.pvp @người item <item> <sl>`")
        bet_type, item_id, amount = "item", args[2].lower(), int(args[3])
    else:
        raise GameError("Loại cược chỉ gồm `lt` hoặc `item`.")
    result = await run_engine(engine.pvp_challenge, str(message.author.id), str(target.id), bet_type, item_id, amount)
    preview = await run_engine(engine.pvp_preview, str(message.author.id), str(target.id))
    if bet_type == "stones":
        stake_text = f"{fmt(amount)} {LINH_THACH_ICON}"
    else:
        stake_text = f"{ITEMS[item_id]['name']} ×{amount}"
    cs, ts = preview["challenger_stats"], preview["target_stats"]
    text=(f"⚔️ **LỜI THÁCH ĐẤU PVP**\n\n"
          f"🗡️ **{message.author.display_name}** · HP {fmt(cs['hp'])} · Công {fmt(cs['attack'])} · Thủ {fmt(cs['defense'])}\n"
          f"🛡️ **{target.display_name}** · HP {fmt(ts['hp'])} · Công {fmt(ts['attack'])} · Thủ {fmt(ts['defense'])}\n\n"
          f"📊 Ước tính: **{preview['challenger_chance']:.0f}%** / **{preview['target_chance']:.0f}%**\n"
          f"💰 Mỗi bên cược: **{stake_text}**\n\n"
          f"<@{target.id}> hãy chọn **⚔️ Chấp nhận** hoặc **✖️ Từ chối**.")
    await message.reply(embed=make_embed(text, color=COLOR_WARN, footer="PvP · Lời thách đấu · 10 phút"),
                        view=PvpChallengeView(result["id"], target.id), mention_author=False)

async def command_be_quan(message: discord.Message) -> None:
    result = await run_engine(engine.start_be_quan, str(message.author.id))
    if result.get("first_cycle_paid"):
        await reply_ui(message, f"🧘 **BẾ QUAN ĐÃ BẮT ĐẦU**\n\nĐã khấu trừ **{BE_QUAN_COST} Linh Thạch** cho chu kỳ đầu tiên.\nSau mỗi **5 phút**, bot sẽ tự động tu luyện và tính thưởng ngay cả khi ngươi offline.\n\nDùng `.bequan` để cập nhật trạng thái · `.xuatquan` để xuất quan.", color=COLOR_SUCCESS)
        return
    processed = result.get("processed") or {}
    extra = ""
    if processed.get("cycles"):
        extra = f"\nVừa xử lý **{processed['cycles']} chu kỳ** · +**{fmt(processed.get('gain', 0))} tu vi**."
        if processed.get("drops"):
            extra += "\n🎁 " + ", ".join(processed["drops"])
    if not result.get("active"):
        await reply_ui(message, f"🧘 **BẾ QUAN ĐÃ TỰ ĐỘNG KẾT THÚC**\n\nKhông đủ Linh Thạch để duy trì thêm chu kỳ.{extra}", color=COLOR_WARN)
        return
    remain = result["remaining"]
    minutes, seconds = divmod(remain, 60)
    await reply_ui(message, f"🧘 **BẾ QUAN ĐANG DIỄN RA**\n\nChu kỳ tiếp theo sau **{minutes}m {seconds}s**.\nChi phí: **{BE_QUAN_COST} Linh Thạch / 5 phút**.{extra}", color=COLOR_INFO)

async def command_xuat_quan(message: discord.Message) -> None:
    result = await run_engine(engine.stop_be_quan, str(message.author.id))
    processed = result.get("processed") or {}
    extra = f"\nĐã xử lý **{processed.get('cycles', 0)} chu kỳ** · +**{fmt(processed.get('gain', 0))} tu vi**." if processed else ""
    await reply_ui(message, f"🧘 **XUẤT QUAN**\n\nĐã kết thúc Bế Quan. Linh Thạch còn lại: **{fmt(result['player'].spirit_stones)}**.{extra}", color=COLOR_WARN)


def shop_items_for_category(category: str) -> list[tuple[str, dict]]:
    items = []
    for item_id in SHOP_ORDER:
        item = ITEMS.get(item_id)
        if not item:
            continue
        if category == "all" or item.get("category") == category:
            items.append((item_id, item))
    return items


def shop_embed(category: str = "all", page: int = 0, selected_item: str | None = None, player=None) -> discord.Embed:
    items = shop_items_for_category(category)
    per_page = 8
    max_page = max(0, (len(items) - 1) // per_page)
    page = max(0, min(page, max_page))
    start = page * per_page
    visible = items[start:start + per_page]
    icon = category_icon(category)
    title = f"{icon} TIÊN PHƯỜNG · {dict((x[0], x[1]) for x in SHOP_CATEGORIES).get(category, 'Tất cả').upper()}"
    lines = [f"Trang **{page + 1}/{max_page + 1}**", ""]
    if player is not None:
        lines.append(f"{LINH_THACH_ICON} Linh Thạch: **{fmt(player.spirit_stones)}**\n")
    if not visible:
        lines.append("Tiên Phường hiện không có vật phẩm trong danh mục này.")
    else:
        for item_id, item in visible:
            mark = " ◀ đã chọn" if item_id == selected_item else ""
            stats = []
            if item.get("attack"):
                stats.append(f"⚔️ {item['attack']}")
            if item.get("defense"):
                stats.append(f"🛡️ {item['defense']}")
            stat_text = " · " + " · ".join(stats) if stats else ""
            lines.append(
                f"**{rarity_icon(item.get('rarity', 'Phàm'))} {item['name']}**{mark}\n"
                f"`{item_id}` · **{fmt(item['price'])}** {LINH_THACH_ICON}{stat_text}\n"
                f"> {item.get('description', '')}"
            )
    if selected_item and selected_item in ITEMS:
        item = ITEMS[selected_item]
        lines.append(f"\n🛒 Đã chọn: **{item['name']}** · dùng nút mua bên dưới.")
    return make_embed("\n".join(lines), color=COLOR_MAIN, footer="Tiên Phường · `.mua <item> [sl]` vẫn dùng được")


class ShopCategorySelect(discord.ui.Select):
    def __init__(self, view: "ShopView"):
        self.shop_view = view
        options = [
            discord.SelectOption(label=label, value=value, description=desc[:100], emoji=category_icon(value))
            for value, label, desc in SHOP_CATEGORIES
        ]
        super().__init__(placeholder="🛍️ Chọn danh mục Tiên Phường...", options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.shop_view.owner_id:
            await interaction.response.send_message("Chỉ người mở Tiên Phường mới điều khiển được giao diện này.", ephemeral=True)
            return
        self.shop_view.category = self.values[0]
        self.shop_view.page = 0
        self.shop_view.selected_item = None
        self.shop_view.refresh()
        await interaction.response.edit_message(embed=shop_embed(self.shop_view.category, self.shop_view.page, player=await run_engine(engine.info, str(self.shop_view.owner_id))), view=self.shop_view)


class ShopItemSelect(discord.ui.Select):
    def __init__(self, view: "ShopView", items: list[tuple[str, dict]]):
        self.shop_view = view
        options = [
            discord.SelectOption(
                label=f"{item['name']} · {fmt(item['price'])} LT"[:100],
                value=item_id,
                description=f"{item.get('rarity', 'Phàm')} · {item.get('description', '')}"[:100],
                emoji=rarity_icon(item.get('rarity', 'Phàm')),
            )
            for item_id, item in items
        ]
        super().__init__(placeholder="🔎 Chọn vật phẩm để mua...", options=options, row=1)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.shop_view.owner_id:
            await interaction.response.send_message("Chỉ người mở Tiên Phường mới điều khiển được giao diện này.", ephemeral=True)
            return
        self.shop_view.selected_item = self.values[0]
        await interaction.response.edit_message(
            embed=shop_embed(self.shop_view.category, self.shop_view.page, self.shop_view.selected_item, player=await run_engine(engine.info, str(self.shop_view.owner_id))),
            view=self.shop_view,
        )


class ShopView(discord.ui.View):
    def __init__(self, owner_id: int):
        super().__init__(timeout=180)
        self.owner_id = owner_id
        self.category = "all"
        self.page = 0
        self.selected_item: str | None = None
        self.refresh()

    def refresh(self):
        self.clear_items()
        self.add_item(ShopCategorySelect(self))
        items = shop_items_for_category(self.category)
        start = self.page * 8
        visible = items[start:start + 8]
        if visible:
            self.add_item(ShopItemSelect(self, visible))
        prev = discord.ui.Button(label="Trang trước", emoji="◀️", style=discord.ButtonStyle.secondary, row=2)
        next_btn = discord.ui.Button(label="Trang sau", emoji="▶️", style=discord.ButtonStyle.secondary, row=2)
        prev.disabled = self.page <= 0
        next_btn.disabled = start + 8 >= len(items)
        prev.callback = self.prev_page
        next_btn.callback = self.next_page
        self.add_item(prev); self.add_item(next_btn)
        for qty, label, style in [(1, "Mua ×1", discord.ButtonStyle.success), (5, "Mua ×5", discord.ButtonStyle.primary), (10, "Mua ×10", discord.ButtonStyle.primary)]:
            button = discord.ui.Button(label=label, style=style, row=3)
            button.callback = self.make_buy_callback(qty)
            button.disabled = not self.selected_item
            self.add_item(button)

    async def _edit(self, interaction: discord.Interaction):
        player = await run_engine(engine.info, str(self.owner_id))
        self.refresh()
        await interaction.response.edit_message(embed=shop_embed(self.category, self.page, self.selected_item, player=player), view=self)

    async def prev_page(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Chỉ người mở Tiên Phường mới điều khiển được giao diện này.", ephemeral=True); return
        self.page = max(0, self.page - 1); self.selected_item = None
        await self._edit(interaction)

    async def next_page(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Chỉ người mở Tiên Phường mới điều khiển được giao diện này.", ephemeral=True); return
        max_page = max(0, (len(shop_items_for_category(self.category)) - 1) // 8)
        self.page = min(max_page, self.page + 1); self.selected_item = None
        await self._edit(interaction)

    def make_buy_callback(self, qty: int):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.owner_id:
                await interaction.response.send_message("Chỉ người mở Tiên Phường mới điều khiển được giao diện này.", ephemeral=True); return
            if not self.selected_item:
                await interaction.response.send_message("Hãy chọn một vật phẩm trước.", ephemeral=True); return
            await interaction.response.defer()
            try:
                player, item, total = await run_engine(engine.buy, str(self.owner_id), self.selected_item, qty)
                self.selected_item = None
                self.refresh()
                await interaction.edit_original_response(
                    content=f"✅ Đã mua **{item['name']} ×{qty}** với **{fmt(total)}** {LINH_THACH_ICON}. Còn lại **{fmt(player.spirit_stones)}** {LINH_THACH_ICON}.",
                    embed=shop_embed(self.category, self.page, player=player),
                    view=self,
                )
            except GameError as exc:
                await interaction.edit_original_response(content=decorate_currency(str(exc)), embed=shop_embed(self.category, self.page, self.selected_item, player=await run_engine(engine.info, str(self.owner_id))), view=self)
            except Exception as exc:
                logger.exception("Shop purchase failed: %s", exc)
                await interaction.edit_original_response(content="Không thể mua vật phẩm lúc này. Hãy thử lại.", view=self)
        return callback

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True


async def command_shop(message: discord.Message) -> None:
    await message.reply(
        embed=shop_embed(),
        view=ShopView(message.author.id),
        mention_author=False,
    )


async def command_buy(message: discord.Message, args: list[str]) -> None:
    if not args: raise GameError("Cú pháp: `.mua <item> [so_luong]`")
    item_id = args[0].lower(); qty = int(args[1]) if len(args) > 1 else 1
    player, item, total = await run_engine(engine.buy, str(message.author.id), item_id, qty)
    await reply_ui(message, f"Đã mua **{item['name']} ×{qty}** với **{fmt(total)} linh thạch**. Còn lại: **{fmt(player.spirit_stones)}**.", color=COLOR_SUCCESS)


class InventoryUseModal(discord.ui.Modal, title="🎒 Dùng vật phẩm"):
    quantity = discord.ui.TextInput(label="Số lượng", placeholder="Ví dụ: 20", required=True, min_length=1, max_length=4)
    def __init__(self, owner_id: int, item_id: str):
        super().__init__(); self.owner_id = owner_id; self.item_id = item_id
    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Phiên túi đồ này không thuộc về ngươi.", ephemeral=True); return
        try:
            qty = int(str(self.quantity.value).strip())
            result = await run_engine(engine.use_item, str(self.owner_id), self.item_id, qty)
            await interaction.response.send_message(result["text"], ephemeral=True)
        except (ValueError, TypeError):
            await interaction.response.send_message("Số lượng phải là số nguyên.", ephemeral=True)
        except GameError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)


class InventoryView(discord.ui.View):
    def __init__(self, owner_id: int):
        super().__init__(timeout=240); self.owner_id=owner_id; self.category="all"; self.selected=None; self.rows=[]

    async def rebuild(self):
        self.clear_items()
        self.rows = await run_engine(engine.inventory, str(self.owner_id))
        categories = ["all", "Đan dược", "Bùa chú", "Binh khí", "Công pháp", "Linh vật"]
        options = [discord.SelectOption(label=("Tất cả" if c=="all" else c), value=c, emoji=category_icon(c)) for c in categories]
        cat = discord.ui.Select(placeholder="🎒 Chọn loại vật phẩm...", options=options, row=0)
        async def cat_cb(i: discord.Interaction):
            if i.user.id!=self.owner_id: await i.response.send_message("Chỉ người mở Túi mới điều khiển được menu.",ephemeral=True); return
            self.category=cat.values[0]; self.selected=None; await self.rebuild(); await i.response.edit_message(embed=await self.embed(),view=self)
        cat.callback=cat_cb; self.add_item(cat)
        visible=[x for x in self.rows if self.category=="all" or x[1].get("category")==self.category]
        item_options=[discord.SelectOption(label=f"{x[1]['name']} ×{x[2]}"[:100],value=x[0],description=f"{x[1].get('rarity','?')} · {x[1].get('description','')[:70]}",emoji=category_icon(x[1].get('category',''))) for x in visible[:25]]
        if item_options:
            sel=discord.ui.Select(placeholder="🎯 Chọn vật phẩm...",options=item_options,row=1)
            async def sel_cb(i: discord.Interaction):
                if i.user.id!=self.owner_id: await i.response.send_message("Chỉ người mở Túi mới điều khiển được menu.",ephemeral=True); return
                self.selected=sel.values[0]; await i.response.edit_message(embed=await self.embed(),view=self)
            sel.callback=sel_cb; self.add_item(sel)
        use1=discord.ui.Button(label="Dùng ×1",emoji="💊",style=discord.ButtonStyle.primary,row=2)
        use5=discord.ui.Button(label="Dùng ×5",emoji="5️⃣",style=discord.ButtonStyle.primary,row=2)
        use10=discord.ui.Button(label="Dùng ×10",emoji="🔟",style=discord.ButtonStyle.primary,row=2)
        custom=discord.ui.Button(label="Số khác",emoji="🔢",style=discord.ButtonStyle.secondary,row=2)
        equip=discord.ui.Button(label="Trang bị/Học",emoji="⚔️",style=discord.ButtonStyle.success,row=2)
        async def do_use(i, qty):
            if i.user.id!=self.owner_id: await i.response.send_message("Không thuộc phiên Túi này.",ephemeral=True); return
            if not self.selected: await i.response.send_message("Hãy chọn vật phẩm trước.",ephemeral=True); return
            try:
                result=await run_engine(engine.use_item,str(self.owner_id),self.selected,qty); self.rows=await run_engine(engine.inventory,str(self.owner_id)); await i.response.edit_message(embed=await self.embed(),view=self); await i.followup.send(result["text"],ephemeral=True)
            except GameError as exc: await i.response.send_message(str(exc),ephemeral=True)
        use1.callback=lambda i: do_use(i,1); use5.callback=lambda i: do_use(i,5); use10.callback=lambda i: do_use(i,10)
        async def custom_cb(i):
            if i.user.id!=self.owner_id: await i.response.send_message("Không thuộc phiên Túi này.",ephemeral=True); return
            if not self.selected: await i.response.send_message("Hãy chọn vật phẩm trước.",ephemeral=True); return
            await i.response.send_modal(InventoryUseModal(self.owner_id,self.selected))
        custom.callback=custom_cb
        async def equip_cb(i):
            if i.user.id!=self.owner_id: await i.response.send_message("Không thuộc phiên Túi này.",ephemeral=True); return
            if not self.selected: await i.response.send_message("Hãy chọn vật phẩm trước.",ephemeral=True); return
            item=ITEMS.get(self.selected,{})
            try:
                if item.get("type")=="equipment":
                    r=await run_engine(engine.equip,str(self.owner_id),self.selected); msg=f"⚔️ Đã trang bị **{r['item']['name']}**."
                elif item.get("type")=="technique":
                    r=await run_engine(engine.learn_technique,str(self.owner_id),self.selected); msg=f"📜 Đã học **{r['item']['name']}**."
                else:
                    await i.response.send_message("Vật phẩm này dùng bằng nút số lượng.",ephemeral=True); return
                self.rows=await run_engine(engine.inventory,str(self.owner_id)); await i.response.edit_message(embed=await self.embed(),view=self); await i.followup.send(msg,ephemeral=True)
            except GameError as exc: await i.response.send_message(str(exc),ephemeral=True)
        equip.callback=equip_cb
        for b in (use1,use5,use10,custom,equip): self.add_item(b)
        refresh=discord.ui.Button(label="Làm mới",emoji="🔄",style=discord.ButtonStyle.secondary,row=3); refresh.callback=self.refresh; self.add_item(refresh)

    async def embed(self):
        visible=[x for x in self.rows if self.category=="all" or x[1].get("category")==self.category]
        lines=["🎒 **TÚI CÀN KHÔN**",f"Loại vật phẩm: **{('Tất cả' if self.category=='all' else self.category)}**","",f"**{len(visible)} loại vật phẩm**"]
        if not visible: lines.append("\nTúi hiện chưa có vật phẩm ở nhóm này.")
        for item_id,item,count in visible[:12]:
            marker="➡️ " if item_id==self.selected else ""
            lines.append(f"{marker}{category_icon(item.get('category',''))} **{item['name']}** ×{count} · {rarity_icon(item.get('rarity','Phàm'))} {item.get('rarity','Phàm')}")
        lines.append("\n💡 Dùng nhanh: chọn vật phẩm → Dùng ×1/×5/×10 hoặc Số khác.")
        return make_embed("\n".join(lines),footer="Túi Càn Khôn · Menu")
    async def refresh(self,i):
        if i.user.id!=self.owner_id: await i.response.send_message("Chỉ người mở Túi mới điều khiển được menu.",ephemeral=True); return
        await self.rebuild(); await i.response.edit_message(embed=await self.embed(),view=self)
    async def on_timeout(self):
        for c in self.children: c.disabled=True


async def command_inventory(message: discord.Message) -> None:
    view=InventoryView(message.author.id)
    await view.rebuild()
    await message.reply(embed=await view.embed(),view=view,mention_author=False)


async def command_use(message: discord.Message, args: list[str]) -> None:
    if not args: raise GameError("Cú pháp: `.dung <item> [so_luong]`")
    qty = int(args[1]) if len(args) > 1 else 1
    result = await run_engine(engine.use_item, str(message.author.id), args[0].lower(), qty); await reply_ui(message, result["text"], color=COLOR_SUCCESS)


async def command_learn(message: discord.Message, args: list[str]) -> None:
    if not args: raise GameError("Cú pháp: `.hoc <item>`")
    result = await run_engine(engine.learn_technique, str(message.author.id), args[0].lower())
    stat_text = f"+{result['bonus']} {result['stat']}" if result.get("bonus") else "không tăng thêm (chỉ số đã đạt giới hạn)"
    await reply_ui(message, f"📖 Đã học **{result['item']['name']}**. Đạo lộ lĩnh hội: **{stat_text}**.", color=COLOR_SUCCESS)


async def command_equip(message: discord.Message, args: list[str]) -> None:
    if not args: raise GameError("Cú pháp: `.trangbi <item>`")
    result = await run_engine(engine.equip, str(message.author.id), args[0].lower())
    await reply_ui(message, f"Đã trang bị **{result['item']['name']}**. Pháp bảo đã nhập vào chiến đấu.", color=COLOR_SUCCESS)


async def command_unequip(message: discord.Message) -> None:
    await run_engine(engine.unequip, str(message.author.id)); await reply_ui(message, "Đã tháo trang bị.")


class MarketListingSelect(discord.ui.Select):
    def __init__(self, view: "MarketView", rows: list[dict]):
        self.market_view=view
        options=[]
        for row in rows[:25]:
            item=ITEMS.get(row["item_id"],{})
            if not item: continue
            options.append(discord.SelectOption(label=f"#{row['id']} {item.get('name',row['item_id'])}"[:100],value=str(row['id']),description=f"×{row['quantity']} · {fmt(int(row['unit_price']))} LT/món"[:100],emoji=category_icon(item.get('category',''))))
        if not options: options=[discord.SelectOption(label="Chợ đang trống",value="__empty__")]
        super().__init__(placeholder="🛍️ Chọn một gian hàng...",options=options,row=0)
    async def callback(self,interaction:discord.Interaction):
        if interaction.user.id!=self.market_view.owner_id: await interaction.response.send_message("Chỉ người mở Chợ mới có thể thao tác.",ephemeral=True); return
        self.market_view.selected=None if self.values[0]=="__empty__" else int(self.values[0])
        await interaction.response.edit_message(embed=await self.market_view.embed(),view=self.market_view)

class MarketView(discord.ui.View):
    def __init__(self,owner_id:int,item_filter:str|None=None):
        super().__init__(timeout=180); self.owner_id=owner_id; self.item_filter=item_filter; self.selected=None; self.refresh_items()
    def refresh_items(self):
        self.clear_items()
        # This is called only for constructing; refresh() is async because DB access is offloaded.
    async def rebuild(self):
        self.clear_items(); rows=await run_engine(engine.market,self.item_filter,20); self.rows=rows; self.add_item(MarketListingSelect(self,rows))
        buy=discord.ui.Button(label="Mua gian đã chọn",emoji="💰",style=discord.ButtonStyle.success,row=1); buy.callback=self.buy; self.add_item(buy)
        refresh=discord.ui.Button(label="Làm mới",emoji="🔄",style=discord.ButtonStyle.secondary,row=1); refresh.callback=self.refresh; self.add_item(refresh)
    async def embed(self):
        rows=getattr(self,"rows",await run_engine(engine.market,self.item_filter,20)); lines=["🛍️ **CHỢ ĐẠO HỮU**",""]
        if not rows: lines.append("Chợ hiện chưa có gian hàng.")
        for row in rows:
            item=ITEMS.get(row["item_id"]);
            if item: lines.append(f"`#{row['id']}` **{item['name']} ×{row['quantity']}** · **{fmt(int(row['unit_price']))} LT/món** · <@{row['seller_id']}>")
        if self.selected: lines.append(f"\nĐang chọn gian **#{self.selected}**. Bấm **Mua gian đã chọn**.")
        return make_embed("\n".join(lines),footer="Chợ Đạo Hữu · Giao dịch")
    async def refresh(self,i):
        if i.user.id!=self.owner_id: await i.response.send_message("Chỉ người mở Chợ mới điều khiển được giao diện này.",ephemeral=True); return
        self.selected=None; await self.rebuild(); await i.response.edit_message(embed=await self.embed(),view=self)
    async def buy(self,i):
        if i.user.id!=self.owner_id: await i.response.send_message("Chỉ người mở Chợ mới điều khiển được giao diện này.",ephemeral=True); return
        if not self.selected: await i.response.send_message("Hãy chọn một gian hàng trước.",ephemeral=True); return
        await i.response.defer()
        try:
            listing=await run_engine(engine.market_buy,str(self.owner_id),self.selected); total=int(listing["quantity"])*int(listing["unit_price"]); self.selected=None; await self.rebuild(); await i.edit_original_response(content=f"✅ Mua thành công **{ITEMS[listing['item_id']]['name']} ×{listing['quantity']}** · **{fmt(total)} LT**.",embed=await self.embed(),view=self)
        except GameError as exc: await i.edit_original_response(content=str(exc),embed=await self.embed(),view=self)
    async def on_timeout(self):
        for c in self.children: c.disabled=True

async def command_market(message: discord.Message, args: list[str]) -> None:
    item_filter=args[0].lower() if args else None
    if item_filter and item_filter not in ITEMS: raise GameError("Không tìm thấy vật phẩm để lọc.")
    view=MarketView(message.author.id,item_filter); await view.rebuild()
    await message.reply(embed=await view.embed(),view=view,mention_author=False)


async def command_market_list(message: discord.Message, args: list[str]) -> None:
    if len(args) != 3:
        raise GameError("Cú pháp: `.dangban <item> <so_luong> <gia_moi_mon>`")
    item_id, qty, price = args[0].lower(), int(args[1]), int(args[2])
    listing_id = await run_engine(engine.market_list, str(message.author.id), item_id, qty, price)
    await reply_ui(message, f"Đã đăng gian hàng **#{listing_id}**: **{ITEMS[item_id]['name']} ×{qty}** · **{fmt(price)}/món**.", color=COLOR_SUCCESS)


async def command_market_cancel(message: discord.Message, args: list[str]) -> None:
    if len(args) != 1: raise GameError("Cú pháp: `.huyban <id>`")
    listing = await run_engine(engine.market_cancel, str(message.author.id), int(args[0]))
    await reply_ui(message, f"Đã hủy gian hàng **#{listing['id']}** và hoàn lại **{ITEMS[listing['item_id']]['name']} ×{listing['quantity']}**.")


async def command_market_buy(message: discord.Message, args: list[str]) -> None:
    if len(args) != 1: raise GameError("Cú pháp: `.muacho <id>`")
    listing = await run_engine(engine.market_buy, str(message.author.id), int(args[0]))
    total = int(listing["quantity"]) * int(listing["unit_price"])
    await reply_ui(message, f"Mua thành công **{ITEMS[listing['item_id']]['name']} ×{listing['quantity']}** với **{fmt(total)} linh thạch**.", color=COLOR_SUCCESS)


async def command_transfer(message: discord.Message, args: list[str]) -> None:
    if len(args) != 2 or len(message.mentions) != 1:
        raise GameError("Cú pháp: `.chuyen @người <số_linh_thạch>`")
    try:
        amount = int(args[1])
    except ValueError as exc:
        raise GameError("Số Linh Thạch phải là số nguyên.") from exc
    target = message.mentions[0]
    result = await run_engine(engine.transfer_spirit_stones, str(message.author.id), str(target.id), amount)
    await reply_ui(
        message,
        f"CHUYỂN LINH THẠCH THÀNH CÔNG\nĐã chuyển **{fmt(result['amount'])} Linh Thạch** cho <@{target.id}>.\nSố dư của ngươi: **{fmt(result['sender'].spirit_stones)} Linh Thạch**.",
        color=COLOR_SUCCESS,
    )


async def command_code(message: discord.Message, args: list[str]) -> None:
    if len(args) != 1:
        raise GameError("Cú pháp: `.code <mã>`")
    result = await run_engine(engine.redeem_code, str(message.author.id), args[0])
    lines = ["NHẬN QUÀ THÀNH CÔNG", f"Mã: `{result['code']}`"]
    if result.get("description"):
        lines.append(result["description"])
    stones = int(result.get("spirit_stones", 0))
    if stones:
        lines.append(f"💎 +**{fmt(stones)} linh thạch**")
    for item_id, qty in result.get("items", {}).items():
        item = ITEMS.get(item_id)
        if item:
            lines.append(f"📖 **{item['name']} ×{qty}**")
    await reply_ui(message, "\n".join(lines), color=COLOR_SUCCESS)


async def command_gacha(message: discord.Message, args: list[str]) -> None:
    count = int(args[0]) if args else 1
    if count < 1 or count > 10: raise GameError("Số lượt phải từ 1 đến 10.")
    uid = str(message.author.id)
    available = await run_engine(db.get_item_count, uid, "thien_co_lenh")
    if available < count: raise GameError(f"Không đủ Thiên Cơ Lệnh cho {count} lượt. Hiện có **{available}**.")
    lines = ["🎲 **THIÊN CƠ CÁC**", "", f"{LINH_THACH_ICON} **Thiên Cơ Lệnh:** `{available}`"]
    for _ in range(count):
        result = await run_engine(engine.gacha_once, uid); lines.append(f"{rarity_icon(result['rarity'])} **{result['rarity']} phẩm** → {result['text']}")
    lines.append(f"\nPity hiện tại: **{(await run_engine(engine.info, uid)).pity}/50**")
    await reply_ui(message, "\n".join(lines))


async def command_explore_zone(message: discord.Message, args: list[str]) -> None:
    if not args:
        zones=await run_engine(engine.list_explore_zones)
        lines=["🗺️ **BẢN ĐỒ TU CHÂN**"]
        for z in zones: lines.append(f"`{z['key']}` · **{z['name']}** · yêu cầu {REALMS[int(z['min_realm'])][0]}")
        lines.append("\nDùng `.khu <mã_khu>` để chọn.")
        await reply_ui(message,"\n".join(lines)); return
    zone=await run_engine(engine.set_explore_zone,str(message.author.id),args[0].lower())
    await reply_ui(message,f"🗺️ Đã chọn **{zone['name']}** làm khu vực khám phá.",color=COLOR_SUCCESS)

class TrialTowerView(discord.ui.View):
    def __init__(self, owner_id: int):
        super().__init__(timeout=180)
        self.owner_id = owner_id
        self.busy = False

    async def guard(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Chỉ người mở Thí Luyện Tháp mới có thể điều khiển menu này.", ephemeral=True)
            return False
        if self.busy:
            await interaction.response.send_message("Đang xử lý lượt leo tháp...", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Leo 1 tầng", emoji="🗼", style=discord.ButtonStyle.primary, row=0)
    async def climb(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.guard(interaction):
            return
        self.busy = True
        try:
            await interaction.response.defer()
            result = await run_engine(engine.trial_challenge, str(self.owner_id))
            status = result["status"]
            color = COLOR_SUCCESS if result["success"] else COLOR_WARN
            text = (
                f"🗼 **THÍ LUYỆN THÁP · CÁ NHÂN**\n\n{result['text']}\n\n"
                f"🏆 Cao nhất: **tầng {status['best']}**\n"
                f"🌠 Tầng kế tiếp: **{status['next_floor']}**\n"
                f"🎫 Lượt còn hôm nay: **{status['remaining']}**\n"
                f"📈 Tỷ lệ vượt tầng: **{result['chance']*100:.1f}%**\n\n"
                "*Chỉ nhận Linh Thạch và tu vi; không cấp buff chỉ số/Đạo vĩnh viễn.*"
            )
            await interaction.edit_original_response(embed=make_embed(text, color=color, footer="Thí Luyện Tháp · Solo · Không cần Tông"), view=self)
        except GameError as exc:
            await interaction.edit_original_response(content=decorate_currency(str(exc)), embed=None, view=self)
        finally:
            self.busy = False

    @discord.ui.button(label="Trạng thái", emoji="📜", style=discord.ButtonStyle.secondary, row=0)
    async def status(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.guard(interaction):
            return
        status = await run_engine(engine.trial_status, str(self.owner_id))
        await interaction.response.send_message(
            embed=make_embed(
                f"🗼 **THÍ LUYỆN THÁP · CÁ NHÂN**\n\n🏆 Cao nhất: **tầng {status['best']}**\n🌠 Kế tiếp: **tầng {status['next_floor']}**\n🎫 Lượt còn: **{status['remaining']} / {TRIAL_TOWER['daily_attempts']}**"
            ),
            ephemeral=True,
        )

    @discord.ui.button(label="BXH", emoji="🏆", style=discord.ButtonStyle.secondary, row=0)
    async def leaderboard(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.guard(interaction):
            return
        rows = await run_engine(engine.trial_leaderboard, 10)
        lines = ["🏆 **BXH THÍ LUYỆN THÁP**"]
        if not rows:
            lines.append("\nChưa có đạo hữu nào lưu tầng.")
        else:
            for idx, row in enumerate(rows, 1):
                lines.append(f"#{idx} **{row.display_name}** · tầng {row.trial_best} · {engine.realm_text(row)}")
        await interaction.response.send_message(embed=make_embed("\n".join(lines), footer="Thí Luyện Tháp · BXH"), ephemeral=True)


async def command_trial(message: discord.Message) -> None:
    status = await run_engine(engine.trial_status, str(message.author.id))
    await message.reply(
        embed=make_embed(
            f"🗼 **THÍ LUYỆN THÁP · CÁ NHÂN**\n\n"
            f"Đây là chế độ **leo tháp cá nhân**, không cần thuộc Tông Môn.\n\n"
            f"🏆 Cao nhất: **tầng {status['best']}**\n"
            f"🌠 Tầng kế tiếp: **{status['next_floor']}**\n"
            f"🎫 Lượt hôm nay: **{status['remaining']} / {TRIAL_TOWER['daily_attempts']}**\n\n"
            "Phần thưởng được cân bằng theo tầng và **không cấp buff chỉ số vĩnh viễn**."
        ),
        view=TrialTowerView(message.author.id),
        mention_author=False,
    )

class DaoSelect(discord.ui.Select):
    def __init__(self, view: "DaoView"):
        self.dao_view = view
        options = [
            discord.SelectOption(label="Kiếm Đạo", value="kiem", emoji="🗡️", description="Kiếm Khí → Kiếm Ý → Kiếm Thế → Kiếm Tâm"),
            discord.SelectOption(label="Đao Đạo", value="dao", emoji="🔪", description="Đao Khí → Đao Ý → Đao Thế → Đao Tâm"),
            discord.SelectOption(label="Pháp Đạo", value="phap", emoji="🔥", description="Pháp Khí → Pháp Ý → Pháp Thế → Pháp Tâm"),
            discord.SelectOption(label="Thể Đạo", value="the", emoji="🛡️", description="Luyện thể và tôi luyện thân tâm"),
        ]
        super().__init__(placeholder="🧭 Chọn một con đường Đạo...", options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.dao_view.owner_id:
            await interaction.response.send_message("Chỉ người mở menu Đạo mới được chọn.", ephemeral=True); return
        try:
            info = await run_engine(engine.choose_dao, str(self.dao_view.owner_id), self.values[0])
            self.dao_view.selected_info = info
            await interaction.response.edit_message(embed=await self.dao_view.embed(), view=self.dao_view)
        except GameError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)


class DaoView(discord.ui.View):
    def __init__(self, owner_id: int):
        super().__init__(timeout=180)
        self.owner_id = owner_id
        self.selected_info = None
        self.select = DaoSelect(self)
        self.add_item(self.select)
        self.home_button = discord.ui.Button(label="Đại Điện", emoji="🏠", style=discord.ButtonStyle.secondary, row=2)
        self.refresh_button = discord.ui.Button(label="Làm mới", emoji="🔄", style=discord.ButtonStyle.secondary, row=2)
        self.home_button.callback = self.home
        self.refresh_button.callback = self.refresh
        self.add_item(self.refresh_button); self.add_item(self.home_button)

    async def guard(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Chỉ người mở menu Đạo mới điều khiển được menu này.", ephemeral=True); return False
        return True

    async def embed(self):
        info = self.selected_info or await run_engine(engine.dao_info, str(self.owner_id))
        if not info:
            return make_embed("🧭 CON ĐƯỜNG ĐẠO", "Chọn Đạo bên dưới. Đạo đã định thì không thể đổi tùy ý.", footer="Đạo · Khí → Ý → Thế → Tâm")
        next_text = fmt(info['next']) if info.get('next') is not None else "Tối đa"
        text = (f"{info['icon']} **{info['name']}**\n\n"
                f"Cảnh giới Đạo: **{info['stage_name']}**\n"
                f"Tiến độ: **{fmt(info['progress'])} / {next_text}**\n\n"
                "Sự lĩnh hội đến từ chiến đấu, công pháp/pháp bảo và cơ duyên phù hợp; không có nút cộng miễn phí để tránh phá cân bằng.")
        return make_embed(text, footer="Đạo · Khí → Ý → Thế → Tâm")

    async def refresh(self, interaction: discord.Interaction):
        if await self.guard(interaction):
            self.selected_info = await run_engine(engine.dao_info, str(self.owner_id))
            await interaction.response.edit_message(embed=await self.embed(), view=self)

    async def home(self, interaction: discord.Interaction):
        if await self.guard(interaction):
            await interaction.response.edit_message(embed=make_plain_embed("🌌 ĐẠI ĐIỆN KATO TU TIÊN", "Chọn hệ thống để tiếp tục."), view=MainMenuView(self.owner_id))

    async def on_timeout(self):
        for child in self.children: child.disabled = True


async def command_dao(message: discord.Message, args: list[str]) -> None:
    if not args:
        view = DaoView(message.author.id)
        await message.reply(embed=await view.embed(), view=view, mention_author=False)
        return
    info = await run_engine(engine.choose_dao, str(message.author.id), args[0].lower())
    await reply_ui(message, f"{info['icon']} Đã nhập **{info['name']}** · **{info['stage_name']}**", color=COLOR_SUCCESS)

class TribulationView(discord.ui.View):
    def __init__(self,owner_id:int): super().__init__(timeout=90); self.owner_id=owner_id; self.busy=False
    async def guard(self,i):
        if i.user.id!=self.owner_id: await i.response.send_message("Chỉ người mở Thiên Kiếp mới được quyết định.",ephemeral=True); return False
        if self.busy: await i.response.send_message("Thiên Kiếp đang được xử lý.",ephemeral=True); return False
        return True
    @discord.ui.button(label="Ứng Kiếp",emoji="⚡",style=discord.ButtonStyle.danger,row=0)
    async def face(self,i:discord.Interaction,b:discord.ui.Button):
        if not await self.guard(i): return
        self.busy=True; [setattr(c,"disabled",True) for c in self.children]
        try:
            r=await run_engine(engine.face_tribulation,str(self.owner_id)); await i.response.edit_message(embed=make_embed(f"⚡ **THIÊN KIẾP**\n\n{r['text']}\nTỷ lệ vượt kiếp: **{r['chance']:.1f}%**",color=COLOR_SUCCESS if r['success'] else COLOR_ERROR,footer="Thiên Kiếp · Kết quả"),view=self)
        except GameError as exc: await i.response.send_message(str(exc),ephemeral=True)
        finally:self.busy=False
    @discord.ui.button(label="Chuẩn bị thêm",emoji="🛡️",style=discord.ButtonStyle.secondary,row=0)
    async def cancel(self,i:discord.Interaction,b:discord.ui.Button):
        if not await self.guard(i): return
        await i.response.edit_message(embed=make_embed("⚡ **CHƯA ĐỘ KIẾP**\n\nNgươi giữ lại lần ứng kiếp này để tiếp tục chuẩn bị.",color=COLOR_WARN,footer="Thiên Kiếp · Chuẩn bị"),view=None)
    async def on_timeout(self):
        for c in self.children:c.disabled=True


async def command_tribulation(message: discord.Message) -> None:
    # Preview through the existing engine gate; actual roll only occurs after confirmation.
    await message.reply(embed=make_embed("⚡ **THIÊN KIẾP**\n\nNgươi đã bước tới cửa đại cảnh. Đây là một quyết định không thể spam; hãy xác nhận trước khi ứng kiếp.",color=COLOR_WARN,footer="Thiên Kiếp · Xác nhận"),view=TribulationView(message.author.id),mention_author=False)

async def command_sect_missions(message: discord.Message) -> None:
    missions=await run_engine(engine.sect_mission_list,str(message.author.id))
    lines=["📜 **NHIỆM VỤ TÔNG MÔN**"]
    for m in missions: lines.append(f"`{m['key']}` · **{m['name']}** · {m['progress']}/{m['target']} · thưởng {m['reward']} LT + {m['contribution']} cống hiến" + (" · ✅ Đã nhận" if m['completed'] else ""))
    lines.append("\nNhận thưởng: `.nvtong <mã>`")
    await reply_ui(message,"\n".join(lines))

async def command_sect_mission_claim(message: discord.Message,args:list[str])->None:
    if not args: raise GameError("Cú pháp: `.nvtong <ma_nhiem_vu>`")
    r=await run_engine(engine.sect_mission_claim,str(message.author.id),args[0].lower())
    await reply_ui(message,f"🏯 Hoàn thành nhiệm vụ: +**{fmt(r['reward'])} Linh Thạch** · +**{r['contribution']} cống hiến**",color=COLOR_SUCCESS)


# ---------- Thiên Đạo / Admin ----------
def owner_ids() -> set[str]:
    return {x.strip() for x in os.getenv("KATO_OWNER_IDS", "").split(",") if x.strip()}


def is_owner(user_id: str) -> bool:
    return str(user_id) in owner_ids()


def is_authorized_admin(user_id: str) -> bool:
    return is_owner(user_id) or db.is_admin_user(str(user_id))


def has_admin_session(user_id: str) -> bool:
    # Thiên Đạo is password-only. Session is RAM-only so a bot restart clears all sessions.
    key = str(user_id)
    expiry = ADMIN_SESSIONS.get(key, 0.0)
    if expiry <= time.time():
        ADMIN_SESSIONS.pop(key, None)
        return False
    return True


def grant_admin_session(user_id: str) -> float:
    expires_at = time.time() + ADMIN_SESSION_TTL
    ADMIN_SESSIONS[str(user_id)] = expires_at
    return expires_at


def clear_admin_session(user_id: str) -> None:
    ADMIN_SESSIONS.pop(str(user_id), None)


def verify_admin_password(password: str) -> bool:
    expected = os.getenv("KATO_ADMIN_PASSWORD")
    if not expected:
        return False
    return hmac.compare_digest(str(password), str(expected))

def too_many_admin_failures(user_id: str) -> bool:
    now = time.time()
    attempts = [t for t in ADMIN_FAILS.get(str(user_id), []) if now - t < 60]
    ADMIN_FAILS[str(user_id)] = attempts
    return len(attempts) >= 5

def record_admin_failure(user_id: str) -> None:
    ADMIN_FAILS.setdefault(str(user_id), []).append(time.time())


class AdminPanelView(discord.ui.View):
    def __init__(self, owner_id: int):
        super().__init__(timeout=300); self.owner_id=owner_id
    async def guard(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id or not has_admin_session(str(self.owner_id)):
            await interaction.response.send_message("Phiên Thiên Đạo đã hết hạn hoặc không thuộc về ngươi.", ephemeral=True); return False
        return True
    @discord.ui.button(label="Xuất Database", emoji="🗄️", style=discord.ButtonStyle.danger, row=0)
    async def export_db(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.guard(interaction): return
        await interaction.response.defer(ephemeral=True)
        try:
            msg=await export_database_to_user(interaction.user,str(self.owner_id))
            await interaction.edit_original_response(content=msg,view=self)
        except GameError as exc:
            await interaction.edit_original_response(content=f"❌ {exc}",view=self)
    @discord.ui.button(label="Admin hiện tại", emoji="👥", style=discord.ButtonStyle.secondary, row=0)
    async def admins(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.guard(interaction): return
        rows=await run_engine(db.list_admin_users); text="👥 **ADMIN ĐƯỢC CẤP QUYỀN**\n\n"+("\n".join(f"• <@{uid}>" for uid in rows) if rows else "Chưa có admin phụ.")
        await interaction.response.send_message(embed=make_embed(text,footer="Thiên Đạo · Access Control"),ephemeral=True)
    @discord.ui.button(label="Audit", emoji="📜", style=discord.ButtonStyle.secondary, row=0)
    async def audit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.guard(interaction): return
        rows=await run_engine(db.get_admin_audit,10); lines=["📜 **THIÊN ĐẠO AUDIT**"]
        for r in rows: lines.append(f"• `{r['action']}` · <@{r['actor_id']}> · {time.strftime('%d/%m %H:%M',time.localtime(int(r['created_at'])))}")
        await interaction.response.send_message(embed=make_embed("\n".join(lines),footer="Thiên Đạo · Audit"),ephemeral=True)
    @discord.ui.button(label="Đăng xuất", emoji="🔒", style=discord.ButtonStyle.danger, row=1)
    async def logout(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.guard(interaction): return
        clear_admin_session(str(self.owner_id)); await run_engine(db.add_admin_audit,str(self.owner_id),"logout",str(self.owner_id),"Admin session closed")
        await interaction.response.edit_message(content="🔒 Đã đóng phiên Thiên Đạo.",embed=None,view=None)
    async def on_timeout(self):
        clear_admin_session(str(self.owner_id))
        for child in self.children: child.disabled=True

class AdminOpenView(discord.ui.View):
    def __init__(self, owner_id:int): super().__init__(timeout=60); self.owner_id=owner_id
    @discord.ui.button(label="Nhập mật khẩu Thiên Đạo",emoji="🔐",style=discord.ButtonStyle.danger)
    async def open_password(self,interaction:discord.Interaction,button:discord.ui.Button):
        if interaction.user.id!=self.owner_id: await interaction.response.send_message("Chỉ người gọi lệnh mới được xác minh.",ephemeral=True); return
        await interaction.response.send_modal(AdminPasswordModal())
    async def on_timeout(self):
        for child in self.children: child.disabled=True

class AdminPasswordModal(discord.ui.Modal, title="☯️ Pháp Tắc Thiên Đạo"):
    password = discord.ui.TextInput(label="Mật khẩu Thiên Đạo", placeholder="Nhập pháp tắc...", required=True, min_length=4, max_length=128, style=discord.TextStyle.short)

    async def on_submit(self, interaction: discord.Interaction):
        uid = str(interaction.user.id)
        if too_many_admin_failures(uid):
            await interaction.response.send_message("❌ Thiên Đạo tạm phong ấn xác minh trong 60 giây do có quá nhiều lần thử sai.", ephemeral=True)
            return
        # Defer immediately: PBKDF2 verification must not risk the 3s interaction window.
        await interaction.response.defer(ephemeral=True)
        try:
            ok = await run_engine(verify_admin_password, str(self.password))
        except Exception as exc:
            logger.exception("thien-dao password verify failed: %s", exc)
            await interaction.edit_original_response(content="❌ Không thể xác minh mật khẩu lúc này.")
            return
        if not ok:
            record_admin_failure(uid)
            await run_engine(db.add_admin_audit, uid, "auth_fail", uid, "Invalid admin password")
            await interaction.edit_original_response(content="❌ Pháp tắc không hợp. Xác minh thất bại.")
            return
        ADMIN_FAILS.pop(uid, None)
        grant_admin_session(uid)
        await run_engine(db.add_admin_audit, uid, "auth_success", uid, "Admin session created")
        await interaction.edit_original_response(content="☯️ Thiên Đạo đã xác nhận thân phận. Phiên quản trị có hiệu lực 5 phút.", view=AdminPanelView(interaction.user.id))


@tree.command(name="thien-dao", description="Nhập mật khẩu để mở phiên quản trị Thiên Đạo")
async def thien_dao(interaction: discord.Interaction):
    # No user ID / owner ID / admin whitelist is requested here.
    await interaction.response.send_modal(AdminPasswordModal())



def create_sqlite_backup(source_path: str) -> str:
    """Create a consistent SQLite snapshot and return its temporary path."""
    fd, temp_path = tempfile.mkstemp(prefix="kato_filedb_", suffix=".db")
    os.close(fd)
    try:
        with sqlite3.connect(source_path) as live, sqlite3.connect(temp_path) as backup:
            live.backup(backup)
        return temp_path
    except Exception as exc:
        logger.exception("Unhandled error: %s", exc)
        try:
            os.remove(temp_path)
        except OSError:
            pass
        raise


async def export_database_to_user(user: discord.User | discord.Member, actor_id: str) -> str:
    """Create SQLite backup off the event loop and DM it. Returns status message for the caller."""
    if not os.path.exists(DB_PATH):
        raise GameError("Không tìm thấy database người chơi.")
    temp_path = await run_engine(create_sqlite_backup, DB_PATH)
    try:
        await user.send(
            content="🗄️ **KATO TU TIÊN — DATABASE**\nĐây là bản sao database người chơi được xuất từ Thiên Đạo.",
            file=discord.File(temp_path, filename="kato_tutien_players.db"),
        )
        await run_engine(db.add_admin_audit, actor_id, "filedb_export", None, "Database exported to requester DM")
        return "✅ Đã xuất database và gửi riêng vào DM của ngươi."
    except discord.Forbidden:
        await run_engine(db.add_admin_audit, actor_id, "filedb_export_fail", None, "DM forbidden")
        raise GameError("Không thể gửi DM. Hãy bật nhận tin nhắn riêng từ server rồi thử lại.")
    finally:
        try:
            os.remove(temp_path)
        except OSError:
            pass


class FileDBPasswordModal(discord.ui.Modal, title="🗄️ Thiên Đạo — Xuất dữ liệu"):
    password = discord.ui.TextInput(
        label="Mật khẩu Thiên Đạo",
        placeholder="Nhập mật khẩu để lấy database...",
        required=True,
        min_length=4,
        max_length=128,
        style=discord.TextStyle.short,
    )

    async def on_submit(self, interaction: discord.Interaction):
        uid = str(interaction.user.id)
        if too_many_admin_failures(uid):
            await interaction.response.send_message(
                "❌ Thiên Đạo tạm phong ấn xác minh trong 60 giây do có quá nhiều lần thử sai.",
                ephemeral=True,
            )
            return

        # Defer immediately so the interaction never hangs during PBKDF2 / backup.
        await interaction.response.defer(ephemeral=True)

        try:
            ok = await run_engine(verify_admin_password, str(self.password))
        except Exception as exc:
            logger.exception("filedb password verify failed: %s", exc)
            await interaction.edit_original_response(content="❌ Không thể xác minh mật khẩu lúc này.")
            return

        if not ok:
            record_admin_failure(uid)
            await run_engine(db.add_admin_audit, uid, "filedb_auth_fail", None, "Invalid database export password")
            await interaction.edit_original_response(content="❌ Mật khẩu không đúng. Không tạo database.")
            return

        ADMIN_FAILS.pop(uid, None)
        grant_admin_session(uid)
        await run_engine(db.add_admin_audit, uid, "auth_success", uid, "Admin session created via filedb")
        try:
            msg = await export_database_to_user(interaction.user, uid)
            await interaction.edit_original_response(content=msg)
        except GameError as exc:
            await interaction.edit_original_response(content=f"❌ {exc}")
        except Exception as exc:
            logger.exception("filedb export failed: %s", exc)
            await run_engine(db.add_admin_audit, uid, "filedb_export_fail", None, f"Database export failed: {type(exc).__name__}")
            await interaction.edit_original_response(content="❌ Không thể xuất database lúc này.")


@tree.command(name="filedb", description="Xuất bản sao database người chơi qua DM (cần phiên Thiên Đạo hoặc mật khẩu)")
async def filedb(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    if has_admin_session(uid):
        # Already authenticated — never ask for password again within the 5-minute window.
        await interaction.response.defer(ephemeral=True)
        try:
            msg = await export_database_to_user(interaction.user, uid)
            await interaction.edit_original_response(content=msg)
        except GameError as exc:
            await interaction.edit_original_response(content=f"❌ {exc}")
        except Exception as exc:
            logger.exception("filedb export failed: %s", exc)
            await run_engine(db.add_admin_audit, uid, "filedb_export_fail", None, f"Database export failed: {type(exc).__name__}")
            await interaction.edit_original_response(content="❌ Không thể xuất database lúc này.")
        return
    await interaction.response.send_modal(FileDBPasswordModal())


class FileDBOpenView(discord.ui.View):
    def __init__(self, owner_id: int):
        super().__init__(timeout=60)
        self.owner_id = owner_id

    @discord.ui.button(label="Nhập mật khẩu", style=discord.ButtonStyle.danger, emoji="🔐")
    async def open_password(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Chỉ người gọi lệnh mới được nhập mật khẩu.", ephemeral=True)
            return
        await interaction.response.send_modal(FileDBPasswordModal())

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True


async def command_admin(message: discord.Message, args: list[str]) -> None:
    uid=str(message.author.id)
    if has_admin_session(uid):
        await message.reply(embed=make_embed("☯️ **THIÊN ĐẠO**\n\nPhiên quản trị đang hoạt động.",color=COLOR_WARN,footer="Thiên Đạo · Quản trị"),view=AdminPanelView(message.author.id),mention_author=False)
        return
    await message.reply(embed=make_embed("☯️ **THIÊN ĐẠO**\n\nChưa có phiên quản trị. Mật khẩu bắt buộc nằm trong `KATO_ADMIN_PASSWORD`.",color=COLOR_WARN,footer="Thiên Đạo · Xác thực"),view=AdminOpenView(message.author.id),mention_author=False)

async def command_filedb(message: discord.Message) -> None:
    """Prefix `.filedb`: use active Admin Session if present, otherwise open password modal."""
    uid = str(message.author.id)
    if has_admin_session(uid):
        try:
            msg = await export_database_to_user(message.author, uid)
            await message.reply(msg, mention_author=False)
        except GameError as exc:
            await message.reply(f"❌ {exc}", mention_author=False)
        except Exception as exc:
            logger.exception("filedb prefix export failed: %s", exc)
            await message.reply("❌ Không thể xuất database lúc này.", mention_author=False)
        return
    await message.channel.send(
        "🗄️ **FILEDB THIÊN ĐẠO**\nChưa có phiên quản trị. Bấm nút bên dưới để nhập mật khẩu và nhận database qua DM.",
        view=FileDBOpenView(message.author.id),
        delete_after=60,
    )


async def dispatch(message: discord.Message, command: str, args: list[str]) -> None:
    spec = COMMAND_LOOKUP.get(command)
    if not spec:
        raise GameError("Không nhận ra lệnh. Dùng `.help` hoặc `.menu`.")
    handler = globals().get(spec.handler)
    if handler is None:
        raise GameError(f"Lệnh `.{spec.name}` chưa được nối handler. Hãy kiểm tra Command Registry.")
    if spec.takes_args:
        await handler(message, args)
    else:
        await handler(message)


@tasks.loop(seconds=30)
async def be_quan_worker():
    try:
        results = await run_engine(engine.process_be_quan)
        if results:
            for result in results:
                if result.get("stopped"):
                    logger.info("[be-quan] %s stopped: insufficient stones after %s cycles", result["user_id"], result["cycles"])
    except Exception as exc:
        logger.exception("[be-quan] worker error: %s: %s", type(exc).__name__, exc)


@client.event
async def on_ready():
    try:
        await tree.sync()
    except Exception as exc:
        logger.exception("Slash command sync warning: %r", exc)
    if not be_quan_worker.is_running():
        be_quan_worker.start()
    logger.info("Kato Tu Tiên online: %s", client.user)


@client.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    content = message.content.strip()
    if not content.startswith("."):
        return
    payload = content[1:].strip()
    if not payload:
        await reply_ui(message, "Kato Tu Tiên\nDùng `.help` để xem đường tu luyện.")
        return
    parts = payload.split()
    command, args = parts[0].lower(), parts[1:]
    try:
        await dispatch(message, command, args)
    except ValueError:
        await reply_ui(message, "Tham số không hợp lệ.", color=COLOR_ERROR)
    except GameError as exc:
        await send_error(message, exc)
    except Exception as exc:
        logger.exception("Command error: %r", exc)
        await reply_ui(message, "Thiên cơ gặp lỗi. Hãy thử lại sau.", color=COLOR_ERROR)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    token = os.getenv(TOKEN_ENV)
    if not token:
        raise RuntimeError("Thiếu DISCORD_TOKEN. Hãy thêm token vào Secrets/Environment của Replit.")
    if not os.getenv("KATO_ADMIN_PASSWORD"):
        raise RuntimeError("Thiếu KATO_ADMIN_PASSWORD. Hãy thêm mật khẩu Thiên Đạo vào Secrets/Environment trước khi khởi động bot.")
    # Admin sessions are RAM-only; nothing to restore from disk.
    client.run(token)


if __name__ == "__main__":
    main()
