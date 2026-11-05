/* RetailVision AI frontend (vanilla SPA). Real API data only; no mock metrics. */
"use strict";

/* ------------------------------- helpers ------------------------------- */
const $ = (sel, root) => (root || document).querySelector(sel);
const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
function el(tag, attrs = {}, ...children) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") n.className = v;
    else if (k === "html") n.innerHTML = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else if (k === "dataset") Object.assign(n.dataset, v);
    else n.setAttribute(k, v);
  }
  for (const c of [].concat(...children)) if (c != null) n.append(c.nodeType ? c : document.createTextNode(c));
  return n;
}
const apiBase = () => (window.RV_API_BASE || "");
const u = p => apiBase() + p;
const fmtTime = s => { s = Math.max(0, s | 0); return `${String(s / 60 | 0).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`; };
const fmtDur = s => { if (s == null) return "–"; const m = s / 60; return m >= 1 ? `${m.toFixed(1)} min` : `${s.toFixed(0)} s`; };
const fmtBytes = b => b >= 1e6 ? `${(b / 1e6).toFixed(1)} MB` : `${(b / 1e3).toFixed(0)} KB`;
const fmtDate = iso => { if (!iso) return "–"; return iso.replace("T", " ").slice(0, 16); };

async function api(path, opts = {}) {
  const headers = Object.assign({ "Content-Type": "application/json" }, opts.headers || {});
  const token = localStorage.getItem("rv_token");
  if (token) headers["x-auth-token"] = token;
  const res = await fetch(apiBase() + "/api" + path, { ...opts, headers });
  if (res.status === 401 && path !== "/auth/login") { logout(); throw new Error("Session expired"); }
  if (!res.ok) {
    let msg = res.statusText;
    try { msg = (await res.json()).detail || msg; } catch (e) { /* keep */ }
    throw new Error(msg);
  }
  const ct = res.headers.get("content-type") || "";
  return ct.includes("json") ? res.json() : res.text();
}
function upload(url, formData) {
  const headers = {};
  const token = localStorage.getItem("rv_token");
  if (token) headers["x-auth-token"] = token;
  return fetch(apiBase() + "/api" + url, { method: "POST", headers, body: formData }).then(async r => {
    if (!r.ok) { let m = r.statusText; try { m = (await r.json()).detail || m; } catch (e) {} throw new Error(m); }
    return r.json();
  });
}

/* ------------------------------- state ------------------------------- */
let USER = null;
async function loadUser() {
  if (!localStorage.getItem("rv_token")) return;
  try { USER = await api("/auth/me"); } catch (e) { USER = null; }
}
function logout() { localStorage.removeItem("rv_token"); USER = null; location.hash = "#/login"; }

/* ------------------------------- icons ------------------------------- */
const I = {
  overview: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/></svg>',
  stores: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M3 9l1.5-5h15L21 9"/><path d="M3 9a3 3 0 0 0 6 0 3 3 0 0 0 6 0 3 3 0 0 0 6 0"/><path d="M5 12v8h14v-8"/><path d="M9 20v-5h6v5"/></svg>',
  videos: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="5" width="14" height="14" rx="2"/><path d="M16 10l6-3v10l-6-3"/></svg>',
  traffic: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M3 17l5-6 4 3 6-8"/><path d="M16 6h5v5"/></svg>',
  heatmap: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="3"/><circle cx="16" cy="14" r="4"/></svg>',
  incidents: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 8v5"/><circle cx="12" cy="16.5" r=".5" fill="currentColor"/></svg>',
  alerts: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>',
  reports: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M8 13h8M8 17h5"/></svg>',
  model: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="4" y="4" width="16" height="16" rx="2"/><path d="M9 9h6v6H9z"/></svg>',
  settings: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33h0a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51h0a1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82v0a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z"/></svg>',
  audit: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M9 13h6M9 17h4"/></svg>',
  chevron: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M9 18l6-6-6-6"/></svg>',
  upload: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M17 8l-5-5-5 5"/><path d="M12 3v12"/></svg>',
};

/* ------------------------------- nav ------------------------------- */
const NAV = [
  { group: "Overview", items: [{ id: "overview", label: "Overview", icon: I.overview }] },
  { group: "Operations", items: [
    { id: "stores", label: "Stores", icon: I.stores },
    { id: "videos", label: "Videos", icon: I.videos },
  ]},
  { group: "Insights", items: [
    { id: "traffic", label: "Traffic analytics", icon: I.traffic },
    { id: "heatmaps", label: "Heatmaps", icon: I.heatmap },
  ]},
  { group: "Care", items: [
    { id: "incidents", label: "Incident review", icon: I.incidents },
    { id: "alerts", label: "Operational alerts", icon: I.alerts },
  ]},
  { group: "Platform", items: [
    { id: "reports", label: "Reports & export", icon: I.reports },
    { id: "model", label: "Model", icon: I.model },
    { id: "settings", label: "Settings", icon: I.settings },
    { id: "audit", label: "Audit log", icon: I.audit },
  ]},
];
function renderNav() {
  const nav = $("#nav"); nav.innerHTML = "";
  for (const g of NAV) {
    nav.append(el("div", { class: "nav-group" }, g.group));
    for (const item of g.items) {
      const a = el("a", {
        class: "nav-item" + (location.hash === "#/" + item.id ? " active" : ""),
        href: "#/" + item.id, html: item.icon,
      }, [el("span", {}, item.label)]);
      a.addEventListener("click", () => { $("#sidebar").classList.remove("open"); });
      nav.append(a);
    }
  }
}
function setCrumb(parts) {
  const c = $("#breadcrumb"); c.innerHTML = "";
  parts.forEach((p, i) => {
    if (i) c.append(el("span", { class: "crumb" }, " / "));
    if (p.href) c.append(el("a", { href: p.href, class: "crumb" }, p.text));
    else c.append(el("span", { class: "crumb", style: "color:var(--text)" }, p.text));
  });
}
function setTitle(t) { setCrumb([{ text: t }]); }

