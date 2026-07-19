"""
decision/decision_scorer.py — Chấm điểm sản phẩm thuần code, không dùng LLM.

Trọng số ưu tiên: 4–3–2–1 theo thứ tự factor người dùng chọn.

Kết quả:
- Nếu có ≥1 sản phẩm đạt TẤT CẢ tiêu chí → trả 1 best_match
- Nếu không → trả tối đa 3 trade-off: balanced / top_priority / budget
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.catalog.parse_specs import parse_number
from app.decision.decision_factors import (
    BUSINESS_TO_DMX_SLUG,
    FactorDef,
    filter_products_by_subtype,
    get_factors,
)


# ---------------------------------------------------------------------------
# Weights
# ---------------------------------------------------------------------------
PRIORITY_WEIGHTS = [4, 3, 2, 1]  # Factor 1 → 4, Factor 2 → 3, ...


def _clamp(n: float) -> int:
    return max(0, min(100, round(n)))


# ---------------------------------------------------------------------------
# Normalize: đưa giá trị spec thực về 0-100 trong range min-max của category
# ---------------------------------------------------------------------------

def _extract_numeric(raw: Any) -> float | None:
    """Trích số từ giá trị spec (có thể là số, text "8 GB", "49 dB", ...)."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, bool):
        return 1.0 if raw else 0.0
    if isinstance(raw, str):
        return parse_number(raw)
    return None


def _compute_range(products: list[dict], spec_field: str) -> tuple[float, float]:
    """Tính min/max thực tế của 1 field trong toàn bộ sản phẩm category."""
    values = []
    for p in products:
        v = _extract_numeric(p.get("spec", {}).get(spec_field))
        if v is not None:
            values.append(v)
    if not values:
        return (0.0, 1.0)
    lo, hi = min(values), max(values)
    if lo == hi:
        return (lo - 1.0, hi + 1.0)
    return (lo, hi)


def _normalize_score(
    value: float, lo: float, hi: float, higher_is_better: bool
) -> int:
    """Normalize value to 0-100 within [lo, hi]."""
    if hi == lo:
        return 50
    raw = (value - lo) / (hi - lo) * 100
    if not higher_is_better:
        raw = 100 - raw
    return _clamp(raw)


def _text_has_value(raw: Any) -> bool:
    """Kiểm tra text field có giá trị thực (không phải None/""/whitespace)."""
    if raw is None:
        return False
    if isinstance(raw, bool):
        return True
    if isinstance(raw, str):
        return bool(raw.strip())
    return True


# ---------------------------------------------------------------------------
# Score 1 sản phẩm
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FactorScore:
    factor_id: str
    label: str
    spec_field: str
    raw_value: Any       # Giá trị thực từ data
    score: int           # 0-100
    has_data: bool       # False = "chưa có dữ liệu"
    weight: int          # 4/3/2/1
    display_value: str   # Giá trị hiển thị dễ đọc


@dataclass
class ProductScore:
    product: dict[str, Any]
    product_id: str
    name: str
    brand: str
    image: str | None
    url: str | None
    effective_price: int | None
    weighted_score: float      # Tổng điểm có trọng số
    max_possible: float        # Tổng điểm tối đa có thể đạt
    fit_percent: float         # weighted_score / max_possible * 100
    confidence: float          # Giảm khi thiếu dữ liệu
    factor_scores: list[FactorScore] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    tradeoffs: list[str] = field(default_factory=list)
    missing_data: list[str] = field(default_factory=list)


@dataclass
class DecisionResult:
    mode: str  # "best_match" | "tradeoff"
    business_category_id: str
    results: list[dict[str, Any]] = field(default_factory=list)
    total_products_scored: int = 0


