# LocalReader Pro

**A modern, privacy-focused PDF/EPUB reader with AI-powered text-to-speech, multilingual support, and smart audio caching.**

> **Based on** [LocalReader Pro](https://github.com/revisionhiep-create/LocalReader-Pro) by
> revisionhiep-create, and maintained separately by [@merica199](https://github.com/merica199).
> This version adds one-click installers for Mac and Windows with in-app updates, sleep
> recordings, and a voice preview, and corrects documented values that had drifted from
> the code. See [Changes from the original](#-changes-from-the-original) for the full list.
>
> **To install:** on Windows, **Code > Download ZIP**, extract it, and double-click
> **`Install on Windows.bat`**. On a Mac, clone this repository and double-click
> **`Install on Mac.command`**. Details in [Installation](#-installation).

<div align="center">
  <img src="docs/images/image1.png" alt="LocalReader Pro Main Interface" width="85%">
  <br><br>
  <img src="docs/images/image2.png" alt="LocalReader Pro Settings" width="85%">
</div>

---

## 🔘 Key Features

### 🔳 Core Reading

- **Multi-Format Support:** PDF, EPUB, Markdown and plain text files
- **Multilingual UI:** Full interface translation (**English, French, Spanish, Chinese**)
- **Dual-Model Architecture:** Choose between the quantized model (88 MB) and the full FP32 model (~309 MB). Note that the UI labels these "CPU" and "GPU", but the label refers to the *model file*, not the hardware: `kokoro_onnx` pins `CPUExecutionProvider` unless the Windows/Linux-only `onnxruntime-gpu` package is installed, so both run on the CPU
- **Fast TTS Engine:** Kokoro-82M v1.0. Synthesis speed is hardware-dependent, measured at ~2.3x real-time with the quantized model on an Apple Silicon Mac
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
- **FFMPEG Handling:** On Windows, auto-downloads the encoder (~100MB) on first export. On macOS and Linux, uses the system-installed `ffmpeg` from `PATH`; the bundled download is a Windows build and is not used there
- **Export is a batch job, not playback:** reading synthesizes one sentence at a time on demand and starts immediately, but export renders the whole document up front. Budget roughly (audiobook length ÷ synthesis speed), and check the estimate the app shows before confirming

### 🔘 Sleep Timer

- **Auto-Shutdown:** Automatically closes the application after a set duration.
- **Visual Feedback:** Button displays remaining time in a neutral style when active.
- **Background Safe:** Timer runs on the backend to guarantee shutdown.

---

## 🔳 Installation

Download the repository, then double-click the installer for your computer:

| Computer | Double-click | The app goes to |
|---|---|---|
| **Mac** | `Install on Mac.command` | `/Applications/LocalReader Pro.app` |
| **Windows** | `Install on Windows.bat` | `%LOCALAPPDATA%\Programs\LocalReader Pro`, with Start Menu and Desktop shortcuts |
| **Linux** | not yet: `Install on Linux.sh` is a placeholder | see [Linux (manual)](#linux-manual) |

**On Windows**, the ZIP is enough, with no command line:

1. On the GitHub page, click **Code > Download ZIP**.
2. Right-click the downloaded ZIP and choose **Extract All**. (Opening the installer
   from inside the ZIP without extracting it does not work, and it says so.)
3. In the extracted folder, double-click **Install on Windows**. If Windows says it
   protected your PC, since the file came from the internet, click **More info**, then
   **Run anyway**.

The installer then downloads the app itself from GitHub, at its newest version, as a
git clone, which is what lets it update. A clone works too, and installs the clone's
own version.

**On a Mac**, clone it (a ZIP is refused there, since the installed app updates itself
through git):

```bash
git clone https://github.com/merica199/LocalReader-Pro.git
```

The installer sets up everything the app needs: Python 3.12, the app's libraries in a
private environment, FFmpeg for MP3 export, and the voice model (about 115 MB). A first
install takes several minutes, mostly downloads. Afterwards the downloaded folder is no
longer needed and can be deleted.

Your library and settings are kept outside the app, so updating, reinstalling or
uninstalling never touches them:

- **Mac:** `~/Library/Application Support/LocalReader Pro`
- **Windows:** `%APPDATA%\LocalReader Pro`

### Updating

In the app: **Check for Updates** in the menus (the **LocalReader Pro** menu on a Mac,
**Help** on Windows), or **Settings > Updates**. It goes online when you ask (or, if you tick **Check automatically**, when the
app opens and once a day, showing an **Update available** button when there is one),
shows what changed, and on your OK closes the app, installs the update and opens it again. An update that cannot install its libraries
leaves the app as it was. Running the installer again from a newer clone, or from any
downloaded ZIP on Windows, also updates.

### Uninstalling

- **Mac:** drag LocalReader Pro from Applications to the Trash. To remove your library
  too, delete `~/Library/Application Support/LocalReader Pro`.
- **Windows:** Settings > Apps > LocalReader Pro > Uninstall. It asks before deleting
  your library (the default is to keep it). Python stays as its own entry in Settings >
  Apps, to remove separately if nothing else uses it.

### What the installers need

- **Mac:** macOS 11 or later and Homebrew, which the installer offers to install if it is
  missing (Homebrew asks for your Mac password once). Git comes with Apple's command line
  tools, which cloning already required.
- **Windows:** Windows 10 or 11, 64-bit. No administrator password for the app: Python
  is installed for your Windows user only, from python.org, and checked against
  python.org's published fingerprint before it runs. Git is installed through winget if
  it is missing, and Windows asks permission for that one.

Each installer describes every step at the top of its script
([installers/mac/install.sh](installers/mac/install.sh),
[installers/windows/install.ps1](installers/windows/install.ps1)), and running one again
is safe: it repairs what is missing and never deletes your library.

### Linux (manual)

There is no one-click installer for Linux yet
([installers/linux/README.md](installers/linux/README.md) lists what one needs). By hand:

```bash
# Debian/Ubuntu: Python 3.12, FFmpeg, and the GTK WebKit pywebview draws with
sudo apt install python3.12 python3.12-venv ffmpeg python3-gi gir1.2-webkit2-4.1

git clone https://github.com/merica199/LocalReader-Pro.git
cd LocalReader-Pro
python3.12 -m venv --system-site-packages venv
./venv/bin/pip install -r dist/requirements.txt

cd dist && ../venv/bin/python main.py
```

The app downloads the voice model on first run (**Setup Voice Engine** in the sidebar).

---

## 🔘 Using the app

The [user guide](docs/user-guide.md) covers every feature: the library,
reading, voices, pronunciation, exporting, sleep recordings, the sleep timer,
updates, and troubleshooting, including the app's known issues. Every setting,
with its default, range and exactly what it affects, is in the
[settings reference](docs/settings-reference.md).

Writing text for the app to read, and sleep scripts in particular, is covered
in [writing for read-aloud](docs/writing-for-read-aloud.md) and
[writing sleep scripts](docs/writing-sleep-scripts.md).

**Quick start:** click **Upload Book** (or drop a file on the window), click
the document in the library, and press play. Space plays and pauses, the left
and right arrows move a sentence, and Ctrl+F (Cmd+F) searches.

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
├── Install on Mac.command       # Double-click to install on a Mac
├── Install on Windows.bat       # Double-click to install on Windows
├── Install on Linux.sh          # Placeholder
├── installers/
│   ├── mac/                     # install.sh, the app's launcher and Info.plist
│   ├── windows/                 # install.ps1, uninstall.ps1
│   ├── linux/                   # What a Linux installer needs to do
│   ├── update.py                # Applies an update once the app has closed
│   └── tests/check_install.py   # End-to-end check of an installed copy
├── sample-scripts/              # A sleep script to try
├── docs/                        # User guide, settings reference, writing guides
├── tests/                       # Pronunciation list checks
├── tools/                       # Record a script, time it, check and share pronunciations
├── CLAUDE.md                    # Notes for a Claude agent working here
├── README.md
│
└── dist/
    ├── main.py                  # App entry point (FastAPI + WebView)
    ├── requirements.txt         # Python libraries, pinned
    │
    ├── app/
    │   ├── server.py            # FastAPI initialization
    │   ├── state.py             # Global engine/status singleton
    │   ├── routers/             # API Controllers (TTS, Library, Export, Update, etc.)
    │   ├── logic/               # Core logic (Normalize, Detector, Cache, Sleep)
    │   ├── locales/             # UI Translations (EN, ES, FR, ZH, JA)
    │   └── ui/
    │       ├── index.html       # Main SPA
    │       ├── css/style.css    # Premium styling
    │       └── js/modules/      # ES6 Logic modules
    │
    └── userdata/                # Your library and settings (a link, when installed)
```

**Additional folders created during use:**

- `bin/` - FFmpeg on Windows (downloaded by the installer)
- `app/models/` - the voice models (a link to your data folder, when installed)
- `userdata/audio_cache.db` - SQLite Audio Cache

### Storage Requirements

| Component                 | Size                       |
| ------------------------- | -------------------------- |
| **App Files**             | ~10 MB                     |
| **Python Libraries**      | ~450 MB                    |
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
  1. Python 3.12 (Windows: from python.org, ~27 MB; Mac: from Homebrew)
  2. The Python libraries (~450 MB installed)
  3. The voice model (~115 MB)
  4. FFmpeg (Windows: ~100 MB; Mac: from Homebrew)
- **Updates:** only when you choose Check for Updates, which asks GitHub whether a
  newer version exists, or, if you turn on **Check automatically** (off by default),
  when the app opens and once a day
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

## 🔀 Changes from the original

Everything below is specific to [merica199/LocalReader-Pro](https://github.com/merica199/LocalReader-Pro)
and is not in the original.

### Added

- **Voice preview.** A play button beside the voice dropdown renders a short
  sample of the selected voice via `GET /api/voices/preview/{voice_id}` and
  caches the WAV under `userdata/voice_previews/`. First request per voice takes
  roughly 2.5s; later ones are served from disk in about 0.15s. Every voice in a
  language reads the same sentence so they can be compared directly.
- **macOS support.** The `.app` bundle is built by
  [installers/mac/install.sh](installers/mac/install.sh), which describes each step
  at its top.
- **Plain text files.** `.txt` and `.text` files open from the upload button or
  by dropping them on the window. They do not go through the Markdown reader:
  rendering ordinary prose as Markdown dropped indented passages as code blocks,
  turned a line starting `#1` into a heading, and swallowed anything shaped like
  `<tag>`. The file is decoded by byte order mark, then UTF-8, then
  Windows-1252, so an older Windows file keeps its curly quotes and dashes. Pages
  are cut near 2500 characters, between paragraphs where possible and
  mid-paragraph only when one paragraph is longer than a page. A binary file
  renamed to `.txt` is refused rather than read aloud.
- **Sleep mode export.** The export dialog offers Normal (the MP3 export as
  before, at reading pace) or Sleep mode, which renders a slow, evenly paced
  recording to fall asleep to. The model is given one sentence at a time and
  every pause is silence inserted afterwards, so pacing is exact. Each sentence
  is trimmed of the silence the model leaves at its edges (0.07 to 0.25 s,
  varying) and leveled to the same loudness. A script can mark up its own
  pacing:

  | Markup | Effect |
  |---|---|
  | blank line | paragraph pause (2.6 s) |
  | `...` or `…` | soft pause mid-thought (1.1 s) |
  | `[pause 6]` | exactly 6 s of silence |
  | `# note` | the whole line is skipped |

  The voice track is then finished in two FFmpeg passes, one that measures
  loudness and one that applies everything and encodes:

  | Option | Default | Choices |
  |---|---|---|
  | Pauses | 1.0 s sentence, 2.6 s paragraph, 1.1 s `...`, 3 s before, 8 s after | any, after the voice up to an hour |
  | Background | brown noise, 18 dB under the voice | none, brown, pink, white, or your own sound file looped |
  | Soften the voice | light (low-pass at 8.5 kHz) | off, 6 kHz, 4 kHz |
  | Room | subtle | off, roomy |
  | Loudness | -22 LUFS | as rendered, -26, -18 |
  | Fades | 3 s in, 45 s out | any |
  | File | MP3, 96 kbps | M4A, WAV; 64 to 192 kbps |

  The room is a generated reverb tail (noise decaying 60 dB over 0.45 s or
  0.9 s, darker as it decays, different on each side) rather than the
  reference's two fixed echoes. Loudness is measured with dual-mono weighting,
  so a mono file and a stereo one at the same setting sound equally loud. A
  limiter keeps peaks under -1 dBFS for the encoders. Background sounds you add
  (rain, waves) are kept under `userdata/sleep_sounds/`; the background level is
  set against the voice's measured loudness, so it holds whatever the source
  file's own level. **Preview the first minute** renders the opening with every
  option applied and plays it in the dialog, so a change can be heard in seconds;
  its sentences land in the same cache, so the full render reuses them. Options
  are remembered between sessions (`userdata/sleep_settings.json`).

  Nothing holds the recording in memory: the voice is written as it renders,
  and FFmpeg streams. Measured on a three-hour track: 6 s to measure, 85 s to
  mix and encode, 130 MB as MP3. Every sentence is cached under
  `userdata/sleep_cache/`, about 170 MB per hour of speech, so a cancelled or
  crashed render resumes where it stopped, and re-rendering with different
  pauses or sound regenerates nothing. Kokoro returns identical audio for
  identical input, so a sentence that comes out implausibly short or long is
  retried as two halves split at its middle clause rather than regenerated
  unchanged. Default speed is 0.9. Paragraph pauses need blank lines in the
  stored text, which text and Markdown files keep and PDF and EPUB extraction
  does not. WAV with every sound option off needs no FFmpeg. The approach comes
  from [docs/reference/sleepcast.py](docs/reference/sleepcast.py). To try it,
  add [sample-scripts/skin-histology.txt](sample-scripts/skin-histology.txt), a
  nine-minute slow tour of the skin that uses every kind of markup.
- **Built-in science pronunciations.** About 230 biology, chemistry and medical
  terms that espeak-ng mispronounces, found by running 627 common terms through
  it and reading the sounds it produced. Each entry is the word's sounds in
  espeak's own phonetic alphabet, put into the engine's output in place of its
  guess (`logic/pronunciations.py`), so it covers every reading path and both
  models, and controls stress, which respelling cannot. Saved audio is keyed on
  the entries each sentence uses, so changing an entry regenerates only the
  sentences that say that word. Also found: the PDF cleanup joins spaced single
  letters, so "A T P" was read as "aptee". Checked against Wiktionary with
  `tools/lookup_pronunciation.py --audit`: of the 118 words it has
  pronunciations for, 116 agree on stress and syllables, and the other two
  (microglia, oxaloacetate) have more than one accepted pronunciation. The
  rest are not on Wiktionary and await a listener.
- **Settings in the menus, as in other apps.** Settings is a full-window page (Voice &
  Audio, Processing Mode, Updates) opened from **LocalReader Pro > Settings...** on a Mac
  or **File > Settings** on Windows, or with Cmd+comma / Ctrl+comma; Esc closes it. It
  replaces the sidebar's Settings tab and the round Voice & Audio button. Check for
  Updates moved to the LocalReader Pro menu on a Mac (Help on Windows), and Windows
  gained File > Exit. Settings meant for one platform can be marked `only-windows` or
  `only-mac` in the page.
- **Honest names for the two voice models.** Processing Mode's "High Performance (CPU)"
  and "High Quality (GPU)" are now **Standard (compressed, 87 MB)** and **Full precision
  (309 MB)**, since both always ran on the processor; the line under it says which model
  files are downloaded ("Downloaded" / "Not downloaded") instead of ✓ and ✗ that read as
  if they showed the choice.
- **A Settings tab** (since replaced by the Settings page above). Processing Mode and Updates moved from the bottom of the sidebar,
  where they left the library a few lines of room, into a fourth sidebar tab beside
  Library, Rules and Ignore. Help > Check for Updates and the Update available button
  switch to it.
- **Automatic update checks, opt-in.** Ticking **Check automatically** in the Updates
  panel checks GitHub shortly after launch and once a day, and an **Update available**
  button appears at the top of the sidebar (with a dot on the collapsed sidebar's tab)
  when there is one. Off by default, since it goes online unasked; installing still
  waits for a click. The choice is kept in `userdata/update_settings.json`.
- **Developer tools on demand.** The window runs in pywebview's debug mode so
  right-click > Inspect Element works, and pywebview also opened the developer tools
  window at every launch in that mode; it no longer does.
- **Personal pronunciations, and Claude doing the work.** Each user has a
  personal pronunciation list in their library folder, which wins over the
  built-in one, applies without a restart and survives updates, so a word heard
  wrong is fixed at once without changing the app (which would block its
  updates). `tools/promote_pronunciations.py` merges such fixes into the
  built-in list for everyone. `tools/make_sleep_recording.py` records a script
  through the running app with the user's own voice and settings, and
  `CLAUDE.md` gives a Claude agent step-by-step procedures for the requests a
  non-programmer makes, so writing, recording and fixing words all happen from
  plain requests.
- **Writing guides and notes for Claude.** `docs/writing-for-read-aloud.md` and
  `docs/writing-sleep-scripts.md` hold what testing showed about writing for the
  voice (numbers, units, acronyms, pronunciation, and how a sleep script is
  built), `tools/estimate_sleep_script.py` times a script the way the Export
  dialog does, and `CLAUDE.md` points a Claude agent at all of it.
- **One-click install and in-app updates.** Download the repository (on Windows the
  ZIP is enough; the installer then clones the app from GitHub itself) and double-click
  `Install on Mac.command` or `Install on Windows.bat`; see [Installation](#-installation).
  Each installs Python 3.12, the libraries, FFmpeg and the voice model, puts the app
  where the platform expects it (`/Applications`; `%LOCALAPPDATA%\Programs` with
  shortcuts and a Settings > Apps entry), and keeps the library in the platform's
  data folder, outside the app. The installed code is a git clone following GitHub,
  so **Help > Check for Updates** can fast-forward it: libraries for the new version
  install first, while the app is closed, so a failed install leaves the old version
  working. The installers replace the original author's `setup.exe`, which installed
  into the system-wide Python, could not update, and could not be rebuilt outside
  Windows. Tested end to end on macOS (install, re-install, install from inside the
  app, a good update and a refused one); Windows is tested by
  `.github/workflows/installers.yml` on GitHub's Windows machines.
- **Paragraph pause in live reading.** A Paragraph slider (1200 ms by default)
  sets the silence after the last sentence of a paragraph, which used to get the
  same 0.7 s as any sentence end. A paragraph ends where a blank line separates
  two sentences; for text and Markdown the last sentence on a page counts too.
  The pause is added to the clip itself rather than timed, which keeps it inside
  the playback chain's race guards.

### Fixed

- **Sentences were synthesized in fragments.** Pause handling split text at every
  comma, colon, semicolon and period, rendered each fragment as a separate
  utterance, and concatenated them with silence. The punctuation was consumed as
  a split marker and never reached the model, so it saw `Some years ago` rather
  than `Some years ago,`. It could not produce comma prosody for a comma it was
  never shown, and each fragment came out with its own falling sentence-final
  contour. Punctuation now stays in the text and a split happens only where the
  pause for that mark is above zero.
- **Playback went silent while the text kept advancing.** macOS binds an
  AudioContext to the output device it was created against, so when that device
  goes away (sleep/wake, headphones, Bluetooth) the context still reports
  "running" and still fires its ended events; it just plays to nothing. There is
  no way to ask a context whether its audio is reaching a speaker, so the failure
  cannot be detected, only pre-empted: the context is rebuilt whenever playback
  is explicitly started. That is affordable because an AudioBuffer is not tied to
  the context that decoded it, so the audio cache survives the swap.
- **The chunk size was wrong in both directions.** Text was pre-split at 200
  characters, justified as 510 phonemes at ~2.5x expansion. Measured against the
  tokenizer, English expands about 1.09x and Chinese about 4.81x, so 200
  characters of English used less than half the budget and split sentences that
  would have fitted, while 200 characters of Chinese overran the limit and was
  truncated. The budget is now derived from the script.
- **Live reading went silent before long sentences.** Read-aloud generated two
  sentences ahead, so two short sentences (a few seconds of audio) ran out
  before a long one behind them (about ten seconds to generate) was ready:
  measured at 7.5 to 12 s of silence each time. Generation now runs ahead by
  time, about 30 s of audio, and audio already generated for the next page is
  no longer thrown away at the page turn. Cache keys include the sentence text
  and settings, so the cache no longer has to be cleared to stay correct.
- **Document text could run as code.** Sentences with `[DIM]` markers,
  document names and search snippets were inserted with `innerHTML`, so markup
  in a document or its file name ran inside the app, with access to its local
  API. They are now inserted as text.
- **Markdown with a byte order mark lost its first heading.** Decoding tried
  plain UTF-8 first, which kept the mark in front of `# Title`, and UTF-16 files
  came out as noise. Markdown now uses the text reader's decoder.

- **Any website could use the app's server.** The server allowed cross-origin
  requests from every origin, with credentials. A web page open in any browser
  on the same Mac could read the library, delete documents and change settings
  through `127.0.0.1:8000`. CORS is gone (the window loads the UI from the same
  server, so it was never needed), and because browsers still deliver simple
  requests such as form posts without asking first, the server also refuses any
  request whose Host is not this machine (DNS rebinding), whose Origin is
  another site, or whose `Sec-Fetch-Site` says another site sent it. Tested
  from a page on another origin in a Chromium with its own localhost protection
  turned off: before, it read the library and reached the delete route; after,
  every request is refused.
- **A wait soon after pressing play.** Nothing was generated until play was
  pressed, so short opening sentences followed by a long one ran out before the
  long one was ready. Opening a document, or changing voice, speed or pauses,
  now generates the first 20 s or so from the reading position in the
  background, which play picks up from the cache. Measured with two short
  sentences before a long one: pressing play 12 s after opening, the wait
  before the long sentence went from 6.8 s to none; pressing play at once is
  unchanged (about 7.5 s), since nothing has had time to generate. Clicking a
  sentence waits 2 s to let clicks settle; generation now runs during that wait
  instead of after it (a long sentence: 9.6 s to sound, now 7.6 s).
- **The server stalled while a sentence was generated.** Synthesis ran on the
  server's event loop, so every other request queued behind it: a library read
  measured up to 9.6 s during playback. It now runs on a worker thread; the same
  read measured under 40 ms.
- **The sleep timer showed its icon beside the countdown.** The timer kept a
  reference to its button's icon from startup, which the icon library replaces
  when it draws, so hiding it did nothing (and when the icons were drawn first,
  every timer update threw an error). The icon is now looked up when needed.

- **An interrupted voice model download looked finished.** The downloader wrote
  straight to the final file name, and the app treats an existing file as a complete
  model, so a cut-off download stayed broken. It now downloads to a temporary name,
  checks the size, and renames.
- **A fresh install asked for a model it did not have.** New settings defaulted to the
  309 MB FP32 model while setup fetched the 88 MB quantized one, so the app fell back
  with a warning. New installs now default to the quantized model, which is what the
  installers download; existing settings are unchanged.
- **A 530 MB library nothing used.** `torch` was in the requirements but never
  imported. It is gone, and every version is now pinned to the one the app is tested
  with.
- **Missing dependencies.** `psutil` is imported by `app/server.py` but was never
  declared, so a clean install failed on first launch. On Python 3.13, `pydub`
  additionally needs `audioop-lts`, because PEP 594 removed the stdlib `audioop`
  module and pydub's fallback imports `pyaudioop`, which does not exist on PyPI.
  `audioop-lts` requires Python 3.13+, so it is gated behind an environment
  marker rather than breaking installs on 3.10 to 3.12.
- **Windows-only FFmpeg.** Binary paths were hardcoded to `.exe`, the installer
  downloaded a Windows build that cannot run elsewhere, and nothing consulted
  `PATH`. Binaries now resolve per platform and fall back to a system-managed
  install.
- **FFmpeg reported as missing when present.** `ffmpeg_status["is_installed"]`
  defaulted to `False` and was only ever set by the installer, so an existing
  FFmpeg (including a bundled `bin/ffmpeg.exe` on Windows) was reported
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

> **Note on this repository.** It began as a fork of
> [revisionhiep-create/LocalReader-Pro](https://github.com/revisionhiep-create/LocalReader-Pro),
> and most of its code is still that project's. The original has no `LICENSE`
> file; the statement above is its only license statement, and it reserves
> redistribution to the original author. Nothing here is relicensed, and nothing
> here grants redistribution rights the original author has not given. If you
> want to use this beyond personal use, ask
> [@revisionhiep-create](https://github.com/revisionhiep-create).

### Third-Party Components

| Component        | License      |
| ---------------- | ------------ |
| **Kokoro-82M**   | Apache 2.0   |
| **FastAPI**      | MIT          |
| **ONNX Runtime** | MIT          |
| **espeak-ng**    | GPL 3.0      |
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

- FastAPI, uvicorn, onnxruntime, kokoro-onnx, pydub, soundfile, pywebview, ebooklib, beautifulsoup4, and more (see `requirements.txt`)

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
