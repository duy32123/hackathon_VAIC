/* eslint-disable */
/**
 * Decision Copilot — Frontend module độc lập.
 * KHÔNG sửa app.js hiện có. Inject overlay UI riêng cho flow Decision.
 *
 * Flow:
 *  1. User click "🎯 Tư vấn thông minh" → mở overlay
 *  2. Gõ tên sản phẩm → POST /api/decision/start → nhận diện ngành
 *  3. Hiển thị 4 thẻ tiêu chí → click chọn thứ tự ưu tiên (badge 1-4)
 *  4. POST /api/decision/recommend → render kết quả cards
 *  5. Buttons "Chọn" / "Đổi ưu tiên" / "Đóng"
 */

const DECISION_API = '';

// ==========================================
// STATE
// ==========================================
let _dcState = {
  isOpen: false,
  step: 0, // 0=closed, 1=input, 2=factors, 3=results
  businessCategoryId: null,
  categoryName: null,
  factors: [],
  selectedPriorities: [], // factor_ids in order
  results: null,
  sessionId: 'dc_' + Date.now(),
};

// ==========================================
// HELPERS
// ==========================================
function dcEscape(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function dcFormatVND(amount) {
  if (amount == null) return 'Chưa có giá';
  return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(amount).replace('₫', 'đ');
}

// ==========================================
// OVERLAY MANAGEMENT
// ==========================================
function dcOpen() {
  _dcState.isOpen = true;
  _dcState.step = 1;
  _dcState.selectedPriorities = [];
  _dcState.results = null;
  _dcState.businessCategoryId = null;
  _dcState.sessionId = 'dc_' + Date.now();
  const overlay = document.getElementById('decision-copilot-overlay');
  if (overlay) {
    overlay.classList.remove('hidden');
    overlay.classList.add('dc-fade-in');
  }
  dcRenderStep1();
}

function dcClose() {
  _dcState.isOpen = false;
  _dcState.step = 0;
  const overlay = document.getElementById('decision-copilot-overlay');
  if (overlay) {
    overlay.classList.add('hidden');
    overlay.classList.remove('dc-fade-in');
  }
}

// ==========================================
// STEP 1: NHẬP SẢN PHẨM
// ==========================================
function dcRenderStep1() {
  const container = document.getElementById('dc-content');
  if (!container) return;
  container.innerHTML = `
    <div class="dc-step-card">
      <div class="dc-step-header">
        <span class="dc-step-badge">Bước 1</span>
        <h3 class="dc-step-title">Bạn muốn mua sản phẩm gì?</h3>
      </div>
      <p class="dc-step-desc">Nhập tên loại sản phẩm bằng tiếng Việt tự nhiên — hệ thống sẽ tự nhận diện.</p>
      <form id="dc-start-form" class="dc-input-row">
        <input type="text" id="dc-product-input" placeholder="Ví dụ: máy lạnh, tủ lạnh, micro karaoke, màn hình..."
          class="dc-input" autocomplete="off" required>
        <button type="submit" class="dc-btn-primary">
          <i class="fa-solid fa-magnifying-glass"></i> Nhận diện
        </button>
      </form>
      <div id="dc-start-error" class="dc-error hidden"></div>
      <div id="dc-category-grid" class="dc-category-grid"></div>
    </div>
  `;
  // Render quick category buttons
  const grid = document.getElementById('dc-category-grid');
  if (grid && window._dcAllCategories) {
    grid.innerHTML = '<p class="dc-grid-label">Hoặc chọn nhanh:</p><div class="dc-grid-items">' +
      window._dcAllCategories.map(c =>
        `<button class="dc-cat-btn" data-id="${dcEscape(c.business_category_id)}" data-name="${dcEscape(c.name)}">${dcEscape(c.name)}</button>`
      ).join('') + '</div>';
    grid.querySelectorAll('.dc-cat-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const id = btn.dataset.id;
        const name = btn.dataset.name;
        _dcState.businessCategoryId = id;
        _dcState.categoryName = name;
        _dcState.step = 2;
        dcLoadFactors(id);
      });
    });
  }

  const form = document.getElementById('dc-start-form');
  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const input = document.getElementById('dc-product-input');
      const errDiv = document.getElementById('dc-start-error');
      if (!input || !input.value.trim()) return;

      const btn = form.querySelector('button[type=submit]');
      btn.disabled = true;
      btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Đang xử lý...';
      errDiv.classList.add('hidden');

      try {
        const res = await fetch(`${DECISION_API}/api/decision/start`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ session_id: _dcState.sessionId, message: input.value.trim() }),
        });
        const data = await res.json();

        if (data.status === 'ok') {
          _dcState.businessCategoryId = data.business_category_id;
          _dcState.categoryName = data.category_name;
          _dcState.step = 2;
          dcLoadFactors(data.business_category_id);
        } else {
          errDiv.textContent = data.message || 'Không nhận diện được. Vui lòng chọn bên dưới.';
          errDiv.classList.remove('hidden');
          btn.disabled = false;
          btn.innerHTML = '<i class="fa-solid fa-magnifying-glass"></i> Nhận diện';
        }
      } catch (err) {
        errDiv.textContent = 'Lỗi kết nối. Vui lòng thử lại.';
        errDiv.classList.remove('hidden');
        btn.disabled = false;
        btn.innerHTML = '<i class="fa-solid fa-magnifying-glass"></i> Nhận diện';
      }
    });
  }
}

