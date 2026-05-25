// ===== 激活检查 =====
async function checkLicenseGate() {
  try {
    const r = await fetch("/api/license/status");
    const s = await r.json();
    if (!s.licensed && !s.trial) {
      window.location.href = "/static/activate.html";
      return false;
    }
    // 显示剩余天数提示
    if (s.trial && s.days_left <= 3) {
      setTimeout(() => {
        const banner = document.createElement("div");
        banner.style.cssText = "background:#fef3c7;color:#92400e;padding:8px 16px;text-align:center;font-size:0.85rem;border-bottom:1px solid #fcd34d";
        banner.innerHTML = `试用期还剩 <strong>${s.days_left}</strong> 天，<a href="/static/activate.html" style="color:#b45309">点击激活</a>`;
        document.querySelector(".app")?.prepend(banner);
      }, 500);
    }
    return true;
  } catch(e) {
    console.error("License check failed:", e);
    return true; // 网络错误放行
  }
}

// 在 DOM ready 时检查
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", checkLicenseGate);
} else {
  checkLicenseGate();
}

const API = "/api";
let currentLibId = localStorage.getItem("currentLibId") || null;
let batchMode = false;

const $ = (id) => document.getElementById(id);

async function api(path, opts = {}) {
  const res = await fetch(API + path, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const d = data.detail;
    const msg = Array.isArray(d) ? d.map((x) => x.msg || x).join("; ") : d || data.message;
    throw new Error(msg || res.statusText);
  }
  return data;
}


function showLoading(btn, text) {
  btn.disabled = true;
  btn.dataset.origText = btn.textContent;
  btn.innerHTML = '<span class="spinner"></span>' + text;
}

function hideLoading(btn) {
  btn.disabled = false;
  btn.textContent = btn.dataset.origText || btn.textContent;
}

function showToast(msg, ok = true) {
  const t = document.createElement("div");
  t.className = "toast " + (ok ? "toast-ok" : "toast-bad");
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => { t.style.opacity = "0"; t.style.transition = "opacity 0.3s"; }, 3000);
  setTimeout(() => t.remove(), 3300);
}

function formatSize(n) {
  if (n < 1024) return n + " B";
  if (n < 1024 * 1024) return (n / 1024).toFixed(1) + " KB";
  return (n / 1024 / 1024).toFixed(1) + " MB";
}

function setStatus(el, text, ok) {
  el.textContent = text;
  el.style.color = ok ? "var(--ok)" : "var(--bad)";
}

async function loadLibraries() {
  const { libraries } = await api("/libraries");
  const ul = $("libList");
  ul.innerHTML = "";
  libraries.forEach((lib) => {
    const li = document.createElement("li");
    li.className = "lib-item" + (lib.id === currentLibId ? " active" : "");
    li.innerHTML = `
      <button type="button" class="del" title="删除">×</button>
      <div class="name">${escapeHtml(lib.name)}</div>
      <div class="sub">${lib.question_count || 0} 题 · ${lib.status === "ready" ? "已构建" : "待构建"}</div>
    `;
    li.onclick = (e) => {
      if (e.target.classList.contains("del")) return;
      selectLibrary(lib.id);
    };
    li.querySelector(".del").onclick = (e) => {
      e.stopPropagation();
      deleteLibrary(lib.id);
    };
    ul.appendChild(li);
  });
  if (!currentLibId && libraries.length) selectLibrary(libraries[0].id);
  updatePanels();
}

function selectLibrary(id) {
  currentLibId = id;
  localStorage.setItem("currentLibId", id);
  loadLibraries();
  refreshLibraryDetail();
  renderHistory();
}

async function refreshLibraryDetail() {
  if (!currentLibId) return;
  const { library } = await api(`/libraries/${currentLibId}`);
  $("currentLibTitle").textContent = library.name;
  $("toolbarMeta").textContent = library.name;
  const stats = [];
  if (library.question_count) {
    stats.push(`${library.question_count} 道题`);
    stats.push(`${library.red_count || 0} 道标红答案`);
  }
  stats.push(`${library.file_count || 0} 个文件`);
  $("libStats").textContent = stats.join(" · ");
  renderFiles(library.files || []);
}

