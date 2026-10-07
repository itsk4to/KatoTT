from __future__ import annotations


EQUIP_SLOTS = ("weapon", "artifact", "armor", "accessory")

MINOR_REALM_NAMES = ("Sơ kỳ", "Trung kỳ", "Hậu kỳ", "Viên mãn")

def minor_realm_name(layer: int, layer_count: int) -> str:
    """Map numeric layer onto four named minor realms without changing storage."""
    if layer_count <= 1 or layer <= 0:
        return MINOR_REALM_NAMES[0]
    # layer is 1-based display depth in existing saves (0 means unlayered).
    span = max(1, layer_count)
    idx = min(3, int((max(0, layer) * 4) / span))
    return MINOR_REALM_NAMES[idx]

REALMS = [
    ("Phàm Nhân", 1),
    ("Luyện Khí", 9),
    ("Trúc Cơ", 9),
    ("Kim Đan", 9),
    ("Nguyên Anh", 9),
    ("Hóa Thần", 9),
    ("Luyện Hư", 9),
    ("Hợp Thể", 9),
    ("Đại Thừa", 9),
    ("Độ Kiếp", 3),
    ("Chân Tiên", 9),
    ("Thiên Tiên", 9),
    ("Tiên Vương", 9),
    ("Tiên Đế", 9),
]

