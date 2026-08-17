# LocalReader Pro — macOS Setup Reference

Everything about how this app is installed on macOS: where each piece lives, why
it lives there, what is safe to delete, and how to perform common tasks.

Upstream (`revisionhiep-create/LocalReader-Pro`) is a Windows application. It
ships `setup.exe`, `uninstall.exe`, and `launch.vbs`, and its `INSTALL.txt`
describes a Windows-only flow. **None of that is used on macOS.** This document
describes the macOS installation instead.

---

## 1. The mental model

There are **three separate things**, stored in three separate places. Keeping
them separate is the entire point of this layout.

| # | Thing | Lives in | Replaceable? |
|---|---|---|---|
| 1 | **The program** — Python source, app logic, config defaults | Inside the app bundle in `/Applications` | Yes — re-clone from GitHub |
| 2 | **Your stuff** — books, exported MP3s, library, settings | `~/Library/Application Support/LocalReader Pro/` | **No — this is the only copy** |
| 3 | **Downloaded models** — the AI voice engine | `~/Library/Application Support/LocalReader Pro/models/` | Yes — re-downloadable, ~115 MB |

The critical consequence: **you can delete the entire app and lose nothing of
yours.** Your books and settings are not inside the app. That was the specific
goal of this setup.

Only category 1 is in the git repository. Categories 2 and 3 are never committed
and never leave your machine.

---

## 2. Exact locations

### 2.1 The application

```
/Applications/LocalReader Pro.app
```

A macOS `.app` is not a file — it is a **directory** with a required internal
layout. Finder displays it as a single icon. To look inside: right-click →
**Show Package Contents**, or use `cd` in a terminal (quote the path; it has a
space).

```
/Applications/LocalReader Pro.app/
└── Contents/
    ├── Info.plist                    ← app metadata: name, identifier, version
    ├── MacOS/
    │   └── LocalReaderPro            ← the launcher script macOS executes
    └── Resources/
        └── LocalReader-Pro/          ← THE GIT REPO (all source code)
```

`Info.plist` is what makes it a real application: it declares the bundle name,
identifier (`com.localreaderpro.app`), and which file inside `MacOS/` to run.
That registration is why the app appears in Launchpad and Spotlight.

### 2.2 The git repository — the answer to "where is the repo?"

```
/Applications/LocalReader Pro.app/Contents/Resources/LocalReader-Pro
```

To work in it:

```sh
cd "/Applications/LocalReader Pro.app/Contents/Resources/LocalReader-Pro"
git status
```

The quotes are required — `LocalReader Pro.app` contains a space, and without
quotes the shell reads it as two arguments.

Optional convenience — a shortcut in your home directory:

```sh
ln -s "/Applications/LocalReader Pro.app/Contents/Resources/LocalReader-Pro" ~/localreader
cd ~/localreader
```

Inside the repo:

```
LocalReader-Pro/
├── .git/                      ← version history
├── .gitignore                 ← rules for what is NEVER committed
├── MACOS-SETUP.md             ← this file
├── README.md, CHANGELOG.md    ← upstream docs (Windows-oriented)
├── INSTALL.txt                ← upstream Windows instructions (ignore on macOS)
├── setup.spec, uninstall.spec ← PyInstaller configs for the Windows build
├── build_installer.py         ← Windows installer builder
├── venv/                      ← Python environment (NOT in git, ~1 GB)
└── dist/
    ├── main.py                ← entry point: starts server, opens window
    ├── requirements.txt       ← Python dependency list
    ├── setup.exe              ← Windows installer (unused on macOS)
    ├── uninstall.exe          ← Windows uninstaller (unused on macOS)
    ├── launch.vbs             ← Windows launch script (unused on macOS)
    ├── userdata  →  SYMLINK   ← points to Application Support (see §4)
    └── app/
        ├── server.py          ← FastAPI web server + startup logic
        ├── config.py          ← path definitions
        ├── state.py           ← shared runtime state
        ├── models.py          ← data shapes
        ├── routers/           ← API endpoints
        │   ├── export.py      ← MP3 export + FFmpeg endpoints
        │   ├── system.py      ← engine loading, model download, status
        │   ├── library.py     ← your document library
        │   ├── tts.py         ← text-to-speech generation
        │   ├── settings.py    ← settings read/write
        │   └── timer.py       ← sleep timer
        ├── logic/
        │   ├── downloader.py            ← fetches voice models
        │   ├── dependency_manager.py    ← FFmpeg detection (customized, §7)
        │   ├── smart_content_detector.py
        │   └── text_normalizer.py       ← pronunciation rules
        ├── ui/                ← the web frontend (HTML/CSS/JS)
        ├── locales/           ← translations
        └── models  →  SYMLINK ← points to Application Support (see §4)
```