function renderFiles(files) {
  const ul = $("fileList");
  if (!files.length) {
    ul.innerHTML = '<li style="color:var(--ink-faint);font-size:0.85rem;padding:0.5rem">暂无文件</li>';
    return;
  }
  ul.innerHTML = "";
  files.forEach((f) => {
    const li = document.createElement("li");
    li.innerHTML = `<span>${escapeHtml(f.name)} (${formatSize(f.size)})</span>
      <button type="button">删除</button>`;
    li.querySelector("button").onclick = () => removeFile(f.name);
    ul.appendChild(li);
  });
}

async function createLibrary() {
  const name = $("libName").value.trim();
  if (!name) return alert("请输入题库名称");
  const { library } = await api("/libraries", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  $("libName").value = "";
  selectLibrary(library.id);
}

async function deleteLibrary(id) {
  if (!confirm("确定要删除该题库？\n此操作不可恢复！")) return;
  if (!confirm("确定删除该题库及全部文件？")) return;
  await api(`/libraries/${id}`, { method: "DELETE" });
  if (currentLibId === id) {
    currentLibId = null;
    localStorage.removeItem("currentLibId");
    $("toolbarMeta").textContent = "未选择题库";
  }
  loadLibraries();
}

async function uploadFiles(fileList) {
  if (!currentLibId) return alert("请先选择题库");
  const errors = [];
  for (const file of fileList) {
    try {
      const fd = new FormData();
      fd.append("file", file);
      await api(`/libraries/${currentLibId}/upload`, { method: "POST", body: fd });
    } catch (e) {
      errors.push(`${file.name}: ${e.message}`);
    }
  }
  await refreshLibraryDetail();
  if (errors.length) {
    setStatus($("buildStatus"), errors.join("；"), false);
  } else {
    setStatus($("buildStatus"), "已上传，请点击「开始构建」", true);
  }
}

async function removeFile(name) {
  if (!confirm(`确定要删除文件 "${name}"？`)) return;
  await api(`/libraries/${currentLibId}/files/${encodeURIComponent(name)}`, {
    method: "DELETE",
  });
  refreshLibraryDetail();
}

async function buildIndex() {
  if (!currentLibId) return;
  $("buildProgress").classList.remove("hidden");
  $("btnBuild").disabled = true;
  $("buildStatus").textContent = "";
  try {
    const r = await api(`/libraries/${currentLibId}/build`, { method: "POST" });
    setStatus(
      $("buildStatus"),
      `构建完成：共 ${r.question_count} 题（${r.red_count} 道来自 PDF 红色标注）`,
      true
    );
    loadLibraries();
    refreshLibraryDetail();
  } catch (e) {
    setStatus($("buildStatus"), e.message, false);
  } finally {
    $("buildProgress").classList.add("hidden");
    $("btnBuild").disabled = false;
  }
}

async function doSearch() {
  const query = $("query").value.trim();
  if (!query) return alert("请输入题目内容");
  if (!currentLibId) return alert("请先选择题库");

  $("btnSearch").disabled = true;
  const box = $("searchResult");
  box.classList.remove("hidden");
  box.innerHTML =
    '<div class="skeleton" style="height:1rem;width:30%;margin-bottom:1rem"></div>' +
    '<div class="skeleton" style="height:0.85rem;width:55%;margin-bottom:0.6rem"></div>' +
    '<div class="skeleton" style="height:3rem;margin-bottom:0.5rem"></div>' +
    '<div class="skeleton" style="height:2.4rem;margin-bottom:0.3rem"></div>' +
    '<div class="skeleton" style="height:2.4rem;margin-bottom:0.3rem"></div>' +
    '<div class="skeleton" style="height:2.4rem;margin-bottom:0.3rem"></div>';

  try {
    const r = await api(`/libraries/${currentLibId}/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });
    box.innerHTML = renderSearchResult(r);
    addHistoryEntry(query, r);
  } catch (e) {
    box.innerHTML = `<p class="err">${escapeHtml(e.message)}</p>`;
  } finally {
    $("btnSearch").disabled = false;
  }
}

function renderSearchResult(r) {
  if (r.found && r.question) {
    const q = r.question;
    const src = q.answer_from_red
      ? '<span class="badge badge-red">PDF 红色标注</span>'
      : '<span class="badge badge-infer">解析推断</span>';
    let html = `
      <h3>正确答案</h3>
      <p class="meta-line">题号 ${q.number} · 匹配度 ${(r.score * 100).toFixed(0)}% ${src}</p>
      <div class="stem-preview">${escapeHtml(q.stem)}</div>
    `;
    q.options.forEach((o) => {
      html += `<div class="option${o.correct ? " correct" : ""}">
        <span class="lab">${o.label}</span> ${escapeHtml(o.text)}
      </div>`;
    });
    if (r.alternatives?.length) {
      html += `<p class="meta-line" style="margin-top:1rem">其他可能：${r.alternatives
        .map((a) => `第 ${a.number} 题 (${(a.score * 100).toFixed(0)}%)`)
        .join("、")}</p>`;
    }
    return html;
  }
  if (r.fallback) {
    return `<h3>未精确匹配</h3><p class="meta-line">以下为资料库检索片段</p><pre class="fallback">${escapeHtml(r.fallback)}</pre>`;
  }
  return `<p class="err">${escapeHtml(r.message || "未找到匹配，请换关键词重试")}</p>`;
}

function updatePanels() {
  const has = !!currentLibId;
  $("noLibHint").classList.toggle("hidden", has);
  $("uploadArea").classList.toggle("hidden", !has);
  $("searchHint").classList.toggle("hidden", has);
  $("searchArea").classList.toggle("hidden", !has);
  if (has) refreshLibraryDetail();
  else $("toolbarMeta").textContent = "未选择题库";
}

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

function toggleBatchMode() {
  batchMode = !batchMode;
  $("btnBatchToggle").textContent = batchMode ? "单题查询" : "批量查题";
  $("btnBatchToggle").classList.toggle("active", batchMode);
  $("batchHint").classList.toggle("hidden", !batchMode);
  $("btnSearch").textContent = batchMode ? "批量查找" : "查找正确答案";
  $("batchResults").classList.add("hidden");
  $("searchResult").classList.add("hidden");
}

function splitBatchQueries(text) {
  const blocks = text.split(/\n\s*\n/);
  return blocks.map((b) => b.trim()).filter((b) => b.length >= 3);
}

async function doBatchSearch() {
  const raw = $("query").value.trim();
  if (!raw) return alert("请输入题目内容");
  if (!currentLibId) return alert("请先选择题库");

  const queries = splitBatchQueries(raw);
  if (!queries.length) return alert("至少需要一道完整题目（≥3 字符）");
  if (queries.length > 20) return alert("单次最多 20 道题");

  $("btnSearch").disabled = true;
  $("searchResult").classList.add("hidden");
  const box = $("batchResults");
  box.classList.remove("hidden");
  box.innerHTML = `<p class="meta-line" style="margin-bottom:0.75rem">正在批量匹配 ${queries.length} 道题…</p>` +
    Array(3).fill('<div class="skeleton" style="height:4rem;margin-bottom:0.5rem"></div>').join("");

  try {
    const r = await api(`/libraries/${currentLibId}/batch-search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ queries }),
    });
    box.innerHTML = renderBatchResults(r.results);
  } catch (e) {
    box.innerHTML = `<p class="err">${escapeHtml(e.message)}</p>`;
  } finally {
    $("btnSearch").disabled = false;
  }
}