/* ------------------------------- notifications ------------------------------- */
let NOTIFS = [];
async function refreshNotifs() {
  try { NOTIFS = await api("/notifications"); } catch (e) { NOTIFS = []; }
  $("#bellDot").style.display = NOTIFS.some(n => !n.read) ? "" : "none";
}
function renderBell() {
  const pop = $("#bellPop");
  pop.innerHTML = "";
  pop.append(el("div", { class: "head" }, "Notifications"));
  if (!NOTIFS.length) pop.append(el("div", { class: "item" }, "No notifications yet."));
  for (const n of NOTIFS.slice(0, 10)) {
    const a = el("a", { class: "item", href: n.link || "#/overview" });
    a.append(el("div", { class: "t" }, esc(n.text)), el("div", { class: "s" }, fmtDate(n.created_at)));
    pop.append(a);
  }
  $("#bellBtn").onclick = async e => {
    e.stopPropagation();
    const show = pop.style.display === "none";
    $("#overlay").style.display = show ? "" : "none";
    pop.style.display = show ? "" : "none";
    if (show) { await api("/notifications/read"); refreshNotifs(); }
  };
  $("#overlay").onclick = () => { pop.style.display = "none"; $("#overlay").style.display = "none"; };
}

/* ------------------------------- router ------------------------------- */
const ROUTES = {
  "": overviewView, overview: overviewView,
  login: loginView,
  stores: storesView,
  videos: videosView,
  traffic: trafficView,
  heatmaps: heatmapsView,
  incidents: incidentsView,
  alerts: alertsView,
  reports: reportsView,
  model: modelView,
  settings: settingsView,
  audit: auditView,
};
async function route() {
  renderNav();
  const { 0: seg, 1: id } = decodeURIComponent(location.hash.slice(2)).split("/");
  const view = $("#view");
  view.innerHTML = "";
  if (!USER) {
    if (seg !== "login") { location.hash = "#/login"; return; }
    loginView(view); return;
  }
  if (seg === "login") { location.hash = "#/overview"; return; }
  $("#userChip").innerHTML = "";
  if (seg === "stores" && id) { storeDetailView(view, id); await refreshNotifs(); return; }
  if (seg === "videos" && id) { videoDetailView(view, id); await refreshNotifs(); return; }
  if (seg === "analysis" && id) { analysisView(view, id); await refreshNotifs(); return; }
  $("#userChip").append(
    el("div", { class: "avatar" }, (USER.name || USER.email)[0].toUpperCase()),
    el("div", {}, el("div", { style: "font-weight:600;font-size:13px" }, esc(USER.name || USER.email)),
      el("div", { style: "font-size:11.5px;color:var(--faint);text-transform:capitalize" }, esc(USER.role))),
    el("button", { class: "btn btn-sm", style: "margin-left:6px", onclick: logout }, "Log out"),
  );
  const fn = ROUTES[seg] || nullView;
  try {
    await fn(view, id);
  } catch (e) {
    view.append(el("div", { class: "alert err" }, "Failed to load: " + esc(e.message)));
  }
  refreshNotifs();
}
window.addEventListener("hashchange", route);

/* ------------------------------- login ------------------------------- */
function loginView(view) {
  setTitle("Sign in");
  const card = el("div", { class: "card card-pad", style: "max-width:400px;margin:8vh auto" });
  card.append(
    el("div", { style: "display:flex;gap:10px;align-items:center;margin-bottom:16px" },
      el("div", { class: "brand-mark" }, "R"),
      el("div", {}, el("div", { style: "font-weight:700;font-size:16px" }, "RetailVision AI"),
        el("div", { class: "hint" }, "Retail CCTV intelligence"))),
    el("label", { class: "field" }, [el("span", {}, "Email"), el("input", { class: "input", type: "email", id: "em" })]),
    el("label", { class: "field" }, [el("span", {}, "Password"), el("input", { class: "input", type: "password", id: "pw" })]),
    el("div", { id: "loginErr" }),
    el("button", { class: "btn btn-primary btn-block", id: "go" }, "Sign in"),
    el("div", { class: "hint", style: "margin-top:12px;text-align:center" },
      "New? Use the demo account below or click Register."),
    el("button", { class: "btn btn-block", style: "margin-top:8px", id: "demo" }, "Use demo account"),
  );
  view.append(card);
  const tryLogin = async (email, pw) => {
    $("#loginErr").innerHTML = "";
    try {
      const r = await api("/auth/login", { method: "POST", body: JSON.stringify({ email, password: pw }) });
      localStorage.setItem("rv_token", r.token);
      USER = r.user; location.hash = "#/overview";
    } catch (e) { $("#loginErr").append(el("div", { class: "alert err" }, esc(e.message))); }
  };
  $("#go").onclick = () => tryLogin($("#em").value.trim(), $("#pw").value);
  $("#pw").addEventListener("keydown", e => { if (e.key === "Enter") $("#go").click(); });
  $("#demo").onclick = async () => {
    // Ensure a demo user exists (idempotent) then log in.
    try { await api("/auth/register", { method: "POST", body: JSON.stringify({ email: "demo@retailvision.ai", name: "Demo Analyst", password: "demo1234", role: "analyst" }) }); }
    catch (e) { /* already exists is fine */ }
    await tryLogin("demo@retailvision.ai", "demo1234");
  };
}

/* ------------------------------- shared widgets ------------------------------- */
function stateBox(label, value, sub, cls) {
  return el("div", { class: "stat" },
    el("div", { class: "k" }, label),
    el("div", { class: "v" + (cls ? " " + cls : "") }, value),
    sub ? el("div", { class: "sub" }, sub) : null);
}
function emptyState(icon, title, sub, action) {
  const d = el("div", { class: "empty" }, [el("div", { html: icon }), el("h3", {}, title), el("p", {}, sub)]);
  if (action) d.append(el("div", { style: "margin-top:14px" }, action));
  return d;
}
function loadingState(msg) {
  return el("div", { class: "center-state" }, [el("div", { class: "spin" }), el("span", {}, msg || "Loading…")]);
}
function jobBadge(j) {
  if (!j) return el("span", { class: "badge gray" }, "no job");
  const m = { queued: ["gray", "Queued"], running: ["blue", "Running"], done: ["green", "Done"], failed: ["red", "Failed"] }[j.status] || ["gray", j.status];
  return el("span", { class: "badge " + m[0] + " statusdot " + j.status }, [el("span", { class: "dot" }), m[1]]);
}
function eventBadge(e) {
  const st = { open: ["amber", "Open"], reviewing: ["blue", "Reviewing"], resolved: ["green", "Resolved"], confirmed: ["green", "Confirmed"], dismissed: ["gray", "Dismissed"] }[e.status] || ["gray", e.status];
  return el("span", { class: "badge " + st[0] }, st[1]);
}
function typeBadge(t) {
  const m = { operational: ["amber", "Operational"], security: ["red", "Security"], queue: ["blue", "Queue"], congestion: ["gray", "Congestion"] }[t] || ["gray", t];
  return el("span", { class: "badge " + m[0] }, m[1]);
}
function cardHead(title, sub, actions) {
  const d = el("div", {}, el("div", { class: "card-title" }, title));
  if (sub) d.append(el("div", { class: "card-sub" }, sub));
  const head = el("div", { class: "card-head" }, d);
  if (actions) {
    head.append(el("div", { class: "spacer" }), actions);
  }
  return head;
}
function makeChart(canvas, type, labels, datasets, opts = {}) {
  return new Chart(canvas, { type, data: { labels, datasets }, options: Object.assign({
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { display: false }, tooltip: { backgroundColor: "#0E1B1A" } },
    scales: { x: { grid: { display: false }, ticks: { color: "#98A2B3", maxTicksLimit: 12 } },
             y: { beginAtZero: true, grid: { color: "#EDF0EF" }, ticks: { color: "#98A2B3" } } },
  }, opts) });
}