ITEMS = {
    # ---------- Shop · Pháp bảo (10) ----------
    "thanh_tam_ngoc_boi": {
        "category": "Pháp bảo", "name": "Thanh Tâm Ngọc Bội", "rarity": "Hoàng", "type": "equipment",
        "slot": "artifact", "attack": 20, "defense": 70, "price": 8_000, "marketable": True,
        "description": "Ngọc bội hộ tâm, tăng sức phòng thủ cho người tu luyện.",
    },
    "tu_linh_chau": {
        "category": "Pháp bảo", "name": "Tụ Linh Châu", "rarity": "Hoàng", "type": "equipment",
        "slot": "artifact", "attack": 35, "defense": 85, "price": 15_000, "marketable": True,
        "description": "Bảo châu tụ linh, hỗ trợ chiến lực và hộ thân.",
    },
    "huyen_thiet_linh_kinh": {
        "category": "Pháp bảo", "name": "Huyền Thiết Linh Kính", "rarity": "Huyền", "type": "equipment",
        "slot": "artifact", "attack": 55, "defense": 120, "price": 25_000, "marketable": True,
        "description": "Linh kính huyền thiết, phản chiếu linh lực hộ thân.",
    },
    "kim_cang_ho_tam_kinh": {
        "category": "Pháp bảo", "name": "Kim Cang Hộ Tâm Kính", "rarity": "Huyền", "type": "equipment",
        "slot": "artifact", "attack": 45, "defense": 170, "price": 40_000, "marketable": True,
        "description": "Bảo kính cứng như kim cang, chuyên thủ hộ tâm mạch.",
    },
    "ngu_hanh_linh_chau": {
        "category": "Pháp bảo", "name": "Ngũ Hành Linh Châu", "rarity": "Địa", "type": "equipment",
        "slot": "artifact", "attack": 90, "defense": 190, "price": 60_000, "marketable": True,
        "description": "Năm viên linh châu vận chuyển ngũ hành chi lực.",
    },
    "thien_co_bao_kinh": {
        "category": "Pháp bảo", "name": "Thiên Cơ Bảo Kính", "rarity": "Địa", "type": "equipment",
        "slot": "artifact", "attack": 110, "defense": 230, "price": 90_000, "marketable": True,
        "description": "Bảo kính xem thấu thiên cơ, tăng chiến lực toàn diện.",
    },
    "cuu_long_ngoc_an": {
        "category": "Pháp bảo", "name": "Cửu Long Ngọc Ấn", "rarity": "Thiên", "type": "equipment",
        "slot": "artifact", "attack": 160, "defense": 300, "price": 150_000, "marketable": True,
        "description": "Ngọc ấn khắc chín long văn, uy áp kinh người.",
    },
    "thai_hu_linh_dang": {
        "category": "Pháp bảo", "name": "Thái Hư Linh Đăng", "rarity": "Thiên", "type": "equipment",
        "slot": "artifact", "attack": 210, "defense": 360, "price": 250_000, "marketable": True,
        "description": "Linh đăng soi chiếu Thái Hư, vừa công vừa thủ.",
    },
    "tru_tien_co_an": {
        "category": "Pháp bảo", "name": "Tru Tiên Cổ Ấn", "rarity": "Tiên", "type": "equipment",
        "slot": "artifact", "attack": 320, "defense": 480, "price": 500_000, "marketable": True,
        "description": "Cổ ấn sát phạt, áp chế khí cơ đối thủ.",
    },
    "hon_don_thien_chau": {
        "category": "Pháp bảo", "name": "Hỗn Độn Thiên Châu", "rarity": "Thần", "type": "equipment",
        "slot": "artifact", "attack": 500, "defense": 650, "price": 1_000_000, "marketable": True,
        "description": "Thiên châu ẩn chứa hỗn độn chi lực, cực kỳ hiếm có.",
    },

    # ---------- Shop · Bùa chú (10) ----------
    "hoi_xuan_phu": {
        "category": "Bùa chú", "name": "Hồi Xuân Phù", "rarity": "Phàm", "type": "consumable",
        "price": 2_000, "marketable": True, "injury_reduction": 5,
        "description": "Phù chú chữa thương, giảm 5% thương thế khi sử dụng.",
    },
    "tu_linh_phu": {
        "category": "Bùa chú", "name": "Tụ Linh Phù", "rarity": "Phàm", "type": "consumable",
        "price": 3_500, "marketable": True, "cultivation": 500,
        "description": "Thu nạp linh khí, lập tức nhận thêm tu vi.",
    },
    "kim_cang_phu": {
        "category": "Bùa chú", "name": "Kim Cang Phù", "rarity": "Hoàng", "type": "consumable",
        "price": 6_000, "marketable": True, "cultivation": 650, "root": 1,
        "description": "Phù hộ thể, tôi luyện căn cơ và bổ sung linh lực.",
    },
    "ngu_phong_phu": {
        "category": "Bùa chú", "name": "Ngự Phong Phù", "rarity": "Hoàng", "type": "consumable",
        "price": 8_000, "marketable": True, "cultivation": 900, "fate": 1,
        "description": "Phù ngự phong giúp thân pháp thuận lợi, tăng nhẹ khí vận.",
    },
    "liet_hoa_phu": {
        "category": "Bùa chú", "name": "Liệt Hỏa Phù", "rarity": "Huyền", "type": "consumable",
        "price": 12_000, "marketable": True, "cultivation": 1_300, "insight": 1,
        "description": "Hỏa lực mạnh mẽ, tôi luyện ngộ tính qua linh hỏa.",
    },
    "bang_tam_phu": {
        "category": "Bùa chú", "name": "Băng Tâm Phù", "rarity": "Huyền", "type": "consumable",
        "price": 18_000, "marketable": True, "cultivation": 1_600, "mind": 2,
        "description": "Giữ tâm tĩnh lặng, tăng đạo tâm sau khi sử dụng.",
    },
    "tran_hon_phu": {
        "category": "Bùa chú", "name": "Trấn Hồn Phù", "rarity": "Địa", "type": "consumable",
        "price": 30_000, "marketable": True, "cultivation": 2_400, "mind": 3,
        "description": "Ổn định thần hồn, củng cố tâm tính và tu vi.",
    },
    "thien_loi_phu": {
        "category": "Bùa chú", "name": "Thiên Lôi Phù", "rarity": "Địa", "type": "consumable",
        "price": 50_000, "marketable": True, "cultivation": 3_500, "insight": 3,
        "description": "Thu thiên lôi nhập thể để tôi luyện ngộ tính.",
    },
    "cuu_thien_than_phu": {
        "category": "Bùa chú", "name": "Cửu Thiên Thần Phù", "rarity": "Thiên", "type": "consumable",
        "price": 100_000, "marketable": True, "cultivation": 5_000, "all_stats": 2,
        "description": "Thần phù hiếm, tăng đều các chỉ số căn cơ khi sử dụng.",
    },
    "diet_ma_thien_phu": {
        "category": "Bùa chú", "name": "Diệt Ma Thiên Phù", "rarity": "Tiên", "type": "consumable",
        "price": 250_000, "marketable": True, "cultivation": 8_000, "insight": 5, "mind": 5,
        "description": "Thiên phù trấn ma, ban cho người sử dụng lượng tu vi lớn.",
    },

    # ---------- Shop · Đan dược (10) ----------
    "tu_khi_dan": {
        "category": "Đan dược", "name": "Tụ Khí Đan", "rarity": "Phàm", "type": "consumable",
        "price": 1_000, "marketable": True, "cultivation": 250,
        "description": "Đan dược nhập môn, bổ sung linh khí và tu vi.",
    },
    "hoi_khi_dan": {
        "category": "Đan dược", "name": "Hồi Khí Đan", "rarity": "Phàm", "type": "consumable",
        "price": 2_000, "marketable": True, "cultivation": 500,
        "description": "Hồi phục linh khí, cho lượng tu vi cao hơn Tụ Khí Đan.",
    },
    "hoi_huyet_dan": {
        "category": "Đan dược", "name": "Hồi Huyết Đan", "rarity": "Hoàng", "type": "consumable",
        "price": 2_500, "marketable": True, "cultivation": 300, "injury_reduction": 8,
        "description": "Đan chữa thương, đồng thời bổ sung một ít tu vi.",
    },
    "tang_toc_dan": {
        "category": "Đan dược", "name": "Tăng Tốc Đan", "rarity": "Hoàng", "type": "consumable",
        "price": 5_000, "marketable": True, "cultivation": 750,
        "description": "Đan tăng tốc hấp thu linh khí, chuyển hóa thành tu vi tức thời.",
    },
    "truc_co_dan": {
        "category": "Đan dược", "name": "Trúc Cơ Đan", "rarity": "Huyền", "type": "consumable",
        "price": 12_000, "marketable": True, "cultivation": 1_500, "root": 1,
        "description": "Đan dược củng cố căn cơ, phù hợp người đang xây nền.",
    },
    "kim_dan_ngung_hon_dan": {
        "category": "Đan dược", "name": "Kim Đan Ngưng Hồn Đan", "rarity": "Địa", "type": "consumable",
        "price": 25_000, "marketable": True, "cultivation": 3_000, "mind": 2,
        "description": "Tụ thần ngưng hồn, hỗ trợ tiến cảnh Kim Đan.",
    },
    "anh_hon_dan": {
        "category": "Đan dược", "name": "Anh Hồn Đan", "rarity": "Địa", "type": "consumable",
        "price": 50_000, "marketable": True, "cultivation": 5_000, "mind": 3,
        "description": "Đan dưỡng thần, bồi đắp nội tình Nguyên Anh.",
    },
    "hoa_than_dan": {
        "category": "Đan dược", "name": "Hóa Thần Đan", "rarity": "Thiên", "type": "consumable",
        "price": 100_000, "marketable": True, "cultivation": 8_000, "insight": 4,
        "description": "Đan dược quý hiếm, giúp lĩnh hội thần thông nhanh hơn.",
    },
    "do_kiep_than_dan": {
        "category": "Đan dược", "name": "Độ Kiếp Thần Đan", "rarity": "Tiên", "type": "consumable",
        "price": 250_000, "marketable": True, "cultivation": 15_000, "fate": 5, "mind": 3,
        "description": "Thần đan dùng trước đại kiếp, tăng nội tình và khí vận.",
    },
    "cuu_chuyen_tien_dan": {
        "category": "Đan dược", "name": "Cửu Chuyển Tiên Đan", "rarity": "Thần", "type": "consumable",
        "price": 1_000_000, "marketable": True, "cultivation": 30_000, "all_stats": 6,
        "description": "Tiên đan cực phẩm, cải thiện toàn diện tu hành trong một lần sử dụng.",
    },

    # ---------- Shop · Binh khí (10) ----------
    "thiet_kiem": {
        "category": "Binh khí", "name": "Thiết Kiếm", "rarity": "Phàm", "type": "equipment", "slot": "weapon",
        "attack": 45, "defense": 5, "price": 3_000, "marketable": True,
        "description": "Thanh kiếm nhập môn, bền chắc và dễ sử dụng.",
    },
    "thanh_phong_kiem": {
        "category": "Binh khí", "name": "Thanh Phong Kiếm", "rarity": "Hoàng", "type": "equipment", "slot": "weapon",
        "attack": 80, "defense": 10, "price": 8_000, "marketable": True,
        "description": "Pháp kiếm nhẹ, cân bằng giữa tốc độ và công kích.",
    },
    "huyen_thiet_dao": {
        "category": "Binh khí", "name": "Huyền Thiết Đao", "rarity": "Hoàng", "type": "equipment", "slot": "weapon",
        "attack": 110, "defense": 8, "price": 15_000, "marketable": True,
        "description": "Đao huyền thiết nặng, thích hợp lối đánh áp đảo.",
    },
    "bich_ngoc_kiem": {
        "category": "Binh khí", "name": "Bích Ngọc Kiếm", "rarity": "Huyền", "type": "equipment", "slot": "weapon",
        "attack": 145, "defense": 20, "price": 25_000, "marketable": True,
        "description": "Ngọc kiếm sắc bén, linh lực lưu chuyển ổn định.",
    },
    "xich_viem_thuong": {
        "category": "Binh khí", "name": "Xích Viêm Thương", "rarity": "Huyền", "type": "equipment", "slot": "weapon",
        "attack": 190, "defense": 25, "price": 40_000, "marketable": True,
        "description": "Hỏa thương đỏ rực, thiên về sát thương trực diện.",
    },
    "huyen_bang_kiem": {
        "category": "Binh khí", "name": "Huyền Băng Kiếm", "rarity": "Địa", "type": "equipment", "slot": "weapon",
        "attack": 230, "defense": 45, "price": 60_000, "marketable": True,
        "description": "Băng kiếm ngàn năm, sắc bén và ổn định phòng thủ.",
    },
    "cuu_u_ma_dao": {
        "category": "Binh khí", "name": "Cửu U Ma Đao", "rarity": "Địa", "type": "equipment", "slot": "weapon",
        "attack": 310, "defense": 20, "price": 100_000, "marketable": True,
        "description": "Ma đao từ Cửu U, sức công kích hung lệ.",
    },
    "thien_loi_chien_kich": {
        "category": "Binh khí", "name": "Thiên Lôi Chiến Kích", "rarity": "Thiên", "type": "equipment", "slot": "weapon",
        "attack": 430, "defense": 60, "price": 200_000, "marketable": True,
        "description": "Chiến kích dẫn thiên lôi, uy lực cực mạnh.",
    },
    "tru_thien_kiem": {
        "category": "Binh khí", "name": "Tru Thiên Kiếm", "rarity": "Tiên", "type": "equipment", "slot": "weapon",
        "attack": 600, "defense": 100, "price": 500_000, "marketable": True,
        "description": "Kiếm tiên chuyên phá hộ thể và đại trận.",
    },
    "hon_don_than_binh": {
        "category": "Binh khí", "name": "Hỗn Độn Thần Binh", "rarity": "Thần", "type": "equipment", "slot": "weapon",
        "attack": 900, "defense": 160, "price": 1_000_000, "marketable": True,
        "description": "Thần binh sơ khai, cực hạn chiến lực trong Tiên Phường.",
    },

    # ---------- Shop · Linh vật (10) ----------
    "tu_linh_thao": {
        "category": "Linh vật", "name": "Tụ Linh Thảo", "rarity": "Phàm", "type": "consumable",
        "price": 1_000, "marketable": True, "cultivation": 120, "root": 1,
        "description": "Linh thảo cơ bản, dùng trực tiếp để bồi bổ căn cơ.",
    },
    "huyet_linh_hoa": {
        "category": "Linh vật", "name": "Huyết Linh Hoa", "rarity": "Phàm", "type": "consumable",
        "price": 2_500, "marketable": True, "cultivation": 250, "mind": 1,
        "description": "Hoa linh huyết, bổ sung tinh lực và đạo tâm.",
    },
    "bang_tam_lien": {
        "category": "Linh vật", "name": "Băng Tâm Liên", "rarity": "Hoàng", "type": "consumable",
        "price": 5_000, "marketable": True, "cultivation": 400, "insight": 2,
        "description": "Liên hoa hàn khí giúp tâm thần thanh tịnh.",
    },
    "thien_linh_qua": {
        "category": "Linh vật", "name": "Thiên Linh Quả", "rarity": "Huyền", "type": "consumable",
        "price": 10_000, "marketable": True, "cultivation": 700, "root": 2,
        "description": "Linh quả giàu linh lực, nâng cao căn cơ khi dùng.",
    },
    "long_huyet_qua": {
        "category": "Linh vật", "name": "Long Huyết Quả", "rarity": "Địa", "type": "consumable",
        "price": 20_000, "marketable": True, "cultivation": 1_200, "all_stats": 1,
        "description": "Quả mang huyết mạch long tộc, cải thiện toàn diện.",
    },
    "phuong_hoang_thao": {
        "category": "Linh vật", "name": "Phượng Hoàng Thảo", "rarity": "Địa", "type": "consumable",
        "price": 35_000, "marketable": True, "cultivation": 1_800, "fate": 3,
        "description": "Tiên thảo tái sinh, mang theo khí vận phượng hoàng.",
    },
    "ngu_sac_linh_chi": {
        "category": "Linh vật", "name": "Ngũ Sắc Linh Chi", "rarity": "Thiên", "type": "consumable",
        "price": 60_000, "marketable": True, "cultivation": 2_500, "all_stats": 2,
        "description": "Linh chi ngũ sắc, hỗ trợ mọi phương diện tu luyện.",
    },
    "cuu_diep_tien_lien": {
        "category": "Linh vật", "name": "Cửu Diệp Tiên Liên", "rarity": "Thiên", "type": "consumable",
        "price": 120_000, "marketable": True, "cultivation": 4_000, "root": 4, "insight": 2,
        "description": "Tiên liên chín lá, củng cố căn cơ và ngộ tính.",
    },
    "van_nien_linh_duoc": {
        "category": "Linh vật", "name": "Vạn Niên Linh Dược", "rarity": "Tiên", "type": "consumable",
        "price": 300_000, "marketable": True, "cultivation": 7_000, "all_stats": 3,
        "description": "Linh dược vạn năm, dược lực thuần hậu và toàn diện.",
    },
    "hon_don_tien_qua": {
        "category": "Linh vật", "name": "Hỗn Độn Tiên Quả", "rarity": "Thần", "type": "consumable",
        "price": 800_000, "marketable": True, "cultivation": 15_000, "all_stats": 5,
        "description": "Tiên quả hỗn độn, bảo vật tối thượng của Tiên Phường.",
    },

    # ---------- Shop · Công pháp (10) ----------
    "thanh_van_quyet": {
        "category": "Công pháp", "name": "《Thanh Vân Quyết》", "rarity": "Hoàng", "type": "technique",
        "price": 5_000, "marketable": False, "technique_stat": "root", "technique_bonus": 3,
        "description": "Công pháp nhập môn của Thanh Vân nhất mạch, chú trọng căn cơ và tu luyện ổn định.",
    },
    "hoa_van_cong": {
        "category": "Công pháp", "name": "《Hỏa Vân Công》", "rarity": "Hoàng", "type": "technique",
        "price": 10_000, "marketable": False, "technique_stat": "insight", "technique_bonus": 4,
        "description": "Công pháp hỏa hệ thiên về công kích và bạo phát.",
    },
    "bang_tam_quyet": {
        "category": "Công pháp", "name": "《Băng Tâm Quyết》", "rarity": "Huyền", "type": "technique",
        "price": 20_000, "marketable": False, "technique_stat": "mind", "technique_bonus": 5,
        "description": "Tâm pháp băng hệ, ổn định tâm tính và thần hồn.",
    },
    "kim_cang_quyet": {
        "category": "Công pháp", "name": "《Kim Cang Quyết》", "rarity": "Huyền", "type": "technique",
        "price": 30_000, "marketable": False, "technique_stat": "root", "technique_bonus": 6,
        "description": "Luyện thể tâm pháp, đề cao phòng ngự và căn cơ.",
    },
    "tu_duong_chan_kinh": {
        "category": "Công pháp", "name": "《Tử Dương Chân Kinh》", "rarity": "Địa", "type": "technique",
        "price": 50_000, "marketable": False, "technique_stat": "fate", "technique_bonus": 7,
        "description": "Chân kinh cổ xưa, dẫn dương khí tôi luyện thân và thần.",
    },
    "cuu_u_ma_kinh": {
        "category": "Công pháp", "name": "《Cửu U Ma Kinh》", "rarity": "Địa", "type": "technique",
        "price": 80_000, "marketable": False, "technique_stat": "mind", "technique_bonus": 8,
        "description": "Ma kinh Cửu U, thiên về sát phạt và bạo phát.",
    },
    "thien_loi_kinh": {
        "category": "Công pháp", "name": "《Thiên Lôi Kinh》", "rarity": "Thiên", "type": "technique",
        "price": 120_000, "marketable": False, "technique_stat": "insight", "technique_bonus": 10,
        "description": "Lôi pháp cao cấp, dẫn thiên lôi nhập thể.",
    },
    "thai_hu_kinh": {
        "category": "Công pháp", "name": "《Thái Hư Kinh》", "rarity": "Thiên", "type": "technique",
        "price": 200_000, "marketable": False, "technique_stat": "insight", "technique_bonus": 12,
        "description": "Thiên cấp công pháp, lĩnh hội hư không để tăng trưởng đạo hạnh.",
    },
    "cuu_thien_tien_kinh": {
        "category": "Công pháp", "name": "《Cửu Thiên Tiên Kinh》", "rarity": "Tiên", "type": "technique",
        "price": 500_000, "marketable": False, "technique_stat": "fate", "technique_bonus": 14,
        "description": "Tiên kinh thượng phẩm, mở rộng con đường tu hành lên cảnh giới cao.",
    },
    "hon_don_dao_kinh": {
        "category": "Công pháp", "name": "《Hỗn Độn Đạo Kinh》", "rarity": "Thần", "type": "technique",
        "price": 1_000_000, "marketable": False, "technique_stat": "root", "technique_bonus": 18,
        "description": "Đạo kinh tối thượng, lĩnh hội bản nguyên hỗn độn.",
    },

    # ---------- Non-shop legacy / gacha items ----------
    # These remain available to old saves / Gacha but are not part of the 60-item Shop.
    "tinh_thiet_ma_dao": {
        "category": "Binh khí", "name": "Tinh Thiết Ma Đao", "rarity": "Hoàng", "type": "equipment", "slot": "weapon",
        "attack": 95, "defense": 5, "path": "ma", "price": 800, "marketable": True,
        "description": "Bản vật phẩm cũ, giữ tương thích với dữ liệu và Gacha.",
    },
    "thien_co_lenh": {
        "category": "Bùa chú", "name": "Thiên Cơ Lệnh", "rarity": "Huyền", "type": "material", "price": 500,
        "marketable": False,
        "description": "Lệnh dùng cho Thiên Cơ Các và hệ thống Gacha.",
    },
    "tu_van_linh_qua": {
        "category": "Linh vật", "name": "Tử Vân Linh Quả", "rarity": "Huyền", "type": "consumable", "root": 3,
        "cultivation": 600, "price": 1800, "marketable": False,
        "description": "Linh quả hiếm tăng căn cốt và tu vi.",
    },
    "dao_qua_vo_cuc": {
        "category": "Linh vật", "name": "Đạo Quả Vô Cực", "rarity": "Thần", "type": "consumable", "all_stats": 5,
        "cultivation": 5000, "marketable": False,
        "description": "Đạo quả hiếm, tăng đều toàn bộ căn cơ bản thân.",
    },
    "thanh_lien_ho": {
        "category": "Pháp bảo", "name": "Thanh Liên Hộ", "rarity": "Địa", "type": "equipment", "slot": "artifact",
        "attack": 35, "defense": 125, "path": "tien", "price": 2500, "marketable": False,
        "description": "Pháp bảo hộ thân của Thanh Liên nhất mạch.",
    },
    "huyet_ma_dao": {
        "category": "Binh khí", "name": "Huyết Ma Đao", "rarity": "Địa", "type": "equipment", "slot": "weapon",
        "attack": 190, "defense": 0, "path": "ma", "price": 0, "marketable": False,
        "description": "Ma khí hung lệ, phần thưởng cũ/gacha; không bán trong Tiên Phường.",
    },
    "thanh_van_kiem": {
        "category": "Binh khí", "name": "Thanh Vân Kiếm", "rarity": "Thiên", "type": "equipment", "slot": "weapon",
        "attack": 260, "defense": 40, "path": "tien", "price": 0, "marketable": False,
        "description": "Kiếm ý thanh tịnh, phần thưởng cũ/gacha; không bán trong Tiên Phường.",
    },
    "thien_kiep_phap_bao": {
        "category": "Pháp bảo", "name": "Thiên Kiếp Pháp Bảo", "rarity": "Tiên", "type": "equipment", "slot": "artifact",
        "attack": 380, "defense": 260, "price": 0, "marketable": False,
        "description": "Mảnh pháp bảo chống thiên uy, phần thưởng cũ/gacha; không bán trong Tiên Phường.",
    },

    "huyen_thiet_giap": {
        "category": "Áo giáp", "name": "Huyền Thiết Giáp", "rarity": "Huyền", "type": "equipment",
        "slot": "armor", "attack": 10, "defense": 140, "price": 28_000, "marketable": True,
        "description": "Giáp huyền thiết tăng phòng thủ, phù hợp Thể Đạo.",
    },
    "thanh_van_dao_bao": {
        "category": "Áo giáp", "name": "Thanh Vân Đạo Bào", "rarity": "Địa", "type": "equipment",
        "slot": "armor", "attack": 25, "defense": 200, "price": 70_000, "marketable": True,
        "description": "Đạo bào thanh vân, cân bằng công thủ cho pháp tu.",
    },
    "linh_ngoc_gioi": {
        "category": "Phụ kiện", "name": "Linh Ngọc Giới", "rarity": "Hoàng", "type": "equipment",
        "slot": "accessory", "attack": 15, "defense": 25, "price": 12_000, "marketable": True,
        "description": "Nhẫn linh ngọc, tăng nhẹ công và thủ.",
    },
    "thien_co_ho_phu": {
        "category": "Phụ kiện", "name": "Thiên Cơ Hộ Phù", "rarity": "Huyền", "type": "equipment",
        "slot": "accessory", "attack": 30, "defense": 40, "price": 35_000, "marketable": True,
        "description": "Hộ phù thiên cơ, hỗ trợ tẩu thoát và phòng ngự.",
    },
}

