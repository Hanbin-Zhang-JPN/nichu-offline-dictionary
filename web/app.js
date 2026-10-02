"use strict";
const $ = id => document.getElementById(id);
const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const number = value => Number(value).toLocaleString("zh-CN");
const STORE = "nichu-learning-v1";
let learning = {version: 1, favorites: [], history: []};
let state = {view: "search", mode: "auto", offset: 0, limit: 30, total: 0, selected: "", rows: []};
let searchController, searchSequence = 0, detailSequence = 0, timer, composing = false, activeEntry;

function notice(text) { $("notice").textContent = text; $("notice").hidden = !text; }
function validateLearning(value) {
  if (!value || value.version !== 1 || !Array.isArray(value.favorites) || !Array.isArray(value.history)) throw new Error("记录格式不正确，请导入本词典导出的 JSON 文件。");
  if (value.favorites.length > 10000 || value.history.length > 200) throw new Error("记录过多（最多 10000 个收藏、200 条历史）。");
  const seen = new Set();
  const favorites = value.favorites.filter(row => {
    if (!row || !/^[a-f0-9]{24}$/.test(row.id) || seen.has(row.id)) return false;
    seen.add(row.id); return true;
  }).map(row => Object.fromEntries(["id", "word", "pos", "pos_title", "reading", "roman", "preview"].map(k => [k, String(row[k] || "").slice(0, 300)])));
  return {version: 1, favorites, history: value.history.filter(s => typeof s === "string" && s.trim() && s.length <= 120)};
}
try { const stored = localStorage.getItem(STORE); if (stored) learning = validateLearning(JSON.parse(stored)); }
catch { notice("浏览器学习记录无法读取。本次仍可查词；如需保留收藏，请导出记录。"); }
function persist() {
  try { localStorage.setItem(STORE, JSON.stringify(learning)); }
  catch { notice("浏览器存储不可用或已满。请使用“导出学习记录”保存收藏。"); }
  $("fav-count").textContent = learning.favorites.length;
}
const saved = id => learning.favorites.some(row => row.id === id);
function remember(q) { if (!q.trim()) return; learning.history = [q, ...learning.history.filter(x => x !== q)].slice(0, 100); persist(); }
function toggleSave(id) {
  if (saved(id)) learning.favorites = learning.favorites.filter(row => row.id !== id);
  else {
    const row = state.rows.find(row => row.id === id) || (activeEntry?.id === id ? {
      id, word: activeEntry.word, pos: activeEntry.pos, pos_title: activeEntry.pos_title,
      reading: activeEntry.readings.join(" · "), roman: activeEntry.romaji.join(" · "),
      preview: activeEntry.senses.flatMap(s => s.glosses || []).join("；").slice(0, 240)
    } : null);
    if (row) learning.favorites.push(row);
  }
  persist();
  if (state.view === "favorites") showLocal(); else renderRows();
  if (activeEntry) renderDetail(activeEntry);
}

async function api(path, signal) {
  const response = await fetch(path, {signal});
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || "本地服务读取失败");
  return body;
}

function renderRows() {
  $("results").innerHTML = state.rows.length ? state.rows.map(row => `<div class="result-row ${state.selected === row.id ? "active" : ""}"><button class="result-select" data-entry="${esc(row.id)}" aria-label="查看 ${esc(row.word)}"><span class="result-word" lang="ja">${esc(row.word)}</span><span class="result-pos">${esc(row.pos_title || "未标注")}</span><span class="result-reading" lang="ja">${esc(row.reading || row.roman || "读音未收录")}</span><span class="result-gloss">${esc(row.preview)}</span></button><button class="save-button ${saved(row.id) ? "saved" : ""}" data-save="${esc(row.id)}" aria-label="${saved(row.id) ? "取消收藏" : "收藏"} ${esc(row.word)}" aria-pressed="${saved(row.id)}">${saved(row.id) ? "♥" : "♡"}</button></div>`).join("") : '<div class="empty-results">这里还没有词条。<br>试试其他词语、假名或中文释义。</div>';
  $("previous").disabled = state.offset === 0 || state.view !== "search";
  $("next").disabled = state.offset + state.limit >= state.total || state.view !== "search";
  $("page-number").textContent = state.view === "search" && state.total ? `${Math.floor(state.offset / state.limit) + 1} / ${Math.ceil(state.total / state.limit)}` : "";
  $("result-count").textContent = `${number(state.total)} 条`;
  $("results").setAttribute("aria-busy", "false");
}

