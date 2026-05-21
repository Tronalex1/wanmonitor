# WAN Monitoring Dashboard

Real-time WAN link health monitor — Flask web app deployable on [Koyeb](https://koyeb.com).

![Dark dashboard showing 21 ISP links with status, latency and uptime](https://img.shields.io/badge/status-live-22c55e?style=flat-square)

## Features

- **21 ISP links** across all plant locations — polled every 5 seconds
- **Color-coded status**: OK (green) · WARN (amber) · DOWN (red)
- **Live latency** and uptime percentage per link
- **Filter pills** (ALL / OK / WARN / DOWN) + search box
- **Auto-refresh** progress bar — no manual reload needed
- **Connection-lost** indicator if the backend is unreachable

## Project Structure

```
wan-monitor/
├── app.py              # Flask backend + background ping monitor
├── templates/
│   └── index.html      # Single-page dashboard UI
├── requirements.txt
├── Dockerfile
└── .gitignore
```

---

## Local Development

```bash
# 1. Clone
git clone https://github.com/<your-username>/wan-monitor.git
cd wan-monitor

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run
python app.py
# Open http://localhost:5000
```

---

## Deploy on Koyeb

### Step 1 — Push to GitHub

```bash
git init
git add .
git commit -m "initial commit"
git branch -M main
git remote add origin https://github.com/<your-username>/wan-monitor.git
git push -u origin main
```

### Step 2 — Create a Koyeb Service

1. Log in at [app.koyeb.com](https://app.koyeb.com)
2. Click **Create Service → Web Service**
3. Choose **GitHub** as the source
4. Select your `wan-monitor` repository, branch `main`
5. Koyeb auto-detects the **Dockerfile** — no extra config needed
6. Click **Deploy**

Koyeb will:
- Build the Docker image
- Inject `PORT` automatically
- Give you a public URL like `https://wan-monitor-<hash>.koyeb.app`

### Step 3 — Done ✓

Visit your URL. The dashboard starts polling immediately.

---

## Configuration

Edit constants in `app.py`:

| Variable | Default | Description |
|---|---|---|
| `PING_INTERVAL` | `5` | Seconds between poll cycles |
| `DROP_THRESHOLD` | `4` | Consecutive failures before DOWN |
| `PING_TIMEOUT` | `1` | Per-ping timeout in seconds |
| `BASE_SITES` | 21 entries | List of (location, IP, ISP) tuples |

---

## Notes

- **Private IPs** (10.x.x.x) are only reachable if the Koyeb service is on the same private network or VPN.
- **Public IPs** are monitored over the internet from Koyeb's infrastructure.
- The gunicorn config uses `--workers 1 --threads 8` to keep the background monitor thread alive in a single process.
