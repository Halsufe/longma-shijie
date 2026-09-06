import { api, fetchBlob } from "./api.js";
import { escapeHtml, formatBytes, icon } from "./ui.js";

const ALLOWED_TYPES = new Set(["application/pdf", "image/jpeg", "image/png"]);
const MAX_FILE_BYTES = 20 * 1024 * 1024;

function proofId(proof) {
  return String(proof?.id || proof?.stored_name || proof?.path || "");
}

function renderProof(proof, index) {
  const pending = Boolean(proof._file);
  return `<li class="achievement-proof-item" data-proof-index="${index}">
    <span class="achievement-proof-icon">${icon(proof.mime === "application/pdf" ? "file" : "eye")}</span>
    <span class="achievement-proof-main"><strong>${escapeHtml(proof.name || "未命名附件")}</strong><small>${formatBytes(proof.size || 0)} · ${pending ? "等待上传" : "已上传"}</small></span>
    <button class="icon-button" type="button" data-preview-proof="${index}" aria-label="预览附件">${icon("eye")}</button>
    <button class="icon-button" type="button" data-replace-proof="${index}" aria-label="替换附件">${icon("upload")}</button>
    <button class="icon-button danger" type="button" data-remove-proof="${index}" aria-label="删除附件">${icon("trash")}</button>
  </li>`;
}

export async function openAchievementProof(fileId, options = {}) {
  const targetWindow = options.download ? null : window.open("about:blank", "_blank");
  try {
    // fetchBlob supplies the Authorization header for this protected file endpoint.
    const blobUrl = URL.createObjectURL(await fetchBlob(`/api/v1/achievements/files/${encodeURIComponent(fileId)}${options.download ? "?download=true" : ""}`));
    if (options.download) {
      const link = document.createElement("a");
      link.href = blobUrl;
      link.download = options.name || fileId;
      link.click();
    } else if (targetWindow) {
      targetWindow.location.href = blobUrl;
    } else {
      window.open(blobUrl, "_blank", "noopener");
    }
    setTimeout(() => URL.revokeObjectURL(blobUrl), 60000);
  } catch (error) {
    targetWindow?.close();
    throw error;
  }
}

export function renderAchievementUpload(proofs = []) {
  return `<section class="achievement-upload" data-achievement-upload>
    <div class="achievement-upload-head">
      <div><strong>证明材料 <span class="required-mark">*</span></strong><small>支持多份 PDF、JPG、PNG，单份不超过20MB</small></div>
      <button class="button button-secondary button-small" type="button" data-add-proof>${icon("upload")} 选择文件</button>
    </div>
    <input class="visually-hidden" type="file" accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png" multiple data-proof-input>
    <ul class="achievement-proof-list" data-proof-list>${proofs.map(renderProof).join("")}</ul>
    <p class="achievement-upload-empty" data-proof-empty ${proofs.length ? "hidden" : ""}>至少上传1份证明材料后才能提交。</p>
    <small class="field-error" data-proof-error aria-live="polite"></small>
  </section>`;
}

function validateFile(file) {
  if (!ALLOWED_TYPES.has(file.type)) return "证明材料仅支持 PDF、JPG、PNG 格式";
  if (!file.size) return "证明材料不能为空";
  if (file.size > MAX_FILE_BYTES) return "单份证明材料不能超过20MB";
  return "";
}

export function createAchievementUpload(root, options = {}) {
  const uploadApi = options.apiClient || api;
  const input = root.querySelector("[data-proof-input]");
  const list = root.querySelector("[data-proof-list]");
  const empty = root.querySelector("[data-proof-empty]");
  const errorNode = root.querySelector("[data-proof-error]");
  let replacementIndex = null;
  let proofs = (options.proofs || []).map(proof => ({ ...proof }));

  const revokePreview = proof => {
    if (proof?._previewUrl) URL.revokeObjectURL(proof._previewUrl);
  };
  const draw = () => {
    list.innerHTML = proofs.map(renderProof).join("");
    empty.hidden = proofs.length > 0;
  };
  const addFiles = files => {
    errorNode.textContent = "";
    const accepted = [];
    for (const file of files) {
      const message = validateFile(file);
      if (message) {
        errorNode.textContent = `${file.name}：${message}`;
        continue;
      }
      accepted.push({
        id: `pending-${crypto.randomUUID()}`,
        name: file.name,
        size: file.size,
        mime: file.type,
        _file: file,
        _previewUrl: URL.createObjectURL(file),
      });
    }
    if (replacementIndex !== null && accepted.length) {
      revokePreview(proofs[replacementIndex]);
      proofs.splice(replacementIndex, 1, accepted[0]);
    } else {
      proofs.push(...accepted);
    }
    replacementIndex = null;
    input.multiple = true;
    input.value = "";
    draw();
  };

  root.querySelector("[data-add-proof]").addEventListener("click", () => {
    replacementIndex = null;
    input.multiple = true;
    input.click();
  });
  input.addEventListener("change", () => addFiles([...input.files]));
  list.addEventListener("click", event => {
    const previewButton = event.target.closest("[data-preview-proof]");
    if (previewButton) {
      const proof = proofs[Number(previewButton.dataset.previewProof)];
      const open = proof?._previewUrl
        ? Promise.resolve(window.open(proof._previewUrl, "_blank", "noopener"))
        : openAchievementProof(proofId(proof));
      open.catch(error => { errorNode.textContent = error.message; });
      return;
    }
    const removeButton = event.target.closest("[data-remove-proof]");
    if (removeButton) {
      const index = Number(removeButton.dataset.removeProof);
      revokePreview(proofs[index]);
      proofs.splice(index, 1);
      draw();
      return;
    }
    const replaceButton = event.target.closest("[data-replace-proof]");
    if (replaceButton) {
      replacementIndex = Number(replaceButton.dataset.replaceProof);
      input.multiple = false;
      input.click();
    }
  });

  draw();
  return {
    validate() {
      errorNode.textContent = proofs.length ? "" : "请至少上传1份证明材料";
      return proofs.length > 0;
    },
    getProofs() {
      return proofs.filter(proof => !proof._file).map(({ _previewUrl, ...proof }) => proof);
    },
    async uploadAll() {
      if (!this.validate()) throw new Error("请至少上传1份证明材料");
      const uploaded = [];
      for (const proof of proofs) {
        if (!proof._file) {
          uploaded.push({ ...proof });
          continue;
        }
        errorNode.textContent = `正在上传 ${proof.name}...`;
        const body = new FormData();
        body.append("file", proof._file, proof.name);
        const result = await uploadApi("/api/v1/achievements/files", { method: "POST", body });
        revokePreview(proof);
        uploaded.push(result);
      }
      proofs = uploaded;
      errorNode.textContent = "";
      draw();
      return proofs.map(proof => ({ ...proof }));
    },
    destroy() {
      proofs.forEach(revokePreview);
    },
  };
}