/* ------------------------------- overview ------------------------------- */
async function overviewView(view) {
  setCrumb([{ text: "Overview" }]);
  view.append(loadingState());
  const [stores, videos, jobs, events, agg] = await Promise.all([
    api("/stores"), api("/videos"), api("/jobs"), api("/events?status=open"), api("/analyses/summary"),
  ]);
  view.innerHTML = "";
  const done = jobs.filter(j => j.status === "done");
  const running = jobs.filter(j => j.status === "running" || j.status === "queued");
  const failed = jobs.filter(j => j.status === "failed");
  const totalDets = agg.analyses.detections || 0;
  const totalVisits = agg.analyses.visits || 0;
  view.append(
    el("div", { style: "display:flex;align-items:center;gap:14px;margin-bottom:18px" },
      el("h1", { style: "margin:0;font-size:20px" }, "Overview"),
      el("div", { class: "hint" }, fmtDate(new Date().toISOString()))),
    el("div", { class: "stat-grid" },
      stateBox("Stores", stores.length, "registered"),
      stateBox("Analyzed videos", done.length, running.length ? `${running.length} in progress` : undefined),
      stateBox("People observed (detections)", totalDets.toLocaleString(), `across ${agg.analyses.analyses} analyses`),
      stateBox("Unique visits (est.)", totalVisits.toLocaleString(), "tracked, within camera limits"),
      stateBox("Open incidents", events.length, "awaiting review")),
    el("div", { class: "card", style: "margin-top:18px" }),
  );
  const card = $(".card:last-child", view);
  card.append(cardHead("Recent activity", "Latest uploads and analysis jobs",
    el("a", { href: "#/videos", class: "btn btn-sm" }, "All videos")));
  if (!videos.length) {
    card.append(emptyState(I.upload, "No videos yet", "Upload a CCTV recording from a store to start analyzing.", el("a", { href: "#/stores", class: "btn btn-primary" }, "Go to stores")));
  } else {
    const table = el("table", { class: "table" });
    table.append(el("thead", {}, el("tr", {}, ["Video", "Store", "Uploaded", "Duration", "Status", ""].map(h => el("th", {}, h)))));
    const tbody = el("tbody");
    for (const v of videos.slice(0, 8)) {
      const j = v.latest_job;
      const tr = el("tr", {},
        el("td", {}, el("a", { href: j && j.analysis ? `#/analysis/${j.analysis}` : `#/videos/${v.id}` }, esc(v.filename))),
        el("td", {}, esc(v.store_name)),
        el("td", {}, fmtDate(v.created_at)),
        el("td", {}, fmtDur(v.duration_s)),
        el("td", {}, jobBadge(j)),
        el("td", {}, j && j.analysis ? el("a", { href: `#/analysis/${j.analysis}`, class: "btn btn-sm" }, "Open analysis") : el("a", { href: `#/videos/${v.id}`, class: "btn btn-sm" }, "Details")),
      );
      tbody.append(tr);
    }
    table.append(tbody);
    card.append(table);
  }
  // failure banner
  if (failed.length) view.append(el("div", { class: "alert err", style: "margin-top:16px" }, `${failed.length} job(s) failed. See the Videos page for details.`));
}

/* ------------------------------- stores ------------------------------- */
async function storesView(view) {
  setCrumb([{ text: "Stores" }]);
  view.append(loadingState());
  const stores = await api("/stores");
  view.innerHTML = "";
  view.append(el("div", { style: "display:flex;gap:12px;align-items:center;margin-bottom:16px" },
    el("h1", { style: "margin:0;font-size:20px;flex:1" }, "Stores"),
    el("button", { class: "btn btn-primary", id: "addStore" }, "+ New store")));
  const grid = el("div", { class: "stat-grid", style: "grid-template-columns:repeat(auto-fill,minmax(280px,1fr))" });
  if (!stores.length) {
    view.append(el("div", { class: "card" }, emptyState(I.stores, "No stores yet", "Create a store to organize cameras and video uploads.")));
  } else {
    for (const s of stores) {
      grid.append(el("div", { class: "card" },
        el("div", { class: "card-pad" },
          el("div", { style: "font-weight:650;font-size:15px" }, esc(s.name)),
          el("div", { class: "hint" }, esc(s.address || "No address")),
          el("div", { style: "display:flex;gap:8px;margin-top:12px;align-items:center" },
            el("span", { class: "badge gray" }, `${s.camera_count} camera(s)`),
            el("div", { class: "spacer", style: "flex:1" }),
            el("a", { href: `#/stores/${s.id}`, class: "btn btn-sm" }, "Open")))));
    }
    view.append(grid);
  }
  $("#addStore").onclick = () => {
    const name = prompt("Store name");
    if (!name) return;
    api("/stores", { method: "POST", body: JSON.stringify({ name }) }).then(() => storesView(view));
  };
}

