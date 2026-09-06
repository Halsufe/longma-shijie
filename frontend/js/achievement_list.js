import { ACHIEVEMENT_CATEGORIES, ACHIEVEMENT_TEMPLATES, getAchievementTemplate } from "./achievement_templates.js";
import { emptyState, escapeHtml, icon, statusBadge } from "./ui.js";

const CATEGORY_DESCRIPTIONS = Object.freeze({
  paper: "论文发表与学术研究记录",
  award: "学科竞赛与综合赛事获奖",
  research: "科研项目与课题参与经历",
  patent: "专利申请与软件著作权",
  innovation: "创新训练与创业项目",
  organization: "学生组织与管理任职",
  social: "志愿服务与社会实践",
  arts: "文化、体育与艺术活动",
});

function achievementYear(item) {
  const match = String(item?.achievement_date || "").match(/^(\d{4})/);
  return match ? match[1] : "未设置";
}

export function getAchievementDoiUrl(item) {
  if (item?.category !== "paper") return null;
  const value = String(item?.details?.doi || "").trim().replace(/^doi:\s*/i, "");
  if (!value || value === "无") return null;
  if (/^10\.\d{4,9}\/\S+$/i.test(value)) return `https://doi.org/${encodeURI(value)}`;
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}

function renderTitle(item) {
  const title = escapeHtml(item.title || "未命名成果");
  const doiUrl = getAchievementDoiUrl(item);
  if (!doiUrl) return `<h3>${title}</h3>`;
  return `<h3><a class="achievement-doi-link" href="${escapeHtml(doiUrl)}" target="_blank" rel="noopener noreferrer" aria-label="打开论文 DOI：${title}">${title}${icon("arrow", 14)}</a></h3>`;
}

function renderAchievement(item, editable) {
  const template = getAchievementTemplate(item.category);
  const category = template?.category_label || item.category || "未设置";
  const proofCount = Array.isArray(item.proofs) ? item.proofs.length : 0;
  return `
    <article class="achievement-list-item" data-achievement-id="${Number(item.id)}">
      <span class="quick-item-icon">${icon("trophy")}</span>
      <div class="achievement-list-main">
        ${renderTitle(item)}
        <div class="achievement-list-meta">
          <span><b>类别</b>${escapeHtml(category)}</span>
          <span><b>级别</b>${escapeHtml(item.level || "不适用")}</span>
          <span><b>年份</b>${achievementYear(item)}</span>
          <span><b>附件</b>${proofCount} 份</span>
        </div>
      </div>
      <div class="achievement-list-status">${statusBadge(item.status)}</div>
      <div class="achievement-list-actions">
        <button class="icon-button" type="button" data-view-achievement="${Number(item.id)}" aria-label="查看成果">${icon("eye")}</button>
        ${editable ? `<button class="icon-button" type="button" data-edit-achievement="${Number(item.id)}" aria-label="编辑成果">${icon("edit")}</button><button class="icon-button danger" type="button" data-delete-achievement="${Number(item.id)}" aria-label="删除成果">${icon("trash")}</button>` : ""}
      </div>
    </article>`;
}

export function renderAchievementList(items = [], options = {}) {
  const editable = options.editable !== false;
  if (!items.length) {
    return emptyState(
      options.emptyTitle || "该年份暂无成果",
      options.emptyDescription || "切换到其他年份，或添加一条新的成果记录。",
      options.emptyAction || "",
    );
  }
  return `<section class="achievement-list" aria-label="成果列表">${items.map(item => renderAchievement(item, editable)).join("")}</section>`;
}

export function groupAchievementsByCategory(items = []) {
  const groups = Object.fromEntries(ACHIEVEMENT_CATEGORIES.map(category => [category, []]));
  items.forEach(item => {
    if (groups[item?.category]) groups[item.category].push(item);
  });
  return groups;
}

export function renderAchievementCategoryGroups(items = [], options = {}) {
  const editable = options.editable !== false;
  const groups = groupAchievementsByCategory(items);
  return `<section class="achievement-category-groups" aria-label="八类成果">
    ${ACHIEVEMENT_CATEGORIES.map((category, index) => {
      const categoryItems = groups[category];
      const label = ACHIEVEMENT_TEMPLATES[category].category_label;
      const content = categoryItems.length
        ? renderAchievementList(categoryItems, { editable })
        : `<div class="achievement-category-empty"><span>当前范围内暂无${escapeHtml(label)}</span>${editable ? `<button class="button button-ghost button-small" type="button" data-add-achievement-category="${category}">${icon("plus", 14)} 添加</button>` : ""}</div>`;
      return `<section class="achievement-category-section" id="achievement-category-${category}" data-achievement-category-group="${category}">
        <header class="achievement-category-header">
          <span class="achievement-category-index" aria-hidden="true">${String(index + 1).padStart(2, "0")}</span>
          <span class="achievement-category-heading"><strong>${escapeHtml(label)}</strong><small>${escapeHtml(CATEGORY_DESCRIPTIONS[category])}</small></span>
          <span class="achievement-category-count" aria-label="${escapeHtml(label)}共${categoryItems.length}项"><strong>${categoryItems.length}</strong> 项</span>
        </header>
        <div class="achievement-category-body">${content}</div>
      </section>`;
    }).join("")}
  </section>`;
}

export function bindAchievementList(container, handlers = {}) {
  const bindings = [
    ["[data-view-achievement]", "viewAchievement", handlers.onView],
    ["[data-edit-achievement]", "editAchievement", handlers.onEdit],
    ["[data-delete-achievement]", "deleteAchievement", handlers.onDelete],
  ];
  const listeners = [];
  bindings.forEach(([selector, datasetKey, callback]) => {
    if (typeof callback !== "function") return;
    container.querySelectorAll(selector).forEach(node => {
      const listener = () => callback(Number(node.dataset[datasetKey]));
      node.addEventListener("click", listener);
      listeners.push([node, listener]);
    });
  });
  return () => listeners.forEach(([node, listener]) => node.removeEventListener("click", listener));
}

export function createAchievementList(container, options = {}) {
  let items = options.items || [];
  let unbind = () => {};
  const draw = () => {
    unbind();
    container.innerHTML = renderAchievementList(items, options);
    unbind = bindAchievementList(container, options);
  };
  draw();
  return {
    setItems(value) {
      items = value || [];
      draw();
    },
    destroy() {
      unbind();
      container.innerHTML = "";
    },
  };
}