async function search({reset = true, record = false} = {}) {
  if (state.view !== "search") return showLocal();
  if (reset) state.offset = 0;
  const sequence = ++searchSequence;
  searchController?.abort(); searchController = new AbortController();
  $("results").setAttribute("aria-busy", "true");
  const q = $("query").value.trim();
  const params = new URLSearchParams({q, mode: state.mode, pos: $("pos").value, examples: $("examples").checked ? "1" : "0", offset: state.offset, limit: state.limit, script: $("script").value});
  try {
    const result = await api(`/api/search?${params}`, searchController.signal);
    if (sequence !== searchSequence) return;
    state.rows = result.results; state.total = result.total;
    $("result-title").firstChild.textContent = q ? "查询结果 " : "全部词条 ";
    renderRows();
    if (record) remember(q);
    if (reset && state.rows.length) await selectEntry(state.rows[0].id, false);
    else if (reset && !state.rows.length) { activeEntry = null; ++detailSequence; $("detail").innerHTML = '<div class="empty-state"><span class="empty-kanji">辞</span><h2>暂时没有找到这个词。</h2><p>可尝试原形、假名或“包含”模式。<br>中文反查检索的是释义中的文字。</p></div>'; }
  } catch (error) {
    if (error.name !== "AbortError" && sequence === searchSequence) {
      $("results").setAttribute("aria-busy", "false");
      notice(`${error.message}。请确认终端中的词典服务仍在运行。`);
    }
  }
}

async function selectEntry(id, scroll = true) {
  state.selected = id; renderRows();
  const sequence = ++detailSequence;
  $("detail").setAttribute("aria-busy", "true");
  try {
    const entry = await api(`/api/entry/${encodeURIComponent(id)}?script=${$("script").value}`);
    if (sequence !== detailSequence) return;
    activeEntry = entry; renderDetail(entry);
    if (scroll) {
      remember(entry.word);
      if (window.innerWidth <= 620) $("detail").scrollIntoView({behavior: "smooth", block: "start"});
    }
  } catch (error) { if (sequence === detailSequence) { notice(error.message); $("detail").setAttribute("aria-busy", "false"); } }
}

const tagNames = {Heiban: "平板型", Atamadaka: "头高型", Nakadaka: "中高型", Odaka: "尾高型", archaic: "古语", informal: "口语", polite: "礼貌语", slang: "俚语", transitive: "及物", intransitive: "不及物", obsolete: "已废用", "alt-of": "异体形式", "form-of": "词形", "no-gloss": "缺少释义"};
const tagText = tags => (tags || []).map(t => tagNames[t] || t).join(" · ");
function exampleHTML(example) {
  return `<div class="example"><p lang="ja">${esc(example.text || "")}</p>${example.translation ? `<p class="translation">${esc(example.translation)}</p>` : ""}${example.roman ? `<p class="roman">${esc(example.roman)}</p>` : ""}${example.ref ? `<p class="reference">${esc(example.ref)}</p>` : ""}</div>`;
}
function relatedHTML(items) {
  return `<div class="related">${items.map(item => `<button data-query="${esc(item.word)}" lang="ja">${esc(item.word)}${item.roman ? ` <small>${esc(item.roman)}</small>` : ""}</button>`).join("")}</div>`;
}