async function storeDetailView(view, id) {
  setCrumb([{ text: "Stores", href: "#/stores" }, { text: "Store " + id }]);
  view.append(loadingState());
  const [store, cameras, videos] = await Promise.all([
    api("/stores").then(rs => rs.find(r => r.id == id)),
    api(`/stores/${id}/cameras`), api(`/videos?store_id=${id}`),
  ]);
  view.innerHTML = "";
  if (!store) { view.append(el("div", { class: "alert err" }, "Store not found")); return; }
  view.append(el("h1", { style: "margin:0 0 4px;font-size:20px" }, esc(store.name)),
    el("div", { class: "hint", style: "margin-bottom:18px" }, esc(store.address || "No address")));

  // Cameras
  const camCard = el("div", { class: "card", style: "margin-bottom:16px" });
  camCard.append(cardHead("Cameras", "Cameras you plan to analyze footage from",
    el("button", { class: "btn btn-sm", id: "addCam" }, "+ Add camera")));
  camCard.append(el("div", { class: "list" }));
  const camList = $(".list", camCard);
  if (!cameras.length) camList.append(emptyState(null, "No cameras yet", "Add a camera name and location as a reference for uploads."));
  else for (const c of cameras) camList.append(el("div", { class: "list-row" },
    el("div", { style: "flex:1" }, el("div", { style: "font-weight:600" }, esc(c.name)), el("div", { class: "hint" }, esc(c.location || "No location"))),
    el("span", { class: "badge gray" }, "configured")));
  view.append(camCard);

  // Uploads
  const upCard = el("div", { class: "card" });
  upCard.append(cardHead("Upload CCTV recording",
    "MP4 / MOV / AVI, up to 1024 MB. You confirm you are authorized to use this footage.",
    el("a", { href: "#/videos", class: "btn btn-sm" }, "All videos")));
  const body = el("div", { class: "card-pad" });
  body.append(el("div", { class: "dropzone" },
    el("label", { for: "fileInput" },
      el("div", { class: "table" }, el("div", { style: "font-size:15px;font-weight:600;margin-bottom:6px" }, el("span", { style: "color:var(--accent)" }, "Choose a video file"), " or drop it here")),
      el("div", { class: "hint" }, "The clip is stored locally on this machine and never uploaded to third parties.")),
    el("input", { type: "file", id: "fileInput", accept: ".mp4,.mov,.avi" }),
    el("label", { style: "display:flex;gap:8px;justify-content:center;margin-top:14px;align-items:center" },
      el("input", { type: "checkbox", id: "consent", style: "width:16px;height:16px" }),
      el("span", {}, "I am authorized to process this footage")),
    el("div", { id: "upMsg" }),
    el("button", { class: "btn btn-primary", id: "upBtn", style: "margin-top:14px", disabled: true }, el("span", { html: I.upload }), "Upload"),
  ));
  upCard.append(body);
  view.append(upCard);
  $("#fileInput").onchange = () => { $("#upBtn").disabled = !$("#fileInput").files.length; };
  $("#consent").onchange = () => { $("#upBtn").disabled = !($("#consent").checked && $("#fileInput").files.length); };
  $("#upBtn").onclick = async () => {
    const f = $("#fileInput").files[0];
    if (!f) return;
    if (!$("#consent").checked) { $("#upMsg").innerHTML = '<div class="alert err">Please confirm authorization first.</div>'; return; }
    $("#upMsg").innerHTML = '<div class="alert info"><span class="spin"></span> Uploading…</div>';
    const fd = new FormData();
    fd.append("file", f); fd.append("store_id", id); fd.append("consent", "1");
    try {
      const v = await upload("/videos", fd);
      $("#upMsg").innerHTML = `<div class="alert ok">Uploaded. <a href="#/videos/${v.id}">Open video →</a></div>`;
      $("#fileInput").value = ""; $("#consent").checked = false; $("#upBtn").disabled = true;
    } catch (e) { $("#upMsg").innerHTML = `<div class="alert err">${esc(e.message)}</div>`; }
  };
}

/* ------------------------------- videos ------------------------------- */
async function videosView(view) {
  setCrumb([{ text: "Videos" }]);
  view.append(loadingState());
  const [videos, jobs] = await Promise.all([api("/videos"), api("/jobs")]);
  view.innerHTML = "";
  view.append(el("h1", { style: "margin:0 0 14px;font-size:20px" }, "Videos"));
  if (!videos.length) {
    view.append(el("div", { class: "card" }, emptyState(I.videos, "No videos uploaded", "Upload a recording from a store page.", el("a", { href: "#/stores", class: "btn btn-primary" }, "Go to stores"))));
    return;
  }
  const card = el("div", { class: "card" });
  const table = el("table", { class: "table" });
  table.append(el("thead", {}, el("tr", {}, ["Video", "Store", "Size", "Duration", "Resolution", "Jobs", ""].map(h => el("th", {}, h)))));
  const tbody = el("tbody");
  for (const v of videos) {
    const vjobs = jobs.filter(j => j.video_id === v.id);
    const last = vjobs[0];
    const tr = el("tr", {},
      el("td", {}, el("a", { href: `#/videos/${v.id}`, style: "font-weight:600" }, esc(v.filename))),
      el("td", {}, esc(v.store_name)),
      el("td", { class: "num" }, fmtBytes(v.size_bytes)),
      el("td", { class: "num" }, fmtDur(v.duration_s)),
      el("td", { class: "num" }, `${v.width}×${v.height}`),
      el("td", {}, jobBadge(last)),
      el("td", {}, el("a", { href: `#/videos/${v.id}`, class: "btn btn-sm" }, "Open")));
    tbody.append(tr);
  }
  table.append(tbody);
  card.append(table);
  view.append(card);
}

