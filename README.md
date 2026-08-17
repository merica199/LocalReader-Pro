# LocalReader Pro

**A modern, privacy-focused PDF/EPUB reader with AI-powered text-to-speech, multilingual support, and smart audio caching.**

> **This is a fork** of [revisionhiep-create/LocalReader-Pro](https://github.com/revisionhiep-create/LocalReader-Pro),
> maintained by [@merica199](https://github.com/merica199). It adds macOS support and a
> voice preview, and corrects documented values that had drifted from the code.
> See [Changes in this fork](#-changes-in-this-fork) for the full list and
> [MACOS-SETUP.md](MACOS-SETUP.md) for the macOS installation layout.

<div align="center">
  <img src="docs/images/image1.png" alt="LocalReader Pro Main Interface" width="85%">
  <br><br>
  <img src="docs/images/image2.png" alt="LocalReader Pro Settings" width="85%">
</div>

---

## 🔘 Key Features

### 🔳 Core Reading

- **Multi-Format Support:** PDF and EPUB files
- **Multilingual UI:** Full interface translation (**English, French, Spanish, Chinese**)
- **Dual-Model Architecture:** Choose between the quantized model (88 MB) and the full FP32 model (~309 MB). Note that the UI labels these "CPU" and "GPU", but the label refers to the *model file*, not the hardware — `kokoro_onnx` pins `CPUExecutionProvider` unless the Windows/Linux-only `onnxruntime-gpu` package is installed, so both run on the CPU
- **Fast TTS Engine:** Kokoro-82M v1.0. Synthesis speed is hardware-dependent — measured at ~2.3x real-time with the quantized model on an Apple Silicon Mac
- **Auto-Save Progress:** Resume exactly where you left off
- **Sentence-Level Control:** Click any sentence to start reading from there

### 🔘 Smart TTS Controls

- **Dynamic Voice Library:** Automatically loads voices for **English (US/UK), French, Spanish, Chinese, Japanese, Italian, and Portuguese**.
- **Voice Preview:** Play a short sample of any voice from the dropdown before committing to it. Samples are rendered on first use and cached, so repeats are instant
- **Voice Settings Drawer:** Floating button for quick access to voice, speed, and filter controls
- **Player Text Customization:** New **Text Size Slider** to adjust subtitle/caption size (12px-24px) in real-time.
- **Decoupled Browsing:** Browse other pages freely without jumping the audio. A "Back to Reading" button lets you snap back instantly.
- **Natural Speech Flow:** Intelligent line joining prevents mid-sentence stops
- **Smart Punctuation Logic:**
  - Supports English (`...`, `?!`) and CJK (`。`, `！`, `？`) punctuation correctly.
  - Smart "Soft Newlines" prevent rushing without creating double pauses.
- **Custom Pause Settings:** Granular control over pause duration for punctuation (0-2000ms).
- **Custom Pronunciation Rules:** Fix mispronunciations with RegEx support.
- **Speed Control:** 0.5x to 3.0x playback speed.

### ⚙️ Smart Features

- **Smart Start:** Auto-skip blank/cover pages on first open
- **Header/Footer Filter:** Detect and remove/dim repeated page clutter
- **Global Search:** Full-book search with instant navigation (Ctrl+F)
- **SQLite Audio Cache:** 200MB LRU cache with automatic cleanup (Self-healing).

### 📁 MP3 Export

- **One-Click Export:** Convert entire document to MP3
- **Background Processing:** UI stays responsive during export
- **FFMPEG Handling:** On Windows, auto-downloads the encoder (~100MB) on first export. On macOS and Linux, uses the system-installed `ffmpeg` from `PATH` — the bundled download is a Windows build and is not used there
- **Export is a batch job, not playback:** reading synthesizes one sentence at a time on demand and starts immediately, but export renders the whole document up front. Budget roughly (audiobook length ÷ synthesis speed) — check the estimate the app shows before confirming

### 🔘 Sleep Timer

- **Auto-Shutdown:** Automatically closes the application after a set duration.
- **Visual Feedback:** Button displays remaining time in a neutral style when active.
- **Background Safe:** Timer runs on the backend to guarantee shutdown.

---

## 🔳 Installation

### Windows (Recommended)

**One-Click Installer - No Manual Setup Required**

1. **Extract the ZIP** to your desired location
2. **Navigate to the `dist` folder**
3. **Double-click:** `setup.exe`
4. **Approve UAC Prompt** when Windows requests administrator access
5. **Wait for Installation:**
   - Checks for Python 3.12+ (downloads and installs if missing)
   - Deploys application files
   - Installs all dependencies automatically
   - Creates Desktop and Start Menu shortcuts
6. **Launch:** Double-click "LocalReader Pro" on your Desktop

**What the installer does:**

- ✅ Installs Python 3.12 if not present
- ✅ Installs all required packages (FastAPI, PyTorch, Kokoro-TTS, etc.)
- ✅ Creates shortcuts on Desktop and Start Menu
- ✅ Sets up the application in the selected directory

**Uninstalling:**

- Run `uninstall.exe` in the installation directory
- Removes all shortcuts (application files remain for manual deletion)

To completely remove the supporting software (Python and Libraries):

**Uninstall Python**: Go to Windows Settings > Apps > Installed Apps, search for "Python 3.12", and select Uninstall.

**Remove Libraries**: If you haven't deleted the folder yet, open a terminal in the "dist" folder and run: `pip uninstall -r requirements.txt`

**Clear Model Cache**: Many voices and AI models are stored in your user profile. You can delete the `.cache` folder in your user directory (usually `C:\Users\<YourName>\.cache\kokoro`) to free up additional space.

**Installation Size:**

- Installer: ~24 MB
- Full installation: ~2.6 GB (including Python dependencies)

---

### macOS

The Windows installer (`setup.exe`), uninstaller, and `launch.vbs` do not apply
on macOS. Install manually:

```bash
brew install python@3.12 ffmpeg

git clone https://github.com/merica199/LocalReader-Pro.git
cd LocalReader-Pro

python3.12 -m venv venv
./venv/bin/pip install -r dist/requirements.txt

cd dist && ../venv/bin/python main.py
```

`ffmpeg` is only needed for MP3 export, and comes from Homebrew rather than the
in-app download, which fetches a Windows build. Everything else, including the
voice models, is fetched by the app on first run.

To run it as a normal double-clickable application with your data stored in
`~/Library/Application Support` rather than inside the project, see
**[MACOS-SETUP.md](MACOS-SETUP.md)** — it documents the `.app` bundle layout,
where every file lives, and the macOS-specific launch pitfalls.

---

### Linux / Manual Installation

**Prerequisites:** Python 3.10 - 3.13 (Recommended: Python 3.12)

> ⚠️ **Important:** Python 3.14+ is not yet supported due to `onnxruntime` compatibility.

**Step 1: Install Python**

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3.12 python3.12-pip python3.12-venv

# Verify installation
python3.12 --version
```

**Step 2: Extract and Navigate**

```bash
unzip LocalReader_Pro_v2.5.zip
cd LocalReader_Pro_v2.5/dist
```

**Step 3: Install Dependencies**

```bash
# Option A: Using pip
pip install -r requirements.txt

# Option B: Using python -m pip (if pip not in PATH)
python3.12 -m pip install -r requirements.txt
```

This will install:

- FastAPI (web framework)
- uvicorn (web server)
- torch (PyTorch for ML)
- kokoro-onnx (TTS engine)
- pydub (audio processing)
- pywebview (desktop wrapper)
- And other dependencies

**Installation time:** 5-10 minutes (downloading PyTorch ~2GB)

**Step 4: Launch the App**

```bash
python3.12 main.py
```

---

## 🔘 First-Time Setup

After launching the application:

1. **Choose Your Engine Mode:**

   - Open **Settings** section in sidebar
   - Find **"Processing Mode"** dropdown
   - Choose between:
     - **High Performance (CPU):** Faster, lower RAM (~87MB model)
     - **High Quality (GPU):** Best audio quality (~309MB model)

2. **Download Voice Engine:**

   - Click **"Setup Voice Engine"** button in sidebar
   - Downloads the model matching your selected mode
   - Wait for green status indicator (⚪ → 🔘)
   - **Tip:** You can download both models and switch anytime!

3. **Upload Your First Book:**

   - Click **"Upload Book (PDF/EPUB)"**
   - Select any PDF or EPUB file
   - App will process and display the book

4. **Start Reading:**

   - Click the blue **Play** button
   - Or press `Space` to play/pause

5. **First MP3 Export (Optional):**
   - Click **"Export Audio (MP3)"** in sidebar
   - Prompt appears: "Download FFMPEG encoder (~100MB)"
   - Click **"Download FFMPEG"** and wait ~2-3 minutes
   - Export starts automatically after download
   - Subsequent exports skip this step

---

## 🔘 Usage Guide

### Basic Reading

- **Navigate Pages:** Use buttons (◀ ▶) or scroll to bottom/top for auto-flip
- **Play Audio:** Press `Space` or click play button
- **Jump to Sentence:** Click any sentence in the text
- **Change Voice:** Use dropdown in sidebar settings
- **Adjust Speed:** Drag speed slider (0.5x - 3.0x)

### Smart Features

**Smart Start:**

- Automatically activates on first open
- Finds first page with >500 characters
- Shows notification: "🔘 Skipped to start of content (Page X)"

**Header/Footer Filter:**

1. Open **Settings** section in sidebar
2. Find **"Header/Footer Filter"** dropdown
3. Choose: **Off**, **Clean** (remove), or **Dim** (show faded)
4. TTS skips filtered content in all modes

**Global Search:**

1. Press `Ctrl+F` (or `Cmd+F` on Mac)
2. Type query (minimum 2 characters)
3. Click any result to jump to that page
4. Press `ESC` to close

### Custom Pronunciation Rules

1. Click **"Pronunciation"** tab in sidebar
2. Click **+** button to add rule
3. Configure:
   - **Original Text:** The text to replace (e.g., "SQL")
   - **Replacement Text:** How to pronounce (e.g., "S Q L")
4. Options:
   - ☑️ **Match Case:** "SQL" ≠ "sql"
   - ☑️ **Whole Word:** "cat" won't match "category"
   - ☑️ **Use Pattern Matching:** Enable RegEx

**Example Rules:**

- `ChatGPT` → `Chat G P T` (spell out)
- `COVID-19` → `COVID nineteen` (pronounce naturally)

### Custom Pause Settings

1. Open **"Pause Settings"** section in sidebar
2. Adjust sliders to set pause duration (0-2000ms):
   - **Comma (,)** - Default: 300ms
   - **Period (.)** - Default: 600ms
   - **Question (?)** - Default: 600ms
   - **Exclamation (!)** - Default: 600ms
   - **Colon (:)** - Default: 400ms
   - **Semicolon (;)** - Default: 400ms
   - **Newline** - Default: 0ms (Hidden; soft-newline handling adds ~300ms where appropriate)

   Defaults are defined in `dist/app/ui/js/modules/state.js`. They are only
   applied when no `pause_settings` block has been saved yet — once a slider is
   touched, the saved values in `userdata/settings.json` take over.
3. Settings save automatically

**Smart Behavior:**

- Pauses apply only to single punctuation or the last char of a group
- `"..."` creates ONE pause (e.g. 600ms), not three
- `"?!` creates ONE pause (based on `!`)
- `Title\n` creates a soft pause (300ms)

### Exporting to MP3

1. Open any PDF/EPUB document
2. Click **"Export Audio (MP3)"** button
3. Review time estimate (e.g., "~3 minutes")
4. Confirm export
5. Monitor real-time progress
6. Click **"📂 Open Folder"** to access file

**Export Details:**

- **Format:** MP3, 192 kbps
- **Naming:** `{document_name}_{voice_name}.mp3`
- **Location:** `userdata/` folder in project directory
- **Speed:** ~15 seconds per 1,000 characters

### Sleep Timer

1. Click the **Timer Icon** (clock) on the right side of the screen.
2. Set the desired duration in **Hours** and **Minutes**.
3. Click **"Start Timer"**.
4. The drawer will show a countdown, and the main button will display the remaining minutes.
5. The application will automatically close when the timer reaches zero.

---

## 🔳 Keyboard Shortcuts

| Key                | Action            |
| ------------------ | ----------------- |
| `Space`            | Play/Pause        |
| `←`                | Previous Sentence |
| `→`                | Next Sentence     |
| `Ctrl+F` / `Cmd+F` | Open Search       |
| `ESC`              | Close Search      |

---

## ⚙️ Technical Details

### Architecture

| Layer               | Technology                        |
| ------------------- | --------------------------------- |
| **Frontend**        | Vanilla JavaScript + Tailwind CSS |
| **Backend**         | FastAPI (Python)                  |
| **TTS Engine**      | Kokoro-82M (ONNX Runtime)         |
| **Desktop Wrapper** | pywebview                         |
| **PDF Parsing**     | PDF.js (Mozilla)                  |
| **Audio Export**    | pydub + FFMPEG                    |
| **EPUB Support**    | ebooklib + xhtml2pdf              |

### File Structure

```
LocalReader-Pro/
├── build_installer.py           # Master build script
├── installer_logic.py           # setup.exe core logic
├── README.md
├── CHANGELOG.md
│
└── dist/
    ├── setup.exe                # One-click installer (~22 MB)
    ├── main.py                  # App entry point (FastAPI + WebView)
    ├── launch.vbs               # Silent runner
    │
    ├── app/
    │   ├── server.py            # FastAPI initialization
    │   ├── state.py             # Global engine/status singleton
    │   ├── routers/             # API Controllers (TTS, Library, Export, etc.)
    │   ├── logic/               # Core logic (Normalize, Detector, Cache)
    │   ├── locales/             # UI Translations (EN, ES, FR, ZH, JA)
    │   └── ui/
    │       ├── index.html       # Main SPA
    │       ├── css/style.css    # Premium styling
    │       └── js/modules/      # ES6 Logic modules
    │
    └── userdata/                # User settings and book database
```

**Additional folders created during use:**

- `bin/` - FFMPEG binaries (auto-downloaded on first export)
- `models/` - TTS engine models (auto-downloaded based on your choice)
- `userdata/audio_cache.db` - SQLite Audio Cache

### Storage Requirements

| Component                 | Size                       |
| ------------------------- | -------------------------- |
| **Installer**             | ~22 MB                     |
| **App Files**             | ~10 MB                     |
| **Python Dependencies**   | ~2 GB (PyTorch, etc.)      |
| **TTS Engine (GPU Mode)** | ~309 MB                    |
| **TTS Engine (CPU Mode)** | ~87 MB                     |
| **Voice Pack (shared)**   | ~30 MB                     |
| **FFMPEG**                | ~100 MB (optional)         |
| **Audio Cache (SQLite)**  | ~200 MB max (auto-managed) |
| **Per Document Cache**    | ~1-5 MB                    |
| **Exported MP3**          | ~1 MB per minute of audio  |

**Total (GPU Mode):** ~2.6 GB (without exported audio)  
**Total (CPU Mode):** ~2.4 GB (saves ~220MB)  
**Total (Both Engines):** ~2.8 GB (maximum flexibility)

### System Requirements

| Component      | Minimum                                     | Recommended                             |
| -------------- | ------------------------------------------- | --------------------------------------- |
| **OS**         | Windows 10+ / Ubuntu 20.04+ / macOS 11+     | Windows 11 / Ubuntu 22.04+ / macOS 14+  |
| **Python**     | 3.10 - 3.13                 | 3.12.10                    |
| **RAM**        | 4 GB                        | 8 GB+                      |
| **Disk Space** | 3 GB free                   | 5 GB+ free                 |
| **CPU**        | Dual-core 2.0 GHz           | Quad-core 2.5 GHz+         |
| **Internet**   | Required for setup only     | Offline after setup        |

---

## 🔘 Privacy & Security

### Data Storage

- **100% Local:** All documents, settings, and exports stored on your machine
- **No Cloud:** Zero data sent to external servers
- **No Accounts:** No login, no sign-up, no user tracking

### Network Usage

- **Setup Only:** Internet required for:
  1. Downloading Python (Windows installer only, ~100 MB)
  2. Installing dependencies (~2 GB)
  3. Downloading Kokoro-82M model (~309 MB)
  4. Downloading FFMPEG (~100 MB, optional)
- **Fully Offline:** After setup, works without internet indefinitely

### Analytics & Telemetry

- **Zero Tracking:** No analytics, no usage stats, no crash reports
- **No Cookies:** Web UI runs locally
- **No Logs:** App doesn't phone home

### File Access

- **Read-Only Documents:** PDFs/EPUBs are only read (never modified)
- **Writable Folders:** Only `userdata/`, `models/`, `bin/`, and `.cache/`
- **No Background Access:** App closes completely when you exit

---

## 🔀 Changes in this fork

Everything below is specific to [merica199/LocalReader-Pro](https://github.com/merica199/LocalReader-Pro)
and is not in upstream.

### Added

- **Voice preview.** A play button beside the voice dropdown renders a short
  sample of the selected voice via `GET /api/voices/preview/{voice_id}` and
  caches the WAV under `userdata/voice_previews/`. First request per voice takes
  roughly 2.5s; later ones are served from disk in about 0.15s. Every voice in a
  language reads the same sentence so they can be compared directly.
- **macOS support.** See [MACOS-SETUP.md](MACOS-SETUP.md) for the `.app` bundle
  layout, where each file lives, and the platform-specific launch pitfalls.

### Fixed

- **Missing dependencies.** `psutil` is imported by `app/server.py` but was never
  declared, so a clean install failed on first launch. On Python 3.13, `pydub`
  additionally needs `audioop-lts`, because PEP 594 removed the stdlib `audioop`
  module and pydub's fallback imports `pyaudioop`, which does not exist on PyPI.
  `audioop-lts` requires Python 3.13+, so it is gated behind an environment
  marker rather than breaking installs on 3.10–3.12.
  *(Also open upstream as [PR #9](https://github.com/revisionhiep-create/LocalReader-Pro/pull/9).)*
- **Windows-only FFmpeg.** Binary paths were hardcoded to `.exe`, the installer
  downloaded a Windows build that cannot run elsewhere, and nothing consulted
  `PATH`. Binaries now resolve per platform and fall back to a system-managed
  install. *(Also open upstream as [PR #10](https://github.com/revisionhiep-create/LocalReader-Pro/pull/10).)*
- **FFmpeg reported as missing when present.** `ffmpeg_status["is_installed"]`
  defaulted to `False` and was only ever set by the installer, so an existing
  FFmpeg — including a bundled `bin/ffmpeg.exe` on Windows — was reported
  missing and the UI kept offering an unnecessary download. It is now detected
  once at startup. This one affected Windows too.

### Corrected in documentation

- Four of the seven documented pause defaults did not match
  `dist/app/ui/js/modules/state.js`: comma (250 → 300ms), colon (500 → 400ms),
  semicolon (500 → 400ms), and newline (800 → 0ms).
- The "~5x real-time synthesis" claim is hardware-dependent. Measured ~2.3x with
  the quantized model on an Apple Silicon Mac.
- The "GPU" engine mode selects a *model file*, not an execution device. Both
  modes run on the CPU unless the Windows/Linux-only `onnxruntime-gpu` package is
  installed, because `kokoro_onnx` otherwise pins `CPUExecutionProvider`. Forcing
  `CoreMLExecutionProvider` on Apple Silicon measured within noise of CPU
  (2.34x vs 2.26x), so there is nothing to gain there.

---

## 🔳 License

### LocalReader Pro

- **Code:** Proprietary (review, modify, use personally)
- **Redistribution:** Contact author for permission

> **Note on this fork.** The upstream repository has no `LICENSE` file; this
> section is the only license statement, and it reserves redistribution to the
> original author. This fork exists under GitHub's Terms of Service, which grant
> the right to fork and view public repositories on GitHub, and the changes here
> are personal modifications of the kind the statement above permits. It is
> **not** relicensed, and nothing here grants redistribution rights the upstream
> author has not given. If you want to use this beyond personal use, ask
> [@revisionhiep-create](https://github.com/revisionhiep-create).

### Third-Party Components

| Component        | License      |
| ---------------- | ------------ |
| **Kokoro-82M**   | Apache 2.0   |
| **FastAPI**      | MIT          |
| **PyTorch**      | BSD-3-Clause |
| **PDF.js**       | Apache 2.0   |
| **Tailwind CSS** | MIT          |
| **Lucide Icons** | ISC          |
| **FFMPEG**       | LGPL 2.1+    |

---

## ⚪ Credits

### Core Technologies

- **TTS Engine:** [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) by hexgrad
- **PDF Rendering:** [PDF.js](https://mozilla.github.io/pdf.js/) by Mozilla
- **UI Framework:** [Tailwind CSS](https://tailwindcss.com/)
- **Icons:** [Lucide](https://lucide.dev/)
- **Audio Processing:** [FFMPEG](https://ffmpeg.org/)

### Python Libraries

- FastAPI, uvicorn, torch, onnxruntime, pydub, soundfile, pywebview, ebooklib, beautifulsoup4, and more (see `requirements.txt`)

---

## 🔘 Support

### Found a Bug?

1. Check **Troubleshooting** section above
2. Verify you're on latest version (v2.5.0)
3. Check `CHANGELOG.md` for known issues
4. Contact developer with:
   - Python version (`python --version`)
   - Error message or screenshot
   - Steps to reproduce

### Feature Requests

- Review `CHANGELOG.md` to see if already implemented
- Describe use case and expected behavior
- Provide examples or mockups if applicable

---

**Version:** 3.5.0 (The "Explorer" Update)
**Engine:** Kokoro-82M (Dual-Mode: CPU/GPU)
**Last Updated:** January 6, 2026
**Status:** 🔘 Stable Release

---

**Enjoy your reading! 🔳⚪**
