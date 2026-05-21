"""
WAN Monitoring Dashboard — Web Edition
Flask backend: pings all ISP links in background threads,
exposes /api/status for the dashboard to poll every 3 s.
"""

import os
import re
import platform
import subprocess
import threading
import time
from collections import deque
from datetime import datetime

from flask import Flask, jsonify, render_template

app = Flask(__name__)

# ===========================================================
# CONFIG
# ===========================================================

PING_INTERVAL  = 5      # seconds between full poll cycles
DROP_THRESHOLD = 4      # consecutive failures → DOWN
PING_TIMEOUT   = 1      # seconds per ping attempt

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
# MONITOR
# ===========================================================

def _ping_cmd(ip: str) -> list:
    """Return OS-appropriate ping command."""
    if platform.system() == "Windows":
        return ["ping", "-n", "1", "-w", str(PING_TIMEOUT * 1000), ip]
    return ["ping", "-c", "1", "-W", str(PING_TIMEOUT), ip]


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
            time.sleep(PING_INTERVAL)

    def _probe(self, lnk: Link):
        try:
            r = subprocess.run(
                _ping_cmd(lnk.ip),
                capture_output=True, text=True, timeout=PING_TIMEOUT + 1
            )
            m  = re.search(r"time[=<]\s*([\d.]+)", r.stdout)
            ok = bool(m)
        except Exception:
            ok = False
            m  = None

        with self._lock:
            lnk.results.append(ok)
            lnk.checks += 1
            if ok:
                lnk.last_ok = datetime.now().strftime("%H:%M:%S")
                lnk.latency = f"{float(m.group(1)):.0f} ms"
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
            "updated": datetime.now().strftime("%H:%M:%S"),
        }


# Start monitor when module loads (works with gunicorn --preload)
_monitor = Monitor()

# ===========================================================
# ROUTES
# ===========================================================

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def api_status():
    return jsonify(_monitor.snapshot())


# ===========================================================
# ENTRY POINT
# ===========================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, threaded=True)