// ==========================================
// STEP 2: CHỌN TIÊU CHÍ ƯU TIÊN
// ==========================================
async function dcLoadFactors(businessCategoryId) {
  const container = document.getElementById('dc-content');
  if (!container) return;

  container.innerHTML = `
    <div class="dc-step-card">
      <div class="dc-step-header">
        <span class="dc-step-badge dc-step-badge-loading"><i class="fa-solid fa-spinner fa-spin"></i></span>
        <h3 class="dc-step-title">Đang tải tiêu chí...</h3>
      </div>
    </div>
  `;

  try {
    const res = await fetch(`${DECISION_API}/api/decision/factors/${businessCategoryId}`);
    const data = await res.json();
    _dcState.factors = data.factors || [];
    _dcState.selectedPriorities = [];
    dcRenderStep2();
  } catch (err) {
    container.innerHTML = `
      <div class="dc-step-card">
        <p class="dc-error">Không tải được tiêu chí. <button class="dc-link-btn" onclick="dcRenderStep1()">Thử lại</button></p>
      </div>
    `;
  }
}

function dcRenderStep2() {
  const container = document.getElementById('dc-content');
  if (!container) return;

  const factors = _dcState.factors;
  const selected = _dcState.selectedPriorities;

  let cardsHtml = '';
  factors.forEach((f, idx) => {
    const priorityIdx = selected.indexOf(f.factor_id);
    const isSelected = priorityIdx !== -1;
    const priorityNum = priorityIdx + 1;

    cardsHtml += `
      <div class="dc-factor-card ${isSelected ? 'dc-factor-selected' : ''}" data-fid="${dcEscape(f.factor_id)}">
        ${isSelected ? `<span class="dc-priority-badge">${priorityNum}</span>` : '<span class="dc-priority-badge dc-priority-empty"><i class="fa-solid fa-hand-pointer"></i></span>'}
        <div class="dc-factor-body">
          <h4 class="dc-factor-label">${dcEscape(f.label)}</h4>
          <div class="dc-factor-layers">
            <div class="dc-layer">
              <span class="dc-layer-icon dc-layer-spec"><i class="fa-solid fa-microchip"></i></span>
              <span class="dc-layer-text"><strong>Thông số:</strong> ${dcEscape(f.spec_field)}${f.unit ? ' (' + dcEscape(f.unit) + ')' : ''}</span>
            </div>
            <div class="dc-layer">
              <span class="dc-layer-icon dc-layer-meaning"><i class="fa-solid fa-lightbulb"></i></span>
              <span class="dc-layer-text">${dcEscape(f.simple_meaning)}</span>
            </div>
            <div class="dc-layer">
              <span class="dc-layer-icon dc-layer-context"><i class="fa-solid fa-house-user"></i></span>
              <span class="dc-layer-text">${dcEscape(f.use_context)}</span>
            </div>
          </div>
        </div>
      </div>
    `;
  });

  container.innerHTML = `
    <div class="dc-step-card">
      <div class="dc-step-header">
        <span class="dc-step-badge">Bước 2</span>
        <h3 class="dc-step-title">Chọn tiêu chí theo thứ tự ưu tiên — ${dcEscape(_dcState.categoryName || '')}</h3>
      </div>
      <p class="dc-step-desc">Bấm vào thẻ theo thứ tự quan trọng nhất → ít quan trọng nhất. Bấm lại để bỏ chọn.</p>

      <div id="dc-budget-row" class="dc-budget-row">
        <label class="dc-budget-label">Ngân sách tối đa (tuỳ chọn):</label>
        <input type="number" id="dc-budget-input" placeholder="VD: 15000000" class="dc-budget-input" min="0" step="500000">
      </div>

      <div class="dc-factors-grid">${cardsHtml}</div>

      <div class="dc-actions">
        <button class="dc-btn-secondary" onclick="dcRenderStep1()"><i class="fa-solid fa-arrow-left"></i> Quay lại</button>
        <button id="dc-recommend-btn" class="dc-btn-primary ${selected.length === 0 ? 'dc-btn-disabled' : ''}" ${selected.length === 0 ? 'disabled' : ''}>
          <i class="fa-solid fa-wand-magic-sparkles"></i> Tư vấn ngay (${selected.length} tiêu chí)
        </button>
      </div>
    </div>
  `;

  // Factor card click handlers
  container.querySelectorAll('.dc-factor-card').forEach(card => {
    card.addEventListener('click', () => {
      const fid = card.dataset.fid;
      const idx = _dcState.selectedPriorities.indexOf(fid);
      if (idx !== -1) {
        _dcState.selectedPriorities.splice(idx, 1);
      } else if (_dcState.selectedPriorities.length < 4) {
        _dcState.selectedPriorities.push(fid);
      }
      dcRenderStep2(); // Re-render to update badges
    });
  });

  // Recommend button
  const recBtn = document.getElementById('dc-recommend-btn');
  if (recBtn) {
    recBtn.addEventListener('click', () => {
      if (_dcState.selectedPriorities.length > 0) {
        dcDoRecommend();
      }
    });
  }
}