SHOP_ORDER = [
    # Pháp bảo
    "thanh_tam_ngoc_boi", "tu_linh_chau", "huyen_thiet_linh_kinh", "kim_cang_ho_tam_kinh", "ngu_hanh_linh_chau",
    "thien_co_bao_kinh", "cuu_long_ngoc_an", "thai_hu_linh_dang", "tru_tien_co_an", "hon_don_thien_chau",
    # Bùa chú
    "hoi_xuan_phu", "tu_linh_phu", "kim_cang_phu", "ngu_phong_phu", "liet_hoa_phu",
    "bang_tam_phu", "tran_hon_phu", "thien_loi_phu", "cuu_thien_than_phu", "diet_ma_thien_phu",
    # Đan dược
    "tu_khi_dan", "hoi_khi_dan", "hoi_huyet_dan", "tang_toc_dan", "truc_co_dan",
    "kim_dan_ngung_hon_dan", "anh_hon_dan", "hoa_than_dan", "do_kiep_than_dan", "cuu_chuyen_tien_dan",
    # Binh khí
    "thiet_kiem", "thanh_phong_kiem", "huyen_thiet_dao", "bich_ngoc_kiem", "xich_viem_thuong",
    "huyen_bang_kiem", "cuu_u_ma_dao", "thien_loi_chien_kich", "tru_thien_kiem", "hon_don_than_binh",
    # Linh vật
    "tu_linh_thao", "huyet_linh_hoa", "bang_tam_lien", "thien_linh_qua", "long_huyet_qua",
    "phuong_hoang_thao", "ngu_sac_linh_chi", "cuu_diep_tien_lien", "van_nien_linh_duoc", "hon_don_tien_qua",
    # Công pháp
    "thanh_van_quyet", "hoa_van_cong", "bang_tam_quyet", "kim_cang_quyet", "tu_duong_chan_kinh",
    "cuu_u_ma_kinh", "thien_loi_kinh", "thai_hu_kinh", "cuu_thien_tien_kinh", "hon_don_dao_kinh",
]

