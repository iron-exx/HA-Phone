"""
Wallbox Billing — HA Addon Web Dashboard HTML

Self-contained single-page dashboard served at GET /
Polls /api/status, /api/sessions, /dead-letter/list every 30s.
No external CDN dependencies.
"""

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Wallbox Billing</title>
<style>
/* ============================================================
   Wallbox Billing Dashboard — Dark Theme
   Design: IoT Monitoring · OLED Dark · Indigo/Emerald
   ============================================================ */

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg:        #0F172A;
  --surface:   #1E293B;
  --surface2:  #263348;
  --border:    #334155;
  --border2:   #1E293B;
  --text:      #F1F5F9;
  --muted:     #94A3B8;
  --primary:   #6366F1;
  --primary-d: #4F46E5;
  --success:   #22C55E;
  --success-d: #16A34A;
  --warn:      #F59E0B;
  --error:     #EF4444;
  --purple:    #A855F7;
}

html, body {
  background: var(--bg);
  color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, 'Inter', 'Segoe UI', sans-serif;
  font-size: 14px;
  line-height: 1.5;
  min-height: 100vh;
}

/* ---- Header ---- */
.header {
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  padding: 0 20px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  position: sticky;
  top: 0;
  z-index: 50;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.header-logo {
  width: 32px; height: 32px;
  background: linear-gradient(135deg, var(--primary), #818CF8);
  border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.header-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--text);
  letter-spacing: -0.01em;
}
.header-sub {
  font-size: 11.5px;
  color: var(--muted);
}
.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}
.status-dot {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 12.5px;
  font-weight: 500;
}
.dot {
  width: 8px; height: 8px;
  border-radius: 50%;
  background: var(--muted);
  flex-shrink: 0;
}
.dot-ok     { background: var(--success); box-shadow: 0 0 0 3px rgba(34,197,94,.2); }
.dot-err    { background: var(--error);   box-shadow: 0 0 0 3px rgba(239,68,68,.2); }
.dot-warn   { background: var(--warn);    box-shadow: 0 0 0 3px rgba(245,158,11,.2); }
.dot-pulse  { animation: pulse-dot 2s ease infinite; }
@keyframes pulse-dot {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
.refresh-btn {
  display: flex; align-items: center; gap: 6px;
  padding: 6px 12px;
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--muted);
  font-size: 12px;
  cursor: pointer;
  transition: all 150ms ease;
  white-space: nowrap;
}
.refresh-btn:hover { color: var(--text); border-color: var(--primary); }
.refresh-btn:focus { outline: 2px solid var(--primary); outline-offset: 2px; }
.refresh-btn.spinning svg { animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.refresh-meta {
  font-size: 11.5px;
  color: var(--muted);
  white-space: nowrap;
}
.countdown {
  display: inline-block;
  font-variant-numeric: tabular-nums;
  min-width: 16px;
}

/* ---- Main layout ---- */
.main { padding: 20px; max-width: 1200px; margin: 0 auto; }

/* ---- Stat cards ---- */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 20px;
}
@media (max-width: 900px) { .stats-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 480px) { .stats-grid { grid-template-columns: 1fr 1fr; } }

.stat-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 16px 18px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  transition: border-color 150ms ease;
}
.stat-card:hover { border-color: #475569; }
.stat-label {
  font-size: 11.5px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: .06em;
  color: var(--muted);
  display: flex;
  align-items: center;
  gap: 7px;
}
.stat-value {
  font-size: 28px;
  font-weight: 700;
  letter-spacing: -0.02em;
  line-height: 1;
  color: var(--text);
  font-variant-numeric: tabular-nums;
}
.stat-sub {
  font-size: 11.5px;
  color: var(--muted);
}
.stat-card-ok     { border-left: 3px solid var(--success); }
.stat-card-err    { border-left: 3px solid var(--error); }
.stat-card-warn   { border-left: 3px solid var(--warn); }
.stat-card-purple { border-left: 3px solid var(--purple); }
.stat-card-blue   { border-left: 3px solid var(--primary); }

/* ---- Section ---- */
.section {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  margin-bottom: 16px;
  overflow: hidden;
}
.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  border-bottom: 1px solid var(--border);
}
.section-title {
  font-size: 13.5px;
  font-weight: 700;
  color: var(--text);
  display: flex;
  align-items: center;
  gap: 8px;
}
.section-badge {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 20px; height: 20px; padding: 0 6px;
  border-radius: 10px;
  background: var(--surface2);
  color: var(--muted);
  font-size: 11px;
  font-weight: 700;
}
.section-badge-err  { background: rgba(239,68,68,.15);  color: var(--error); }
.section-badge-ok   { background: rgba(34,197,94,.15);  color: var(--success); }