function renderDetail(entry) {
  const sounds = entry.sounds || [], forms = entry.forms || [], senses = entry.senses || [];
  const ipa = sounds.filter(s => s.ipa).map(s => s.ipa);
  const pitch = sounds.filter(s => s.other || (s.tags || []).some(t => ["Heiban", "Atamadaka", "Nakadaka", "Odaka"].includes(t)));
  const tags = [...new Set([...(entry.tags || []), ...senses.flatMap(s => (s.tags || []).filter(t => ["transitive", "intransitive", "polite", "archaic", "slang", "informal"].includes(t)))])];
  let html = `<div class="detail-topline"><span>DICTIONARY ENTRY · 日语词条</span><div class="detail-actions"><button id="copy-word">复制词语</button><button data-save="${esc(entry.id)}">${saved(entry.id) ? "♥ 已收藏" : "♡ 收藏"}</button></div></div><div class="word-heading"><h2 lang="ja">${esc(entry.word)}</h2><button class="listen" id="listen" disabled title="需要系统已安装的本地日语语音" aria-label="使用本地日语语音朗读">♪</button></div><p class="reading-line" lang="ja">${esc(entry.readings.join(" / ") || "读音未收录")}<small>${esc(entry.romaji.join(" / "))}</small></p><div class="tag-line"><span class="tag">${esc(entry.pos_title || entry.pos || "未标注词性")}</span>${tags.map(t => `<span class="tag">${esc(tagNames[t] || t)}</span>`).join("")}${pitch.slice(0, 4).map(s => `<span class="tag accent">${esc(tagText(s.tags) || "源发音信息")} ${esc((s.raw_tags || []).join(" · "))}</span>`).join("")}</div><hr class="detail-divider"><h3 class="section-label">释义与用法 <span>MEANINGS & USAGE</span></h3>`;
  senses.forEach((sense, i) => {
    const examples = sense.examples || [];
    html += `<section class="sense"><span class="sense-number">${String(i + 1).padStart(2, "0")}</span><div class="sense-body"><p class="sense-gloss">${esc((sense.glosses || []).join("；") || "此义项暂无释义")}</p><div class="sense-tags">${esc([tagText(sense.tags), ...(sense.raw_tags || [])].filter(Boolean).join(" · "))}</div>${exampleHTML(examples[0] || {}).replace('<div class="example"><p lang="ja"></p></div>', "")}${examples.length > 1 ? `<details><summary>另有 ${examples.length - 1} 条用例 / 引文</summary>${examples.slice(1).map(exampleHTML).join("")}</details>` : ""}${sense.alt_of || sense.form_of ? relatedHTML(sense.alt_of || sense.form_of) : ""}</div></section>`;
  });
  if (entry.notes?.length) html += `<hr class="detail-divider"><h3 class="section-label">用法说明 <span>USAGE NOTES</span></h3><div class="etymology">${entry.notes.map(t => `<p>${esc(t)}</p>`).join("")}</div>`;
  if (ipa.length || pitch.length) html += `<hr class="detail-divider"><h3 class="section-label">发音与音调 <span>PRONUNCIATION</span></h3><div class="sounds">${ipa.map(t => `<span>IPA ${esc(t)}</span>`).join("")}${pitch.map(s => `<span lang="ja">${esc([s.other, s.roman, tagText(s.tags), ...(s.raw_tags || [])].filter(Boolean).join(" · "))}</span>`).join("")}</div>`;
  if (entry.etymology_texts?.length) html += `<hr class="detail-divider"><h3 class="section-label">语源 <span>ETYMOLOGY</span></h3><div class="etymology">${entry.etymology_texts.map(t => `<p>${esc(t)}</p>`).join("")}</div>`;
  for (const [field, label] of [["synonyms", "近义词"], ["antonyms", "反义词"], ["derived", "派生词"], ["related", "相关词"], ["coordinate_terms", "同类词"]]) {
    if (entry[field]?.length) html += `<details><summary>${label} · ${entry[field].length}</summary>${relatedHTML(entry[field])}</details>`;
  }
  if (forms.length) html += `<details><summary>词形与活用 · ${forms.length} 项源记录</summary><table class="forms-table"><tbody>${forms.map(f => `<tr><td lang="ja">${esc(f.form)}</td><td>${esc([tagText(f.tags), ...(f.raw_tags || [])].filter(Boolean).join(" · "))}</td></tr>`).join("")}</tbody></table></details>`;
  html += `<details><summary>原始结构字段（当前显示视图）</summary><pre>${esc(JSON.stringify(entry, null, 2))}</pre></details><div class="entry-source">来源：中文维基词典贡献者，经 Wiktextract / Kaikki.org 提取。派生词典内容采用 CC BY-SA 4.0。<br><a href="https://zh.wiktionary.org/wiki/${encodeURIComponent(entry.word)}#日語" target="_blank" rel="noopener noreferrer">查看来源与编辑历史 ↗（需联网）</a> · <a href="/guide#license">数据说明与许可</a><br>词条 ID：${esc(entry.id)} · 未展示字段保留于词库快照；缺失字段不会自动补写。</div>`;
  $("detail").innerHTML = html; $("detail").setAttribute("aria-busy", "false");
  updateVoice();
}