SHOP_CATEGORIES = [
    ("all", "Tất cả", "Xem toàn bộ vật phẩm trong Tiên Phường"),
    ("Pháp bảo", "Pháp bảo", "Bảo vật hộ thân, thiên về phòng thủ và chiến lực"),
    ("Bùa chú", "Bùa chú", "Linh phù, pháp lệnh và vật phẩm kỳ môn"),
    ("Đan dược", "Đan dược", "Đan dược dùng để tăng tu vi và trạng thái"),
    ("Binh khí", "Binh khí", "Kiếm, đao và các loại vũ khí chiến đấu"),
    ("Linh vật", "Linh vật", "Linh quả, đạo quả và vật phẩm đặc biệt"),
    ("Công pháp", "Công pháp", "Bí điển tu hành, khai mở con đường và nội tình đạo pháp"),
]

GACHA_TABLE = [
    ("Phàm", 60.0, [("item", "tu_khi_dan", 2), ("stones", 250, None)]),
    ("Hoàng", 25.0, [("item", "hoi_khi_dan", 2), ("item", "thanh_phong_kiem", 1), ("item", "tinh_thiet_ma_dao", 1), ("stones", 700, None)]),
    ("Huyền", 10.0, [("item", "tu_van_linh_qua", 1), ("item", "thanh_lien_ho", 1), ("cultivation", 1000, None)]),
    ("Địa", 4.0, [("item", "huyet_ma_dao", 1), ("item", "thanh_lien_ho", 1), ("cultivation", 2500, None)]),
    ("Thiên", 0.9, [("item", "thanh_van_kiem", 1), ("item", "thien_kiep_phap_bao", 1)]),
    ("Tiên", 0.099, [("item", "thien_kiep_phap_bao", 1), ("stones", 30000, None)]),
    ("Thần", 0.001, [("item", "dao_qua_vo_cuc", 1)]),
]