### 2.3 Your personal files

```
~/Library/Application Support/LocalReader Pro/
├── userdata/
│   ├── content/          ← your imported EPUBs and PDFs
│   ├── library.json      ← your reading list and progress
│   ├── settings.json     ← voice, speed, pronunciation rules
│   ├── audio_cache.db    ← cached generated speech (capped at 200 MB)
│   └── *.mp3             ← your exported audiobooks
└── models/
    ├── kokoro.int8.onnx  ← the AI voice model (88 MB)
    └── voices.bin        ← the 54 voice definitions (27 MB)
```

`~` means your home folder (`/Users/tmerica`). `~/Library` is hidden by default
in Finder — press **⌘⇧G** and paste the path, or hold **Option** while clicking
the **Go** menu.

`Application Support` is the standard macOS location for exactly this kind of
data. Putting it here is why deleting the app cannot touch your books.

### 2.4 The log

```
~/Library/Logs/LocalReader-Pro.log
```

When launched from Finder there is no terminal, so all output is redirected
here. This is the first place to look if anything misbehaves:

```sh
tail -f ~/Library/Logs/LocalReader-Pro.log
```

---

## 3. What is in git and what is not

**In the repo (55 files):** Python source, the web frontend, translations,
config defaults, dependency lists, upstream docs, and the Windows build files.
Program logic and configuration only.

**Never in the repo:** every one of your personal files. Three independent
mechanisms guarantee this:

1. **Location.** Your files physically live in `~/Library/Application Support/`,
   outside the repository directory. Git cannot track files outside its tree.
2. **Symlinks.** The in-repo paths `dist/userdata` and `dist/app/models` are
   pointers, not folders (§4).
3. **`.gitignore`.** Those paths, plus `*.mp3`, `*.epub`, `*.pdf`, `*.onnx`,
   `*.bin`, `*.log*`, and `venv/`, are explicitly excluded.

Verify at any time:

```sh
cd "/Applications/LocalReader Pro.app/Contents/Resources/LocalReader-Pro"

# Should print nothing — no personal media tracked
git ls-files | grep -iE '\.(mp3|epub|pdf|wav|onnx|db)$'

# Shows exactly what would be committed
git status
```

`git status` showing "nothing to commit, working tree clean" while your library
is full of books is the system working correctly.

---

## 4. How the symlinks work

A **symlink** (symbolic link) is a file whose contents are a path to somewhere
else. Programs opening it are transparently redirected to the target.

```
dist/userdata     →  ~/Library/Application Support/LocalReader Pro/userdata
dist/app/models   →  ~/Library/Application Support/LocalReader Pro/models
```

**Why this approach.** The app computes its own paths relative to its source
files ([`config.py`](dist/app/config.py) anchors everything to the script
location) so it always looks for `dist/userdata`. Rather than rewrite that
logic — which would create a permanent difference from upstream and cause merge
conflicts on every update — the paths stay where the code expects and the
symlinks redirect the storage. **Zero code changes, correct macOS behavior.**

Inspect them:

```sh
ls -l "/Applications/LocalReader Pro.app/Contents/Resources/LocalReader-Pro/dist/userdata"
```

An `l` at the start of the permissions and an `->` arrow confirm a symlink.

Note: `.gitignore` lists these paths **both** with and without a trailing slash.
The `dir/` form only matches real directories, so a symlink named `userdata`
would otherwise show up as an untracked file.

---

## 5. How launching works

1. You double-click the app (or use Launchpad/Spotlight/Dock).
2. macOS reads `Info.plist` and runs `Contents/MacOS/LocalReaderPro`.
3. That script redirects all output to the log, verifies the environment,
   and checks whether port 8000 is already in use.
4. It replaces itself with `venv/bin/python -u dist/main.py`.
5. `main.py` starts a FastAPI web server on `127.0.0.1:8000` in a background
   thread, waits for it to respond, then opens a native window pointed at it.

The app is a **local web app in a native window** — the interface is HTML
rendered by macOS WebKit. Nothing is exposed to your network: it binds to
`127.0.0.1` (your machine only), never `0.0.0.0`.

### Two macOS-specific hazards, already handled

**The launcher must never invoke Python before `exec`.** The venv's interpreter
is the framework `Python.app` GUI stub. Run from a terminal it behaves normally,
but launched under `launchd` with no controlling terminal it **blocks during
startup**. A Python subprocess in the launcher therefore hangs the app before it
starts, and the Dock icon bounces forever. The single-instance check uses `lsof`
(a plain binary) for this reason. There is a comment in the launcher saying so —
please leave it there.

