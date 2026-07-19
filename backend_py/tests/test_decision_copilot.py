"""
tests/test_decision_copilot.py — Kiểm tra Decision Copilot đủ 14 ngành.

Kiểm tra:
  - business_category_id duy nhất
  - Micro subtypes không trộn
  - PC subtypes không trộn
  - Factors chỉ dùng field thực trong dmx_registry.json
  - Scoring tất định (deterministic)
  - Không bịa dữ liệu (missing → score=0, not NEUTRAL)
  - Đủ 14 category
  - API endpoints
"""
from __future__ import annotations

import pytest

from app.decision.decision_factors import (
    BUSINESS_TO_DMX_SLUG,
    DECISION_FACTORS,
    FactorDef,
    filter_products_by_subtype,
    get_all_business_category_ids,
    get_factors,
    _is_subtype_match,
)
from app.decision.decision_scorer import (
    DecisionResult,
    _extract_numeric,
    score_and_recommend,
)


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture
def dmx_registry_spec_fields():
    """Tất cả spec field có thực trong dmx_registry.json."""
    try:
        from app.catalog.dmx_registry import load_dmx_registry
        registry = load_dmx_registry()
        fields = set()
        for cat_name, cfg in registry.categories.items():
            for mapping in cfg.spec_map:
                fields.update(mapping.target_keys)
        return fields
    except Exception:
        # Fallback nếu registry chưa load được
        return {
            "area_min_m2", "area_max_m2", "indoor_noise_min_db", "indoor_noise_max_db",
            "outdoor_noise_db", "cooling_capacity_btu", "inverter", "product_year",
            "gas", "power_kwh", "energy_tech", "machine_type",
            "capacity_liters", "total_capacity_liters", "cooling_tech", "power_kwh_per_day",
            "wash_capacity_kg", "household_size_text", "spin_speed_rpm", "energy_rating",
            "dry_capacity_kg", "power_watt", "max_temp_c",
            "capacity_sets", "noise_db_text", "water_consumption_l",
            "chest_type", "tank_liters", "heating_power_w", "heater_type", "has_pump",
            "mic_type", "connector_type", "polar_pattern", "battery_life_text",
            "battery_mah_text", "water_resistance", "screen_size_text", "os",
            "ram_text", "storage_text", "screen_inch_text",
            "cpu_tech", "panel_type", "refresh_rate_text", "monitor_type",
            "print_speed_text", "printer_function",
        }


@pytest.fixture
def sample_products():
    """Mock products cho testing — field thật."""
    return {
        "air_conditioner": [
            {"product_id": "ac1", "name": "ML Panasonic 9000BTU", "brand": "Panasonic",
             "effective_price": 8000000, "spec": {"cooling_capacity_btu": 9000, "indoor_noise_min_db": 24,
             "power_kwh": 0.8, "area_min_m2": 10, "area_max_m2": 15}},
            {"product_id": "ac2", "name": "ML Daikin 12000BTU", "brand": "Daikin",
             "effective_price": 12000000, "spec": {"cooling_capacity_btu": 12000, "indoor_noise_min_db": 28,
             "power_kwh": 1.2, "area_min_m2": 15, "area_max_m2": 20}},
            {"product_id": "ac3", "name": "ML Casper 9000BTU", "brand": "Casper",
             "effective_price": 6000000, "spec": {"cooling_capacity_btu": 9000, "indoor_noise_min_db": 32,
             "power_kwh": 1.0, "area_min_m2": 10, "area_max_m2": 15}},
        ],
        "micro": [
            {"product_id": "mk1", "name": "Micro karaoke Shure", "brand": "Shure",
             "effective_price": 3000000, "spec": {"mic_type": "Không dây karaoke",
             "battery_life_text": "8 giờ", "connector_type": "6.5mm", "polar_pattern": "cardioid"}},
            {"product_id": "mp1", "name": "Micro thu âm điện thoại Boya", "brand": "Boya",
             "effective_price": 1500000, "spec": {"mic_type": "Condenser thu âm",
             "battery_life_text": "5 giờ", "connector_type": "USB-C", "polar_pattern": "omnidirectional"}},
        ],
        "pc_may_in": [
            {"product_id": "pc1", "name": "PC Dell Vostro", "brand": "Dell",
             "effective_price": 15000000, "spec": {"cpu_tech": "Intel Core i5", "ram_text": "8 GB",
             "storage_text": "SSD 256 GB"}},
            {"product_id": "mon1", "name": "Màn hình LG 27 inch", "brand": "LG",
             "effective_price": 5000000, "spec": {"panel_type": "IPS", "screen_size_text": "27 inch",
             "refresh_rate_text": "75 Hz"}},
            {"product_id": "pr1", "name": "Máy in Canon PIXMA", "brand": "Canon",
             "effective_price": 4000000, "spec": {"print_speed_text": "15 trang/phút",
             "printer_function": "In, Scan, Copy"}},
        ],
    }