function renderBatchResults(results) {
  let html = `<h3>批量结果（${results.length} 题）</h3>`;
  results.forEach((r, i) => {
    const delay = i * 40;
    if (r.found && r.question) {
      const q = r.question;
      html += `<div class="answer-card" style="margin-bottom:0.75rem;animation-delay:${delay}ms">
        <p class="meta-line">题号 ${q.number} · 匹配度 ${(r.score * 100).toFixed(0)}%</p>
        <div class="stem-preview">${escapeHtml(q.stem)}</div>
      </div>`;
    } else {
      html += `<div class="answer-card" style="margin-bottom:0.75rem;animation-delay:${delay}ms">
        <p class="meta-line">未匹配</p>
        <div class="stem-preview" style="color:var(--ink-faint)">${escapeHtml(r.query || `第 ${i + 1} 题`)}</div>
        ${r.fallback ? `<pre class="fallback">${escapeHtml(r.fallback)}</pre>` : ""}
      </div>`;
    }
  });
  return html;
}

function _historyKey() {
  return `search_history_${currentLibId}`;
}

function loadHistory() {
  try {
    return JSON.parse(localStorage.getItem(_historyKey()) || "[]");
  } catch {
    return [];
  }
}

function saveHistory(entries) {
  const capped = entries.slice(0, 50);
  localStorage.setItem(_historyKey(), JSON.stringify(capped));
}