**Only one instance can run.** `main.py` starts its server thread *before*
testing the port, so a second launch does not fail — it silently points a new
window at the first instance's backend. The launcher refuses the second launch
with a dialog instead.

### Manual launch (for debugging, shows output live)

```sh
cd "/Applications/LocalReader Pro.app/Contents/Resources/LocalReader-Pro/dist"
../venv/bin/python main.py
```

### Quitting

Close the window, or:

```sh
pkill -f "main.py"
```

---

## 6. The Python environment

```
/Applications/LocalReader Pro.app/Contents/Resources/LocalReader-Pro/venv/
```

Python **3.12**, roughly 100 packages, about 1 GB. Not in git — it is rebuilt
from `requirements.txt`, not version-controlled.

**`requirements.txt` lists 17 packages but ~100 get installed.** That is
correct and expected: it names only what the app imports *directly*. Each of
those has its own dependencies (`uvicorn` needs `click` and `h11`;
`huggingface_hub` needs `httpx`, `tqdm`, and others).

**Never install with `--no-deps`.** That flag skips every transitive dependency
and produces an environment that fails at the first import. On macOS it also
skips `pyobjc-framework-Cocoa` and `pyobjc-framework-WebKit`, which the app
window requires — so the app cannot open at all.

**`psutil` is missing from `requirements.txt`** but is imported by
`dist/app/server.py`. It must be installed explicitly (see below). This is an
upstream bug.

**`torch` and `scipy` are listed but never imported** by any app code. `torch`
alone is ~111 MB and pulls in `sympy`, `networkx`, and `mpmath`. They appear to
be leftovers from a PyTorch-based version of the voice engine; this build uses
`onnxruntime`. They are installed for safety but are not known to be used.

### Rebuilding the environment from scratch

```sh
cd "/Applications/LocalReader Pro.app/Contents/Resources/LocalReader-Pro"
rm -rf venv
python3.12 -m venv venv
./venv/bin/pip install -r dist/requirements.txt psutil
```

Your books, settings, and models are untouched by this — they are elsewhere.

---

## 7. Local changes vs upstream

One commit on top of upstream: **"Use platform-native FFmpeg instead of assuming
a Windows build."**

Upstream assumed Windows throughout its FFmpeg handling, which made MP3 export
impossible on macOS:

- Binary paths were hardcoded to `ffmpeg.exe` / `ffprobe.exe`.
- The installer downloaded a **Windows** build from gyan.dev, producing `.exe`
  files that cannot run on macOS.
- Nothing consulted `PATH`, so a Homebrew-installed `ffmpeg` was ignored.

Changes made:

| File | Change |
|---|---|
| `dist/app/logic/dependency_manager.py` | Resolve `ffmpeg`/`ffmpeg.exe` per platform; fall back to `PATH` via `shutil.which`; short-circuit the installer on non-Windows with a message pointing at the system package manager |
| `dist/app/server.py` | Detect FFmpeg once at startup and set `ffmpeg_status` accordingly |
| `dist/main.py` | Downgrade the misleading "FFMPEG will need to be downloaded" warning |
| `.gitignore` | Also ignore the symlink forms of the data paths |

The `server.py` change fixes a **platform-independent** bug:
`ffmpeg_status["is_installed"]` defaulted to `False` and was only ever flipped
by the installer, so an already-present FFmpeg was reported missing and the UI
kept offering an unnecessary download. That affected Windows too.

**FFmpeg itself is not bundled** — it comes from Homebrew at
`/opt/homebrew/bin/ffmpeg`. If it ever goes missing:

```sh
brew install ffmpeg
```

Do **not** use any in-app "install FFmpeg" button on macOS. With this patch it
tells you to use Homebrew; without it, it downloads unusable Windows binaries.

---

## 8. Git remotes

Two remotes, following standard fork convention:

| Remote | Points at | Purpose |
|---|---|---|
| `origin` | `github.com/merica199/LocalReader-Pro` | **Your fork.** You push here. |
| `upstream` | `github.com/revisionhiep-create/LocalReader-Pro` | Original author. Read-only; you cannot push here. |

A **remote** is a nickname for a copy of the repo on a server. A **checkout** is
the working copy of files on your disk (§2.2).

Commits are authored as `merica199 <24942127+merica199@users.noreply.github.com>`
— GitHub's private no-reply address, set **for this repo only**. Commits link to
your account without publishing a real email address. Your global git config is
unchanged and still uses your work address for other projects.