REDEEM_CODES = {
    "meta102026": {
        "max_uses": 0,  # 0 = không giới hạn tổng lượt; mỗi người vẫn chỉ nhận 1 lần.
        "rewards": {
            "spirit_stones": 500_000,
            "items": {
                "thanh_van_quyet": 1,
                "tu_duong_chan_kinh": 1,
                "thai_hu_kinh": 1,
            },
        },
        "description": "Quà ra mắt Meta 10/2026.",
    },
}

DESTINIES = [
    ("Thiên Mệnh Chi Tử", 0.5),
    ("Đại Khí Vãn Thành", 4.0),
    ("Sát Phạt Chi Mệnh", 7.0),
    ("Thiên Sát Cô Tinh", 4.0),
    ("Phúc Tinh", 5.0),
    ("Kiếm Tu Chi Mệnh", 4.5),
    ("Bình Phàm Chi Mệnh", 75.0),
]

PATH_TALENTS = {
    "tien": [
        ("Thanh Vân Đạo Thể", 30.0), ("Kiếm Tâm Sơ Thành", 27.0),
        ("Tử Khí Đông Lai", 18.0), ("Dược Linh Thân", 25.0),
    ],
    "ma": [
        ("Huyết Ma Chi Thể", 30.0), ("Thôn Thiên Ma Cốt", 27.0),
        ("Ma Diễm Tâm", 18.0), ("Hắc Nhật Ma Thai", 25.0),
    ],
}