async function videoDetailView(view, id) {
  setCrumb([{ text: "Videos", href: "#/videos" }, { text: "Video " + id }]);
  view.append(loadingState());
  const v = await api(`/videos/${id}`);
  view.innerHTML = "";
  if (!v) { view.append(el("div", { class: "alert err" }, "Video not found")); return; }
  view.append(
    el("h1", { style: "margin:0 0 4px;font-size:20px" }, esc(v.filename)),
    el("div", { class: "hint", style: "margin-bottom:16px" },
      `${esc(v.store_name)} · ${fmtBytes(v.size_bytes)} · ${v.width}×${v.height} · ${fmtDur(v.duration_s)} · uploaded ${fmtDate(v.created_at)}`),
    el("div", { class: "video-wrap" }, el("video", { controls: true, src: u(v.stream_url || `/api/videos/${v.id}/stream`), preload: "metadata" })),
    el("div", { class: "card", style: "margin-top:16px" }),
  );
  const card = $(".card:last-child", view);
  card.append(cardHead("Analysis", "Run a real computer-vision analysis on this recording",
    el("button", { class: "btn btn-primary", id: "analyzeBtn" }, "Analyze video")));
  const stats = el("div", { class: "card-pad" });
  card.append(stats);

  const renderJobs = () => {
    api(`/jobs?video_id=${id}`).then(jobs => {
      stats.innerHTML = "";
      if (!jobs.length) { stats.append(el("div", { class: "hint" }, "No analysis run yet. Configure and start one.")); return; }
      for (const j of jobs) {
        const row = el("div", { class: "list-row" });
        row.append(
          el("div", { style: "flex:1" },
            el("div", { style: "display:flex;gap:10px;align-items:center" }, jobBadge(j), el("span", { style: "font-weight:600" }, `Job #${j.id}`), el("span", { class: "hint" }, `model ${esc(j.model_id || "default")}`)),
            j.status === "running" ? el("div", { class: "progress", style: "margin-top:8px" }, el("div", { style: `width:${j.progress}%` })) : null,
            j.error ? el("div", { class: "alert err", style: "margin-top:8px;margin-bottom:0" }, esc(j.error)) : null),
          el("span", { class: "hint" }, `${j.progress}%`),
          j.status === "done" && j.analysis ? el("a", { href: `#/analysis/${j.analysis}`, class: "btn btn-primary btn-sm" }, "Open analysis") : el("a", { href: `#/videos/${id}?job=${j.id}`, class: "btn btn-sm" }, "Refresh"),
        );
        stats.append(row);
      }
    });
  };
  renderJobs();

  $("#analyzeBtn").onclick = async () => {
    $("#analyzeBtn").disabled = true;
    $("#analyzeBtn").textContent = "Queuing…";
    try {
      const j = await api(`/videos/${id}/analyze`, { method: "POST", body: JSON.stringify({}) });
      stats.innerHTML = "";
      stats.append(el("div", { class: "alert info" }, `Job #${j.id} queued. Processing started.`));
      pollJob(j.id);
    } catch (e) { alert(e.message); $("#analyzeBtn").disabled = false; $("#analyzeBtn").textContent = "Analyze video"; }
  };

  function pollJob(jobId) {
    const timer = setInterval(async () => {
      try {
        const j = await api(`/jobs/${jobId}`);
        renderJobs();
        if (j.status === "done" || j.status === "failed") {
          clearInterval(timer);
          $("#analyzeBtn").disabled = false;
          $("#analyzeBtn").textContent = "Analyze video";
          if (j.status === "done" && j.analysis) location.hash = `#/analysis/${j.analysis}`;
        }
      } catch (e) { clearInterval(timer); }
    }, 1500);
  }
  // initial poll if last job is running
  const last = await api(`/jobs?video_id=${id}`);
  if (last[0] && (last[0].status === "running" || last[0].status === "queued")) pollJob(last[0].id);
}

/* ------------------------------- analysis ------------------------------- */
async function analysisView(view, id) {
  setCrumb([{ text: "Videos", href: "#/videos" }, { text: "Analysis " + id }]);
  view.append(loadingState());
  const data = await api(`/analyses/${id}`);
  view.innerHTML = "";
  const a = data.analysis, v = data.video, events = data.events;
  view.append(...[
    el("h1", { style: "margin:0 0 4px;font-size:20px" }, `Analysis #${a.id}`),
    el("div", { class: "hint", style: "margin-bottom:16px" },
      `${esc(v.filename)} · ${esc(v.store_name)} · model ${esc(a.model_id)} on ${esc(a.inference_device)} · ${a.processed_frames} frames sampled · ${a.inference_ms_avg} ms/frame`),
    (a.scene && a.scene.moving_camera
      ? el("div", { class: "alert info", style: "margin-bottom:14px" },
          "Heads up: camera motion detected in this footage, so counts and tracking may be unreliable.")
      : null),
    (a.scene && a.scene.mosaic
      ? el("div", { class: "alert info", style: "margin-bottom:14px" },
          `Camera wall detected: ${a.scene.mosaic.rows}x${a.scene.mosaic.cols} grid ` +
          `(${a.scene.mosaic.cameras} cameras, each about ` +
          `${Math.round((v.width || 640) / a.scene.mosaic.cols)}x` +
          `${Math.round((v.height || 360) / a.scene.mosaic.rows)}px in this recording). ` +
          `Analysis ran per camera; a person moving between cameras cannot be re-identified, ` +
          `so visit counts are per camera and never summed across them.` +
          (a.scene.sample_interval_s ? ` Sampled every ${a.scene.sample_interval_s}s.` : ""))
      : null),
    (a.scene && a.scene.blob_events_suppressed
      ? el("div", { class: "alert info", style: "margin-bottom:14px" },
          `Object and debris detection was disabled for this clip: ` +
          `${Math.round((a.scene.blob_events_suppressed.busy_frame_ratio || 0) * 100)}% of ` +
          `frames were crowded, where background subtraction cannot tell a dropped ` +
          `object from a passing crowd. Queue and occupancy results are unaffected.`)
      : null),
    (a.scene && a.scene.track_quality && a.scene.track_quality.short_track_ratio > 0.35
      ? el("div", { class: "alert warn", style: "margin-bottom:14px" },
          `Data quality note: ${Math.round(a.scene.track_quality.short_track_ratio * 100)}% of ` +
          `tracks were shorter than a few samples, so visit counts are inflated. ` +
          `Read them as relative activity per camera, not as a headcount. ` +
          `Re-run with a smaller sampling interval for tighter tracks.`)
      : null),
    el("div", { class: "stat-grid", style: "margin-bottom:16px" },
      stateBox("People observed (detections)", a.total_detections.toLocaleString(), "sum of sampled frames"),
      stateBox("Unique visits (est.)", a.unique_visits_est ?? "–", "tracked persons, within camera limits"),
      stateBox("Avg occupancy", a.avg_occupancy, "people per sampled frame"),
      stateBox("Peak occupancy", a.max_occupancy, "simultaneous people"),
      stateBox("Avg dwell", fmtDur(a.dwell_avg_s), "per observed person"),
      stateBox("Dwell median", fmtDur(a.dwell_p50_s), "per observed person")),
    (a.per_camera && a.per_camera.length
      ? el("div", { class: "card", style: "margin-bottom:16px" },
          cardHead("Per-camera visits", "each tile treated as a separate scene"),
          el("div", { class: "stat-grid", style: "grid-template-columns:repeat(8,1fr);padding:14px" },
            ...a.per_camera.map((c) => el("div", {},
              el("div", { class: "hint", style: "font-size:11px" }, c.camera),
              el("div", { style: "font-size:16px;font-weight:600" }, String(c.visits_est))))))
      : null),
    el("div", { class: "layout-2col" }),
  ].filter(Boolean));
  const col = $(".layout-2col", view);

  // Left column
  const left = el("div");
  left.append(
    el("div", { class: "card" },
      el("div", { class: "video-wrap" }, el("video", { id: "anVideo", controls: true, src: u(v.stream_url || `/api/videos/${v.id}/stream`), preload: "metadata" })),
      el("div", { class: "timeline" },
        el("span", { class: "tl-label" }, "0:00"),
        el("div", { class: "timeline-track", id: "tl" }),
        el("span", { class: "tl-label" }, fmtTime(v.duration_s)))),
    el("div", { class: "card", style: "margin-top:16px" },
      cardHead("Heatmap", "From tracked positions, real data"),
      el("div", { class: "img-frame", style: "margin:14px" }, el("img", { src: u(`/api/analyses/${id}/heatmap`), alt: "Heatmap" }))),
    el("div", { class: "card", style: "margin-top:16px" },
      cardHead("Reference frame", "First analyzed frame"),
      el("div", { class: "img-frame", style: "margin:14px" }, el("img", { src: u(`/api/analyses/${id}/reference`), alt: "Reference frame" }))),
  );
  // Right column
  const right = el("div");
  right.append(
    el("div", { class: "card" },
      cardHead("Traffic per minute", "estimated visit starts"),
      el("div", { style: "height:180px;padding:12px" }, el("canvas", { id: "trafficChart" }))),
    el("div", { class: "card", style: "margin-top:16px" },
      cardHead("Events", `${events.length} in this analysis`),
      el("div", { class: "list", id: "eventList" })),
    el("div", { class: "card", style: "margin-top:16px" }, [
      el("div", { class: "card-head" },
        el("div", {}, el("div", { class: "card-title" }, "Export"))),
      el("div", { class: "card-pad", style: "display:flex;gap:10px" },
        el("a", { href: u(`/api/analyses/${id}/report.csv`), class: "btn", target: "_blank" }, "Download CSV"),
        el("a", { href: u(`/api/analyses/${id}/report.json`), class: "btn", target: "_blank" }, "Download JSON")),
    ]),
  );
  col.append(left, right);

  // traffic chart
  const series = a.traffic_series || [];
  try {
    makeChart($("#trafficChart"), "line", series.map(s => s.label), [{
      data: series.map(s => s.visits), borderColor: "#0B6B55", backgroundColor: "#0B6B5522",
      fill: true, tension: .3, pointRadius: 3, borderWidth: 2,
    }]);
  } catch (e) { /* chart.js off */ }

  // timeline markers
  const tl = $("#tl");
  for (const e of events) {
    const pct = Math.min(100, Math.max(0, e.ts_s / v.duration_s * 100));
    tl.append(el("div", { class: "marker " + e.type, style: `left:${pct}%`, title: `${e.label} @ ${fmtTime(e.ts_s)}` }));
  }

  // event list
  const list = $("#eventList");
  if (!events.length) list.append(el("div", { class: "empty" }, el("p", {}, "No events detected in this analysis.")));
  else for (const e of events) {
    const row = el("div", { class: "list-row", style: "align-items:flex-start" });
    row.append(
      el("div", { style: "flex:1;min-width:0" },
        el("div", { style: "display:flex;gap:8px;align-items:center;flex-wrap:wrap" },
          typeBadge(e.type), el("span", { style: "font-weight:600" }, esc(e.label)), eventBadge(e), el("span", { class: "hint" }, fmtTime(e.ts_s))),
        el("div", { class: "hint", style: "margin-top:2px" }, `confidence ${Math.round((e.confidence ?? 0.5) * 100)}%`),
        e.thumb_path ? el("img", { src: u(`/api/events/${e.id}/thumb`), alt: "event frame", style: "width:120px;margin-top:6px;border-radius:6px;border:1px solid var(--line)" }) : null),
      el("button", { class: "btn btn-sm", onclick: () => { const vid = $("#anVideo"); if (vid) vid.currentTime = e.ts_s; vid && vid.play(); } }, "Jump"),
    );
    list.append(row);
  }
}

