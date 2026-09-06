import { ACHIEVEMENT_CATEGORIES, ACHIEVEMENT_TEMPLATES, getAchievementTemplate } from "./achievement_templates.js";
import { escapeHtml } from "./ui.js";

const CURRENT_YEAR = new Date().getFullYear();

function inputValue(value) {
  if (typeof value === "boolean") return value ? "是" : "否";
  return value ?? "";
}

function fieldName(key) {
  return key === "title" || key === "level" ? key : `details.${key}`;
}

function fieldError(name) {
  return `<small class="field-error" data-error-for="${escapeHtml(name)}" aria-live="polite"></small>`;
}

function inputAttributes(field) {
  const attributes = [`name="details.${escapeHtml(field.key)}"`, `data-detail-key="${escapeHtml(field.key)}"`, 'aria-required="true"'];
  if (field.type === "url") attributes.push('type="url"', 'inputmode="url"');
  else if (field.type === "number") attributes.push('type="number"', 'inputmode="numeric"');
  else attributes.push('type="text"');
  if (field.format === "year:1900-current") attributes.push('min="1900"', `max="${CURRENT_YEAR}"`, 'step="1"');
  if (field.format === "month:1-12") attributes.push('min="1"', 'max="12"', 'step="1"');
  if (field.format === "non-negative-integer") attributes.push('min="0"', 'step="1"');
  return attributes.join(" ");
}

function renderBooleanField(field, value) {
  const normalized = inputValue(value);
  return `<fieldset class="field achievement-choice-field" data-field-name="details.${escapeHtml(field.key)}">
    <legend>${escapeHtml(field.label)} <span class="required-mark">*</span></legend>
    <div class="segmented-control">
      ${field.enum.map(option => `<label><input type="radio" name="details.${escapeHtml(field.key)}" value="${escapeHtml(option)}" ${normalized === option ? "checked" : ""}><span>${escapeHtml(option)}</span></label>`).join("")}
    </div>
    ${field.hint ? `<small>${escapeHtml(field.hint)}</small>` : ""}
    ${fieldError(`details.${field.key}`)}
  </fieldset>`;
}

function renderSelectField(field, value) {
  return `<label class="field" data-field-name="details.${escapeHtml(field.key)}">
    <span>${escapeHtml(field.label)} <span class="required-mark">*</span></span>
    <select class="select" name="details.${escapeHtml(field.key)}" data-detail-key="${escapeHtml(field.key)}" aria-required="true">
      <option value="">请选择</option>
      ${field.enum.map(option => `<option value="${escapeHtml(option)}" ${inputValue(value) === option ? "selected" : ""}>${escapeHtml(option)}</option>`).join("")}
    </select>
    ${field.hint ? `<small>${escapeHtml(field.hint)}</small>` : ""}
    ${fieldError(`details.${field.key}`)}
  </label>`;
}

function renderTemplateField(field, value) {
  if (field.type === "bool") return renderBooleanField(field, value);
  if (field.type === "select") return renderSelectField(field, value);
  const control = field.type === "textarea"
    ? `<textarea class="textarea" name="details.${escapeHtml(field.key)}" data-detail-key="${escapeHtml(field.key)}" aria-required="true">${escapeHtml(inputValue(value))}</textarea>`
    : `<input class="input" ${inputAttributes(field)} value="${escapeHtml(inputValue(value))}">`;
  return `<label class="field ${field.type === "textarea" ? "achievement-field-wide" : ""}" data-field-name="details.${escapeHtml(field.key)}">
    <span>${escapeHtml(field.label)} <span class="required-mark">*</span></span>
    ${control}
    ${field.hint ? `<small>${escapeHtml(field.hint)}</small>` : ""}
    ${fieldError(`details.${field.key}`)}
  </label>`;
}