DESTINY_DESCRIPTIONS = {
    "Thiên Mệnh Chi Tử": "Khí vận và phúc duyên tăng mạnh; dễ gặp kỳ ngộ hiếm.",
    "Đại Khí Vãn Thành": "Đầu game hơi chậm, về sau càng tu càng bứt phá.",
    "Sát Phạt Chi Mệnh": "Chiến đấu nguy hiểm nhưng nhận chiến lợi phẩm tốt hơn.",
    "Thiên Sát Cô Tinh": "Độc hành gặp nhiều cơ duyên; ít phụ thuộc người khác.",
    "Phúc Tinh": "Dễ nhận thêm vật phẩm và linh thạch từ sự kiện.",
    "Kiếm Tu Chi Mệnh": "Tăng hiệu quả cho pháp kiếm và build công kích.",
    "Bình Phàm Chi Mệnh": "Mọi thứ cân bằng; vận mệnh chưa lộ rõ.",
}

TALENT_DESCRIPTIONS = {
    "Thanh Vân Đạo Thể": "Tu luyện ổn định, căn cơ tốt hơn.",
    "Kiếm Tâm Sơ Thành": "Tăng chiến lực khi dùng kiếm.",
    "Tử Khí Đông Lai": "Tăng tỷ lệ kỳ ngộ khi khám phá.",
    "Dược Linh Thân": "Đan dược phát huy hiệu quả tốt hơn.",
    "Huyết Ma Chi Thể": "Ma đạo được tăng sức mạnh khi chiến đấu.",
    "Thôn Thiên Ma Cốt": "Tu luyện nhanh hơn nhưng nghiệp lực tăng.",
    "Ma Diễm Tâm": "Thiên về sát phạt và bạo phát.",
    "Hắc Nhật Ma Thai": "Tăng sức mạnh khi đi vào khu vực nguy hiểm.",
}