/* ------------------------------- traffic ------------------------------- */
async function trafficView(view) {
  setCrumb([{ text: "Traffic analytics" }]);
  view.append(loadingState());
  const analyses = await api("/jobs").then(jobs => Promise.all(
    jobs.filter(j => j.status === "done" && j.analysis).slice(0, 10).map(j => api(`/analyses/${j.analysis}`))));
  view.innerHTML = "";
  if (!analyses.length) {
    view.append(el("div", { class: "card" }, emptyState(I.traffic, "No completed analyses", "Run an analysis on a video to see traffic metrics.")));
    return;
  }
  const latest = analyses[0];
  const a = latest.analysis, s = a.traffic_series || [];
  view.append(
    el("h1", { style: "margin:0 0 14px;font-size:20px" }, "Traffic analytics"),
    el("div", { class: "card" },
      cardHead(`Analysis #${a.id} · ${esc(latest.video.filename)}`, "Latest completed analysis",
        el("a", { href: `#/analysis/${a.id}`, class: "btn btn-sm" }, "Open analysis")),
      el("div", { style: "height:260px;padding:16px" }, el("canvas", { id: "tChart" }))),
    el("div", { class: "card", style: "margin-top:16px" },
      cardHead("Busy periods", "minutes above the average visit rate"),
      el("div", { class: "list" })),
  );
  try {
    makeChart($("#tChart"), "line", s.map(x => x.label), [{
      data: s.map(x => x.visits), borderColor: "#0B6B55", backgroundColor: "#0B6B5522", fill: true, tension: .3, borderWidth: 2,
    }]);
  } catch (e) {}
  const list = $(".card:last-child .list", view);
  if (!a.busy_periods.length) list.append(el("div", { class: "empty" }, el("p", {}, "No busy periods flagged for this analysis.")));
  else for (const b of a.busy_periods) list.append(el("div", { class: "list-row" },
    el("span", { style: "font-weight:600" }, esc(b.label)),
    el("span", { class: "badge amber" }, `${b.minutes} min`)));
}

/* ------------------------------- heatmaps ------------------------------- */
async function heatmapsView(view) {
  setCrumb([{ text: "Heatmaps" }]);
  view.append(loadingState());
  const jobs = await api("/jobs");
  const done = jobs.filter(j => j.status === "done" && j.analysis);
  view.innerHTML = "";
  view.append(el("h1", { style: "margin:0 0 14px;font-size:20px" }, "Heatmaps"));
  if (!done.length) {
    view.append(el("div", { class: "card" }, emptyState(I.heatmap, "No heatmaps yet", "Heatmaps are generated from real tracking data after an analysis.")));
    return;
  }
  const grid = el("div", { class: "hm-grid" });
  for (const j of done) {
    const a = await api(`/analyses/${j.analysis}`);
    grid.append(el("div", { class: "card hm-card" },
      el("div", { class: "img-frame" }, el("img", { src: u(`/api/analyses/${j.analysis}/heatmap`), alt: "heatmap", loading: "lazy", width: "640", height: "360" })),
      el("div", { class: "card-pad" },
        el("div", { style: "font-weight:600" }, esc(a.video.filename)),
        el("div", { class: "hint" }, `Analysis #${a.analysis.id} · ${a.analysis.unique_visits_est ?? 0} visit estimate`),
        el("a", { href: `#/analysis/${j.analysis}`, class: "btn btn-sm", style: "margin-top:8px" }, "Open analysis"))));
  }
  view.append(grid);
}

