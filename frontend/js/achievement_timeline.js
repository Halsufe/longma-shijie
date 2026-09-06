function normalizeYearRecord(record) {
  const rawYear = typeof record === "object" && record !== null ? record.year : record;
  const rawCount = typeof record === "object" && record !== null ? record.count : 0;
  const year = Number(rawYear);
  const count = Number(rawCount);
  if (!Number.isInteger(year) || year < 1900 || year > 9999) return null;
  return { year, count: Number.isFinite(count) && count > 0 ? Math.trunc(count) : 0 };
}

export function normalizeAchievementYears(years = []) {
  const totals = new Map();
  years.forEach(record => {
    const normalized = normalizeYearRecord(record);
    if (normalized) totals.set(normalized.year, (totals.get(normalized.year) || 0) + normalized.count);
  });
  return [...totals.entries()]
    .map(([year, count]) => ({ year, count }))
    .sort((left, right) => right.year - left.year);
}

export function defaultAchievementYear(currentYear = new Date().getFullYear()) {
  return String(currentYear);
}

export function renderAchievementTimeline(
  years = [],
  selectedYear = defaultAchievementYear(),
  currentYear = new Date().getFullYear(),
) {
  const records = normalizeAchievementYears(years);
  const selected = selectedYear === null || selectedYear === "all" ? "all" : String(selectedYear);
  const visibleYears = records.some(record => record.year === currentYear)
    ? records
    : [{ year: currentYear, count: 0 }, ...records].sort((left, right) => right.year - left.year);
  const total = records.reduce((sum, record) => sum + record.count, 0);
  const button = (value, label, count) => `
    <button class="achievement-year${selected === String(value) ? " active" : ""}"
      type="button" role="tab" aria-selected="${selected === String(value)}"
      data-achievement-year="${value}">
      <strong>${label}</strong><span>${count} 项</span>
    </button>`;

  return `
    <section class="achievement-timeline" aria-label="按年份筛选成果">
      <div class="achievement-year-track" role="tablist">
        ${button("all", "全部", total)}
        ${visibleYears.map(record => button(record.year, record.year, record.count)).join("")}
      </div>
      ${records.length ? "" : '<p class="achievement-timeline-empty">暂无成果年份，当前年份将显示空列表。</p>'}
    </section>`;
}

export function bindAchievementTimeline(container, onYearChange = () => {}) {
  const listeners = [];
  container.querySelectorAll("[data-achievement-year]").forEach(node => {
    const listener = () => {
      const value = node.dataset.achievementYear;
      onYearChange(value === "all" ? null : value);
    };
    node.addEventListener("click", listener);
    listeners.push([node, listener]);
  });
  return () => listeners.forEach(([node, listener]) => node.removeEventListener("click", listener));
}

export function createAchievementTimeline(container, options = {}) {
  let years = options.years || [];
  let selectedYear = options.selectedYear ?? defaultAchievementYear();
  let unbind = () => {};

  const draw = () => {
    unbind();
    container.innerHTML = renderAchievementTimeline(years, selectedYear);
    unbind = bindAchievementTimeline(container, value => {
      selectedYear = value ?? "all";
      draw();
      options.onYearChange?.(value);
    });
  };

  draw();
  return {
    getSelectedYear: () => selectedYear === "all" ? null : selectedYear,
    setSelectedYear(value) {
      selectedYear = value ?? "all";
      draw();
    },
    setYears(value) {
      years = value || [];
      draw();
    },
    destroy() {
      unbind();
      container.innerHTML = "";
    },
  };
}