// ==========================================
// STEP 3: KẾT QUẢ
// ==========================================
async function dcDoRecommend() {
  const container = document.getElementById('dc-content');
  if (!container) return;

  container.innerHTML = `
    <div class="dc-step-card">
      <div class="dc-step-header">
        <span class="dc-step-badge dc-step-badge-loading"><i class="fa-solid fa-spinner fa-spin"></i></span>
        <h3 class="dc-step-title">Đang phân tích & chấm điểm sản phẩm...</h3>
      </div>
      <p class="dc-step-desc">Hệ thống đang so sánh toàn bộ catalog dựa trên tiêu chí bạn chọn.</p>
    </div>
  `;

  const budgetInput = document.getElementById('dc-budget-input');
  let budgetMax = null;
  // Budget might have been removed from DOM by re-render, store before
  if (_dcState._lastBudget) {
    budgetMax = _dcState._lastBudget;
  }

  try {
    // Try to read budget before step 3 render cleared it
    const budgetEl = document.getElementById('dc-budget-input');
    if (budgetEl && budgetEl.value) {
      budgetMax = parseInt(budgetEl.value, 10) || null;
    }
  } catch (_) {}

  // Store budget for potential re-use
  if (!budgetMax && _dcState._pendingBudget) {
    budgetMax = _dcState._pendingBudget;
  }

  try {
    const res = await fetch(`${DECISION_API}/api/decision/recommend`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: _dcState.sessionId,
        business_category_id: _dcState.businessCategoryId,
        priority_factors: _dcState.selectedPriorities,
        budget_max: budgetMax,
      }),
    });
    const data = await res.json();
    _dcState.results = data;
    dcRenderStep3(data);
  } catch (err) {
    container.innerHTML = `
      <div class="dc-step-card">
        <p class="dc-error">Lỗi kết nối khi phân tích. <button class="dc-link-btn" onclick="dcRenderStep2()">Thử lại</button></p>
      </div>
    `;
  }
}