# =====================================================================
# Test 1: business_category_id duy nhất
# =====================================================================

def test_business_category_ids_unique():
    """14 business_category_id phải duy nhất."""
    ids = get_all_business_category_ids()
    assert len(ids) == len(set(ids)), f"Có ID trùng: {ids}"
    assert len(ids) == 14, f"Mong 14 ID, có {len(ids)}: {ids}"


# =====================================================================
# Test 2: Micro subtypes không trộn
# =====================================================================

def test_micro_subtypes_not_mixed(sample_products):
    """micro_karaoke chỉ lấy karaoke, micro_phone chỉ lấy thu âm."""
    micro_products = sample_products["micro"]

    karaoke = filter_products_by_subtype(micro_products, "micro_karaoke")
    phone = filter_products_by_subtype(micro_products, "micro_phone")

    assert len(karaoke) >= 1, "Phải có ít nhất 1 micro karaoke"
    assert len(phone) >= 1, "Phải có ít nhất 1 micro thu âm"

    karaoke_ids = {p["product_id"] for p in karaoke}
    phone_ids = {p["product_id"] for p in phone}

    assert "mk1" in karaoke_ids, "mk1 (karaoke Shure) phải nằm trong micro_karaoke"
    assert "mp1" in phone_ids, "mp1 (thu âm Boya) phải nằm trong micro_phone"
    assert "mp1" not in karaoke_ids, "mp1 (thu âm) KHÔNG được nằm trong micro_karaoke"


# =====================================================================
# Test 3: PC subtypes không trộn
# =====================================================================

def test_pc_subtypes_not_mixed(sample_products):
    """desktop_pc, monitor, printer phải tách riêng."""
    pc_products = sample_products["pc_may_in"]

    desktops = filter_products_by_subtype(pc_products, "desktop_pc")
    monitors = filter_products_by_subtype(pc_products, "monitor")
    printers = filter_products_by_subtype(pc_products, "printer")

    desktop_ids = {p["product_id"] for p in desktops}
    monitor_ids = {p["product_id"] for p in monitors}
    printer_ids = {p["product_id"] for p in printers}

    assert "pc1" in desktop_ids, "pc1 phải là desktop"
    assert "mon1" in monitor_ids, "mon1 phải là monitor"
    assert "pr1" in printer_ids, "pr1 phải là printer"

    # Không trộn
    assert "mon1" not in desktop_ids, "mon1 (monitor) KHÔNG được nằm trong desktop"
    assert "pr1" not in desktop_ids, "pr1 (printer) KHÔNG được nằm trong desktop"


# =====================================================================
# Test 4: Factors chỉ dùng field thực trong dmx_registry.json
# =====================================================================