export function renderAchievementTemplate(category, values = {}, level = "") {
  const template = getAchievementTemplate(category);
  if (!template) return '<div class="achievement-template-copy text-danger">请选择有效的成果类别。</div>';
  const levelField = template.level_field;
  return `
    <div class="achievement-template-copy"><strong>${escapeHtml(template.category_label)}</strong><p>${escapeHtml(template.title_copy)}</p></div>
    <div class="achievement-fields-grid">
      <label class="field achievement-field-wide" data-field-name="title">
        <span>${escapeHtml(template.title_field.label)} <span class="required-mark">*</span></span>
        <input class="input" name="title" maxlength="200" value="${escapeHtml(inputValue(values.title))}" aria-required="true" placeholder="${escapeHtml(template.title_field.hint)}">
        ${fieldError("title")}
      </label>
      ${levelField ? `<label class="field" data-field-name="level"><span>${escapeHtml(levelField.label)} <span class="required-mark">*</span></span><select class="select" name="level" aria-required="true"><option value="">请选择</option>${levelField.enum.map(option => `<option value="${escapeHtml(option)}" ${level === option ? "selected" : ""}>${escapeHtml(option)}</option>`).join("")}</select>${levelField.hint ? `<small>${escapeHtml(levelField.hint)}</small>` : ""}${fieldError("level")}</label>` : ""}
      ${template.fields.map(field => renderTemplateField(field, values.details?.[field.key])).join("")}
    </div>`;
}

export function renderAchievementForm(item = null) {
  const category = ACHIEVEMENT_CATEGORIES.includes(item?.category) ? item.category : ACHIEVEMENT_CATEGORIES[0];
  const hasDetails = Boolean(item && item.details && Object.keys(item.details).length);
  const legacyNotice = item && !hasDetails ? `
    <div class="achievement-legacy-notice" role="status">
      <strong>这是一条旧版成果记录</strong>
      <p>已回填类别、标题、级别和公开设置。请参考原日期与说明，补全当前模板的全部必填项后保存。</p>
      <dl><div><dt>原日期</dt><dd>${escapeHtml(item.achievement_date || "未设置")}</dd></div><div><dt>原说明</dt><dd>${escapeHtml(item.description || "未设置")}</dd></div></dl>
    </div>` : "";
  return `
    <section class="achievement-form" data-achievement-form>
      <label class="field achievement-category-field" data-field-name="category">
        <span>成果类别 <span class="required-mark">*</span></span>
        <select class="select" name="category" aria-required="true">
          ${ACHIEVEMENT_CATEGORIES.map(value => `<option value="${value}" ${value === category ? "selected" : ""}>${escapeHtml(ACHIEVEMENT_TEMPLATES[value].category_label)}</option>`).join("")}
        </select>
        ${fieldError("category")}
      </label>
      ${legacyNotice}
      <div data-achievement-template>${renderAchievementTemplate(category, { title: item?.title || "", details: item?.details || {} }, item?.level || "")}</div>
      <label class="achievement-public-toggle">
        <input type="checkbox" name="is_public" ${item?.is_public ? "checked" : ""}>
        <span><strong>公开展示</strong><small>审核通过后展示在成果广场</small></span>
      </label>
    </section>`;
}

export function bindAchievementForm(form, item = null) {
  const categorySelect = form.elements.category;
  const templateRoot = form.querySelector("[data-achievement-template]");
  const onCategoryChange = () => {
    const preserve = categorySelect.value === item?.category;
    templateRoot.innerHTML = renderAchievementTemplate(
      categorySelect.value,
      preserve ? { title: item?.title || "", details: item?.details || {} } : { title: form.elements.title?.value || "", details: {} },
      preserve ? item?.level || "" : "",
    );
  };
  categorySelect.addEventListener("change", onCategoryChange);
  return () => categorySelect.removeEventListener("change", onCategoryChange);
}