function addHistoryEntry(query, result) {
  const entries = loadHistory();
  entries.unshift({
    query: query.slice(0, 200),
    number: result?.question?.number || null,
    score: result?.score || null,
    ts: Date.now(),
  });
  saveHistory(entries);
  renderHistory();
}

function renderHistory() {
  const entries = loadHistory();
  const section = $("searchHistory");
  if (!entries.length) {
    section.classList.add("hidden");
    return;
  }
  section.classList.remove("hidden");
  const ul = $("historyList");
  ul.innerHTML = entries
    .map(
      (e) => `<li class="history-item" data-query="${escapeHtml(e.query)}">
      <span class="history-query">${escapeHtml(e.query.slice(0, 80))}</span>
      ${e.number ? `<span class="badge badge-infer" style="margin-left:auto;flex-shrink:0">题号 ${e.number}</span>` : ""}
    </li>`
    )
    .join("");
  ul.querySelectorAll(".history-item").forEach((li) => {
    li.onclick = () => {
      $("query").value = li.dataset.query;
      $("query").focus();
    };
  });
}

function clearHistory() {
  localStorage.removeItem(_historyKey());
  renderHistory();
}

document.querySelectorAll(".seg-item").forEach((tab) => {
  tab.onclick = () => {
    document.querySelectorAll(".seg-item").forEach((t) => t.classList.remove("active"));
    document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
    tab.classList.add("active");
    $(`panel-${tab.dataset.tab}`).classList.add("active");
  };
});

$("btnCreateLib").onclick = createLibrary;
$("btnBuild").onclick = buildIndex;
$("btnSearch").onclick = () => {
  if (batchMode) doBatchSearch();
  else doSearch();
};
$("btnBatchToggle").onclick = toggleBatchMode;
$("btnClearHistory").onclick = clearHistory;

const dropzone = $("dropzone");
const fileInput = $("fileInput");
dropzone.onclick = () => fileInput.click();
dropzone.ondragover = (e) => {
  e.preventDefault();
  dropzone.classList.add("dragover");
};
dropzone.ondragleave = () => dropzone.classList.remove("dragover");
dropzone.ondrop = (e) => {
  e.preventDefault();
  dropzone.classList.remove("dragover");
  uploadFiles(e.dataTransfer.files);
};
fileInput.onchange = () => uploadFiles(fileInput.files);

loadLibraries().catch((e) =>
  alert("无法连接后台服务。\n请先运行「启动桌面版.bat」或「启动应用.bat」\n\n" + e.message)
);