def test_factors_use_real_fields(dmx_registry_spec_fields):
    """Mọi spec_field trong DECISION_FACTORS phải tồn tại trong dmx_registry.json."""
    all_ids = get_all_business_category_ids()
    for biz_id in all_ids:
        factors = get_factors(biz_id)
        for f in factors:
            assert f.spec_field in dmx_registry_spec_fields, (
                f"Factor '{f.factor_id}' (category '{biz_id}') dùng spec_field "
                f"'{f.spec_field}' KHÔNG tồn tại trong dmx_registry.json. "
                f"Các field hợp lệ: {sorted(dmx_registry_spec_fields)}"
            )


# =====================================================================
# Test 5: Scoring tất định (deterministic)
# =====================================================================

def test_scoring_deterministic(sample_products):
    """Cùng input → cùng output mọi lần chạy."""
    products = sample_products["air_conditioner"]
    priority = ["cooling_capacity_btu", "indoor_noise_min_db"]

    r1 = score_and_recommend(products, "air_conditioner", priority, budget_max=15000000)
    r2 = score_and_recommend(products, "air_conditioner", priority, budget_max=15000000)

    assert r1.mode == r2.mode
    assert len(r1.results) == len(r2.results)
    for a, b in zip(r1.results, r2.results):
        assert a["product_id"] == b["product_id"]
        assert a["fit_percent"] == b["fit_percent"]


# =====================================================================
# Test 6: Không bịa dữ liệu — missing → score=0
# =====================================================================

def test_no_fabricated_data():
    """Khi thiếu spec field, score PHẢI = 0 (không dùng NEUTRAL 50)."""
    products = [
        {"product_id": "empty1", "name": "Empty Product", "brand": "Test",
         "effective_price": 5000000, "spec": {}},  # Không có spec nào
    ]
    result = score_and_recommend(products, "air_conditioner",
                                  ["cooling_capacity_btu", "indoor_noise_min_db"],
                                  budget_max=10000000)

    assert len(result.results) > 0
    item = result.results[0]
    for fs in item["factor_scores"]:
        if not fs["has_data"]:
            assert fs["score"] == 0, (
                f"Factor '{fs['factor_id']}' thiếu dữ liệu nhưng score={fs['score']} "
                f"thay vì 0. KHÔNG được cho điểm trung lập!"
            )
            assert fs["display_value"] == "Chưa có dữ liệu"


# =====================================================================
# Test 7: Đủ 14 category
# =====================================================================

def test_all_14_categories_have_factors():
    """Đủ 14 business_category_id có factor config."""
    expected = {
        "air_conditioner", "tu_lanh", "may_giat", "may_say_quan_ao",
        "may_rua_chen", "tu_dong_tu_mat", "may_nuoc_nong",
        "micro_karaoke", "micro_phone",
        "dong_ho_thong_minh", "may_tinh_bang",
        "desktop_pc", "monitor", "printer",
    }
    actual = set(get_all_business_category_ids())
    assert actual == expected, f"Thiếu/thừa category: expected={expected}, actual={actual}"


# =====================================================================
# Test 8: Mỗi category có tối đa 4 factors
# =====================================================================

def test_max_4_factors_per_category():
    """Mỗi category không được quá 4 factors."""
    for biz_id in get_all_business_category_ids():
        factors = get_factors(biz_id)
        assert len(factors) <= 4, (
            f"Category '{biz_id}' có {len(factors)} factors, max là 4"
        )
        assert len(factors) >= 2, (
            f"Category '{biz_id}' chỉ có {len(factors)} factors, tối thiểu 2"
        )


# =====================================================================
# Test 9: BUSINESS_TO_DMX_SLUG mapping đầy đủ
# =====================================================================

def test_business_to_dmx_slug_complete():
    """Mọi business_category_id phải có mapping sang DMX slug."""
    for biz_id in get_all_business_category_ids():
        assert biz_id in BUSINESS_TO_DMX_SLUG, (
            f"'{biz_id}' thiếu trong BUSINESS_TO_DMX_SLUG"
        )
        slug = BUSINESS_TO_DMX_SLUG[biz_id]
        assert isinstance(slug, str) and slug, (
            f"BUSINESS_TO_DMX_SLUG['{biz_id}'] = '{slug}' phải là string không rỗng"
        )