/* ------------------------------- incidents / alerts ------------------------------- */
async function incidentsView(view) {
  setCrumb([{ text: "Incident review" }]);
  reviewListView(view, "security", "Incident review");
}
async function alertsView(view) {
  setCrumb([{ text: "Operational alerts" }]);
  reviewListView(view, "operational", "Operational alerts");
}
async function reviewListView(view, type, title) {
  view.append(loadingState());
  const events = await api(`/events?type=${type}`);
  view.innerHTML = "";
  view.append(
    el("h1", { style: "margin:0 0 4px;font-size:20px" }, title),
    el("div", { class: "hint", style: "margin-bottom:14px" },
      type === "security" ? "Neutral observations requiring human review. Nothing here is an accusation." : "Experimental detectors flag possible issues. Always verify manually."),
    el("div", { class: "card" }),
  );
  const card = $(".card:last-child", view);
  if (!events.length) {
    card.append(emptyState(null, "Nothing to review", "No " + type + " events recorded yet."));
    return;
  }
  card.append(el("div", { class: "filters" },
    el("select", { class: "input", id: "statusFilter" },
      ["all", "open", "reviewing", "resolved", "confirmed", "dismissed"].map(s => el("option", { value: s }, s === "all" ? "All statuses" : s[0].toUpperCase() + s.slice(1)))),
    el("label", { style: "font-size:12.5px;color:var(--muted)" }, el("input", { type: "checkbox", id: "mineOnly", style: "margin-right:6px" }), "Unreviewed only")));
  const list = el("div", { class: "list" });
  card.append(list);
  const render = () => {
    list.innerHTML = "";
    let evs = events;
    const st = $("#statusFilter").value;
    if (st !== "all") evs = evs.filter(e => e.status === st);
    if ($("#mineOnly").checked) evs = evs.filter(e => e.status === "open" || e.status === "reviewing");
    if (!evs.length) { list.append(el("div", { class: "empty" }, el("p", {}, "No events match the filter."))); return; }
    for (const e of evs) {
      const row = el("div", { class: "list-row", style: "align-items:flex-start;flex-wrap:wrap" });
      const leftWrap = el("div", { style: "flex:1;min-width:280px" });
      leftWrap.append(
        el("div", { style: "display:flex;gap:8px;align-items:center;flex-wrap:wrap" },
          typeBadge(e.type),
          el("span", { style: "font-weight:600" }, esc(e.label)),
          eventBadge(e),
          el("span", { class: "hint" }, `${esc(e.filename)} · ${fmtTime(e.ts_s)}`)),
        el("div", { class: "hint", style: "margin-top:4px" }, `confidence ${Math.round((e.confidence ?? 0.5) * 100)}% · analysis #${e.analysis_id}`),
        e.thumb_path ? el("img", { src: u(`/api/events/${e.id}/thumb`), alt: "event frame", style: "width:140px;margin-top:8px;border-radius:6px;border:1px solid var(--line)" }) : null,
        el("div", { style: "margin-top:8px;width:100%" },
          el("select", { class: "input", style: "width:auto;margin-right:8px", dataset: { evid: e.id } },
            ["open", "reviewing", "resolved", "confirmed", "dismissed"].map(s => el("option", { value: s, selected: e.status === s ? "" : null }, s[0].toUpperCase() + s.slice(1)))),
          el("input", { class: "input", style: "width:auto;min-width:260px;margin-right:8px", placeholder: "Reviewer note…", value: e.reviewer_notes || "", dataset: { evid: e.id } }),
          el("button", { class: "btn btn-sm btn-primary", dataset: { evid: e.id }, onclick: async ev => {
            const sel = $(`select[data-evid="${e.id}"]`, row), note = $(`input[data-evid="${e.id}"]`, row);
            try {
              await api(`/events/${e.id}`, { method: "PATCH", body: JSON.stringify({ status: sel.value, reviewer_notes: note.value }) });
              e.status = sel.value; e.reviewer_notes = note.value; render();
            } catch (err) { alert(err.message); }
          } }, "Save"),
          el("button", { class: "btn btn-sm", style: "margin-left:6px", onclick: () => {
            api("/feedback", { method: "POST", body: JSON.stringify({
              event_id: e.id, label_original: e.label,
              label_corrected: prompt("Correct the label (model feedback):", e.label) || e.label,
              video_time: e.ts_s, model_id: e.model_id || null }) }).then(() => alert("Feedback saved to the model dataset."));
          } }, "Feedback")));
      row.append(leftWrap, el("a", { href: `#/analysis/${e.analysis_id}`, class: "btn btn-sm" }, "Open analysis"));
      list.append(row);
    }
  };
  if ($("#statusFilter")) $("#statusFilter").onchange = render;
  if ($("#mineOnly")) $("#mineOnly").onchange = render;
  render();
}

/* ------------------------------- reports ------------------------------- */
async function reportsView(view) {
  setCrumb([{ text: "Reports & export" }]);
  view.append(loadingState());
  const jobs = await api("/jobs");
  const done = jobs.filter(j => j.status === "done" && j.analysis);
  view.innerHTML = "";
  view.append(
    el("h1", { style: "margin:0 0 4px;font-size:20px" }, "Reports & export"),
    el("div", { class: "hint", style: "margin-bottom:14px" }, "Export analysis results as CSV or JSON. Reports contain only real measured data."),
    el("div", { class: "card" }),
  );
  const card = $(".card:last-child", view);
  if (!done.length) {
    card.append(emptyState(I.reports, "No reports available", "Complete an analysis first."));
    return;
  }
  const table = el("table", { class: "table" });
  table.append(el("thead", {}, el("tr", {}, ["Analysis", "Video", "Visits est.", "Events", ""].map(h => el("th", {}, h)))));
  const tbody = el("tbody");
  for (const j of done) {
    const a = await api(`/analyses/${j.analysis}`);
    tbody.append(el("tr", {},
      el("td", {}, `#${a.analysis.id}`),
      el("td", {}, esc(a.video.filename)),
      el("td", { class: "num" }, a.analysis.unique_visits_est ?? "–"),
      el("td", { class: "num" }, a.events.length),
      el("td", {}, el("div", { style: "display:flex;gap:8px" },
        el("a", { href: u(`/api/analyses/${j.analysis}/report.csv`), class: "btn btn-sm", target: "_blank" }, "CSV"),
        el("a", { href: u(`/api/analyses/${j.analysis}/report.json`), class: "btn btn-sm", target: "_blank" }, "JSON")))));
  }
  table.append(tbody);
  card.append(table);
}