function localVoice() { return window.speechSynthesis?.getVoices().find(v => v.localService && /^ja(?:-|_)/i.test(v.lang)); }
function updateVoice() { const button = $("listen"); if (button) { button.disabled = !localVoice(); button.title = button.disabled ? "系统尚未安装本地日语语音；IPA 和音调仍可离线查看" : "使用系统本地日语语音朗读"; } }
window.speechSynthesis?.addEventListener("voiceschanged", updateVoice);

function showLocal() {
  searchController?.abort(); ++searchSequence;
  const q = $("query").value.trim().toLowerCase();
  if (state.view === "favorites") {
    state.rows = learning.favorites.filter(row => `${row.word}${row.reading}${row.roman}${row.preview}`.toLowerCase().includes(q));
    state.total = state.rows.length; renderRows();
    $("result-title").firstChild.textContent = "我的收藏 ";
    if (!state.rows.length) $("results").innerHTML = '<div class="empty-results">还没有匹配的收藏。<br>点击词条旁的 ♡ 保存下来。</div>';
  } else {
    const history = learning.history.filter(word => word.toLowerCase().includes(q));
    state.rows = []; state.total = history.length; renderRows();
    $("result-title").firstChild.textContent = "最近查询 ";
    $("results").innerHTML = history.length ? history.map(word => `<div class="result-row"><button class="result-select" data-query="${esc(word)}"><span class="result-word" lang="ja">${esc(word)}</span><span class="result-reading">点击重新查询 →</span></button></div>`).join("") : '<div class="empty-results">最近查询会显示在这里。<br>按 Enter 查词，或打开词条即可记录。</div>';
  }
}

function switchView(view) {
  state.view = view; state.offset = 0; $("query").value = "";
  document.querySelectorAll("[data-view]").forEach(button => button.classList.toggle("active", button.dataset.view === view));
  $("page-title").textContent = ({search: "把每一个词，读得明白。", favorites: "把喜欢的词，留在身边。", history: "每一次查询，都有迹可循。"})[view];
  $("result-caption").textContent = ({search: "SEARCH RESULTS", favorites: "YOUR WORD COLLECTION", history: "RECENT LOOKUPS"})[view];
  document.querySelector(".search-tools").hidden = view !== "search";
  if (view === "search") search(); else showLocal();
}
function searchWord(q) { if (state.view !== "search") switchView("search"); $("query").value = q; clearTimeout(timer); search({record: true}); }