def _score_product(
    product: dict,
    factors: list[FactorDef],
    priority_order: list[str],
    ranges: dict[str, tuple[float, float]],
) -> ProductScore:
    """Chấm điểm 1 sản phẩm theo các factor đã chọn với trọng số priority."""
    spec = product.get("spec", {})
    factor_scores: list[FactorScore] = []
    total_weighted = 0.0
    total_max = 0.0
    data_count = 0
    total_factors = 0

    # Build factor lookup
    factor_map = {f.factor_id: f for f in factors}

    for idx, fid in enumerate(priority_order):
        f = factor_map.get(fid)
        if f is None:
            continue
        weight = PRIORITY_WEIGHTS[idx] if idx < len(PRIORITY_WEIGHTS) else 1
        total_factors += 1

        raw_value = spec.get(f.spec_field)
        has_data = _text_has_value(raw_value)

        if not has_data:
            # KHÔNG cho điểm trung lập — ghi rõ "chưa có dữ liệu"
            factor_scores.append(FactorScore(
                factor_id=f.factor_id,
                label=f.label,
                spec_field=f.spec_field,
                raw_value=None,
                score=0,
                has_data=False,
                weight=weight,
                display_value="Chưa có dữ liệu",
            ))
            total_max += weight * 100
            continue

        data_count += 1

        # Numeric scoring
        if f.is_numeric:
            numeric_val = _extract_numeric(raw_value)
            if numeric_val is not None:
                lo, hi = ranges.get(f.spec_field, (0, 1))
                score = _normalize_score(numeric_val, lo, hi, f.higher_is_better)
            else:
                score = 50  # Has text but unparseable → mid score
        else:
            # Text/boolean fields: has data = 70 base score
            # Tốt hơn mặc định vì ít nhất có thông tin
            score = 70

        display_value = str(raw_value) if raw_value is not None else "N/A"
        if f.unit and f.is_numeric:
            numeric_val = _extract_numeric(raw_value)
            if numeric_val is not None:
                display_value = f"{numeric_val:g} {f.unit}".strip()

        factor_scores.append(FactorScore(
            factor_id=f.factor_id,
            label=f.label,
            spec_field=f.spec_field,
            raw_value=raw_value,
            score=score,
            has_data=True,
            weight=weight,
            display_value=display_value,
        ))

        total_weighted += weight * score
        total_max += weight * 100

    # Confidence giảm theo tỷ lệ field thiếu
    confidence = (data_count / total_factors * 100) if total_factors > 0 else 0
    fit_percent = (total_weighted / total_max * 100) if total_max > 0 else 0

    # Strengths & Tradeoffs
    strengths = []
    tradeoffs = []
    missing = []
    for fs in factor_scores:
        if not fs.has_data:
            missing.append(f"{fs.label}: chưa có dữ liệu")
        elif fs.score >= 70:
            strengths.append(f"{fs.label}: {fs.display_value}")
        elif fs.score < 50:
            tradeoffs.append(f"{fs.label}: {fs.display_value} (điểm thấp)")

    price = product.get("effective_price")

    return ProductScore(
        product=product,
        product_id=str(product.get("product_id") or product.get("model_code") or ""),
        name=product.get("name") or "",
        brand=product.get("brand") or "",
        image=product.get("image"),
        url=product.get("url"),
        effective_price=price,
        weighted_score=total_weighted,
        max_possible=total_max,
        fit_percent=round(fit_percent, 1),
        confidence=round(confidence, 1),
        factor_scores=factor_scores,
        strengths=strengths,
        tradeoffs=tradeoffs,
        missing_data=missing,
    )


def _product_score_to_dict(ps: ProductScore, label: str = "") -> dict[str, Any]:
    """Serialize ProductScore thành dict JSON-compatible."""
    return {
        "label": label,
        "product_id": ps.product_id,
        "name": ps.name,
        "brand": ps.brand,
        "image": ps.image,
        "url": ps.url,
        "effective_price": ps.effective_price,
        "fit_percent": ps.fit_percent,
        "confidence": ps.confidence,
        "strengths": ps.strengths,
        "tradeoffs": ps.tradeoffs,
        "missing_data": ps.missing_data,
        "factor_scores": [
            {
                "factor_id": fs.factor_id,
                "label": fs.label,
                "raw_value": fs.raw_value if fs.has_data else None,
                "display_value": fs.display_value,
                "score": fs.score,
                "has_data": fs.has_data,
                "weight": fs.weight,
            }
            for fs in ps.factor_scores
        ],
    }


# ---------------------------------------------------------------------------
# Main scoring entry point
# ---------------------------------------------------------------------------

