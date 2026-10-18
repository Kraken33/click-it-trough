# TikTok iOS Automation & Account Warming Suite

A high-fidelity automation and account warming system running on **macOS** that emulates organic human behavior on a physical **iPhone** connected via USB.

Powered by Apple's **WebDriverAgent (WDA)**, hardware-accelerated **Apple Vision OCR**, and a real-time **React + TypeScript Web Dashboard**.

---

## ✨ Features

- **📱 Physical iPhone Emulation**: Direct control of the genuine TikTok iOS app over USB using Apple's XCTest framework (WebDriverAgent).
- **🖐️ Biometric Gesture Physics**:
  - Cubic Bézier thumb arc trajectories matching natural human hand geometry (right/left-handed pivots).
  - Ease-in / ease-out non-linear velocity curves with natural spring-damper deceleration.
  - Micro-jitter & tremor injection to defeat anti-bot velocity analysis.
  - Alternating double-tap likes vs. heart icon taps.
  - Occasional re-watch swipe-backs (~4%) and micro-flicks (~3%).
- **👁️ Native Apple Vision OCR & Intelligence**:
  - Instant text recognition of video captions, usernames, and `#hashtags` without external binary dependencies.
  - **Niche Keyword Weighting**: Dynamically increases dwell time (2.2x) and like probability on content matching target keywords.
  - **Search Seeding**: Automatically seeds TikTok's algorithm by searching target queries and browsing results before FYP warming.
  - **Ad & LIVE Filter**: Detects and fast-skips sponsored posts and LIVE broadcasts.
  - **Popup Dismissal**: Automatically closes system and in-app modal interruptions.
- **🛡️ Safety Sentinel**:
  - Scans for interactive captchas, puzzles, or verification challenges.
  - Automatically halts automation, takes a high-res screenshot, triggers a macOS audio tone (`afplay`), and sends a native macOS notification.
- **🕒 Autonomous Daily Scheduler**:
  - Simulates natural daily phone usage: 3 daily sessions (Morning, Lunch, Evening) with randomized start jitter (±20 mins) and duration variations.
- **💻 Modern React + TypeScript Web Dashboard**:
  - Real-time iPhone screen mirroring over WebSockets (~3 FPS).
  - Live session telemetry (videos watched, likes given, bookmarks, niche match rate).
  - Interactive sliders for dwell times, like rates, and niche tag configuration.
  - One-click control buttons (Start, Pause, Resume, Stop, Skip Video Now).

---

## 🚀 Quick Start Guide

### 1. Requirements
- **Host**: MacBook running macOS (Apple Silicon or Intel).
- **Device**: iPhone with TikTok installed and connected via USB.
- **Tools**: Xcode installed on macOS, Python 3.10+, and Node.js 18+.

### 2. Environment Setup
The Python virtual environment and frontend are already installed. To activate:

```bash
# 1. Activate Python virtual environment
source .venv/bin/activate

# 2. Run system diagnostics
python3 -m src.main doctor
```

---

### 3. iPhone & WebDriverAgent Setup (One-Time)

To control your iPhone from your Mac, WebDriverAgentRunner needs to be signed with your free Apple ID:

1. **Enable Developer Mode on iPhone**:
   - On your iPhone: **Settings** → **Privacy & Security** → **Developer Mode** → Turn **ON** (reboot required).
2. **Connect iPhone via USB**:
   - Plug into your Mac, unlock the screen, and tap **"Trust This Computer"**.
3. **Bootstrap WebDriverAgent**:
   ```bash
   ./scripts/bootstrap_wda.sh
   ```
   - Open `WebDriverAgent/WebDriverAgent.xcodeproj` in Xcode.
   - Under `Signing & Capabilities`, choose your Personal Apple ID Team.
   - Build and run `WebDriverAgentRunner` on your connected iPhone.
4. **Start the USB Tunnel**:
   ```bash
   ./scripts/start_tunnel.sh
   ```
   *This forwards device port 8100 to `localhost:8100` via USB.*

---

### 4. Launching the Web Dashboard

```bash
source .venv/bin/activate
python3 -m src.main serve
```

Open your browser to:
👉 **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

You will see:
- The live phone screen mirror and active status overlay.
- Real-time counters for likes, bookmarks, and niche match rate.
- Interactive controls to start warming sessions, adjust dwell times, and customize niche keywords.

---

### 5. CLI Commands

You can also run all actions directly from the command line:

```bash
# Run system diagnostic checks
python3 -m src.main doctor

# Test biometric swipe and double-tap like on your phone
python3 -m src.main test-touch

# Run a headless 20-minute warming session directly in terminal
python3 -m src.main warm --duration 20
```

---

### 6. Configuration (`config/default_config.yaml`)

Customize all behavior in `config/default_config.yaml` or directly from the Web Dashboard:

| Parameter | Default | Description |
|---|---|---|
| `niche.target_keywords` | `["code", "ai", "tech", ...]` | Keywords to detect in captions and boost dwell/likes |
| `niche.seed_terms` | `["tech news", "ai tools", ...]` | Search queries executed at session start |
| `dwell_time.min_seconds` | `3.5` | Minimum watch time per video |
| `dwell_time.max_seconds` | `40.0` | Maximum watch time per video |
| `dwell_time.niche_match_multiplier` | `2.2` | Dwell duration multiplier for matching niche videos |
| `probabilities.like_base` | `0.10` (10%) | Probability of liking random FYP content |
| `probabilities.like_niche` | `0.40` (40%) | Probability of liking niche-matched content |
| `probabilities.double_tap_ratio` | `0.75` (75%) | Ratio of double-tap likes vs tapping the heart icon |
| `safety.max_daily_videos` | `150` | Maximum videos scrolled per day |
| `safety.max_daily_likes` | `35` | Maximum likes given per day |

---

## 📁 Project Structure

```
click-it-though/
├── config/
│   └── default_config.yaml         # Configuration parameters & schedules
├── scripts/
│   ├── bootstrap_wda.sh            # WDA clone and Xcode setup guide
│   └── start_tunnel.sh             # USB port-forwarding runner (pymobiledevice3)
├── frontend/                       # React + TypeScript + Vite Web Dashboard
│   ├── src/
│   │   ├── App.tsx                 # Main dashboard UI
│   │   ├── index.css               # Tailwind CSS theme
│   │   └── main.tsx
│   ├── dist/                       # Built static bundle served by FastAPI
│   ├── package.json
│   └── vite.config.ts
├── src/
│   ├── bridge/
│   │   ├── wda_client.py           # HTTP client communicating with WDA
│   │   └── device_manager.py       # USB detection & screen capture
│   ├── physics/
│   │   └── gesture.py              # Biometric Bézier curves & thumb kinematics
│   ├── vision/
│   │   ├── ocr.py                  # Hardware-accelerated Apple Vision OCR
│   │   └── detector.py             # Ad, LIVE, popup, and captcha recognition
│   ├── engine/
│   │   ├── session_runner.py       # FYP loop, dwell timing, interaction decisions
│   │   ├── niche_trainer.py        # Search-seeding & keyword weighting
│   │   └── scheduler.py            # Daily routine scheduler with time jitter
│   ├── safety/
│   │   └── alert.py                # macOS audio & system notification alerts
│   ├── web/
│   │   └── app.py                  # FastAPI web server & WebSocket broadcaster
│   └── main.py                     # Typer CLI application
├── requirements.txt
└── README.md
```