function dcRenderStep3(data) {
  const container = document.getElementById('dc-content');
  if (!container) return;

  if (!data.results || data.results.length === 0) {
    container.innerHTML = `
      <div class="dc-step-card">
        <div class="dc-step-header">
          <span class="dc-step-badge dc-step-badge-warn">!</span>
          <h3 class="dc-step-title">Không tìm thấy sản phẩm phù hợp</h3>
        </div>
        <p class="dc-step-desc">Hệ thống đã duyệt toàn bộ catalog nhưng không có sản phẩm nào khớp tiêu chí. Thử đổi thứ tự ưu tiên hoặc mở rộng ngân sách.</p>
        <div class="dc-actions">
          <button class="dc-btn-secondary" onclick="_dcState.step=2; dcRenderStep2()"><i class="fa-solid fa-shuffle"></i> Đổi ưu tiên</button>
          <button class="dc-btn-secondary" onclick="dcRenderStep1()"><i class="fa-solid fa-arrow-left"></i> Chọn ngành khác</button>
        </div>
      </div>
    `;
    return;
  }

  const modeLabel = data.mode === 'best_match'
    ? '<span class="dc-mode-badge dc-mode-best">🏆 Tìm được sản phẩm phù hợp hoàn hảo!</span>'
    : '<span class="dc-mode-badge dc-mode-trade">⚖️ Không có sản phẩm hoàn hảo — đây là 3 phương án trade-off tốt nhất</span>';

  let cardsHtml = '';
  data.results.forEach((r, idx) => {
    const fitColor = r.fit_percent >= 80 ? 'dc-fit-high' : r.fit_percent >= 60 ? 'dc-fit-mid' : 'dc-fit-low';
    const confColor = r.confidence >= 80 ? 'dc-conf-high' : r.confidence >= 50 ? 'dc-conf-mid' : 'dc-conf-low';

    let factorRows = '';
    (r.factor_scores || []).forEach(fs => {
      const barWidth = fs.has_data ? fs.score : 0;
      const barClass = fs.has_data ? (fs.score >= 70 ? 'dc-bar-good' : fs.score >= 40 ? 'dc-bar-mid' : 'dc-bar-low') : 'dc-bar-none';
      factorRows += `
        <div class="dc-factor-row">
          <span class="dc-factor-row-label">${dcEscape(fs.label)} <span class="dc-weight-badge">×${fs.weight}</span></span>
          <div class="dc-factor-bar-wrap">
            <div class="dc-factor-bar ${barClass}" style="width:${barWidth}%"></div>
          </div>
          <span class="dc-factor-row-value">${fs.has_data ? dcEscape(fs.display_value) : '<em class="dc-no-data">Chưa có dữ liệu</em>'}</span>
        </div>
      `;
    });

    const strengths = (r.strengths || []).map(s => `<li><i class="fa-solid fa-check dc-icon-green"></i> ${dcEscape(s)}</li>`).join('');
    const tradeoffs = (r.tradeoffs || []).map(t => `<li><i class="fa-solid fa-triangle-exclamation dc-icon-amber"></i> ${dcEscape(t)}</li>`).join('');
    const missing = (r.missing_data || []).map(m => `<li><i class="fa-solid fa-circle-question dc-icon-gray"></i> ${dcEscape(m)}</li>`).join('');

    const imgHtml = r.image
      ? `<img src="${dcEscape(r.image)}" alt="${dcEscape(r.name)}" class="dc-product-img" onerror="this.style.display='none'">`
      : '';

    const productUrl = r.url || `https://www.dienmayxanh.com/tim-kiem?key=${encodeURIComponent(r.name || '')}`;

    cardsHtml += `
      <div class="dc-result-card">
        <div class="dc-result-header">
          <span class="dc-result-label">${dcEscape(r.label || 'Đề xuất ' + (idx+1))}</span>
          <div class="dc-result-badges">
            <span class="dc-fit-badge ${fitColor}">${r.fit_percent}% phù hợp</span>
            <span class="dc-conf-badge ${confColor}">Tin cậy: ${r.confidence}%</span>
          </div>
        </div>
        ${imgHtml}
        <h4 class="dc-product-name">${dcEscape(r.name || 'Sản phẩm')}</h4>
        <p class="dc-product-brand">${dcEscape(r.brand || '')} ${r.product_id ? '• #' + dcEscape(r.product_id) : ''}</p>
        <div class="dc-product-price">${dcFormatVND(r.effective_price)}</div>

        <div class="dc-factor-breakdown">
          ${factorRows}
        </div>

        ${strengths ? `<div class="dc-pros"><strong>Điểm mạnh:</strong><ul>${strengths}</ul></div>` : ''}
        ${tradeoffs ? `<div class="dc-cons"><strong>Đánh đổi:</strong><ul>${tradeoffs}</ul></div>` : ''}
        ${missing ? `<div class="dc-missing"><strong>Thiếu dữ liệu:</strong><ul>${missing}</ul></div>` : ''}

        <a href="${productUrl}" target="_blank" rel="noopener" class="dc-btn-select">
          <i class="fa-solid fa-arrow-up-right-from-square"></i> Xem tại Điện Máy Xanh
        </a>
      </div>
    `;
  });

  container.innerHTML = `
    <div class="dc-step-card">
      <div class="dc-step-header">
        <span class="dc-step-badge">Kết quả</span>
        <h3 class="dc-step-title">Đề xuất cho ${dcEscape(_dcState.categoryName || '')} — ${data.total_products_scored} sản phẩm đã phân tích</h3>
      </div>
      ${modeLabel}
      <div class="dc-results-grid">${cardsHtml}</div>
      <div class="dc-actions dc-actions-result">
        <button class="dc-btn-secondary" onclick="_dcState.step=2; dcRenderStep2()"><i class="fa-solid fa-shuffle"></i> Đổi thứ tự ưu tiên</button>
        <button class="dc-btn-secondary" onclick="dcRenderStep1()"><i class="fa-solid fa-rotate-left"></i> Chọn ngành khác</button>
        <button class="dc-btn-close" onclick="dcClose()"><i class="fa-solid fa-xmark"></i> Đóng</button>
      </div>
    </div>
  `;
}