def score_and_recommend(
    products: list[dict],
    business_category_id: str,
    priority_factors: list[str],
    budget_max: int | None = None,
) -> DecisionResult:
    """
    Chấm điểm & recommend sản phẩm cho Decision Copilot.

    Args:
        products: Danh sách sản phẩm đã lọc theo DMX slug
        business_category_id: ID ngành (14 id)
        priority_factors: Danh sách factor_id theo thứ tự ưu tiên
        budget_max: Ngân sách tối đa (optional)

    Returns:
        DecisionResult với mode "best_match" hoặc "tradeoff"
    """
    factors = get_factors(business_category_id)

    # Filter by subtype (micro_karaoke vs micro_phone, etc.)
    products = filter_products_by_subtype(products, business_category_id)

    # Filter by budget
    if budget_max is not None:
        budget_products = [
            p for p in products
            if p.get("effective_price") is not None
            and p["effective_price"] <= budget_max
        ]
        # Nếu lọc ngân sách hết sạch → nới 15%
        if not budget_products:
            budget_products = [
                p for p in products
                if p.get("effective_price") is not None
                and p["effective_price"] <= budget_max * 1.15
            ]
        if budget_products:
            products = budget_products

    if not products:
        return DecisionResult(
            mode="tradeoff",
            business_category_id=business_category_id,
            results=[],
            total_products_scored=0,
        )

    # Chỉ lấy sản phẩm có giá
    products = [p for p in products if p.get("effective_price") is not None]
    if not products:
        return DecisionResult(
            mode="tradeoff",
            business_category_id=business_category_id,
            results=[],
            total_products_scored=0,
        )

    # Precompute ranges cho numeric factors
    ranges: dict[str, tuple[float, float]] = {}
    for f in factors:
        if f.is_numeric:
            ranges[f.spec_field] = _compute_range(products, f.spec_field)

    # Score all
    scored = [
        _score_product(product, factors, priority_factors, ranges)
        for product in products
    ]

    # Kiểm tra: có sản phẩm đạt TẤT CẢ tiêu chí không?
    # "Đạt" = tất cả factor có data VÀ score >= 60
    perfect = [
        s for s in scored
        if all(fs.has_data and fs.score >= 60 for fs in s.factor_scores)
    ]

    if perfect:
        # Best match: sản phẩm fit_percent cao nhất
        perfect.sort(key=lambda s: (-s.fit_percent, s.effective_price or float("inf")))
        best = perfect[0]
        return DecisionResult(
            mode="best_match",
            business_category_id=business_category_id,
            results=[_product_score_to_dict(best, "🏆 Phù hợp nhất")],
            total_products_scored=len(scored),
        )

    # Tradeoff mode: 3 phương án khác nhau
    results = []

    # 1. Balanced: fit_percent cao nhất
    scored_by_fit = sorted(scored, key=lambda s: (-s.fit_percent, s.effective_price or float("inf")))
    if scored_by_fit:
        results.append(_product_score_to_dict(scored_by_fit[0], "⚖️ Cân bằng nhất"))

    # 2. Top priority: score factor #1 cao nhất
    first_factor_id = priority_factors[0] if priority_factors else None
    if first_factor_id:
        def _first_factor_score(s: ProductScore) -> int:
            for fs in s.factor_scores:
                if fs.factor_id == first_factor_id:
                    return fs.score if fs.has_data else -1
            return -1

        scored_by_first = sorted(scored, key=lambda s: (-_first_factor_score(s), s.effective_price or float("inf")))
        candidate = scored_by_first[0]
        # Chỉ thêm nếu khác balanced
        if candidate.product_id != scored_by_fit[0].product_id:
            results.append(_product_score_to_dict(candidate, f"💪 Mạnh nhất về {_factor_label(factors, first_factor_id)}"))

    # 3. Budget: giá thấp nhất trong top 50% fit
    top_half_count = max(1, len(scored) // 2)
    top_half = sorted(scored, key=lambda s: -s.fit_percent)[:top_half_count]
    cheapest = sorted(top_half, key=lambda s: s.effective_price or float("inf"))
    if cheapest:
        candidate = cheapest[0]
        existing_ids = {r["product_id"] for r in results}
        if candidate.product_id not in existing_ids:
            results.append(_product_score_to_dict(candidate, "💰 Tiết kiệm nhất"))

    return DecisionResult(
        mode="tradeoff",
        business_category_id=business_category_id,
        results=results[:3],  # Tối đa 3
        total_products_scored=len(scored),
    )


def _factor_label(factors: list[FactorDef], factor_id: str) -> str:
    for f in factors:
        if f.factor_id == factor_id:
            return f.label
    return factor_id