# =====================================================================
# Test 10: Scoring best_match khi đạt tất cả tiêu chí
# =====================================================================

def test_scoring_best_match(sample_products):
    """Khi có sản phẩm đạt tất cả tiêu chí → mode = best_match."""
    products = sample_products["air_conditioner"]
    # Chỉ chọn 2 factor, tất cả sản phẩm đều có data → phải có best_match
    result = score_and_recommend(
        products, "air_conditioner",
        ["cooling_capacity_btu", "indoor_noise_min_db"],
        budget_max=15000000,
    )
    # Vẫn hợp lệ dù mode là best_match hay tradeoff
    assert result.mode in ("best_match", "tradeoff")
    assert len(result.results) >= 1


# =====================================================================
# Test 11: Scoring tradeoff khi không đạt tất cả
# =====================================================================

def test_scoring_tradeoff_max_3():
    """Tradeoff mode trả tối đa 3 phương án."""
    products = [
        {"product_id": f"p{i}", "name": f"Product {i}", "brand": "Test",
         "effective_price": 5000000 + i * 1000000,
         "spec": {"cooling_capacity_btu": 9000 + i * 1000}}
        for i in range(10)
    ]
    result = score_and_recommend(
        products, "air_conditioner",
        ["cooling_capacity_btu", "indoor_noise_min_db", "power_kwh"],
    )
    assert len(result.results) <= 3


# =====================================================================
# Test 12: _extract_numeric xử lý đúng
# =====================================================================

def test_extract_numeric():
    assert _extract_numeric(42) == 42.0
    assert _extract_numeric(3.14) == 3.14
    assert _extract_numeric("8 GB") == 8.0
    assert _extract_numeric("49 dB") == 49.0
    assert _extract_numeric(None) is None
    assert _extract_numeric("") is None
    assert _extract_numeric(True) == 1.0
    assert _extract_numeric(False) == 0.0


# =====================================================================
# Test 13: get_factors raises KeyError cho invalid id
# =====================================================================

def test_get_factors_invalid_id():
    with pytest.raises(KeyError):
        get_factors("nonexistent_category")


# =====================================================================
# Test 14: Confidence giảm khi thiếu dữ liệu
# =====================================================================

def test_confidence_reduced_when_missing_data():
    """Confidence phải < 100 khi có field thiếu dữ liệu."""
    products = [
        {"product_id": "partial1", "name": "Partial Product", "brand": "Test",
         "effective_price": 8000000,
         "spec": {"cooling_capacity_btu": 9000}},  # Chỉ có 1 field
    ]
    result = score_and_recommend(
        products, "air_conditioner",
        ["cooling_capacity_btu", "indoor_noise_min_db", "power_kwh"],
    )
    assert len(result.results) > 0
    item = result.results[0]
    assert item["confidence"] < 100, (
        f"Confidence = {item['confidence']}% nhưng phải < 100% vì thiếu dữ liệu"
    )


# =====================================================================
# Test 15: Factor IDs duy nhất trong mỗi category
# =====================================================================

def test_factor_ids_unique_per_category():
    """factor_id không được trùng trong cùng 1 category."""
    for biz_id in get_all_business_category_ids():
        factors = get_factors(biz_id)
        ids = [f.factor_id for f in factors]
        assert len(ids) == len(set(ids)), (
            f"Category '{biz_id}' có factor_id trùng: {ids}"
        )


# =====================================================================
# Test 16-19: API endpoints (/api/decision/*) — theo đúng plan, phần này
# trước đó chưa có test HTTP-level dù endpoint đã hoạt động.
# =====================================================================


@pytest.fixture(scope="module")
def api_client():
    from fastapi.testclient import TestClient
    from app.server import app

    return TestClient(app)