function validateFormat(field, value) {
  const text = String(value).trim();
  if (field.format === "year:1900-current" && (!/^\d{4}$/.test(text) || Number(text) < 1900 || Number(text) > CURRENT_YEAR)) return `请输入1900至${CURRENT_YEAR}之间的4位年份`;
  if (field.format === "month:1-12" && (!/^\d{1,2}$/.test(text) || Number(text) < 1 || Number(text) > 12)) return "请输入1至12之间的月份";
  if (field.format === "year:1900-current|进行中" && text !== "进行中" && (!/^\d{4}$/.test(text) || Number(text) < 1900 || Number(text) > CURRENT_YEAR)) return `请输入1900至${CURRENT_YEAR}之间的4位年份，或填写“进行中”`;
  if (field.format === "month:1-12|进行中" && text !== "进行中" && (!/^\d{1,2}$/.test(text) || Number(text) < 1 || Number(text) > 12)) return "请输入1至12之间的月份，或填写“进行中”";
  if (field.format === "year:1900-current|无" && text !== "无" && (!/^\d{4}$/.test(text) || Number(text) < 1900 || Number(text) > CURRENT_YEAR)) return `请输入1900至${CURRENT_YEAR}之间的4位年份，或填写“无”`;
  if (field.format === "month:1-12|无" && text !== "无" && (!/^\d{1,2}$/.test(text) || Number(text) < 1 || Number(text) > 12)) return "请输入1至12之间的月份，或填写“无”";
  if (field.format === "non-negative-integer" && !/^\d+$/.test(text)) return "请输入非负整数";
  if (field.format === "decimal-2|无" && text !== "无" && !/^\d+\.\d{2}$/.test(text)) return "请输入保留两位小数的非负数字，或填写“无”";
  if (field.format === "url") {
    try {
      const url = new URL(text);
      if (!['http:', 'https:'].includes(url.protocol)) return "请输入有效的HTTP或HTTPS链接";
    } catch {
      return "请输入有效的HTTP或HTTPS链接";
    }
  }
  if (field.format === "page-range|forthcoming" && text !== "forthcoming") {
    const match = text.match(/^\s*(\d+)\s*-\s*(\d+)\s*$/);
    if (!match || Number(match[1]) > Number(match[2])) return "请输入页码范围，如20-30，或填写forthcoming";
  }
  if (["name-list:comma-separated-no-empty-items", "text-list:comma-separated-no-empty-items"].includes(field.format)) {
    const parts = text.split(/[,，]/);
    if (!parts.length || parts.some(part => !part.trim())) return "请使用逗号分隔，且不要包含空项";
  }
  return "";
}

function normalizeValue(field, value) {
  const text = String(value).trim();
  if (field.type === "bool") return text === "是";
  if (["year:1900-current", "month:1-12", "non-negative-integer"].includes(field.format)) return Number(text);
  return text;
}

function clearErrors(form) {
  form.querySelectorAll("[data-error-for]").forEach(node => { node.textContent = ""; });
  form.querySelectorAll("[aria-invalid=true]").forEach(node => node.removeAttribute("aria-invalid"));
}

function showErrors(form, errors) {
  Object.entries(errors).forEach(([name, message]) => {
    const error = form.querySelector(`[data-error-for="${CSS.escape(name)}"]`);
    if (error) error.textContent = message;
    const controls = form.querySelectorAll(`[name="${CSS.escape(name)}"]`);
    controls.forEach(control => control.setAttribute("aria-invalid", "true"));
  });
  const first = form.querySelector("[aria-invalid=true]");
  first?.focus();
}

export function validateAchievementForm(form) {
  clearErrors(form);
  const category = String(form.elements.category?.value || "");
  const template = getAchievementTemplate(category);
  const errors = {};
  const title = String(form.elements.title?.value || "").trim();
  if (!template) errors.category = "请选择有效的成果类别";
  if (!title) errors.title = "成果标题不能为空";
  const level = template?.level_usage ? String(form.elements.level?.value || "").trim() : null;
  if (template?.level_usage && !level) errors.level = "请选择成果级别";
  if (template?.level_usage && level && !template.level_field.enum.includes(level)) errors.level = "请选择有效的成果级别";

  const details = {};
  template?.fields.forEach(field => {
    const name = fieldName(field.key);
    const control = form.elements[name];
    const value = control?.value ?? "";
    if (!String(value).trim()) {
      errors[name] = "此项为必填项";
      return;
    }
    const formatError = validateFormat(field, value);
    if (formatError) errors[name] = formatError;
    else if (field.enum.length && !field.enum.includes(String(value))) errors[name] = `请选择${field.enum.join("或")}`;
    else details[field.key] = normalizeValue(field, value);
  });

  if (category === "patent" && details.grant_year !== undefined && details.grant_month !== undefined && ((details.grant_year === "无") !== (details.grant_month === "无"))) {
    errors["details.grant_month"] = "授权年份与月份必须同时填写“无”或同时填写年月";
  }
  if (["research", "innovation", "organization", "social", "arts"].includes(category) && details.end_year !== undefined && details.end_month !== undefined && ((details.end_year === "进行中") !== (details.end_month === "进行中"))) {
    errors["details.end_month"] = "结束年份与月份必须同时填写“进行中”或同时填写年月";
  }

  showErrors(form, errors);
  return {
    valid: Object.keys(errors).length === 0,
    errors,
    payload: { category, title, level, details, is_public: form.elements.is_public?.checked === true },
  };
}