/* ---- Table ---- */
.table-wrap { overflow-x: auto; }
.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  white-space: nowrap;
}
.data-table thead th {
  padding: 10px 16px;
  text-align: left;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .06em;
  color: var(--muted);
  border-bottom: 1px solid var(--border);
  background: var(--surface);
}
.data-table tbody tr {
  border-bottom: 1px solid var(--border2);
  transition: background 100ms ease;
}
.data-table tbody tr:hover { background: var(--surface2); }
.data-table tbody tr:last-child { border-bottom: none; }
.data-table td {
  padding: 10px 16px;
  color: var(--text);
  vertical-align: middle;
}
.td-mono { font-family: 'SF Mono', 'Fira Code', monospace; font-size: 12px; color: var(--muted); }
.td-num  { font-variant-numeric: tabular-nums; }

/* ---- Status badges ---- */
.badge {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 3px 8px; border-radius: 20px;
  font-size: 11px; font-weight: 700; letter-spacing: .02em;
  white-space: nowrap;
}
.badge::before {
  content: ""; display: inline-block;
  width: 5px; height: 5px; border-radius: 50%; background: currentColor;
}
.badge-ok         { background: rgba(34,197,94,.12);  color: #4ADE80; }
.badge-error      { background: rgba(239,68,68,.12);  color: #F87171; }
.badge-dead_letter{ background: rgba(168,85,247,.12); color: #C084FC; }
.badge-pending    { background: rgba(245,158,11,.12); color: #FCD34D; }
.badge-neutral    { background: rgba(148,163,184,.1); color: var(--muted); }

/* ---- Error text ---- */
.err-text {
  font-size: 11.5px;
  font-family: 'SF Mono', 'Fira Code', monospace;
  color: #F87171;
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: block;
}

/* ---- Retry count pill ---- */
.pill {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 22px; height: 22px; padding: 0 6px; border-radius: 11px;
  font-size: 11px; font-weight: 700;
  background: var(--surface2); color: var(--muted);
}
.pill-hi { background: rgba(239,68,68,.15); color: #F87171; }

/* ---- Action buttons ---- */
.btn {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 5px 11px; border-radius: 6px;
  font-size: 12px; font-weight: 500; cursor: pointer;
  border: 1px solid transparent;
  transition: all 150ms ease;
  white-space: nowrap;
}
.btn:focus { outline: 2px solid var(--primary); outline-offset: 2px; }
.btn-retry {
  background: rgba(99,102,241,.12);
  color: #818CF8;
  border-color: rgba(99,102,241,.25);
}
.btn-retry:hover {
  background: rgba(99,102,241,.2);
  border-color: rgba(99,102,241,.4);
}
.btn-retry:disabled {
  opacity: .45;
  cursor: not-allowed;
}
.btn-retry.loading svg { animation: spin 0.8s linear infinite; }

/* ---- Empty state ---- */
.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 40px 20px;
  color: var(--muted);
  font-size: 13px;
  gap: 10px;
}
.empty svg { opacity: .35; }

/* ---- Toast notifications ---- */
#toast-container {
  position: fixed;
  bottom: 20px; right: 20px;
  z-index: 100;
  display: flex;
  flex-direction: column;
  gap: 8px;
  pointer-events: none;
}
.toast {
  display: flex; align-items: center; gap: 10px;
  padding: 12px 16px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  pointer-events: all;
  animation: slide-in 200ms ease;
  max-width: 320px;
}
@keyframes slide-in { from { transform: translateX(20px); opacity: 0; } }
.toast-ok  { background: #1A2E1E; border: 1px solid #166534; color: #4ADE80; }
.toast-err { background: #2C1515; border: 1px solid #991B1B; color: #F87171; }

/* Scrollbar styling */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }

@media (prefers-reduced-motion: reduce) {
  *, .dot-pulse, .refresh-btn.spinning svg, .btn-retry.loading svg { animation: none !important; }
}
</style>
</head>
<body>

<!-- Header -->
<header class="header">
  <div class="header-left">
    <div class="header-logo" aria-hidden="true">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
      </svg>
    </div>
    <div>
      <div class="header-title">Wallbox Billing</div>
      <div class="header-sub">Home Assistant Addon</div>
    </div>
  </div>
  <div class="header-right">
    <div class="status-dot" id="api-status-indicator">
      <span class="dot dot-pulse" id="api-dot"></span>
      <span id="api-label">Verbinde…</span>
    </div>
    <span class="refresh-meta">
      Refresh in <span class="countdown" id="countdown">30</span>s
    </span>
    <button class="refresh-btn" id="refresh-btn" aria-label="Jetzt aktualisieren">
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-3.5"/>
      </svg>
      Aktualisieren
    </button>
  </div>
</header>

<!-- Main -->
<main class="main">

  <!-- Stat cards -->
  <div class="stats-grid" id="stats-grid">
    <div class="stat-card stat-card-blue">
      <div class="stat-label">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
        Sessions gesamt
      </div>
      <div class="stat-value" id="stat-total">—</div>
      <div class="stat-sub">abgeschlossene Ladevorgänge</div>
    </div>
    <div class="stat-card stat-card-ok">
      <div class="stat-label">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
        Übertragen
      </div>
      <div class="stat-value" id="stat-ok">—</div>
      <div class="stat-sub">erfolgreich an Dolibarr</div>
    </div>
    <div class="stat-card stat-card-err">
      <div class="stat-label">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
        Fehlgeschlagen
      </div>
      <div class="stat-value" id="stat-failed">—</div>
      <div class="stat-sub">error + dead-letter</div>
    </div>
    <div class="stat-card stat-card-purple">
      <div class="stat-label">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-3.5"/></svg>
        Ausstehend
      </div>
      <div class="stat-value" id="stat-dl">—</div>
      <div class="stat-sub">Dead-letter (retry nötig)</div>
    </div>
  </div>

  <!-- Recent Sessions -->
  <div class="section">
    <div class="section-head">
      <div class="section-title">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"/></svg>
        Letzte Ladevorgänge
        <span class="section-badge" id="sessions-count">0</span>
      </div>
    </div>
    <div class="table-wrap">
      <table class="data-table" aria-label="Letzte Ladevorgänge">
        <thead>
          <tr>
            <th>Datum / Zeit</th>
            <th>Wallbox-ID</th>
            <th>Energie</th>
            <th>Upload-Status</th>
            <th>Fehler</th>
          </tr>
        </thead>
        <tbody id="sessions-tbody">
          <tr><td colspan="5">
            <div class="empty">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="2" y="7" width="20" height="14" rx="2"/></svg>
              Lade…
            </div>
          </td></tr>
        </tbody>
      </table>
    </div>
  </div>

  <!-- Dead-letter Queue -->
  <div class="section">
    <div class="section-head">
      <div class="section-title">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
        Fehlgeschlagene Übertragungen
        <span class="section-badge" id="dl-count">0</span>
      </div>
    </div>
    <div class="table-wrap">
      <table class="data-table" aria-label="Fehlgeschlagene Übertragungen">
        <thead>
          <tr>
            <th>Erstellt</th>
            <th>Wallbox-ID</th>
            <th>Energie</th>
            <th>Fehler</th>
            <th>Versuche</th>
            <th>Aktion</th>
          </tr>
        </thead>
        <tbody id="dl-tbody">
          <tr><td colspan="6">
            <div class="empty">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/></svg>
              Lade…
            </div>
          </td></tr>
        </tbody>
      </table>
    </div>
  </div>

</main>

<!-- Toast container -->
<div id="toast-container" aria-live="polite" aria-atomic="false"></div>

<script>
// ---- Base path (handles HA ingress prefix) ----
const BASE = (() => {
  const p = location.pathname.replace(/\\/+$/, '');
  return p === '' ? '' : p;
})();

function url(path) {
  return BASE + path;
}

// ---- State ----
let countdownVal = 30;
let countdownTimer = null;
let isRefreshing = false;

// ---- Toast ----
function showToast(msg, type = 'ok') {
  const el = document.createElement('div');
  el.className = 'toast toast-' + type;
  const icon = type === 'ok'
    ? '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>'
    : '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>';
  el.innerHTML = icon + '<span>' + msg + '</span>';
  document.getElementById('toast-container').appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

// ---- Status dot helper ----
function setApiStatus(status) {
  const dot = document.getElementById('api-dot');
  const label = document.getElementById('api-label');
  dot.className = 'dot';
  if (status === 'ok') {
    dot.classList.add('dot-ok');
    label.textContent = 'Verbunden';
  } else if (status === 'error') {
    dot.classList.add('dot-err');
    label.textContent = 'Fehler';
  } else {
    dot.classList.add('dot-pulse');
    label.textContent = 'Prüfe…';
  }
}

// ---- Badge helper ----
function badge(status) {
  const cls = ['ok','error','dead_letter','pending'].includes(status)
    ? 'badge-' + status : 'badge-neutral';
  return '<span class="badge ' + cls + '">' + esc(status || 'pending') + '</span>';
}

function esc(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function truncate(s, n) {
  if (!s) return '';
  return s.length > n ? s.slice(0, n) + '…' : s;
}

// ---- Fetch with timeout ----
async function fetchJson(path, opts = {}) {
  const controller = new AbortController();
  const t = setTimeout(() => controller.abort(), 5000);
  try {
    const resp = await fetch(url(path), { signal: controller.signal, ...opts });
    clearTimeout(t);
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    return await resp.json();
  } catch (e) {
    clearTimeout(t);
    throw e;
  }
}

// ---- Render stats ----
function renderStats(stats) {
  document.getElementById('stat-total').textContent = stats.total ?? '—';
  document.getElementById('stat-ok').textContent = stats.ok ?? '—';
  const failed = (stats.error || 0) + (stats.dead_letter || 0);
  document.getElementById('stat-failed').textContent = failed;
  document.getElementById('stat-dl').textContent = stats.dead_letter_pending ?? '—';
}

// ---- Render sessions ----
function renderSessions(sessions) {
  const tbody = document.getElementById('sessions-tbody');
  document.getElementById('sessions-count').textContent = sessions.length;

  if (!sessions.length) {
    tbody.innerHTML = '<tr><td colspan="5"><div class="empty">' +
      '<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"/></svg>' +
      'Keine abgeschlossenen Sessions vorhanden.' +
      '</div></td></tr>';
    return;
  }

  tbody.innerHTML = sessions.map(s => {
    const kwh = typeof s.total_kwh === 'number' ? s.total_kwh.toFixed(2) : '—';
    const errDisplay = s.upload_error ? truncate(s.upload_error, 70) : '';
    return '<tr>' +
      '<td class="td-mono">' + esc(s.start_time || '—') + '</td>' +
      '<td>' + esc(s.wallbox_id || '—') + '</td>' +
      '<td class="td-num">' + kwh + ' kWh</td>' +
      '<td>' + badge(s.upload_status) + '</td>' +
      '<td>' + (errDisplay ? '<span class="err-text" title="' + esc(s.upload_error) + '">' + esc(errDisplay) + '</span>' : '') + '</td>' +
      '</tr>';
  }).join('');
}

// ---- Render dead-letter ----
function renderDeadLetter(entries) {
  const tbody = document.getElementById('dl-tbody');
  const countEl = document.getElementById('dl-count');
  countEl.textContent = entries.length;
  if (entries.length > 0) {
    countEl.className = 'section-badge section-badge-err';
  } else {
    countEl.className = 'section-badge section-badge-ok';
  }

  if (!entries.length) {
    tbody.innerHTML = '<tr><td colspan="6"><div class="empty">' +
      '<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>' +
      'Keine fehlgeschlagenen Übertragungen — alles gut!' +
      '</div></td></tr>';
    return;
  }

  tbody.innerHTML = entries.map(e => {
    const kwh = typeof e.total_kwh === 'number' ? e.total_kwh.toFixed(2) : '—';
    const retries = parseInt(e.retry_count || 0);
    const pillClass = retries >= 3 ? 'pill pill-hi' : 'pill';
    const errDisplay = truncate(e.error_msg || '', 70);
    return '<tr>' +
      '<td class="td-mono">' + esc(e.created_at || '—') + '</td>' +
      '<td>' + esc(e.wallbox_id || '—') + '</td>' +
      '<td class="td-num">' + kwh + ' kWh</td>' +
      '<td>' + (errDisplay ? '<span class="err-text" title="' + esc(e.error_msg || '') + '">' + esc(errDisplay) + '</span>' : '') + '</td>' +
      '<td><span class="' + pillClass + '">' + retries + '</span></td>' +
      '<td><button class="btn btn-retry" data-id="' + parseInt(e.id) + '" aria-label="Übertragung wiederholen">' +
        '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-3.5"/></svg>' +
        ' Wiederholen' +
      '</button></td>' +
      '</tr>';
  }).join('');

  // Wire up retry buttons
  tbody.querySelectorAll('.btn-retry').forEach(btn => {
    btn.addEventListener('click', async () => {
      const id = parseInt(btn.dataset.id);
      btn.disabled = true;
      btn.classList.add('loading');
      try {
        const result = await fetchJson('/session/retry', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ dead_letter_id: id }),
        });
        if (result.success) {
          showToast('Übertragung erfolgreich wiederholt.', 'ok');
          await loadAll();
        } else {
          showToast('Fehlgeschlagen: ' + (result.error || 'Unbekannter Fehler'), 'err');
          btn.disabled = false;
          btn.classList.remove('loading');
        }
      } catch (e) {
        showToast('Netzwerkfehler: ' + e.message, 'err');
        btn.disabled = false;
        btn.classList.remove('loading');
      }
    });
  });
}

// ---- Load all data ----
async function loadAll() {
  if (isRefreshing) return;
  isRefreshing = true;
  const btn = document.getElementById('refresh-btn');
  btn.classList.add('spinning');

  try {
    const [statusData, sessionsData, dlData] = await Promise.allSettled([
      fetchJson('/api/status'),
      fetchJson('/api/sessions'),
      fetchJson('/dead-letter/list'),
    ]);

    // API health
    if (statusData.status === 'fulfilled') {
      setApiStatus('ok');
      renderStats(statusData.value);
    } else {
      setApiStatus('error');
    }

    // Sessions
    if (sessionsData.status === 'fulfilled') {
      const data = sessionsData.value;
      renderSessions(Array.isArray(data) ? data : []);
    }

    // Dead-letter
    if (dlData.status === 'fulfilled') {
      const data = dlData.value;
      renderDeadLetter(Array.isArray(data) ? data : []);
    } else {
      renderDeadLetter([]);
    }

  } catch (e) {
    setApiStatus('error');
  } finally {
    isRefreshing = false;
    btn.classList.remove('spinning');
    resetCountdown();
  }
}

// ---- Countdown timer ----
function resetCountdown() {
  countdownVal = 30;
  document.getElementById('countdown').textContent = countdownVal;
  if (countdownTimer) clearInterval(countdownTimer);
  countdownTimer = setInterval(() => {
    countdownVal--;
    document.getElementById('countdown').textContent = countdownVal;
    if (countdownVal <= 0) {
      loadAll();
    }
  }, 1000);
}

// ---- Init ----
document.getElementById('refresh-btn').addEventListener('click', loadAll);
loadAll();
</script>
</body>
</html>
"""
