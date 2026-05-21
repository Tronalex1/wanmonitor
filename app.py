"""
WAN Monitoring Dashboard — Web Edition
Flask backend: pings all ISP links in background threads,
exposes /api/status for the dashboard to poll every 3 s.
Single-file: HTML is embedded as a string (no templates/ folder needed).
"""

import os
import socket
import threading
import time
from collections import deque
from datetime import datetime, timezone, timedelta

from flask import Flask, jsonify, render_template_string

_IST = timezone(timedelta(hours=5, minutes=30))

def _now_ist() -> datetime:
    return datetime.now(_IST)

app = Flask(__name__)

# ===========================================================
# DASHBOARD HTML  (embedded — no templates/ folder required)
# ===========================================================

_INDEX_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>WAN Monitoring Dashboard</title>
  <style>
    /* ─── Reset & Base ─────────────────────────────────────── */
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    :root {
      --bg:      #0f172a;
      --panel:   #1e293b;
      --border:  #334155;
      --accent:  #38bdf8;
      --green:   #22c55e;
      --amber:   #f59e0b;
      --red:     #ef4444;
      --fg:      #f1f5f9;
      --fg2:     #94a3b8;
      --ok-bg:   #0b2016;
      --warn-bg: #241900;
      --down-bg: #220a0a;
      --init-bg: #1e293b;
      --font:    'Consolas', 'Courier New', monospace;
    }
    html, body {
      height: 100%; background: var(--bg); color: var(--fg);
      font-family: var(--font); font-size: 14px; overflow: hidden;
    }

    /* ─── Layout ────────────────────────────────────────────── */
    #app { display: flex; flex-direction: column; height: 100vh; }

    /* ─── Header ────────────────────────────────────────────── */
    #header {
      background: var(--panel);
      padding: 14px 24px;
      display: flex; align-items: center; justify-content: space-between;
      border-bottom: 1px solid var(--border);
      flex-shrink: 0;
    }
    #header .title-block h1 {
      font-size: 18px; font-weight: bold; letter-spacing: 1px;
      color: var(--fg);
    }
    #header .title-block p {
      font-size: 11px; color: var(--fg2); margin-top: 3px;
    }
    #header .right { text-align: right; }
    #clock { font-size: 11px; color: var(--fg2); margin-bottom: 6px; }
    .stat-badges { display: flex; gap: 8px; justify-content: flex-end; }
    .badge {
      padding: 3px 10px; border-radius: 4px; font-size: 11px;
      font-weight: bold; background: var(--border); color: var(--fg2);
      min-width: 56px; text-align: center;
    }
    .badge.ok   { background: #0b2016; color: var(--green); }
    .badge.warn { background: #241900; color: var(--amber); }
    .badge.down { background: #220a0a; color: var(--red);   }

    /* ─── Toolbar ───────────────────────────────────────────── */
    #toolbar {
      background: var(--panel);
      padding: 8px 20px;
      display: flex; align-items: center; gap: 8px;
      border-bottom: 1px solid var(--border);
      flex-shrink: 0; flex-wrap: wrap;
    }
    .pills { display: flex; gap: 6px; }
    .pill {
      padding: 4px 14px; border-radius: 4px; font-size: 11px;
      font-weight: bold; cursor: pointer; border: 1px solid var(--border);
      background: var(--border); color: var(--fg2);
      transition: background .15s, color .15s;
      font-family: var(--font);
    }
    .pill:hover { filter: brightness(1.2); }
    .pill.active-all  { background: var(--accent); color: #0f172a; border-color: var(--accent); }
    .pill.active-ok   { background: var(--green);  color: #0f172a; border-color: var(--green);  }
    .pill.active-warn { background: var(--amber);  color: #0f172a; border-color: var(--amber);  }
    .pill.active-down { background: var(--red);    color: #fff;    border-color: var(--red);    }

    .search-wrap {
      margin-left: auto; display: flex; align-items: center; gap: 8px;
    }
    .search-wrap label { font-size: 11px; color: var(--fg2); }
    #search {
      background: var(--bg); color: var(--fg); border: 1px solid var(--border);
      border-radius: 4px; padding: 4px 10px; font-family: var(--font);
      font-size: 12px; width: 200px; outline: none;
    }
    #search:focus { border-color: var(--accent); }

    /* ─── Refresh indicator ─────────────────────────────────── */
    #refresh-bar {
      height: 2px; background: var(--border); position: relative;
      flex-shrink: 0;
    }
    #refresh-prog {
      height: 100%; background: var(--accent);
      transition: width .1s linear;
      width: 0%;
    }

    /* ─── Table wrapper ─────────────────────────────────────── */
    #table-wrap {
      flex: 1; overflow: auto; padding: 8px 12px 0;
    }
    table {
      width: 100%; border-collapse: collapse; font-size: 13px;
    }
    thead th {
      position: sticky; top: 0; z-index: 2;
      background: var(--panel); color: var(--fg2);
      font-size: 11px; font-weight: bold; letter-spacing: .5px;
      padding: 8px 12px; text-align: left;
      border-bottom: 1px solid var(--border);
    }
    tbody tr { border-bottom: 1px solid #1a2540; transition: filter .1s; }
    tbody tr:hover { filter: brightness(1.15); }
    tbody td { padding: 7px 12px; }

    /* status rows */
    tr.r-OK   { background: var(--ok-bg); }
    tr.r-WARN { background: var(--warn-bg); }
    tr.r-DOWN { background: var(--down-bg); }
    tr.r-INIT { background: var(--init-bg); }

    .tag {
      display: inline-block; padding: 2px 8px; border-radius: 3px;
      font-size: 11px; font-weight: bold; min-width: 56px; text-align: center;
    }
    .tag-OK   { background: #0f2518; color: var(--green); border: 1px solid #1a3d20; }
    .tag-WARN { background: #2c1e00; color: var(--amber); border: 1px solid #4a3000; }
    .tag-DOWN { background: #2a0a0a; color: var(--red);   border: 1px solid #4a1010; }
    .tag-INIT { background: #1e293b; color: var(--fg2);   border: 1px solid var(--border); }

    .lat { color: var(--accent); font-variant-numeric: tabular-nums; }
    .loc { color: var(--fg); font-weight: bold; }
    .ip  { color: var(--fg2); font-size: 12px; }
    .isp { color: var(--fg); }
    .ts  { color: var(--fg2); font-size: 12px; }
    .up  { color: var(--fg2); font-size: 12px; font-variant-numeric: tabular-nums; }

    /* ─── Status bar ─────────────────────────────────────────── */
    #statusbar {
      background: var(--panel); border-top: 1px solid var(--border);
      padding: 4px 20px;
      display: flex; justify-content: space-between; align-items: center;
      font-size: 11px; color: var(--fg2);
      flex-shrink: 0;
    }
    #conn-dot {
      display: inline-block; width: 7px; height: 7px; border-radius: 50%;
      background: var(--green); margin-right: 5px;
      box-shadow: 0 0 6px var(--green);
    }
    #conn-dot.err { background: var(--red); box-shadow: 0 0 6px var(--red); }

    /* ─── Empty / loading state ──────────────────────────────── */
    #loading {
      text-align: center; padding: 60px; color: var(--fg2); font-size: 13px;
    }
    .spinner {
      display: inline-block; width: 20px; height: 20px; margin-bottom: 12px;
      border: 2px solid var(--border); border-top-color: var(--accent);
      border-radius: 50%; animation: spin .7s linear infinite;
    }
    @keyframes spin { to { transform: rotate(360deg); } }

    /* ─── Scrollbar ──────────────────────────────────────────── */
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: var(--bg); }
    ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
  </style>
</head>
<body>
<div id="app">

  <!-- ── Header ─────────────────────────────────────────────── -->
  <div id="header">
    <div class="title-block">
      <h1>WAN MONITORING DASHBOARD</h1>
      <p>Real-time link health across all sites</p>
    </div>
    <div class="right">
      <div id="clock">—</div>
      <div class="stat-badges">
        <span class="badge ok"   id="b-ok">  OK  0</span>
        <span class="badge warn" id="b-warn">WARN 0</span>
        <span class="badge down" id="b-down">DOWN 0</span>
      </div>
    </div>
  </div>

  <!-- ── Toolbar ────────────────────────────────────────────── -->
  <div id="toolbar">
    <div class="pills">
      <button class="pill active-all" data-f="ALL"  onclick="setFilter('ALL')">ALL  <span id="c-ALL">0</span></button>
      <button class="pill"            data-f="OK"   onclick="setFilter('OK')">OK  <span id="c-OK">0</span></button>
      <button class="pill"            data-f="WARN" onclick="setFilter('WARN')">WARN  <span id="c-WARN">0</span></button>
      <button class="pill"            data-f="DOWN" onclick="setFilter('DOWN')">DOWN  <span id="c-DOWN">0</span></button>
    </div>
    <div class="search-wrap">
      <label for="search">Search:</label>
      <input id="search" type="text" placeholder="location / IP / ISP…"
             oninput="applyView()" autocomplete="off" />
    </div>
  </div>

  <!-- ── Refresh progress ──────────────────────────────────── -->
  <div id="refresh-bar"><div id="refresh-prog"></div></div>

  <!-- ── Table ──────────────────────────────────────────────── -->
  <div id="table-wrap">
    <div id="loading">
      <div class="spinner"></div><br>Connecting to monitor…
    </div>
    <table id="tbl" style="display:none">
      <thead>
        <tr>
          <th>LOCATION</th>
          <th>IP ADDRESS</th>
          <th>ISP</th>
          <th>STATUS</th>
          <th>LATENCY</th>
          <th>LAST OK</th>
          <th>UPTIME</th>
        </tr>
      </thead>
      <tbody id="tbody"></tbody>
    </table>
  </div>

  <!-- ── Status bar ─────────────────────────────────────────── -->
  <div id="statusbar">
    <span><span id="conn-dot"></span><span id="status-txt">Connecting…</span></span>
    <span>TCP probe · Poll: 10 s · Drop threshold: 4</span>
  </div>

</div><!-- #app -->

<script>
  // ── State ───────────────────────────────────────────────────
  let allLinks   = [];
  let filterMode = 'ALL';
  let pollTimer  = null;
  let progTimer  = null;
  const POLL_MS  = 10000;

  // ── Clock (IST = UTC+5:30) ──────────────────────────────────
  function tickClock() {
    const now = new Date();
    // Convert to IST by adding 5h30m to UTC
    const ist = new Date(now.getTime() + (5 * 60 + 30) * 60000);
    const days   = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];
    const months = ['Jan','Feb','Mar','Apr','May','Jun',
                    'Jul','Aug','Sep','Oct','Nov','Dec'];
    const d = `${days[ist.getUTCDay()]}, ${String(ist.getUTCDate()).padStart(2,'0')} ${months[ist.getUTCMonth()]} ${ist.getUTCFullYear()}`;
    const t = `${String(ist.getUTCHours()).padStart(2,'0')}:${String(ist.getUTCMinutes()).padStart(2,'0')}:${String(ist.getUTCSeconds()).padStart(2,'0')}`;
    document.getElementById('clock').textContent = `${d}   ${t}`;
  }
  setInterval(tickClock, 1000);
  tickClock();

  // ── Refresh progress bar ────────────────────────────────────
  function startProgress() {
    const bar   = document.getElementById('refresh-prog');
    const start = Date.now();
    clearInterval(progTimer);
    bar.style.width = '0%';
    progTimer = setInterval(() => {
      const pct = Math.min(100, ((Date.now() - start) / POLL_MS) * 100);
      bar.style.width = pct + '%';
      if (pct >= 100) clearInterval(progTimer);
    }, 80);
  }

  // ── Fetch status ─────────────────────────────────────────────
  async function fetchStatus() {
    try {
      const res  = await fetch('/api/status');
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();
      allLinks   = data.links;
      updateTable(data);
      updateCounts(data.counts);
      setConnected(true, data.updated);
    } catch (e) {
      setConnected(false, null);
    }
    startProgress();
    pollTimer = setTimeout(fetchStatus, POLL_MS);
  }

  // ── Update table ─────────────────────────────────────────────
  function updateTable(data) {
    document.getElementById('loading').style.display = 'none';
    document.getElementById('tbl').style.display     = '';
    applyView();
  }

  function applyView() {
    const q     = document.getElementById('search').value.trim().toLowerCase();
    const tbody = document.getElementById('tbody');
    tbody.innerHTML = '';

    let shown = 0;
    for (const lnk of allLinks) {
      const health = lnk.health || 'INIT';
      if (filterMode !== 'ALL' && health !== filterMode) continue;
      if (q && !lnk.loc.toLowerCase().includes(q) &&
              !lnk.ip.includes(q) &&
              !lnk.isp.toLowerCase().includes(q)) continue;

      const tr = document.createElement('tr');
      tr.className = 'r-' + health;
      tr.innerHTML = `
        <td class="loc">${esc(lnk.loc)}</td>
        <td class="ip">${esc(lnk.ip)}</td>
        <td class="isp">${esc(lnk.isp)}</td>
        <td><span class="tag tag-${health}">${health}</span></td>
        <td class="lat">${esc(lnk.latency)}</td>
        <td class="ts">${esc(lnk.last_ok)}</td>
        <td class="up">${esc(lnk.uptime)}</td>`;
      tbody.appendChild(tr);
      shown++;
    }

    if (shown === 0) {
      const tr = document.createElement('tr');
      tr.innerHTML = `<td colspan="7" style="text-align:center;padding:30px;color:var(--fg2)">No links match the current filter.</td>`;
      tbody.appendChild(tr);
    }
  }

  function esc(s) {
    if (!s) return '—';
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }

  // ── Counts & badges ──────────────────────────────────────────
  function updateCounts(counts) {
    for (const k of ['ALL','OK','WARN','DOWN']) {
      const el = document.getElementById('c-' + k);
      if (el) el.textContent = counts[k] ?? 0;
    }
    document.getElementById('b-ok').textContent   = `OK  ${counts.OK   ?? 0}`;
    document.getElementById('b-warn').textContent = `WARN  ${counts.WARN ?? 0}`;
    document.getElementById('b-down').textContent = `DOWN  ${counts.DOWN ?? 0}`;
  }

  // ── Filter pills ─────────────────────────────────────────────
  function setFilter(mode) {
    filterMode = mode;
    document.querySelectorAll('.pill').forEach(b => {
      b.className = 'pill';
      if (b.dataset.f === mode) b.classList.add('active-' + mode.toLowerCase());
    });
    applyView();
  }

  // ── Connection state ─────────────────────────────────────────
  function setConnected(ok, ts) {
    const dot = document.getElementById('conn-dot');
    const txt = document.getElementById('status-txt');
    dot.className = ok ? '' : 'err';
    if (ok) {
      const counts = {
        ok:   allLinks.filter(l => l.health === 'OK').length,
        warn: allLinks.filter(l => l.health === 'WARN').length,
        down: allLinks.filter(l => l.health === 'DOWN').length,
      };
      txt.textContent = `MONITORING · Total: ${allLinks.length} · OK: ${counts.ok} · Warn: ${counts.warn} · Down: ${counts.down} · Updated: ${ts}`;
    } else {
      txt.textContent = 'Connection lost — retrying…';
    }
  }

  // ── Bootstrap ────────────────────────────────────────────────
  fetchStatus();
</script>
</body>
</html>
"""

# ===========================================================
# CONFIG
# ===========================================================

POLL_INTERVAL  = 2    # seconds between full poll cycles
DROP_THRESHOLD = 4     # consecutive failures → DOWN
TCP_TIMEOUT    = 2.0   # seconds per TCP probe attempt

# Ports tried in order — first one that responds (open OR refused) wins.
# ConnectionRefused = host is UP, just that port is closed.
# Timeout / unreachable = host may be DOWN.
PROBE_PORTS = [80, 443, 22, 8080, 8443, 53, 25, 21]

# ===========================================================
# SITES
# ===========================================================

BASE_SITES = [
    ("Pimpri",        "61.246.171.174",  "AIRTEL"),
    ("Pimpri",        "103.86.182.182",  "PARADISE"),
    ("Pimpri",        "10.0.0.49",       "TTSL"),
    ("SPARCO-1",      "103.86.182.130",  "PARADISE"),
    ("Accont Office", "1.22.231.192",    "TIKONA"),
    ("Accont Office", "103.86.182.94",   "PARADISE"),
    ("SMET CHENNAI",  "113.193.238.213", "TIKONA"),
    ("SMET CHENNAI",  "14.194.143.166",  "TATA"),
    ("SMET CHENNAI",  "10.0.0.53",       "TTSL"),
    ("Pithampur",     "117.248.249.124", "BSNL"),
    ("Pithampur",     "103.101.111.83",  "SHARPLINK"),
    ("SMET CHAKAN",   "1.22.124.46",     "TIKONA"),
    ("SMET CHAKAN",   "103.86.182.75",   "PARADISE"),
    ("SMA-299",       "1.22.124.188",    "TIKONA"),
    ("SMA-299",       "103.86.182.74",   "PARADISE"),
    ("SMA-B16",       "1.22.231.170",    "TIKONA"),
    ("SMA-B16",       "103.139.243.84",  "PARADISE"),
    ("SMA C-45",      "103.139.243.84",  "PARADISE"),
    ("SMA C-45",      "1.22.231.1",      "TIKONA"),
    ("Sawardari",     "103.162.66.158",  "IMPERIUM"),
    ("SMET HOSUR",    "103.237.59.122",  "RMAX"),
]

# ===========================================================
# LINK MODEL
# ===========================================================

class Link:
    def __init__(self, loc: str, ip: str, isp: str):
        self.loc     = loc
        self.ip      = ip
        self.isp     = isp
        self.results = deque(maxlen=DROP_THRESHOLD)
        self.health  = "INIT"
        self.last_ok = "—"
        self.latency = "—"
        self.checks  = 0
        self.success = 0

    @property
    def uptime(self) -> str:
        return "—" if self.checks == 0 else \
               f"{100.0 * self.success / self.checks:.1f}%"

    def to_dict(self) -> dict:
        return {
            "loc":     self.loc,
            "ip":      self.ip,
            "isp":     self.isp,
            "health":  self.health,
            "latency": self.latency,
            "last_ok": self.last_ok,
            "uptime":  self.uptime,
        }

# ===========================================================
# TCP PROBE  (no ICMP / no ping binary required)
# ===========================================================

def _tcp_probe(ip: str) -> tuple:
    """
    Try TCP connect to PROBE_PORTS in order.
    Returns (alive: bool, latency_str: str).

    Why TCP works in cloud containers:
      - ConnectionRefusedError means the host replied → it's UP.
      - A successful connect is obviously UP.
      - Only a timeout or network-unreachable means DOWN.
    """
    for port in PROBE_PORTS:
        t0  = time.perf_counter()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(TCP_TIMEOUT)
        try:
            err = sock.connect_ex((ip, port))
            ms  = (time.perf_counter() - t0) * 1000
            sock.close()
            # err == 0   → connected (port open)
            # err == 111 → ECONNREFUSED on Linux  (port closed, but host replied)
            # err == 10061 → WSAECONNREFUSED on Windows
            if err in (0, 111, 10061):
                return True, f"{ms:.0f} ms"
        except ConnectionRefusedError:
            ms = (time.perf_counter() - t0) * 1000
            sock.close()
            return True, f"{ms:.0f} ms"
        except (socket.timeout, OSError):
            try:
                sock.close()
            except Exception:
                pass
    return False, "—"

# ===========================================================
# MONITOR
# ===========================================================

class Monitor:
    def __init__(self):
        self._lock  = threading.Lock()
        self.links  = [Link(loc, ip, isp) for loc, ip, isp in BASE_SITES]
        t = threading.Thread(target=self._worker, daemon=True)
        t.start()

    def _worker(self):
        while True:
            for lnk in list(self.links):
                threading.Thread(target=self._probe,
                                 args=(lnk,), daemon=True).start()
            time.sleep(POLL_INTERVAL)

    def _probe(self, lnk: Link):
        ok, latency = _tcp_probe(lnk.ip)

        with self._lock:
            lnk.results.append(ok)
            lnk.checks += 1
            if ok:
                lnk.last_ok = _now_ist().strftime("%H:%M:%S")
                lnk.latency = latency
                lnk.success += 1
            else:
                lnk.latency = "—"
            fails      = lnk.results.count(False)
            lnk.health = (
                "DOWN" if fails >= DROP_THRESHOLD else
                "WARN" if fails > 0 else "OK"
            )

    def snapshot(self) -> dict:
        with self._lock:
            links = [l.to_dict() for l in self.links]
        counts = {s: sum(1 for l in links if l["health"] == s)
                  for s in ("OK", "WARN", "DOWN", "INIT")}
        counts["ALL"] = len(links)
        return {
            "links":   links,
            "counts":  counts,
            "updated": _now_ist().strftime("%H:%M:%S"),
        }


# Start monitor when module loads (works with gunicorn --preload)
_monitor = Monitor()

# ===========================================================
# ROUTES
# ===========================================================

@app.route("/")
def index():
    return render_template_string(_INDEX_HTML)


@app.route("/api/status")
def api_status():
    return jsonify(_monitor.snapshot())


# ===========================================================
# ENTRY POINT
# ===========================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, threaded=True)