MONSTERS = [
    # (name, base_hp, cultivation_reward, spirit_stones) — stats are scaled to player power in engine
    ("Thanh Lang", 100, 140, 120),
    ("Xích Viêm Xà", 130, 180, 180),
    ("Hắc Giáp Hùng", 170, 220, 230),
    ("Quỷ Diện Chu", 220, 280, 300),
    ("Huyết Nha Ma Lang", 300, 400, 420),
    ("Băng Cốt Lang", 150, 200, 200),
    ("Lôi Ảnh Báo", 190, 250, 260),
    ("U Minh Cốt Sư", 260, 340, 350),
    ("Hỏa Lân Giao", 320, 420, 450),
    ("Thiên Kiếm Yêu Hồ", 380, 500, 520),
]

EXPLORATION_EVENTS = [
    ("linh_mach", 25.0), ("linh_thao", 20.0), ("monster", 25.0),
    ("merchant", 9.0), ("ancient_cave", 7.0), ("danger", 6.0), ("epiphany", 5.0), ("boss", 5.0),
]


# Boss encounters for exploration. hp/attack/defense are battle stats; reward is linh thach.
BOSS_MONSTERS = [
    # Base stats are scaled relative to player combat power in engine._new_encounter
    {"name": "Thanh Giao Vương", "hp": 1800, "attack": 170, "defense": 120, "reward": 1800, "cultivation": 900},
    {"name": "Huyết Hải Ma Tôn", "hp": 2600, "attack": 240, "defense": 150, "reward": 3200, "cultivation": 1500},
    {"name": "Cửu Vĩ Thiên Hồ", "hp": 3400, "attack": 310, "defense": 190, "reward": 5200, "cultivation": 2200},
    {"name": "Lôi Phong Kiếm Ma", "hp": 2200, "attack": 210, "defense": 140, "reward": 2500, "cultivation": 1200},
    {"name": "Huyền Thiên Cốt Tôn", "hp": 4000, "attack": 360, "defense": 220, "reward": 6800, "cultivation": 2800},
    {"name": "Vạn Kiếp Ma Hoàng", "hp": 5200, "attack": 420, "defense": 260, "reward": 9000, "cultivation": 3600},
]


# ========================= TU CHAN EXPANSION v1.16 =========================
# These data tables are intentionally data-driven so future realms/zones can be
# added without rewriting engine logic.
TRIBULATION_REALMS = {9}  # Độ Kiếp is the only realm gated by Thiên Kiếp.

