#!/usr/bin/env python3
"""
Ingress Web-Server — Wallbox Dolibarr Addon

Seiten:
  GET  /              Manuelle Session-Erfassung + letzte Sessions
  POST /              Speichert neue manuelle Session
  POST /transmit      Löst sofortige Übertragung an Dolibarr aus
  GET  /history       Monatliche Verlaufsansicht
  GET  /export        CSV-Export für einen Monat
"""
import csv
import io
import logging
import sqlite3
from datetime import datetime

from aiohttp import web

_LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Design-System — dark slate / indigo
# ---------------------------------------------------------------------------

_CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --bg:       #0F172A; --surface:  #1E293B; --surface2: #263348;
  --border:   #334155; --text:     #F1F5F9; --muted:    #94A3B8;
  --dim:      #64748B; --primary:  #6366F1; --primary-d:#4F46E5;
  --success:  #22C55E; --warn:     #F59E0B; --error:    #EF4444;
}
html, body {
  background: var(--bg); color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-size: 14px; line-height: 1.5; min-height: 100vh;
}
/* ── Header ── */
.hdr {
  background: var(--surface); border-bottom: 1px solid var(--border);
  padding: 0 20px; height: 54px;
  display: flex; align-items: center; justify-content: space-between;
  position: sticky; top: 0; z-index: 50;
}
.hdr-left { display: flex; align-items: center; gap: 11px; }
.hdr-logo {
  width: 32px; height: 32px;
  background: linear-gradient(135deg, #6366F1, #818CF8);
  border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.hdr-name { font-size: 15px; font-weight: 700; }
.hdr-sub  { font-size: 11px; color: var(--muted); }
.chip { display: flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 500; color: var(--muted); }
.dot  { width: 7px; height: 7px; border-radius: 50%; background: var(--muted); flex-shrink: 0; }
.dot-ok  { background: var(--success); box-shadow: 0 0 0 3px rgba(34,197,94,.2); }
.dot-err { background: var(--error);   box-shadow: 0 0 0 3px rgba(239,68,68,.2); }
/* ── Nav tabs ── */
.nav {
  background: var(--surface); border-bottom: 1px solid var(--border);
  padding: 0 20px; display: flex; gap: 2px;
}
.nav a {
  display: inline-flex; align-items: center; gap: 7px; padding: 11px 15px;
  text-decoration: none; font-size: 13px; font-weight: 600; color: var(--muted);
  border-bottom: 2px solid transparent; transition: all .15s;
}
.nav a.active { color: var(--primary); border-bottom-color: var(--primary); }
.nav a:hover:not(.active) { color: var(--text); }
/* ── Layout ── */
.page { max-width: 820px; margin: 22px auto; padding: 0 16px; }
/* ── Stats grid ── */
.stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 11px; margin-bottom: 13px; }
@media (max-width: 560px) { .stats { grid-template-columns: 1fr; } }
.stat {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 9px; padding: 15px 17px;
}
.stat-lbl {
  font-size: 10.5px; font-weight: 700; text-transform: uppercase;
  letter-spacing: .06em; color: var(--muted);
  display: flex; align-items: center; gap: 6px; margin-bottom: 7px;
}
.stat-val { font-size: 24px; font-weight: 700; letter-spacing: -.02em; }
.stat-sub { font-size: 11px; color: var(--dim); margin-top: 3px; }
.stat-blue { border-left: 3px solid var(--primary); }
.stat-ok   { border-left: 3px solid var(--success); }
.stat-warn { border-left: 3px solid var(--warn); }
/* ── Card ── */
.card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 9px; padding: 20px; margin-bottom: 13px;
}
.card-title {
  font-size: 11px; font-weight: 700; text-transform: uppercase;
  letter-spacing: .06em; color: var(--muted);
  display: flex; align-items: center; gap: 7px; margin-bottom: 16px;
}
/* ── Form ── */
.flabel {
  display: block; font-size: 11px; font-weight: 700; color: var(--muted);
  text-transform: uppercase; letter-spacing: .05em; margin: 14px 0 5px;
}
.flabel:first-of-type { margin-top: 0; }
input, select {
  width: 100%; padding: 10px 12px;
  background: var(--bg); border: 1.5px solid var(--border);
  border-radius: 7px; font-size: 14px; color: var(--text);
  outline: none; transition: border-color .15s; -webkit-appearance: none;
}
input:focus, select:focus { border-color: var(--primary); }
input::placeholder { color: var(--dim); }
select option { background: var(--surface); color: var(--text); }
.kwh-wrap { position: relative; }
.kwh-wrap input { padding-right: 44px; }
.kwh-unit { position: absolute; right: 12px; top: 50%; transform: translateY(-50%); color: var(--dim); font-size: 13px; }
/* ── Buttons ── */
.btn-save {
  display: flex; align-items: center; justify-content: center; gap: 7px;
  width: 100%; padding: 11px; margin-top: 17px;
  background: var(--primary); color: #fff;
  border: none; border-radius: 7px;
  font-size: 14px; font-weight: 600; cursor: pointer; transition: background .15s;
}
.btn-save:hover { background: var(--primary-d); }
.btn-transmit {
  display: flex; align-items: center; justify-content: center; gap: 7px;
  width: 100%; padding: 9px; margin-top: 8px;
  background: transparent; color: var(--muted);
  border: 1.5px solid var(--border); border-radius: 7px;
  font-size: 13px; font-weight: 600; cursor: pointer; transition: all .15s;
}
.btn-transmit:hover { color: var(--warn); border-color: var(--warn); }
.btn-dl {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 6px 11px; background: transparent;
  border: 1px solid var(--border); border-radius: 6px;
  color: var(--muted); font-size: 12px; font-weight: 600;
  text-decoration: none; transition: all .15s;
}
.btn-dl:hover { color: var(--success); border-color: var(--success); }
/* ── Messages ── */
.msg { padding: 11px 14px; border-radius: 7px; font-size: 13px; line-height: 1.5; margin-bottom: 12px; }
.ok  { background: rgba(34,197,94,.1);  color: #4ADE80; border: 1px solid rgba(34,197,94,.2);  }
.err { background: rgba(239,68,68,.1);  color: #F87171; border: 1px solid rgba(239,68,68,.2);  }
.warn{ background: rgba(245,158,11,.1); color: #FCD34D; border: 1px solid rgba(245,158,11,.2); }
/* ── Session rows ── */
.s-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 9px 0; border-bottom: 1px solid var(--border);
}
.s-row:last-child { border-bottom: none; }
.s-kwh  { font-size: 15px; font-weight: 700; color: var(--primary); }
.s-meta { font-size: 11px; color: var(--muted); margin-top: 2px; }
/* ── Badges ── */
.badge {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 3px 8px; border-radius: 20px;
  font-size: 11px; font-weight: 700; white-space: nowrap;
}
.b-ok   { background: rgba(34,197,94,.12);   color: #4ADE80; }
.b-pend { background: rgba(245,158,11,.12);  color: #FCD34D; }
.b-disc { background: rgba(100,116,139,.1);  color: #94A3B8; }
.b-inc  { background: rgba(245,158,11,.08);  color: #FCD34D; }
/* ── Table ── */
.tbl-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
thead th {
  padding: 8px 12px; text-align: left;
  font-size: 10.5px; font-weight: 700; text-transform: uppercase;
  letter-spacing: .06em; color: var(--muted);
  border-bottom: 1px solid var(--border); white-space: nowrap;
}
tbody tr { border-bottom: 1px solid var(--border); transition: background .1s; }
tbody tr:hover { background: var(--surface2); }
tbody tr:last-child { border-bottom: none; }
td { padding: 9px 12px; vertical-align: middle; }
.td-dim  { color: var(--dim); font-size: 11px; }
.td-bold { font-weight: 700; color: var(--primary); }
.total-row td { border-top: 2px solid var(--border); font-weight: 700; background: var(--surface2); }
/* ── Month tabs ── */
.month-tabs { display: flex; gap: 7px; flex-wrap: wrap; margin-bottom: 13px; }
.m-tab {
  padding: 5px 12px; border-radius: 20px;
  font-size: 12px; font-weight: 600; text-decoration: none;
  background: var(--surface2); color: var(--muted);
  border: 1px solid var(--border); transition: all .15s;
}
.m-tab.active  { background: var(--primary); color: #fff; border-color: var(--primary); }
.m-tab:hover:not(.active) { color: var(--text); }
/* ── Misc ── */
.empty { text-align: center; padding: 32px 16px; color: var(--muted); font-size: 13px; }
#live-card { display: none; }
.live-item {
  border-left: 3px solid var(--primary); padding: 10px 14px;
  background: var(--surface2); border-radius: 0 6px 6px 0; margin-bottom: 8px;
}
.live-item:last-child { margin-bottom: 0; }
"""

# ---------------------------------------------------------------------------
# Inline SVG icons (no external deps)
# ---------------------------------------------------------------------------
_ICO_BOLT = (
    '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"'
    ' stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>'
)
_ICO_HIST = (
    '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"'
    ' stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-3.5"/></svg>'
)
_ICO_UP = (
    '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor"'
    ' stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<polyline points="16 16 12 12 8 16"/><line x1="12" y1="12" x2="12" y2="21"/>'
    '<path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3"/></svg>'
)
_ICO_DL = (
    '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor"'
    ' stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<polyline points="8 17 12 21 16 17"/><line x1="12" y1="12" x2="12" y2="21"/>'
    '<path d="M20.88 18.09A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3"/></svg>'
)
_ICO_CHECK = (
    '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor"'
    ' stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
    '<polyline points="20 6 9 17 4 12"/></svg>'
)
_ICO_BOLT_WHITE = (
    '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff"'
    ' stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>'
)


# ---------------------------------------------------------------------------
# HTML scaffolding
# ---------------------------------------------------------------------------

def _base(active, content, base_href=''):
    base_tag = f'  <base href="{base_href}/">\n' if base_href else ''
    nav_form = (
        f'<a href="./" class="{"active" if active == "form" else ""}">'
        f'{_ICO_BOLT} Erfassen</a>'
    )
    nav_hist = (
        f'<a href="history" class="{"active" if active == "history" else ""}">'
        f'{_ICO_HIST} Verlauf</a>'
    )
    return f"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
{base_tag}  <title>Wallbox Ladevorgänge</title>
  <style>{_CSS}</style>
</head>
<body>
<header class="hdr">
  <div class="hdr-left">
    <div class="hdr-logo">{_ICO_BOLT_WHITE}</div>
    <div>
      <div class="hdr-name">Wallbox Billing</div>
      <div class="hdr-sub">Home Assistant Addon</div>
    </div>
  </div>
  <div class="chip">
    <span class="dot" id="conn-dot"></span>
    <span id="conn-lbl">—</span>
  </div>
</header>
<nav class="nav">{nav_form}{nav_hist}</nav>
<div class="page">{content}</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# DB-Hilfsfunktionen
# ---------------------------------------------------------------------------

def _db_month(db_path, year, month):
    """Alle Sessions eines Monats aus SQLite"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT id, rfid_hash, wallbox_id, start_time, end_time,
               total_kwh, status, transmitted_at
        FROM sessions
        WHERE strftime('%Y', start_time) = ?
          AND strftime('%m', start_time) = ?
        ORDER BY start_time DESC
    """, (str(year), str(month).zfill(2)))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def _db_months(db_path):
    """Verfügbare Monate (max. 12) absteigend"""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT strftime('%Y', start_time) AS y,
                        strftime('%m', start_time) AS m
        FROM sessions
        WHERE start_time IS NOT NULL
        ORDER BY y DESC, m DESC
        LIMIT 12
    """)
    rows = [(int(y), int(m)) for y, m in cur.fetchall()]
    conn.close()
    return rows


def _month_name(month):
    names = ['Jan','Feb','Mär','Apr','Mai','Jun','Jul','Aug','Sep','Okt','Nov','Dez']
    return names[month - 1]


def _db_active_sessions(db_path):
    """Alle laufenden Sessions (status='active') aus SQLite"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT id, rfid_hash, wallbox_id, start_time, start_energy_kwh
        FROM sessions
        WHERE status = 'active'
        ORDER BY start_time ASC
    """)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def _db_stats_month(db_path):
    """Statistiken für den aktuellen Monat"""
    now = datetime.now()
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        SELECT
            COUNT(*) AS total,
            COALESCE(SUM(
                CASE WHEN status NOT IN ('active','discarded') THEN COALESCE(total_kwh, 0)
                     ELSE 0 END), 0) AS kwh,
            SUM(CASE WHEN transmitted_at IS NULL
                      AND status NOT IN ('active','discarded','incomplete') THEN 1
                     ELSE 0 END) AS pending
        FROM sessions
        WHERE strftime('%Y', start_time) = ?
          AND strftime('%m', start_time) = ?
          AND status != 'active'
    """, (str(now.year), str(now.month).zfill(2)))
    row = cur.fetchone()
    conn.close()
    if row:
        return {'total': row[0] or 0, 'kwh': float(row[1] or 0.0), 'pending': row[2] or 0}
    return {'total': 0, 'kwh': 0.0, 'pending': 0}


# ---------------------------------------------------------------------------
# Seiten-Builder
# ---------------------------------------------------------------------------

def _build_form_page(session_manager, config, message_html='', base_href=''):
    whitelist = config.get('rfid_whitelist', [])
    today     = datetime.now().date().isoformat()
    now       = datetime.now()

    # Stats des laufenden Monats
    try:
        stats = _db_stats_month(session_manager.db_path)
    except Exception:
        stats = {'total': 0, 'kwh': 0.0, 'pending': 0}

    month_lbl = f'{_month_name(now.month)} {now.year}'
    warn_cls  = 'stat-warn' if stats['pending'] > 0 else 'stat-ok'
    stats_html = f"""
<div class="stats">
  <div class="stat stat-blue">
    <div class="stat-lbl">{_ICO_BOLT} Sessions {month_lbl}</div>
    <div class="stat-val">{stats['total']}</div>
    <div class="stat-sub">Ladevorgänge diesen Monat</div>
  </div>
  <div class="stat stat-ok">
    <div class="stat-lbl">{_ICO_UP} Energie {month_lbl}</div>
    <div class="stat-val">{stats['kwh']:.1f} kWh</div>
    <div class="stat-sub">geladene Energie gesamt</div>
  </div>
  <div class="stat {warn_cls}">
    <div class="stat-lbl">{_ICO_HIST} Ausstehend</div>
    <div class="stat-val">{stats['pending']}</div>
    <div class="stat-sub">noch nicht übertragen</div>
  </div>
</div>"""

    # RFID-Optionen
    rfid_opts = '\n'.join(
        f'<option value="{r}">{r}</option>' for r in whitelist
    ) or '<option value="">— keine RFID konfiguriert —</option>'

    # Letzte 5 Sessions
    rows_html = ''
    try:
        rows = session_manager.get_completed_sessions(limit=5)
        for s in rows:
            kwh    = s.get('total_kwh') or 0
            date   = (s.get('start_time') or '')[:10]
            rid    = (s.get('rfid_hash') or '')[:8]
            manual = ' · manuell' if (s.get('start_time') or '').endswith('T12:00:00') else ''
            st     = (s.get('status') or '').lower()
            if st == 'discarded':
                tag = '<span class="badge b-disc">⊘ verworfen</span>'
            elif st == 'incomplete':
                tag = '<span class="badge b-inc">⚠ unvollst.</span>'
            elif s.get('transmitted_at'):
                tag = f'<span class="badge b-ok">{_ICO_CHECK} übertragen</span>'
            else:
                tag = '<span class="badge b-pend">ausstehend</span>'
            rows_html += (
                f'<div class="s-row">'
                f'<span>'
                f'<div class="s-kwh">{kwh:.3f} kWh</div>'
                f'<div class="s-meta">{date} · {rid}…{manual}</div>'
                f'</span>'
                f'{tag}</div>'
            )
    except Exception:
        pass

    sessions_block = (
        f'<div class="card">'
        f'<div class="card-title">{_ICO_HIST} Letzte Sessions</div>'
        f'{rows_html}</div>'
    ) if rows_html else ''

    # Live-Karte (JS-gesteuert)
    live_block = """
<div class="card" id="live-card">
  <div class="card-title">
    <span id="live-dot" style="width:8px;height:8px;border-radius:50%;
          background:var(--muted);display:inline-block;flex-shrink:0"></span>
    Aktiver Ladevorgang
  </div>
  <div id="live-banner" style="font-size:12.5px;color:var(--muted);margin-bottom:10px"></div>
  <div id="live-content"></div>
</div>"""

    js_polling = """
<script>
(function(){
  function fmtDuration(s){
    s=Math.max(0,Math.floor(s));
    var h=Math.floor(s/3600),m=Math.floor((s%3600)/60),sec=s%60;
    return (h?h+'h ':'')+(m<10?'0'+m:m)+'m '+(sec<10?'0'+sec:sec)+'s';
  }
  function esc(t){
    return (t||'').replace(/[&<>"']/g,function(c){
      return({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c];
    });
  }
  function render(data){
    var card=document.getElementById('live-card');
    if(!card) return;
    var sessions=data.sessions||[];
    var sensor=data.sensor||{};
    var hasSessions=sessions.length>0;
    var hasSensor=sensor.current_energy!==null && sensor.current_energy!==undefined;

    // Verbindungs-Status im Header
    var cDot=document.getElementById('conn-dot');
    var cLbl=document.getElementById('conn-lbl');
    if(cDot && cLbl){
      if(hasSensor){
        cDot.className='dot dot-ok'; cLbl.textContent='Verbunden';
      } else {
        cDot.className='dot'; cLbl.textContent='Kein Sensor';
      }
    }

    if(!hasSessions && !hasSensor){ card.style.display='none'; return; }
    card.style.display='block';

    var state=sensor.wallbox_state||'';
    var sl=state.toLowerCase();
    var stateColor='var(--muted)';
    if(sl.indexOf('charging')>=0 && sl.indexOf('stopped')<0) stateColor='var(--success)';
    else if(['faulted','unavailable','stopped'].some(function(k){return sl.indexOf(k)>=0;}))
      stateColor='var(--error)';
    else if(state) stateColor='var(--warn)';

    document.getElementById('live-dot').style.background=stateColor;

    var banner='';
    if(hasSensor){
      var chip=state
        ? '<span style="background:'+stateColor+';color:#0F172A;padding:1px 7px;'
          +'border-radius:3px;font-size:11px;font-weight:700;margin-left:6px">'
          +esc(state)+'</span>'
        : '';
      banner='Zähler: <strong>'+sensor.current_energy.toFixed(3)+' kWh</strong>'+chip
        +'<span style="float:right;color:var(--dim);font-size:11px">'
        +(sensor.last_update||'')+'</span>';
    } else {
      banner='<span style="color:var(--muted)">Kein Zähler-Wert vom HA-Sensor</span>';
    }
    document.getElementById('live-banner').innerHTML=banner;

    var html='';
    if(hasSessions){
      sessions.forEach(function(s){
        var kwhStr=(s.current_kwh!==null && s.current_kwh!==undefined)
          ? s.current_kwh.toFixed(3)+' kWh' : '—';
        html+='<div class="live-item">'
          +'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">'
          +'<div>'
          +'<div style="font-size:11px;color:var(--muted)">#'+s.id+' · '+esc(s.wallbox_id)+'</div>'
          +'<code style="font-size:12px;color:var(--muted)">'+esc(s.rfid_prefix)+'</code>'
          +'</div>'
          +'<div style="font-size:18px;font-weight:700;color:var(--primary)">'+kwhStr+'</div>'
          +'</div>'
          +'<div style="font-size:11.5px;color:var(--dim)">'
          +'Start: '+esc(s.start_time_fmt)+' · Dauer: '+fmtDuration(s.elapsed_seconds)
          +'</div></div>';
      });
    } else if(hasSensor){
      html='<div style="color:var(--muted);font-size:13px;text-align:center;padding:8px">'
        +'Kein aktiver Ladevorgang.</div>';
    }
    document.getElementById('live-content').innerHTML=html;
  }
  function poll(){
    fetch('live.json',{cache:'no-store'})
      .then(function(r){return r.json();})
      .then(render)
      .catch(function(){/* Netz weg — nächster Poll */});
  }
  poll();
  setInterval(poll, 5000);
})();
</script>"""

    content = f"""
{message_html}
{stats_html}
{live_block}
<div class="card">
  <div class="card-title">{_ICO_BOLT} Manueller Ladevorgang</div>
  <form method="POST" action="./">
    <label class="flabel">RFID-Karte</label>
    <select name="rfid" required>{rfid_opts}</select>
    <label class="flabel">Geladene Energie</label>
    <div class="kwh-wrap">
      <input type="number" name="kwh" min="0.001" step="0.001"
             placeholder="z.B. 12.500" required>
      <span class="kwh-unit">kWh</span>
    </div>
    <label class="flabel">Datum</label>
    <input type="date" name="date" value="{today}" required>
    <button type="submit" class="btn-save">{_ICO_BOLT} Ladevorgang speichern</button>
  </form>
  <form method="POST" action="transmit"
        onsubmit="this.querySelector('button').textContent='Übertrage…'">
    <button type="submit" class="btn-transmit">{_ICO_UP} Jetzt an Dolibarr übertragen</button>
  </form>
</div>
{sessions_block}
{js_polling}"""

    return _base('form', content, base_href)


def _build_history_page(session_manager, year, month, base_href=''):
    months = _db_months(session_manager.db_path)

    now = datetime.now()
    if not months:
        months = [(now.year, now.month)]
    if year == 0 or month == 0:
        year, month = months[0]

    # Monats-Tabs
    tabs_html = ''
    for y, m in months:
        active = 'active' if (y == year and m == month) else ''
        tabs_html += (
            f'<a href="history?year={y}&month={m}" class="m-tab {active}">'
            f'{_month_name(m)} {y}</a>'
        )

    # Sessions des gewählten Monats
    rows      = _db_month(session_manager.db_path, year, month)
    total_kwh = sum(s.get('total_kwh') or 0 for s in rows)
    n_total   = len(rows)
    n_sent    = sum(1 for s in rows if s.get('transmitted_at'))
    n_pending = sum(
        1 for s in rows
        if not s.get('transmitted_at')
        and (s.get('status') or '').lower() not in ('discarded', 'incomplete', 'active')
    )

    if rows:
        table_rows = ''
        for s in rows:
            kwh      = s.get('total_kwh') or 0
            date     = (s.get('start_time') or '')[:10]
            time_str = (s.get('start_time') or '')[11:16]
            rid      = (s.get('rfid_hash') or '')[:12] + '…'
            wbx      = s.get('wallbox_id') or '—'
            status   = (s.get('status') or '').lower()
            if status == 'discarded':
                tag = ('<span class="badge b-disc" '
                       'title="Karte gelesen, aber zu wenig kWh — nicht übertragen">'
                       '⊘ verworfen</span>')
                row_style = ' style="opacity:0.55"'
            elif status == 'incomplete':
                tag = ('<span class="badge b-inc" '
                       'title="Zählerstand unbekannt — bitte manuell nachtragen">'
                       '⚠ unvollständig</span>')
                row_style = ' style="opacity:0.7"'
            elif s.get('transmitted_at'):
                tag = f'<span class="badge b-ok">{_ICO_CHECK} übertragen</span>'
                row_style = ''
            else:
                tag = '<span class="badge b-pend">ausstehend</span>'
                row_style = ''
            table_rows += (
                f'<tr{row_style}>'
                f'<td>{date}<div class="td-dim">{time_str}</div></td>'
                f'<td class="td-dim">{rid}</td>'
                f'<td>{wbx}</td>'
                f'<td class="td-bold">{kwh:.3f}</td>'
                f'<td>{tag}</td></tr>'
            )
        table_rows += (
            f'<tr class="total-row">'
            f'<td colspan="3">Gesamt ({n_total} Sessions)</td>'
            f'<td class="td-bold">{total_kwh:.3f} kWh</td>'
            f'<td><span style="font-size:11px;color:var(--muted)">'
            f'{n_sent} übertr. · {n_pending} ausst.</span></td></tr>'
        )
        table_html = (
            f'<div class="tbl-wrap">'
            f'<table>'
            f'<thead><tr>'
            f'<th>Datum</th><th>RFID</th><th>Wallbox</th><th>kWh</th><th>Status</th>'
            f'</tr></thead>'
            f'<tbody>{table_rows}</tbody>'
            f'</table></div>'
        )
    else:
        table_html = '<div class="empty">Keine Sessions in diesem Monat</div>'

    export_url = f'export?year={year}&month={month}'
    content = f"""
<div class="card">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:13px">
    <div class="card-title" style="margin:0">{_ICO_HIST} Verlauf</div>
    <a href="{export_url}" class="btn-dl">{_ICO_DL} CSV exportieren</a>
  </div>
  <div class="month-tabs">{tabs_html}</div>
  {table_html}
</div>"""

    return _base('history', content, base_href)


# ---------------------------------------------------------------------------
# App-Factory
# ---------------------------------------------------------------------------

def create_app(session_manager, config, api_state):
    """
    api_state: dict mit key 'client' → WallboxApiClient oder None.
    Wird von main.py befüllt und kann sich zur Laufzeit ändern.
    """
    from utils.hash import hash_rfid

    # -- GET / ---------------------------------------------------------------
    async def handle_get(request):
        base_href = request.headers.get('X-Ingress-Path', '').rstrip('/')
        msg = request.rel_url.query.get('msg', '')
        t   = request.rel_url.query.get('t', '')
        msg_html = f'<div class="msg {t}">{msg}</div>' if msg else ''
        return web.Response(
            text=_build_form_page(session_manager, config, msg_html, base_href=base_href),
            content_type='text/html'
        )

    # -- POST / --------------------------------------------------------------
    async def handle_post(request):
        base_href = request.headers.get('X-Ingress-Path', '').rstrip('/')
        msg_html = ''
        try:
            data     = await request.post()
            rfid_hex = data.get('rfid', '').strip()
            kwh_str  = data.get('kwh', '').strip()
            date_str = data.get('date', datetime.now().date().isoformat()).strip()

            if not rfid_hex:
                raise ValueError("Keine RFID ausgewählt.")
            kwh = float(kwh_str) if kwh_str else 0.0
            if kwh <= 0:
                raise ValueError("kWh muss größer als 0 sein.")

            rfid_hash  = hash_rfid(rfid_hex)
            wallbox_id = config.get('wallbox_id', 'wallbox')
            sid        = session_manager.add_manual_session(rfid_hash, kwh, wallbox_id, date_str)

            if sid:
                msg_html = (f'<div class="msg ok">Session #{sid} gespeichert: '
                            f'<strong>{kwh:.3f} kWh</strong> am {date_str}</div>')
            else:
                raise ValueError("Session konnte nicht gespeichert werden.")
        except Exception as exc:
            msg_html = f'<div class="msg err">Fehler: {exc}</div>'

        return web.Response(
            text=_build_form_page(session_manager, config, msg_html, base_href=base_href),
            content_type='text/html'
        )

    # -- POST /transmit -------------------------------------------------------
    async def handle_transmit(request):
        base_href = request.headers.get('X-Ingress-Path', '').rstrip('/')
        client = api_state.get('client')

        if not client:
            from api_client import WallboxApiClient
            url   = config.get('dolibarr_url', '')
            token = config.get('api_token', '')
            if url and token and url != 'https://dolibarr.example.com':
                try:
                    c = WallboxApiClient(base_url=url, api_token=token, timeout=30)
                    if c.check_connection():
                        client = c
                        api_state['client'] = c
                        _LOGGER.info("API-Client on-demand erstellt")
                except Exception as e:
                    _LOGGER.warning("API-Client Fehler: %s", e)

        if not client:
            msg_html = '<div class="msg err">Dolibarr API nicht erreichbar — bitte URL und Token prüfen.</div>'
        else:
            try:
                result = session_manager.transmit_completed_sessions(client)
                sent   = result.get('transmitted', 0)
                failed = result.get('failed', 0)
                if sent == 0 and failed == 0:
                    msg_html = '<div class="msg warn">Keine ausstehenden Sessions.</div>'
                elif failed > 0:
                    err = result['errors'][0] if result['errors'] else ''
                    msg_html = f'<div class="msg err">{sent} übertragen, {failed} fehlgeschlagen: {err}</div>'
                else:
                    msg_html = f'<div class="msg ok">{sent} Session(s) erfolgreich an Dolibarr übertragen.</div>'
            except Exception as exc:
                msg_html = f'<div class="msg err">Übertragungsfehler: {exc}</div>'

        return web.Response(
            text=_build_form_page(session_manager, config, msg_html, base_href=base_href),
            content_type='text/html'
        )

    # -- GET /history --------------------------------------------------------
    async def handle_history(request):
        base_href = request.headers.get('X-Ingress-Path', '').rstrip('/')
        year  = int(request.rel_url.query.get('year',  0))
        month = int(request.rel_url.query.get('month', 0))
        return web.Response(
            text=_build_history_page(session_manager, year, month, base_href=base_href),
            content_type='text/html'
        )

    # -- GET /export ----------------------------------------------------------
    async def handle_export(request):
        now   = datetime.now()
        year  = int(request.rel_url.query.get('year',  now.year))
        month = int(request.rel_url.query.get('month', now.month))
        rows  = _db_month(session_manager.db_path, year, month)

        output = io.StringIO()
        writer = csv.writer(output, delimiter=';')
        writer.writerow(['Datum', 'Uhrzeit', 'RFID (Prefix)', 'Wallbox', 'kWh', 'Status', 'Übertragen am'])
        for s in rows:
            date_s  = (s.get('start_time') or '')[:10]
            time_s  = (s.get('start_time') or '')[11:16]
            rfid_s  = (s.get('rfid_hash') or '')[:16] + '…'
            wbx_s   = s.get('wallbox_id') or ''
            kwh_s   = f"{(s.get('total_kwh') or 0):.3f}".replace('.', ',')
            _st = (s.get('status') or '').lower()
            status  = ('verworfen'      if _st == 'discarded'
                       else 'unvollständig' if _st == 'incomplete'
                       else 'übertragen'    if s.get('transmitted_at')
                       else 'ausstehend')
            tx_time = (s.get('transmitted_at') or '')[:16]
            writer.writerow([date_s, time_s, rfid_s, wbx_s, kwh_s, status, tx_time])

        filename = f'wallbox_{year}_{str(month).zfill(2)}.csv'
        # aiohttp content_type darf KEINE Parameter (z.B. charset) enthalten —
        # sonst ValueError → 500. Mit BOM für korrekte Umlaut-Darstellung in Excel.
        body = '﻿' + output.getvalue()
        return web.Response(
            body=body.encode('utf-8'),
            content_type='text/csv',
            charset='utf-8',
            headers={'Content-Disposition': f'attachment; filename="{filename}"'}
        )

    # -- GET /live.json (JSON-Endpoint für JS-Polling, flackerfrei) ----------
    async def handle_live_json(request):
        active         = _db_active_sessions(session_manager.db_path)
        current_energy = api_state.get('current_energy') if api_state else None
        wallbox_state  = api_state.get('wallbox_state')  if api_state else None
        last_update    = api_state.get('last_update')    if api_state else None

        now = datetime.now()
        sessions_out = []
        for s in active:
            try:
                start_dt = datetime.fromisoformat(s['start_time'])
            except (ValueError, TypeError):
                start_dt = now
            elapsed      = (now - start_dt).total_seconds()
            start_energy = float(s.get('start_energy_kwh') or 0.0)
            current_kwh  = None
            if current_energy is not None and current_energy >= start_energy:
                current_kwh = current_energy - start_energy
            sessions_out.append({
                'id':              s['id'],
                'rfid_prefix':     ((s.get('rfid_hash') or '')[:16] + '…'),
                'wallbox_id':      s.get('wallbox_id') or '—',
                'start_time_fmt':  start_dt.strftime('%d.%m.%Y %H:%M:%S'),
                'elapsed_seconds': elapsed,
                'start_energy_kwh': start_energy,
                'current_kwh':     current_kwh,
            })

        return web.json_response({
            'sensor': {
                'current_energy': current_energy,
                'wallbox_state':  wallbox_state,
                'last_update':    last_update,
            },
            'sessions': sessions_out,
        })

    app = web.Application()
    app.router.add_get('/',          handle_get)
    app.router.add_post('/',         handle_post)
    app.router.add_post('/transmit', handle_transmit)
    app.router.add_get('/live.json', handle_live_json)
    app.router.add_get('/history',   handle_history)
    app.router.add_get('/export',    handle_export)
    return app


async def start_web_server(session_manager, config, api_state, port=8099):
    app    = create_app(session_manager, config, api_state)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    _LOGGER.info("Ingress Web-Server gestartet auf Port %d", port)