// ==========================================
// BUDGET PERSISTENCE: lưu budget trước khi re-render
// ==========================================
function dcSaveBudget() {
  const el = document.getElementById('dc-budget-input');
  if (el && el.value) {
    _dcState._pendingBudget = parseInt(el.value, 10) || null;
  }
}

// Override dcDoRecommend to save budget first
const _origDoRecommend = dcDoRecommend;
// We handle budget inline in dcDoRecommend already

// ==========================================
// INIT: Load categories & inject overlay
// ==========================================
window._dcAllCategories = [];

async function dcInit() {
  // Load categories for quick-select grid
  try {
    const res = await fetch(`${DECISION_API}/api/categories`);
    if (res.ok) {
      const data = await res.json();
      window._dcAllCategories = data.categories || [];
    }
  } catch (_) {}

  // Wire up trigger button
  const triggerBtn = document.getElementById('dc-trigger-btn');
  if (triggerBtn) {
    triggerBtn.addEventListener('click', () => {
      dcSaveBudget();
      dcOpen();
    });
  }

  // Close on backdrop click
  const overlay = document.getElementById('decision-copilot-overlay');
  if (overlay) {
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) dcClose();
    });
  }

  // ESC to close
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && _dcState.isOpen) dcClose();
  });
}

document.addEventListener('DOMContentLoaded', dcInit);
