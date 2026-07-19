"""
server.py — FastAPI, giữ NGUYÊN API contract của backend Node cũ
(`POST /api/conversation/message`, `GET /api/conversation/{id}/state`,
`POST /api/conversation/{id}/reset`) để frontend (đã viết sẵn, gọi JSON
field cụ thể như `data.status`, `data.reply`, `data.items`...) chạy được
mà không cần sửa gì.

Thêm mới (không phá vỡ contract cũ):
- GET /api/health — status hệ thống, không lộ API key
- GET /api/categories — 14 ngành + slug + prompt mẫu
- MessageRequest có thêm optional field `state` — backward compatible
- Session bền vững qua restart (SQLiteSessionStore mặc định)
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.catalog.catalog_store import get_catalog
from app.config.settings import (
    APP_VERSION,
    LLM_API_KEY,
    LLM_MODEL,
    LLM_PROVIDER,
    SESSION_DB_PATH,
    SESSION_STORE,
    SESSION_TTL_SECONDS,
)
from app.conversation import nlu_lexicon
from app.conversation.clarification import choose_next_slot_to_ask
from app.conversation.missing_slots import compute_missing_slots
from app.conversation.nlu_prompt import build_nlu_prompt
from app.conversation.state import ConversationState, create_conversation_state
from app.conversation.turn import process_turn
from app.explanation.llm_factory import get_default_llm
from app.pipeline import AdviceResult, advise_for_state
from app.session.store import MemorySessionStore, SQLiteSessionStore

logger = logging.getLogger("ai_product_advisor")

app = FastAPI(title="AI Product Advisor API", version=APP_VERSION)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"

# ---------------------------------------------------------------------------
# Session store — chọn theo SESSION_STORE env var
# ---------------------------------------------------------------------------
def _build_session_store():
    if SESSION_STORE == "memory":
        return MemorySessionStore()
    try:
        return SQLiteSessionStore(SESSION_DB_PATH, ttl_seconds=SESSION_TTL_SECONDS)
    except Exception as exc:
        logger.warning("sqlite_session_store_init_failed error=%s; fallback to memory", exc)
        return MemorySessionStore()


_session_store = _build_session_store()


# ---------------------------------------------------------------------------
# 14 ngành — nguồn sự thật duy nhất cho /api/categories + welcome buttons
# ---------------------------------------------------------------------------
CATEGORIES_CATALOG = [
    {"slug": "air_conditioner",  "business_category_id": "air_conditioner",  "name": "Máy lạnh",              "prompt": "Tôi muốn mua máy lạnh",              "popular": True},
    {"slug": "tu_lanh",          "business_category_id": "tu_lanh",          "name": "Tủ lạnh",               "prompt": "Tôi muốn mua tủ lạnh",               "popular": True},
    {"slug": "may_giat",         "business_category_id": "may_giat",         "name": "Máy giặt",              "prompt": "Tôi muốn mua máy giặt",              "popular": True},
    {"slug": "may_say_quan_ao",  "business_category_id": "may_say_quan_ao",  "name": "Máy sấy quần áo",       "prompt": "Tôi muốn mua máy sấy quần áo",       "popular": False},
    {"slug": "may_rua_chen",     "business_category_id": "may_rua_chen",     "name": "Máy rửa chén",          "prompt": "Tôi muốn mua máy rửa chén",          "popular": False},
    {"slug": "tu_dong_tu_mat",   "business_category_id": "tu_dong_tu_mat",   "name": "Tủ đông / Tủ mát",      "prompt": "Tôi muốn mua tủ đông hoặc tủ mát",   "popular": False},
    {"slug": "may_nuoc_nong",    "business_category_id": "may_nuoc_nong",    "name": "Máy nước nóng",         "prompt": "Tôi muốn mua máy nước nóng",         "popular": True},
    {"slug": "micro",            "business_category_id": "micro_karaoke",    "name": "Micro karaoke",         "prompt": "Tôi muốn mua micro karaoke",         "popular": False},
    {"slug": "micro",            "business_category_id": "micro_phone",      "name": "Micro điện thoại",      "prompt": "Tôi muốn mua micro thu âm điện thoại","popular": False},
    {"slug": "dong_ho_thong_minh","business_category_id": "dong_ho_thong_minh","name": "Đồng hồ thông minh",   "prompt": "Tôi muốn mua đồng hồ thông minh",    "popular": True},
    {"slug": "may_tinh_bang",    "business_category_id": "may_tinh_bang",    "name": "Máy tính bảng",         "prompt": "Tôi muốn mua máy tính bảng",         "popular": True},
    {"slug": "pc_may_in",        "business_category_id": "desktop_pc",       "name": "Máy tính để bàn",       "prompt": "Tôi muốn mua máy tính để bàn",       "popular": False},
    {"slug": "pc_may_in",        "business_category_id": "monitor",          "name": "Màn hình máy tính",     "prompt": "Tôi muốn mua màn hình máy tính",     "popular": False},
    {"slug": "pc_may_in",        "business_category_id": "printer",          "name": "Máy in",                "prompt": "Tôi muốn mua máy in",                "popular": False},
]


@app.on_event("startup")
async def _warm_up_on_startup() -> None:
    """Warm-up catalog (đọc + parse products_detail.json 1 lần, thay vì để
    request đầu tiên gánh chi phí này) và LLM client (get_default_llm() đã
    cache bằng @lru_cache — dựng sẵn HTTP client 1 lần). Không chặn khởi
    động app nếu thiếu API key (dev/test không có .env)."""
    try:
        get_catalog()
    except Exception as exc:  # noqa: BLE001
        logger.warning("catalog_warmup_failed exception_type=%s", type(exc).__name__)
    try:
        get_default_llm()
    except Exception as exc:  # noqa: BLE001 — thiếu API key khi dev/test -> bỏ qua, không crash startup
        logger.warning("llm_warmup_skipped exception_type=%s", type(exc).__name__)


def _sanitize_state(state: ConversationState) -> dict[str, Any]:
    return {
        "session_id": state.session_id,
        "category": state.category,
        "slots": state.slots,
        "missing_slots": compute_missing_slots(state),
        "asked_slots": state.asked_slots,
        "rejected_fields": state.rejected_fields,
        "turn_count": state.turn_count,
    }


def _format_item(item: dict) -> dict:
    return {
        "product_id": item.get("product_id"),
        "model_code": item.get("model_code"),
        "name": item.get("name"),
        "brand": item.get("brand"),
        "image": item.get("image"),
        "url": item.get("url"),
        "effective_price": item.get("effective_price"),
        "headline": item.get("headline"),
        "pros": item.get("pros") or [],
        "cons": item.get("cons") or [],
        "recommendation_reason": item.get("recommendation_reason"),
        "matched_reasons": item.get("matched_reasons") or [],
        "tradeoffs": item.get("tradeoffs") or [],
        "missing_data": item.get("missing_data") or [],
        "data_source": item.get("data_source") or {"product_id": item.get("product_id"), "model_code": item.get("model_code"), "url": item.get("url")},
        "llm_explanation_missing": bool(item.get("llm_explanation_missing")),
    }


def _format_ranking(ranking) -> dict | None:
    if not ranking or not getattr(ranking, "results", None):
        return None
    return {
        "results": [
            {
                "rank": r.get("rank"),
                "product_id": r.get("product_id"),
                "model_code": r.get("model_code"),
                "name": r.get("name"),
                "brand": r.get("brand"),
                "image": r.get("image"),
                "url": r.get("url"),
                "effective_price": r.get("effective_price"),
                "total_score": r.get("total_score"),
                "matched_reasons": r.get("matched_reasons"),
                "tradeoffs": r.get("tradeoffs"),
                "data_source": {"product_id": r.get("product_id"), "model_code": r.get("model_code"), "url": r.get("url")},
            }
            for r in ranking.results
        ]
    }


def _build_reply_text(result: AdviceResult) -> str:
    if result.status == "blocked":
        return result.message or "Không có nội dung giải thích hợp lệ sau kiểm tra guardrail. Xin vui lòng thử lại."
    reply = result.summary or "Dưới đây là các sản phẩm phù hợp nhất với nhu cầu của bạn:"
    if result.status == "corrected" and result.corrections:
        reply += f" (⚠️ {len(result.corrections)} thông tin đã được sửa bởi hệ thống kiểm tra để đảm bảo chính xác)"
    return reply


def _build_api_response(session_id: str, state: ConversationState, result: AdviceResult) -> dict[str, Any]:
    base = {"session_id": session_id, "state": _sanitize_state(state)}

    if result.status == "not_ready":
        return {**base, "status": "not_ready", "reply": "Chưa đủ thông tin để tư vấn. Vui lòng cung cấp thêm.", "missing_slots": result.missing_slots or []}

    if result.status == "no_results":
        return {**base, "status": "no_results", "reply": result.message or "Rất tiếc, không tìm thấy sản phẩm phù hợp với yêu cầu của bạn trong catalog hiện tại."}

    if result.status == "llm_error":
        return {**base, "status": "llm_error", "reply": "Đã xảy ra lỗi khi gọi AI diễn giải. Dưới đây là kết quả xếp hạng thuần túy từ dữ liệu thật.", "error": result.message, "ranking": _format_ranking(result.ranking)}

    if result.status == "llm_parse_error":
        return {**base, "status": "llm_parse_error", "reply": "AI trả kết quả không đúng định dạng. Dưới đây là kết quả xếp hạng thuần từ dữ liệu thật.", "ranking": _format_ranking(result.ranking)}

    return {
        **base,
        "status": result.status,
        "reply": _build_reply_text(result),
        "summary": result.summary or None,
        "items": [_format_item(i) for i in (result.items or [])],
        "corrections": result.corrections or [],
        "rejected_items": result.rejected_items or [],
        "validation_status": result.status,
        "ranking_meta": {
            "total_scored": len(result.ranking.results) if result.ranking and result.ranking.results else 0,
            "relaxed_steps": (result.ranking.relaxed_steps if result.ranking else []) or [],
        }
        if result.ranking
        else None,
    }


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class MessageRequest(BaseModel):
    session_id: str
    message: str
    # optional state từ frontend — backward compatible (request cũ không có state vẫn OK)
    state: dict | None = None


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def get_health():
    """Status hệ thống. KHÔNG trả API key hay giá trị bí mật."""
    catalog_ok = False
    product_count = 0
    category_count = 0
    try:
        cat = get_catalog()
        catalog_ok = True
        product_count = sum(len(v) for v in cat.values())
        category_count = len(cat)
    except Exception:
        pass

    return {
        "status": "ok" if catalog_ok else "degraded",
        "version": APP_VERSION,
        "llm_provider": LLM_PROVIDER,
        "llm_model": LLM_MODEL,
        "api_key_configured": bool(LLM_API_KEY),  # True/False, không trả key
        "catalog_loaded": catalog_ok,
        "product_count": product_count,
        "category_count": category_count,
        "session_store": SESSION_STORE,
    }


@app.get("/api/categories")
async def get_categories():
    """Danh sách 14 ngành với slug, tên hiển thị và prompt mẫu cho frontend."""
    return {"categories": CATEGORIES_CATALOG}


@app.post("/api/conversation/message")
async def post_message(body: MessageRequest):
    if not body.session_id or not body.message:
        raise HTTPException(status_code=400, detail="Thiếu session_id hoặc message.")

    state = _session_store.get_or_create(body.session_id, client_state=body.state)
    missing_slots = compute_missing_slots(state)

    known_categories = None
    try:
        known_categories = get_catalog().keys()
    except Exception as exc:  # noqa: BLE001
        logger.warning("catalog_lookup_failed stage=nlu exception_type=%s", type(exc).__name__)

    # Slot vừa được hỏi ở lượt trước (nếu có) — dùng để diễn giải đúng câu
    # trả lời NGẮN (vd "4" cho household_size, "có"/"không" cho slot ưu
    # tiên) mà không cần gọi FPT.
    expected_slot_choice = choose_next_slot_to_ask(state, missing_slots)
    expected_slot = expected_slot_choice.slot if expected_slot_choice else None

    # 1) Chạy dict/regex tất định TRƯỚC — không tốn thời gian gọi mạng.
    raw_extraction: dict[str, Any] = nlu_lexicon.parse_message_deterministic(
        body.message, known_categories=known_categories, expected_slot=expected_slot
    )

    # 2) CHỈ gọi FPT-AI khi dict/regex "không hiểu" — tức là KHÔNG trích
    #    được field nào HOẶC vẫn chưa xác định được category trong khi
    #    category vẫn còn thiếu (raw_extraction có field khác không có
    #    nghĩa là category đã được giải quyết — phải tiếp tục nhận diện
    #    category, không dừng lại chỉ vì raw_extraction khác rỗng).
    #    Đây là lời gọi FPT DUY NHẤT được phép dùng cho request này; nếu
    #    dùng ở đây, giai đoạn giải thích bên dưới sẽ KHÔNG gọi FPT nữa.
    still_missing_category = state.category is None and "category" not in raw_extraction
    llm_call_used_for_nlu = False
    if not raw_extraction or still_missing_category:
        llm_call_used_for_nlu = True
        try:
            llm = get_default_llm()
            system, user = build_nlu_prompt(state, missing_slots, body.message)
            completion = llm.complete(f"{system}\n\n{user}")
            stripped = re.sub(r"^```json\s*|^```\s*|```\s*$", "", completion.text.strip(), flags=re.IGNORECASE | re.MULTILINE)
            llm_extraction = json.loads(stripped.strip())
            # Gộp thêm vào kết quả tất định đã có (nếu có) thay vì ghi đè
            # toàn bộ — giữ lại field dict/regex đã chắc chắn nhận diện được.
            raw_extraction = {**llm_extraction, **raw_extraction} if raw_extraction else llm_extraction
        except Exception as exc:  # noqa: BLE001 — FPT lỗi/chậm/JSON sai -> vẫn tiếp tục, không chết request
            logger.warning("nlu_llm_call_failed stage=nlu_extraction exception_type=%s", type(exc).__name__)

    turn = process_turn(state, raw_extraction)
    state = turn.state
    _session_store.save(body.session_id, state)

    if turn.status == "need_clarification":
        return {
            "session_id": body.session_id,
            "status": "need_clarification",
            "reply": turn.clarifying_question.question if turn.clarifying_question else "Vui lòng cung cấp thêm thông tin.",
            "clarifying_question": (
                {"slot": turn.clarifying_question.slot, "question": turn.clarifying_question.question, "is_repeat": turn.clarifying_question.is_repeat}
                if turn.clarifying_question
                else None
            ),
            "state": _sanitize_state(state),
        }

    try:
        llm = get_default_llm()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # 3) Giai đoạn giải thích: nếu NLU đã dùng hết ngân sách 1 lần gọi FPT,
    #    bỏ qua LLM hoàn toàn (skip_llm=True) — dùng ngay lời giải thích tạo
    #    từ matched_reasons/tradeoffs. Ngược lại, advise_for_state() tự gọi
    #    FPT đúng 1 lần và tự fallback nội bộ nếu FPT lỗi/timeout/JSON sai
    #    (xem pipeline.py) — tổng cộng KHÔNG BAO GIỜ vượt quá 1 lần gọi FPT.
    result = advise_for_state(state, llm=llm, skip_llm=llm_call_used_for_nlu)
    _session_store.save(body.session_id, state)
    return _build_api_response(body.session_id, state, result)


@app.get("/api/conversation/{session_id}/state")
async def get_state(session_id: str):
    state = _session_store.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session không tồn tại.")
    return {"session_id": session_id, "state": _sanitize_state(state)}


@app.post("/api/conversation/{session_id}/reset")
async def reset_session(session_id: str):
    state = _session_store.reset(session_id)
    return {"session_id": session_id, "status": "reset", "state": _sanitize_state(state)}


# ---------------------------------------------------------------------------
# Decision Copilot — 3 API endpoints độc lập, KHÔNG ảnh hưởng API cũ
# ---------------------------------------------------------------------------
from app.decision.decision_factors import (
    BUSINESS_TO_DMX_SLUG,
    get_all_business_category_ids,
    get_factors,
)
from app.decision.decision_scorer import DecisionResult, score_and_recommend


# Alias mapping cho Decision Copilot — dùng nlu_lexicon sẵn có
_DECISION_CATEGORY_ALIASES: dict[str, str] = {
    # Các alias ánh xạ thẳng về business_category_id (khác slug)
    "micro karaoke": "micro_karaoke",
    "karaoke": "micro_karaoke",
    "mic karaoke": "micro_karaoke",
    "micro thu âm": "micro_phone",
    "micro điện thoại": "micro_phone",
    "mic thu âm": "micro_phone",
    "mic điện thoại": "micro_phone",
    "micro livestream": "micro_phone",
    "máy tính để bàn": "desktop_pc",
    "desktop": "desktop_pc",
    "pc": "desktop_pc",
    "case máy tính": "desktop_pc",
    "màn hình": "monitor",
    "màn hình máy tính": "monitor",
    "monitor": "monitor",
    "man hinh": "monitor",
    "máy in": "printer",
    "may in": "printer",
    "printer": "printer",
}


def _resolve_business_category(message: str) -> dict | None:
    """Nhận diện business_category_id từ message người dùng.
    Tái sử dụng nlu_lexicon.parse_message_deterministic() + alias đặc thù."""
    msg_lower = nlu_lexicon.normalize_text(message)
    msg_no_diacritics = nlu_lexicon.strip_diacritics(msg_lower)

    # 1) Thử alias đặc thù (ưu tiên sub-type chính xác)
    for alias, biz_id in _DECISION_CATEGORY_ALIASES.items():
        alias_norm = nlu_lexicon.normalize_text(alias)
        alias_nd = nlu_lexicon.strip_diacritics(alias_norm)
        if alias_norm in msg_lower or alias_nd in msg_no_diacritics:
            cat_entry = next((c for c in CATEGORIES_CATALOG if c["business_category_id"] == biz_id), None)
            if cat_entry:
                return {
                    "business_category_id": biz_id,
                    "category_name": cat_entry["name"],
                    "slug": cat_entry["slug"],
                    "confidence": 0.95,
                }

    # 2) Fallback: dùng nlu_lexicon.parse_message_deterministic
    try:
        known_categories = get_catalog().keys()
    except Exception:
        known_categories = None
    extraction = nlu_lexicon.parse_message_deterministic(
        message, known_categories=known_categories
    )
    slug = extraction.get("category")
    if slug:
        # slug → business_category_id (1:1 nếu không gộp, cần guess cho gộp)
        cat_entry = next(
            (c for c in CATEGORIES_CATALOG if c["slug"] == slug),
            None,
        )
        if cat_entry:
            return {
                "business_category_id": cat_entry["business_category_id"],
                "category_name": cat_entry["name"],
                "slug": slug,
                "confidence": 0.85,
            }

    return None


class DecisionStartRequest(BaseModel):
    session_id: str
    message: str


class DecisionRecommendRequest(BaseModel):
    session_id: str
    business_category_id: str
    priority_factors: list[str]
    budget_max: int | None = None


@app.post("/api/decision/start")
async def decision_start(body: DecisionStartRequest):
    """Step 1: Nhận diện ngành hàng từ message tự nhiên."""
    if not body.message:
        raise HTTPException(status_code=400, detail="Thiếu message.")

    result = _resolve_business_category(body.message)
    if result is None:
        return {
            "status": "not_found",
            "message": "Không nhận diện được ngành hàng. Vui lòng thử lại với tên cụ thể hơn.",
            "available_categories": [
                {"business_category_id": c["business_category_id"], "name": c["name"]}
                for c in CATEGORIES_CATALOG
            ],
        }

    return {
        "status": "ok",
        "business_category_id": result["business_category_id"],
        "category_name": result["category_name"],
        "slug": result["slug"],
        "confidence": result["confidence"],
    }


@app.get("/api/decision/factors/{business_category_id}")
async def decision_factors(business_category_id: str):
    """Step 2: Trả tối đa 4 yếu tố đặc trưng với 3 lớp diễn giải."""
    try:
        factors = get_factors(business_category_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {
        "business_category_id": business_category_id,
        "factors": [
            {
                "factor_id": f.factor_id,
                "label": f.label,
                "spec_field": f.spec_field,
                "unit": f.unit,
                "simple_meaning": f.simple_meaning,
                "use_context": f.use_context,
                "higher_is_better": f.higher_is_better,
            }
            for f in factors
        ],
    }


@app.post("/api/decision/recommend")
async def decision_recommend(body: DecisionRecommendRequest):
    """Step 3: Chấm điểm & recommend sản phẩm, hoàn toàn bằng code."""
    # Validate business_category_id
    valid_ids = get_all_business_category_ids()
    if body.business_category_id not in valid_ids:
        raise HTTPException(
            status_code=400,
            detail=f"business_category_id '{body.business_category_id}' không hợp lệ. "
                   f"Các ID hợp lệ: {valid_ids}",
        )

    # Validate priority_factors
    try:
        factors = get_factors(body.business_category_id)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    valid_factor_ids = {f.factor_id for f in factors}
    for fid in body.priority_factors:
        if fid not in valid_factor_ids:
            raise HTTPException(
                status_code=400,
                detail=f"factor_id '{fid}' không hợp lệ cho category '{body.business_category_id}'. "
                       f"Các factor hợp lệ: {sorted(valid_factor_ids)}",
            )

    # Load catalog
    try:
        catalog = get_catalog()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Không tải được catalog: {exc}") from exc

    dmx_slug = BUSINESS_TO_DMX_SLUG.get(body.business_category_id, body.business_category_id)
    products = catalog.get(dmx_slug, [])
    if not products:
        return {
            "status": "no_products",
            "message": f"Không tìm thấy sản phẩm nào trong ngành '{body.business_category_id}'.",
            "results": [],
        }

    result = score_and_recommend(
        products=products,
        business_category_id=body.business_category_id,
        priority_factors=body.priority_factors,
        budget_max=body.budget_max,
    )

    return {
        "status": "ok",
        "mode": result.mode,
        "business_category_id": result.business_category_id,
        "total_products_scored": result.total_products_scored,
        "results": result.results,
    }


# Mount SAU CÙNG (sau mọi route /api/...) — index.html dùng đường dẫn tương
# đối ("style.css", "app.js" ở cùng cấp), nên phải mount ở "/" với html=True
# để "/" trả về index.html và "/style.css", "/app.js" được phục vụ đúng vị
# trí frontend mong đợi, mà không che các route /api/... đã đăng ký trước.
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