$("search-form").addEventListener("submit", event => { event.preventDefault(); clearTimeout(timer); search({record: true}); });
$("query").addEventListener("compositionstart", () => { composing = true; clearTimeout(timer); });
$("query").addEventListener("compositionend", () => { composing = false; schedule(); });
function schedule() { if (composing) return; clearTimeout(timer); timer = setTimeout(() => search(), 220); }
$("query").addEventListener("input", schedule);
for (const id of ["pos", "examples"]) $(id).addEventListener("change", () => search());
$("script").addEventListener("change", () => { if (state.view === "search") search(); else if (activeEntry) selectEntry(activeEntry.id, false); });
$("previous").addEventListener("click", () => { state.offset -= state.limit; search({reset: false}); $("results").scrollTop = 0; });
$("next").addEventListener("click", () => { state.offset += state.limit; search({reset: false}); $("results").scrollTop = 0; });
document.addEventListener("keydown", event => { if (event.key === "/" && !/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName) && !event.ctrlKey && !event.metaKey) { event.preventDefault(); $("query").focus(); } });
document.addEventListener("click", async event => {
  const button = event.target.closest("button"); if (!button) return;
  if (button.dataset.view) switchView(button.dataset.view);
  if (button.dataset.query) searchWord(button.dataset.query);
  if (button.dataset.entry) selectEntry(button.dataset.entry);
  if (button.dataset.save) toggleSave(button.dataset.save);
  if (button.dataset.mode) {
    state.mode = button.dataset.mode;
    document.querySelectorAll("[data-mode]").forEach(b => { b.classList.toggle("selected", b === button); b.setAttribute("aria-pressed", String(b === button)); });
    search();
  }
  if (button.id === "copy-word" && activeEntry) {
    try { await navigator.clipboard.writeText(activeEntry.word); button.textContent = "已复制"; }
    catch { notice("浏览器未开放剪贴板权限。可以直接选择词语文字进行复制。"); }
  }
  if (button.id === "listen" && activeEntry && localVoice()) {
    speechSynthesis.cancel(); const utterance = new SpeechSynthesisUtterance(activeEntry.word);
    utterance.voice = localVoice(); utterance.lang = "ja-JP"; speechSynthesis.speak(utterance);
  }
});
$("export").addEventListener("click", () => {
  const url = URL.createObjectURL(new Blob([JSON.stringify(learning, null, 2)], {type: "application/json"}));
  const link = document.createElement("a"); link.href = url; link.download = `nichu-learning-${new Date().toISOString().slice(0, 10)}.json`; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
$("import").addEventListener("change", async event => {
  const file = event.target.files[0]; if (!file) return;
  try {
    if (file.size > 2 * 1024 * 1024) throw new Error("文件超过 2 MiB，无法导入。");
    const imported = validateLearning(JSON.parse(await file.text()));
    const rows = new Map(learning.favorites.map(row => [row.id, row]));
    imported.favorites.forEach(row => rows.set(row.id, row));
    learning = validateLearning({version: 1, favorites: [...rows.values()], history: [...new Set([...imported.history, ...learning.history])].slice(0, 100)});
    persist(); if (state.view !== "search") showLocal(); else renderRows(); if (activeEntry) renderDetail(activeEntry);
    notice(`已合并学习记录：${learning.favorites.length} 个收藏。已有记录保留。`);
  } catch (error) { notice(`导入失败：${error.message}`); }
  event.target.value = "";
});

async function init() {
  $("fav-count").textContent = learning.favorites.length;
  try {
    const {stats, manifest, parts_of_speech} = await api("/api/stats");
    $("snapshot-date").textContent = `源快照 · ${manifest.dump_date}`;
    $("corpus-summary").textContent = `${number(stats.headwords)} 个词头 · ${number(stats.senses)} 个义项 · ${number(stats.examples)} 条用例 / 引文`;
    for (const item of parts_of_speech) {
      const option = document.createElement("option"); option.value = item.pos; option.textContent = `${item.title} (${number(item.count)})`; $("pos").append(option);
    }
    if (state.view === "search") {
      $("query").value = new URLSearchParams(location.search).get("q") || "食べる";
      await search();
    }
  } catch (error) { notice(`词库未就绪：${error.message}。请重新启动本地服务。`); $("results").setAttribute("aria-busy", "false"); }
}
init();