DAO_PATHS = {
    "kiem": {"name": "Kiếm Đạo", "icon": "🗡️", "stages": ["Kiếm Khí", "Kiếm Ý", "Kiếm Thế", "Kiếm Tâm"], "stat": "insight"},
    "dao": {"name": "Đao Đạo", "icon": "🔪", "stages": ["Đao Khí", "Đao Ý", "Đao Thế", "Đao Tâm"], "stat": "mind"},
    "phap": {"name": "Pháp Đạo", "icon": "🔮", "stages": ["Pháp Khí", "Pháp Ý", "Pháp Thế", "Pháp Tâm"], "stat": "fate"},
    "the": {"name": "Thể Đạo", "icon": "👊", "stages": ["Khí Huyết", "Thể Ý", "Thể Thế", "Bất Diệt Thể"], "stat": "root"},
}
DAO_STAGE_THRESHOLD = (100, 400, 1200, 3000)

# v1.16 exploration is intentionally staged: only the first two regions are open.
# Future regions remain in the data table but are hidden until their update.
EXPLORE_ZONES = {
    "hoangnguyen": {
        "name": "Hoang Nguyên", "min_realm": 0, "danger": 1.0, "reward": (100, 350), "enabled": True,
        "events": ("linh_mach", "linh_thao", "merchant", "ancient_cave", "epiphany", "monster"),
        "description": "Đất hoang rộng lớn, thích hợp tìm linh mạch, linh thảo và cơ duyên cổ xưa.",
    },
    "yeuthusonmach": {
        "name": "Yêu Thú Sơn Mạch", "min_realm": 1, "danger": 1.25, "reward": (180, 600), "enabled": True,
        "events": ("monster", "boss", "linh_thao", "ancient_cave", "beast_cache", "bloodline"),
        "description": "Núi non hiểm trở, yêu thú dày đặc, dễ gặp yêu bảo và huyết mạch cơ duyên.",
    },
    "dongphu": {"name": "Cổ Động Phủ", "min_realm": 2, "danger": 1.45, "reward": (350, 1200), "enabled": False, "events": ("ancient_cave", "epiphany", "boss", "danger"), "description": "Chưa khai mở."},
    "haivuc": {"name": "Vạn Lý Hải Vực", "min_realm": 4, "danger": 1.75, "reward": (700, 2200), "enabled": False, "events": ("monster", "boss", "ancient_cave", "linh_mach"), "description": "Chưa khai mở."},
    "mavuc": {"name": "Cửu U Ma Vực", "min_realm": 5, "danger": 2.10, "reward": (1000, 3500), "enabled": False, "events": ("boss", "danger", "ancient_cave", "epiphany"), "description": "Chưa khai mở."},
}

ASCENSION_TOWER = {
    "max_floor": 300,
    "daily_attempts": 3,
    "base_reward": 650,
}

SECT_TOWER = {
    "max_floor": 200,
    "daily_attempts": 2,
    "base_reward": 900,
}

TRIAL_TOWER = {
    "base_reward": 320,
    "floor_reward": 85,
    "max_floor": 100,
    "daily_attempts": 5,
    "floor_penalty": 0.0105,
}

SECT_MISSIONS = {
    "hunt_beast": {"name": "Săn Yêu", "target": 5, "reward": 300, "contribution": 120},
    "collect_spirit": {"name": "Thu Linh Thảo", "target": 3, "reward": 250, "contribution": 100},
    "cultivate": {"name": "Tinh Tiến Tu Vi", "target": 3, "reward": 220, "contribution": 90},
    "explore": {"name": "Xuất Sơn Tầm Cơ Duyên", "target": 2, "reward": 280, "contribution": 110},
}

INHERITANCE_EVENTS = [
    {"key": "kiem_tu", "name": "Kiếm Tu Cổ Mộ", "reward": "kiem_y_fragment", "chance": 0.10},
    {"key": "dan_vuong", "name": "Đan Vương Truyền Thừa", "reward": "hoi_khi_dan", "chance": 0.12},
    {"key": "ma_quan", "name": "Ma Quân Tàn Niệm", "reward": "huyet_ma_dao", "chance": 0.08},
]

def item_slot(item_id: str) -> str | None:
    item = ITEMS.get(item_id) or {}
    if item.get("type") != "equipment":
        return None
    if item.get("slot"):
        return item["slot"]
    cat = item.get("category", "")
    if cat == "Binh khí":
        return "weapon"
    if cat == "Pháp bảo":
        return "artifact"
    if cat in {"Áo giáp", "Giáp"}:
        return "armor"
    if cat in {"Phụ kiện", "Linh vật"}:
        return "accessory"
    return "artifact"

STATUS_EFFECTS = {
    "burn": {"name": "Thiêu Đốt", "kind": "dot", "duration": 3, "power": 0.08},
    "poison": {"name": "Trúng Độc", "kind": "dot", "duration": 4, "power": 0.05},
    "stun": {"name": "Choáng", "kind": "control", "duration": 1, "power": 1.0},
    "slow": {"name": "Làm Chậm", "kind": "debuff", "duration": 2, "power": 0.15},
    "shield": {"name": "Hộ Thuẫn", "kind": "buff", "duration": 2, "power": 0.20},
    "bleed": {"name": "Chảy Máu", "kind": "dot", "duration": 3, "power": 0.06},
}

WORLD_REGIONS = {
    "pham_gioi": {
        "name": "Phàm Giới",
        "zones": ["hoangnguyen", "yeuthusonmach", "dongphu", "haivuc"],
        "description": "Cõi phàm nhân và tiên môn sơ cấp.",
    },
    "ma_vuc": {
        "name": "Ma Vực",
        "zones": ["mavuc"],
        "description": "Vùng ma khí, rủi ro cao và cơ duyên bất thường.",
    },
}