/* ------------------------------- model ------------------------------- */
async function modelView(view) {
  setCrumb([{ text: "Model" }]);
  view.append(loadingState());
  const [models, feedback] = await Promise.all([api("/models"), api("/feedback")]);
  view.innerHTML = "";
  const active = models.active || {};
  view.append(
    el("h1", { style: "margin:0 0 14px;font-size:20px" }, "Model"),
    el("div", { class: "stat-grid", style: "margin-bottom:16px" },
      stateBox("Active model", esc(active.display_name || "none"), esc(active.model_id || "")),
      stateBox("Inference device", esc(active.device || "not run yet"), "cuda or cpu"),
      stateBox("Reviewed examples", feedback.length, "model feedback dataset"),
      stateBox("Training", "not active", "laptop prototype only")),
    el("div", { class: "card", style: "margin-bottom:16px" },
      cardHead("Available detectors", "Chosen at analysis time; last used config shown"),
      el("div", { class: "card-pad" }),
    ),
    el("div", { class: "card" },
      cardHead("Feedback dataset", "Corrected labels collected by reviewers, ready for future training"),
      el("div", { class: "list" })),
  );
  const pad = $(".card-pad", view);
  for (const [mid, m] of Object.entries(models.registry)) {
    const isActive = active.model_id === mid;
    pad.append(el("div", { class: "list-row" },
      el("div", { style: "flex:1" },
        el("div", { style: "font-weight:600" }, `${esc(m.display)} ${isActive ? el("span", { class: "badge green" }, "selected") : ""}`),
        el("div", { class: "hint" }, `id ${esc(mid)} · v${esc(m.version)} · ${esc(m.license)}`)),
      el("button", { class: "btn btn-sm" + (isActive ? "" : " btn-primary"), disabled: isActive, onclick: () => { api("/models/active", { method: "PATCH", body: JSON.stringify({ model_id: mid }) }).then(() => modelView(view)); } }, isActive ? "Active" : "Set default")));
  }
  const list = $(".card:last-child .list", view);
  if (!feedback.length) list.append(el("div", { class: "empty" }, el("p", {}, "No reviewer feedback collected yet.")));
  else for (const f of feedback) list.append(el("div", { class: "list-row" },
    el("div", { style: "flex:1" },
      el("div", { style: "font-weight:600" }, `${esc(f.label_original)} → ${esc(f.label_corrected)}`),
      el("div", { class: "hint" }, `by ${esc(f.reviewer_name)} · ${fmtDate(f.created_at)} · ${f.included_in_dataset ? "in dataset" : "not yet in dataset"}`)),
    el("span", { class: "badge gray" }, f.model_id || "?")));
}

/* ------------------------------- settings ------------------------------- */
async function settingsView(view) {
  setCrumb([{ text: "Settings" }]);
  view.append(loadingState());
  const settings = await api("/settings");
  view.innerHTML = "";
  view.append(
    el("h1", { style: "margin:0 0 14px;font-size:20px" }, "Settings"),
    el("div", { class: "card" },
      cardHead("Organization", "Shown in exported reports"),
      el("div", { class: "card-pad" },
        el("label", { class: "field" }, [el("span", {}, "Organization display name"), el("input", { class: "input", id: "org", value: settings.org_name || "RetailVision Demo" })]),
        el("label", { class: "field" }, [el("span", {}, "Data retention note (text)"), el("textarea", { class: "input", id: "ret", rows: 3 }, settings.retention_note || "Footage is stored locally. In production, retention is configurable and deletion is guaranteed on request.")]),
        el("button", { class: "btn btn-primary", id: "save" }, "Save settings"))),
    el("div", { class: "card", style: "margin-top:16px" },
      cardHead("Privacy position", "What this system does and does not do"),
      el("div", { class: "card-pad" },
        el("ul", { style: "margin:0;padding-left:18px;color:var(--muted)" },
          ["No facial recognition, no biometric identification, no demographic profiling.",
           "Temporary anonymous tracking IDs only; no cross-camera identity matching.",
           "Event thumbnails exist only for human review.",
           "The local prototype is not claimed to be DPDP-compliant; legal review is required before commercial deployment in India."].map(t => el("li", {}, t))))),
  );
  $("#save").onclick = async () => {
    await api("/settings", { method: "PATCH", body: JSON.stringify({ org_name: $("#org").value, retention_note: $("#ret").value }) });
    alert("Settings saved.");
  };
}

/* ------------------------------- audit ------------------------------- */
async function auditView(view) {
  setCrumb([{ text: "Audit log" }]);
  view.append(loadingState());
  const rows = await api("/audit");
  view.innerHTML = "";
  view.append(el("h1", { style: "margin:0 0 14px;font-size:20px" }, "Audit log"));
  const card = el("div", { class: "card" });
  if (!rows.length) { card.append(emptyState(null, "No audit entries", "Actions will appear here.")); view.append(card); return; }
  const table = el("table", { class: "table" });
  table.append(el("thead", {}, el("tr", {}, ["When", "User", "Action", "Resource", "Detail"].map(h => el("th", {}, h)))));
  const tbody = el("tbody");
  for (const r of rows) tbody.append(el("tr", {},
    el("td", {}, fmtDate(r.created_at)),
    el("td", {}, esc(r.user_name || "system")),
    el("td", {}, el("span", { class: "badge gray" }, esc(r.action))),
    el("td", {}, esc(r.resource || "")),
    el("td", {}, el("span", { class: "mono" }, esc(r.detail || "")))));
  table.append(tbody);
  card.append(table);
  view.append(card);
}

/* ------------------------------- null view ------------------------------- */
function nullView(view) {
  setTitle("Not found");
  view.append(el("div", { class: "card" }, emptyState(null, "Page not found", "This section does not exist.")));
}

/* ------------------------------- init ------------------------------- */
(async function init() {
  renderNav();
  renderBell();
  await loadUser();
  if (!location.hash || location.hash === "#/") location.hash = "#/overview";
  route();
})();