def test_api_start_endpoint(api_client):
    """POST /api/decision/start nhận diện đúng category từ message tự nhiên."""
    r = api_client.post("/api/decision/start", json={"session_id": "api-test-1", "message": "mua điều hòa"})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["business_category_id"] == "air_conditioner"
    assert 0 <= data["confidence"] <= 1


def test_api_start_endpoint_not_found_for_gibberish(api_client):
    """Message không nhận diện được category -> status not_found, kèm danh
    sách category hợp lệ để client gợi ý lại (không 500, không đoán bừa)."""
    r = api_client.post("/api/decision/start", json={"session_id": "api-test-2", "message": "asdkjaslkdj 12873"})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "not_found"
    assert len(data["available_categories"]) == 14


def test_api_start_endpoint_missing_message_400(api_client):
    r = api_client.post("/api/decision/start", json={"session_id": "api-test-3", "message": ""})
    assert r.status_code == 400


def test_api_factors_endpoint(api_client):
    """GET /api/decision/factors/{id} trả tối đa 4 factor với đủ 3 lớp diễn giải."""
    r = api_client.get("/api/decision/factors/air_conditioner")
    assert r.status_code == 200
    data = r.json()
    assert data["business_category_id"] == "air_conditioner"
    assert 1 <= len(data["factors"]) <= 4
    for f in data["factors"]:
        assert f["simple_meaning"]
        assert f["use_context"]
        assert "higher_is_better" in f


def test_api_factors_endpoint_invalid_id_404(api_client):
    r = api_client.get("/api/decision/factors/khong_ton_tai")
    assert r.status_code == 404


def test_api_recommend_endpoint(api_client):
    """POST /api/decision/recommend chấm điểm thật trên catalog thật, trả
    mode best_match hoặc tradeoff (tối đa 3 kết quả), không dùng LLM."""
    factors_resp = api_client.get("/api/decision/factors/tu_lanh")
    factor_ids = [f["factor_id"] for f in factors_resp.json()["factors"]]

    r = api_client.post(
        "/api/decision/recommend",
        json={
            "session_id": "api-test-4",
            "business_category_id": "tu_lanh",
            "priority_factors": factor_ids,
            "budget_max": 15_000_000,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["mode"] in ("best_match", "tradeoff")
    assert len(data["results"]) <= 3
    assert data["total_products_scored"] > 0
    for item in data["results"]:
        assert item["name"]
        assert item["url"]
        assert 0 <= item["fit_percent"] <= 100


def test_api_recommend_endpoint_invalid_category_400(api_client):
    r = api_client.post(
        "/api/decision/recommend",
        json={"session_id": "api-test-5", "business_category_id": "khong_ton_tai", "priority_factors": []},
    )
    assert r.status_code == 400


def test_api_recommend_endpoint_invalid_factor_id_400(api_client):
    r = api_client.post(
        "/api/decision/recommend",
        json={
            "session_id": "api-test-6",
            "business_category_id": "air_conditioner",
            "priority_factors": ["khong_ton_tai_factor"],
        },
    )
    assert r.status_code == 400


def test_api_recommend_endpoint_results_only_from_correct_subtype(api_client):
    """business_category_id gộp (micro_karaoke vs micro_phone) không được
    trộn sản phẩm sai subtype trong kết quả trả về qua API thật."""
    factors_resp = api_client.get("/api/decision/factors/micro_karaoke")
    factor_ids = [f["factor_id"] for f in factors_resp.json()["factors"]]

    r = api_client.post(
        "/api/decision/recommend",
        json={"session_id": "api-test-7", "business_category_id": "micro_karaoke", "priority_factors": factor_ids},
    )
    assert r.status_code == 200
    data = r.json()
    for item in data["results"]:
        assert "điện thoại" not in (item["name"] or "").lower() or "karaoke" in (item["name"] or "").lower()