### Saving your own changes

```sh
cd "/Applications/LocalReader Pro.app/Contents/Resources/LocalReader-Pro"
git status                  # see what changed
git diff                    # see the actual edits
git add -A                  # stage everything not ignored
git commit -m "Describe what you changed"
git push                    # send to your fork
```

### Pulling the original author's updates

```sh
git fetch upstream
git log --oneline HEAD..upstream/main    # preview what is new
git merge upstream/main                  # apply it
git push                                 # update your fork
```

If a merge conflicts, `git merge --abort` returns you to where you started.

---

## 9. Common tasks

### Switch to the higher-quality voice model

The UI's "GPU" option is a **misnomer on macOS**: it is the FP32 model, ~309 MB,
and it still runs on the CPU. [`kokoro_onnx`](venv/lib/python3.12/site-packages/kokoro_onnx/__init__.py)
hardcodes `providers = ["CPUExecutionProvider"]` unless the Windows/Linux-only
`onnxruntime-gpu` package is present. It is slower than the current model for
marginally better audio.

Your Mac does expose `CoreMLExecutionProvider`, and `kokoro-onnx` honors an
`ONNX_PROVIDER` environment variable — but the upstream changelog records
`v3.6.1: Revert GPU acceleration (static noise)`. Forcing CoreML is likely to
reintroduce that.

### Free up space

```sh
du -sh ~/Library/Application\ Support/LocalReader\ Pro/*
```

`models/` (~115 MB) is re-downloadable. `userdata/` is not — that is your books.
The audio cache self-limits to 200 MB.

### Back up everything that matters

```sh
cp -R ~/Library/Application\ Support/LocalReader\ Pro/userdata ~/Desktop/localreader-backup
```

The code needs no backup — it is on GitHub. Only `userdata/` is irreplaceable.

### Uninstall completely

```sh
pkill -f "main.py"
rm -rf "/Applications/LocalReader Pro.app"           # app + code
rm -rf ~/Library/Application\ Support/LocalReader\ Pro   # data + models
rm -f  ~/Library/Logs/LocalReader-Pro.log            # log
```

Run only the first two lines to reinstall while keeping your library.

### Move the app elsewhere

Drag it anywhere. The launcher derives its own paths from its location, so
nothing breaks. Data in `Application Support` is referenced by absolute path and
is unaffected.

---

## 10. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| Icon bounces forever, never opens | Something in the launcher blocked before `exec`. Check the log; never call Python from the launcher (§5). |
| "LocalReader Pro is already running" | A copy is running — check other Spaces/windows, or `pkill -f "main.py"`. |
| Window opens blank | Server failed to bind port 8000. Check the log and `lsof -nP -iTCP:8000`. |
| "No voices found" | Models missing. Click **Setup Voice Engine**, or see §9. |
| MP3 export fails | `brew install ffmpeg`, then restart the app. |
| `ModuleNotFoundError` on launch | Environment broken or built with `--no-deps`. Rebuild per §6. |
| Speech generates slowly | Expected. The quantized model runs near 1.1× realtime; the app pre-caches ahead of playback. |

Useful checks:

```sh
tail -50 ~/Library/Logs/LocalReader-Pro.log       # what happened last launch
curl -s http://127.0.0.1:8000/api/system/status   # engine, voices, errors
curl -s http://127.0.0.1:8000/api/ffmpeg/status   # export readiness
```

---

## 11. Reference

| Item | Value |
|---|---|
| App bundle | `/Applications/LocalReader Pro.app` |
| Source / git repo | `/Applications/LocalReader Pro.app/Contents/Resources/LocalReader-Pro` |
| Launcher script | `<bundle>/Contents/MacOS/LocalReaderPro` |
| Python environment | `<repo>/venv` (Python 3.12) |
| Entry point | `<repo>/dist/main.py` |
| Personal data | `~/Library/Application Support/LocalReader Pro/userdata/` |
| Voice models | `~/Library/Application Support/LocalReader Pro/models/` |
| Log file | `~/Library/Logs/LocalReader-Pro.log` |
| Server address | `http://127.0.0.1:8000` (local only) |
| Bundle identifier | `com.localreaderpro.app` |
| Your fork | `https://github.com/merica199/LocalReader-Pro` |
| Upstream | `https://github.com/revisionhiep-create/LocalReader-Pro` |
| Voice engine | Kokoro ONNX, int8 quantized, 54 voices |
| FFmpeg | `/opt/homebrew/bin/ffmpeg` (Homebrew, not bundled) |
