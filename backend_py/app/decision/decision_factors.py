"""
decision/decision_factors.py — Yếu tố đặc trưng cho 14 business category.

Mỗi factor có 3 lớp diễn giải:
  1. spec_field — tên field thực trong products_detail.json (qua dmx_registry)
  2. simple_meaning — ý nghĩa đơn giản cho người dùng
  3. use_context — ngữ cảnh sử dụng dễ hình dung

Tất cả spec_field đều có thực trong dmx_registry.json, KHÔNG bịa.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FactorDef:
    factor_id: str           # ID duy nhất: "cooling_capacity_btu"
    label: str               # Tên hiển thị: "Công suất làm lạnh"
    spec_field: str          # Field thực trong spec: "cooling_capacity_btu"
    unit: str                # Đơn vị: "BTU", "dB", "lít"
    simple_meaning: str      # Lớp 2: ý nghĩa đơn giản
    use_context: str         # Lớp 3: ngữ cảnh sử dụng
    higher_is_better: bool   # True = giá trị cao hơn tốt hơn
    is_numeric: bool = True  # False nếu field là text (cần compare khác)


# ---------------------------------------------------------------------------
# Nguồn sự thật: dmx_registry.json → spec_map → keys
# Mỗi category tối đa 4 yếu tố
# ---------------------------------------------------------------------------

DECISION_FACTORS: dict[str, list[FactorDef]] = {
    # -----------------------------------------------------------------------
    # Máy lạnh
    # -----------------------------------------------------------------------
    "air_conditioner": [
        FactorDef(
            factor_id="cooling_capacity_btu",
            label="Công suất làm lạnh",
            spec_field="cooling_capacity_btu",
            unit="BTU",
            simple_meaning="BTU càng cao, máy làm mát càng nhanh và mạnh cho phòng lớn",
            use_context="Phòng 15m² cần ~9.000 BTU, phòng 25m² cần ~18.000 BTU",
            higher_is_better=True,
        ),
        FactorDef(
            factor_id="indoor_noise_min_db",
            label="Độ ồn hoạt động",
            spec_field="indoor_noise_min_db",
            unit="dB",
            simple_meaning="Số dB càng thấp, máy chạy càng êm — quan trọng cho phòng ngủ",
            use_context="Dưới 26 dB gần như không nghe thấy khi ngủ, trên 35 dB sẽ gây ồn",
            higher_is_better=False,
        ),
        FactorDef(
            factor_id="power_kwh",
            label="Tiêu thụ điện",
            spec_field="power_kwh",
            unit="kWh",
            simple_meaning="Số kWh càng thấp, tiền điện hàng tháng càng ít",
            use_context="Máy 0.8 kWh/h chạy 8h/ngày ≈ 600.000đ/tháng tiền điện",
            higher_is_better=False,
        ),
        FactorDef(
            factor_id="area_coverage",
            label="Diện tích phòng phù hợp",
            spec_field="area_min_m2",
            unit="m²",
            simple_meaning="Phạm vi diện tích phòng mà máy làm lạnh hiệu quả nhất",
            use_context="Chọn máy có phạm vi bao phủ phòng bạn — mua quá nhỏ sẽ chạy quá tải",
            higher_is_better=True,
        ),
    ],

    # -----------------------------------------------------------------------
    # Tủ lạnh
    # -----------------------------------------------------------------------
    "tu_lanh": [
        FactorDef(
            factor_id="capacity_liters",
            label="Dung tích sử dụng",
            spec_field="capacity_liters",
            unit="lít",
            simple_meaning="Dung tích càng lớn, chứa được càng nhiều thực phẩm",
            use_context="Gia đình 2 người cần ~150-200L, 4 người cần ~300-400L",
            higher_is_better=True,
        ),
        FactorDef(
            factor_id="power_kwh_per_day",
            label="Điện năng tiêu thụ",
            spec_field="power_kwh_per_day",
            unit="kWh/ngày",
            simple_meaning="Số kWh/ngày càng thấp, tiết kiệm điện càng nhiều",
            use_context="Tủ 1.2 kWh/ngày ≈ 100.000đ/tháng, tủ 0.8 kWh/ngày ≈ 65.000đ/tháng",
            higher_is_better=False,
        ),
        FactorDef(
            factor_id="cooling_tech",
            label="Công nghệ làm lạnh",
            spec_field="cooling_tech",
            unit="",
            simple_meaning="Inverter tiết kiệm điện và êm hơn, No Frost không cần rã đông",
            use_context="Tủ No Frost không bị đóng tuyết — bạn không phải rã đông thủ công",
            higher_is_better=True,
            is_numeric=False,
        ),
        FactorDef(
            factor_id="total_capacity_liters",
            label="Dung tích tổng",
            spec_field="total_capacity_liters",
            unit="lít",
            simple_meaning="Tổng dung tích bao gồm cả ngăn đá và ngăn mát",
            use_context="Dung tích tổng thường lớn hơn dung tích sử dụng 10-20%",
            higher_is_better=True,
        ),
    ],

    # -----------------------------------------------------------------------
    # Máy giặt
    # -----------------------------------------------------------------------
    "may_giat": [
        FactorDef(
            factor_id="wash_capacity_kg",
            label="Khối lượng giặt",
            spec_field="wash_capacity_kg",
            unit="kg",
            simple_meaning="Số kg càng lớn, giặt được càng nhiều quần áo mỗi lần",
            use_context="Gia đình 2-3 người cần 7-8 kg, 4+ người cần 9-10 kg",
            higher_is_better=True,
        ),
        FactorDef(
            factor_id="spin_speed_rpm",
            label="Tốc độ vắt",
            spec_field="spin_speed_rpm",
            unit="vòng/phút",
            simple_meaning="RPM cao hơn = quần áo ra khô hơn, giảm thời gian phơi",
            use_context="1.200 RPM trở lên giúp đồ gần như ráo nước, giảm phơi nắng",
            higher_is_better=True,
        ),
        FactorDef(
            factor_id="energy_rating",
            label="Hiệu suất năng lượng",
            spec_field="energy_rating",
            unit="",
            simple_meaning="Xếp hạng năng lượng càng cao, điện tiêu thụ càng ít",
            use_context="Máy 5 sao tiết kiệm điện hơn 30% so với máy 3 sao cùng loại",
            higher_is_better=True,
            is_numeric=False,
        ),
        FactorDef(
            factor_id="household_size_text",
            label="Số người sử dụng phù hợp",
            spec_field="household_size_text",
            unit="người",
            simple_meaning="Hãng khuyến nghị số thành viên gia đình phù hợp với máy",
            use_context="Máy ghi '5-7 người' là phù hợp hộ gia đình đông, '1-2 người' cho sinh viên",
            higher_is_better=True,
            is_numeric=False,
        ),
    ],

    # -----------------------------------------------------------------------
    # Máy sấy quần áo
    # -----------------------------------------------------------------------
    "may_say_quan_ao": [
        FactorDef(
            factor_id="dry_capacity_kg",
            label="Khối lượng sấy",
            spec_field="dry_capacity_kg",
            unit="kg",
            simple_meaning="Số kg càng lớn, sấy được càng nhiều đồ mỗi lần",
            use_context="Gia đình 4 người cần tối thiểu 8 kg, sấy chăn/mền cần 10 kg+",
            higher_is_better=True,
        ),
        FactorDef(
            factor_id="power_watt",
            label="Công suất tiêu thụ",
            spec_field="power_watt",
            unit="W",
            simple_meaning="Watt càng thấp, tiền điện càng ít — nhưng sấy có thể chậm hơn",
            use_context="Máy 2.000W sấy nhanh nhưng tốn điện, máy 1.000W tiết kiệm hơn",
            higher_is_better=False,
        ),
        FactorDef(
            factor_id="max_temp_c",
            label="Nhiệt độ sấy tối đa",
            spec_field="max_temp_c",
            unit="°C",
            simple_meaning="Nhiệt cao giúp sấy nhanh nhưng có thể hại vải mỏng",
            use_context="Đồ cotton chịu được 60-70°C, đồ lụa/len chỉ nên dưới 40°C",
            higher_is_better=True,
        ),
    ],

    # -----------------------------------------------------------------------
    # Máy rửa chén
    # -----------------------------------------------------------------------
    "may_rua_chen": [
        FactorDef(
            factor_id="capacity_sets",
            label="Số bộ chén bát",
            spec_field="capacity_sets",
            unit="bộ",
            simple_meaning="Số bộ rửa được 1 lần — gia đình đông cần máy rửa được nhiều bộ",
            use_context="4 người thường cần máy 9-12 bộ, 2 người cần 6-8 bộ",
            higher_is_better=True,
        ),
        FactorDef(
            factor_id="noise_db",
            label="Độ ồn hoạt động",
            spec_field="noise_db_text",
            unit="dB",
            simple_meaning="Số dB càng thấp, máy chạy càng êm — quan trọng nếu bếp liền phòng khách",
            use_context="Dưới 45 dB là yên tĩnh, trên 50 dB sẽ nghe rõ tiếng máy chạy",
            higher_is_better=False,
            is_numeric=False,
        ),
        FactorDef(
            factor_id="water_consumption_l",
            label="Tiêu thụ nước",
            spec_field="water_consumption_l",
            unit="lít/lần",
            simple_meaning="Lít nước dùng mỗi lần rửa — tiết kiệm nước hơn rửa tay",
            use_context="Máy dùng 9-12 lít/lần tiết kiệm hơn rửa tay (thường 40-60 lít)",
            higher_is_better=False,
        ),
        FactorDef(
            factor_id="power_watt_dishwasher",
            label="Công suất",
            spec_field="power_watt",
            unit="W",
            simple_meaning="Watt càng thấp, tiền điện mỗi lần rửa càng ít",
            use_context="Máy 1.800W rửa 1 lần tốn khoảng 4.000đ tiền điện",
            higher_is_better=False,
        ),
    ],

    # -----------------------------------------------------------------------
    # Tủ đông / Tủ mát
    # -----------------------------------------------------------------------
    "tu_dong_tu_mat": [
        FactorDef(
            factor_id="capacity_liters_freezer",
            label="Dung tích sử dụng",
            spec_field="capacity_liters",
            unit="lít",
            simple_meaning="Dung tích càng lớn, trữ được càng nhiều thực phẩm đông lạnh",
            use_context="Kinh doanh nhỏ cần 200-300L, gia đình thường 100-200L",
            higher_is_better=True,
        ),
        FactorDef(
            factor_id="power_kwh_per_day_freezer",
            label="Điện năng tiêu thụ",
            spec_field="power_kwh_per_day",
            unit="kWh/ngày",
            simple_meaning="Số kWh/ngày càng thấp, tiết kiệm điện càng nhiều",
            use_context="Tủ đông thường chạy 24/7, tiết kiệm 0.5 kWh/ngày = 45.000đ/tháng",
            higher_is_better=False,
        ),
        FactorDef(
            factor_id="chest_type",
            label="Loại tủ",
            spec_field="chest_type",
            unit="",
            simple_meaning="Tủ đông để trữ đông thực phẩm, tủ mát để bảo quản mát đồ uống",
            use_context="Quán nước/tiệm cần tủ mát, gia đình trữ thịt cá cần tủ đông",
            higher_is_better=True,
            is_numeric=False,
        ),
    ],

    # -----------------------------------------------------------------------
    # Máy nước nóng
    # -----------------------------------------------------------------------
    "may_nuoc_nong": [
        FactorDef(
            factor_id="tank_liters",
            label="Dung tích bình chứa",
            spec_field="tank_liters",
            unit="lít",
            simple_meaning="Bình càng lớn, nước nóng dùng được càng lâu mỗi lần",
            use_context="1 người tắm cần ~20L nước nóng, 4 người dùng liên tục cần 30L+",
            higher_is_better=True,
        ),
        FactorDef(
            factor_id="heating_power_w",
            label="Công suất làm nóng",
            spec_field="heating_power_w",
            unit="W",
            simple_meaning="Watt càng cao, nước nóng lên càng nhanh",
            use_context="2.500W nóng nước 30L trong ~30 phút, 4.500W chỉ cần ~15 phút",
            higher_is_better=True,
        ),
        FactorDef(
            factor_id="heater_type",
            label="Loại máy",
            spec_field="heater_type",
            unit="",
            simple_meaning="Bình nước nóng gián tiếp tiết kiệm, trực tiếp nóng tức thì",
            use_context="Bình gián tiếp phù hợp gia đình, trực tiếp phù hợp phòng trọ nhỏ",
            higher_is_better=True,
            is_numeric=False,
        ),
        FactorDef(
            factor_id="has_pump",
            label="Bơm trợ lực",
            spec_field="has_pump",
            unit="",
            simple_meaning="Có bơm trợ lực giúp nước nóng ra mạnh hơn ở tầng cao",
            use_context="Nhà tầng 2-3 hoặc áp lực nước yếu rất cần bơm trợ lực",
            higher_is_better=True,
            is_numeric=False,
        ),
    ],

    # -----------------------------------------------------------------------
    # Micro karaoke (tách riêng khỏi micro_phone)
    # -----------------------------------------------------------------------
    "micro_karaoke": [
        FactorDef(
            factor_id="battery_life_karaoke",
            label="Thời lượng pin",
            spec_field="battery_life_text",
            unit="",
            simple_meaning="Pin lâu hơn = hát được nhiều giờ hơn không lo hết pin",
            use_context="Micro karaoke pin 6-8 giờ đủ cho buổi tiệc, 3-4 giờ chỉ đủ hát lót",
            higher_is_better=True,
            is_numeric=False,
        ),
        FactorDef(
            factor_id="mic_type_karaoke",
            label="Loại micro",
            spec_field="mic_type",
            unit="",
            simple_meaning="Micro không dây tiện di chuyển, có dây ổn định hơn về tín hiệu",
            use_context="Hát karaoke gia đình nên dùng không dây, hát sân khấu cần có dây",
            higher_is_better=True,
            is_numeric=False,
        ),
        FactorDef(
            factor_id="connector_karaoke",
            label="Jack cắm kết nối",
            spec_field="connector_type",
            unit="",
            simple_meaning="Loại jack quyết định tương thích với loa/amply bạn đang có",
            use_context="Jack 6.5mm phổ biến cho amply karaoke, 3.5mm cho loa bluetooth nhỏ",
            higher_is_better=True,
            is_numeric=False,
        ),
        FactorDef(
            factor_id="polar_karaoke",
            label="Hướng thu âm",
            spec_field="polar_pattern",
            unit="",
            simple_meaning="Thu 1 hướng (cardioid) hát rõ giọng hơn, đa hướng thu cả nhóm",
            use_context="Hát solo chọn cardioid, karaoke nhóm có thể dùng đa hướng",
            higher_is_better=True,
            is_numeric=False,
        ),
    ],

    # -----------------------------------------------------------------------
    # Micro thu âm điện thoại (tách riêng khỏi micro_karaoke)
    # -----------------------------------------------------------------------
    "micro_phone": [
        FactorDef(
            factor_id="connector_phone",
            label="Kiểu kết nối",
            spec_field="connector_type",
            unit="",
            simple_meaning="USB-C / Lightning / 3.5mm — phải khớp cổng điện thoại bạn đang dùng",
            use_context="iPhone cần Lightning/USB-C, Android cần USB-C hoặc 3.5mm",
            higher_is_better=True,
            is_numeric=False,
        ),
        FactorDef(
            factor_id="polar_phone",
            label="Hướng thu âm",
            spec_field="polar_pattern",
            unit="",
            simple_meaning="Thu 1 hướng giảm tạp âm khi quay video, đa hướng thu phỏng vấn",
            use_context="Quay vlog cần cardioid, phỏng vấn/podcast cần omnidirectional",
            higher_is_better=True,
            is_numeric=False,
        ),
        FactorDef(
            factor_id="battery_life_phone",
            label="Thời lượng pin",
            spec_field="battery_life_text",
            unit="",
            simple_meaning="Pin lâu = quay/ghi âm dài mà không lo hết pin",
            use_context="Quay video 2-3 giờ liên tục cần pin ít nhất 4-5 giờ",
            higher_is_better=True,
            is_numeric=False,
        ),
    ],

    # -----------------------------------------------------------------------
    # Đồng hồ thông minh
    # -----------------------------------------------------------------------
    "dong_ho_thong_minh": [
        FactorDef(
            factor_id="battery_life_watch",
            label="Thời gian sử dụng pin",
            spec_field="battery_life_text",
            unit="",
            simple_meaning="Pin dùng càng lâu, sạc ít lần hơn — tiện cho người bận rộn",
            use_context="Pin 7 ngày sạc tuần 1 lần, pin 1-2 ngày phải sạc hàng đêm",
            higher_is_better=True,
            is_numeric=False,
        ),
        FactorDef(
            factor_id="water_resistance",
            label="Chống nước",
            spec_field="water_resistance",
            unit="",
            simple_meaning="Chống nước tốt hơn = đeo bơi, tắm mưa không lo hỏng",
            use_context="5 ATM đeo bơi được, 1 ATM chỉ chịu mồ hôi và mưa nhỏ",
            higher_is_better=True,
            is_numeric=False,
        ),
        FactorDef(
            factor_id="screen_size_watch",
            label="Kích thước màn hình",
            spec_field="screen_size_text",
            unit="",
            simple_meaning="Màn hình to dễ đọc tin nhắn nhưng đeo nặng tay hơn",
            use_context="Cổ tay nhỏ chọn 40-42mm, tay lớn chọn 44-46mm",
            higher_is_better=True,
            is_numeric=False,
        ),
        FactorDef(
            factor_id="os_watch",
            label="Hệ điều hành",
            spec_field="os",
            unit="",
            simple_meaning="WearOS (Android) hoặc watchOS (iPhone) — phải khớp điện thoại bạn",
            use_context="Dùng iPhone nên chọn Apple Watch, Android chọn Galaxy Watch/WearOS",
            higher_is_better=True,
            is_numeric=False,
        ),
    ],

    # -----------------------------------------------------------------------
    # Máy tính bảng
    # -----------------------------------------------------------------------
    "may_tinh_bang": [
        FactorDef(
            factor_id="battery_mah_tablet",
            label="Dung lượng pin",
            spec_field="battery_mah_text",
            unit="",
            simple_meaning="Pin mAh càng lớn, dùng được càng lâu mỗi lần sạc",
            use_context="7.000 mAh dùng khoảng 8 giờ liên tục, 10.000 mAh lên đến 12 giờ",
            higher_is_better=True,
            is_numeric=False,
        ),
        FactorDef(
            factor_id="ram_tablet",
            label="RAM",
            spec_field="ram_text",
            unit="",
            simple_meaning="RAM càng nhiều, mở nhiều app cùng lúc càng mượt, không bị giật",
            use_context="4 GB đủ lướt web, 8 GB+ mượt cho chỉnh ảnh/video/đa nhiệm",
            higher_is_better=True,
            is_numeric=False,
        ),
        FactorDef(
            factor_id="storage_tablet",
            label="Bộ nhớ trong",
            spec_field="storage_text",
            unit="",
            simple_meaning="Bộ nhớ càng lớn, chứa được nhiều ảnh, video, ứng dụng hơn",
            use_context="64 GB đủ dùng cơ bản, 128 GB+ nếu quay phim/tải game nặng",
            higher_is_better=True,
            is_numeric=False,
        ),
        FactorDef(
            factor_id="screen_inch_tablet",
            label="Kích thước màn hình",
            spec_field="screen_inch_text",
            unit="",
            simple_meaning="Màn lớn xem phim/học online sướng hơn, nhỏ gọn dễ mang theo",
            use_context="10 inch phù hợp xem phim, 8 inch gọn cho đọc sách/di chuyển",
            higher_is_better=True,
            is_numeric=False,
        ),
    ],

    # -----------------------------------------------------------------------
    # Desktop PC
    # -----------------------------------------------------------------------
    "desktop_pc": [
        FactorDef(
            factor_id="cpu_tech_pc",
            label="Công nghệ CPU",
            spec_field="cpu_tech",
            unit="",
            simple_meaning="CPU mạnh hơn = xử lý nhanh hơn — quan trọng nhất cho hiệu năng",
            use_context="Core i3 đủ văn phòng, i5/Ryzen 5 chỉnh ảnh, i7+ cho render/game",
            higher_is_better=True,
            is_numeric=False,
        ),
        FactorDef(
            factor_id="ram_pc",
            label="RAM",
            spec_field="ram_text",
            unit="",
            simple_meaning="RAM nhiều hơn = mở nhiều tab Chrome, nhiều app cùng lúc không lag",
            use_context="8 GB tối thiểu cho văn phòng, 16 GB cho đồ họa, 32 GB+ cho video 4K",
            higher_is_better=True,
            is_numeric=False,
        ),
        FactorDef(
            factor_id="storage_pc",
            label="Ổ cứng",
            spec_field="storage_text",
            unit="",
            simple_meaning="SSD nhanh gấp 5 lần HDD, dung lượng lớn chứa được nhiều file",
            use_context="SSD 256 GB cho văn phòng, SSD 512 GB+ nếu cài game/phần mềm nặng",
            higher_is_better=True,
            is_numeric=False,
        ),
    ],

    # -----------------------------------------------------------------------
    # Màn hình máy tính
    # -----------------------------------------------------------------------
    "monitor": [
        FactorDef(
            factor_id="screen_size_monitor",
            label="Kích thước màn hình",
            spec_field="screen_size_text",
            unit="",
            simple_meaning="Inch càng lớn, vùng hiển thị càng rộng — tốt cho đa nhiệm",
            use_context="24 inch đủ văn phòng, 27 inch cho đồ họa/game, 32 inch+ cho trader",
            higher_is_better=True,
            is_numeric=False,
        ),
        FactorDef(
            factor_id="panel_type",
            label="Tấm nền",
            spec_field="panel_type",
            unit="",
            simple_meaning="IPS màu đẹp góc nhìn rộng, VA đen sâu, TN phản hồi nhanh",
            use_context="Chỉnh ảnh/video cần IPS, xem phim cần VA, chơi FPS cần TN/IPS 1ms",
            higher_is_better=True,
            is_numeric=False,
        ),
        FactorDef(
            factor_id="refresh_rate",
            label="Tần số quét",
            spec_field="refresh_rate_text",
            unit="",
            simple_meaning="Hz càng cao, hình ảnh chuyển động càng mượt — game thủ cần cao",
            use_context="75 Hz đủ văn phòng, 144 Hz cho game, 240 Hz+ cho esport chuyên nghiệp",
            higher_is_better=True,
            is_numeric=False,
        ),
    ],

    # -----------------------------------------------------------------------
    # Máy in
    # -----------------------------------------------------------------------
    "printer": [
        FactorDef(
            factor_id="print_speed",
            label="Tốc độ in",
            spec_field="print_speed_text",
            unit="",
            simple_meaning="Trang/phút càng nhiều, in xong càng nhanh — quan trọng cho văn phòng",
            use_context="Gia đình cần 10-20 trang/phút, văn phòng cần 30+ trang/phút",
            higher_is_better=True,
            is_numeric=False,
        ),
        FactorDef(
            factor_id="printer_function",
            label="Chức năng",
            spec_field="printer_function",
            unit="",
            simple_meaning="In đơn thuần hay đa năng (in + scan + copy + fax)",
            use_context="Gia đình cần in-scan là đủ, văn phòng cần đa năng in-scan-copy-fax",
            higher_is_better=True,
            is_numeric=False,
        ),
    ],
}


# ---------------------------------------------------------------------------
# Mapping: business_category_id → dmx_slug (để query đúng catalog)
# Các category gộp trong DMX cần lọc sub-type
# ---------------------------------------------------------------------------
BUSINESS_TO_DMX_SLUG: dict[str, str] = {
    "air_conditioner": "air_conditioner",
    "tu_lanh": "tu_lanh",
    "may_giat": "may_giat",
    "may_say_quan_ao": "may_say_quan_ao",
    "may_rua_chen": "may_rua_chen",
    "tu_dong_tu_mat": "tu_dong_tu_mat",
    "may_nuoc_nong": "may_nuoc_nong",
    "micro_karaoke": "micro",
    "micro_phone": "micro",
    "dong_ho_thong_minh": "dong_ho_thong_minh",
    "may_tinh_bang": "may_tinh_bang",
    "desktop_pc": "pc_may_in",
    "monitor": "pc_may_in",
    "printer": "pc_may_in",
}


# ---------------------------------------------------------------------------
# Sub-type filter: lọc sản phẩm trong category DMX gộp (micro, pc_may_in)
# ---------------------------------------------------------------------------
def _is_subtype_match(product: dict, business_category_id: str) -> bool:
    """Kiểm tra product thuộc đúng subtype hay không.
    Chỉ áp dụng cho category DMX bị gộp (micro, pc_may_in).
    """
    spec = product.get("spec", {})
    name = (product.get("name") or "").lower()

    if business_category_id == "micro_karaoke":
        mic_type = (spec.get("mic_type") or "").lower()
        return "karaoke" in mic_type or "karaoke" in name

    if business_category_id == "micro_phone":
        mic_type = (spec.get("mic_type") or "").lower()
        # Micro điện thoại: condenser / thu âm / livestream
        if any(kw in mic_type for kw in ("condenser", "thu âm", "điện thoại")):
            return True
        if any(kw in name for kw in ("thu âm", "điện thoại", "livestream", "podcast")):
            return True
        # Nếu không phải karaoke → coi là micro điện thoại (fallback)
        if "karaoke" not in mic_type and "karaoke" not in name:
            return True
        return False

    if business_category_id == "desktop_pc":
        has_cpu = bool(spec.get("cpu_tech"))
        has_ram_storage = bool(spec.get("ram_text")) and bool(spec.get("storage_text"))
        return has_cpu or has_ram_storage

    if business_category_id == "monitor":
        has_panel = bool(spec.get("panel_type"))
        has_refresh = bool(spec.get("refresh_rate_text"))
        has_screen = bool(spec.get("screen_size_text"))
        return has_panel or (has_refresh and has_screen)

    if business_category_id == "printer":
        has_print_speed = bool(spec.get("print_speed_text"))
        is_printer_name = any(kw in name for kw in ("máy in", "may in", "printer"))
        return has_print_speed or is_printer_name

    # Non-merged categories: always match
    return True


def get_factors(business_category_id: str) -> list[FactorDef]:
    """Trả danh sách FactorDef cho category. Raise KeyError nếu không tồn tại."""
    if business_category_id not in DECISION_FACTORS:
        raise KeyError(
            f"business_category_id '{business_category_id}' không có trong DECISION_FACTORS. "
            f"Các ID hợp lệ: {sorted(DECISION_FACTORS.keys())}"
        )
    return DECISION_FACTORS[business_category_id]


def get_all_business_category_ids() -> list[str]:
    """Danh sách tất cả 14 business_category_id."""
    return sorted(DECISION_FACTORS.keys())


def filter_products_by_subtype(
    products: list[dict], business_category_id: str
) -> list[dict]:
    """Lọc sản phẩm theo subtype cho category DMX bị gộp."""
    return [p for p in products if _is_subtype_match(p, business_category_id)]
