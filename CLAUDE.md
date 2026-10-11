# LocalReader Pro: notes for Claude

A desktop app that reads documents aloud with a voice running entirely on this
computer (Kokoro, through kokoro_onnx and espeak-ng), and exports MP3s,
including slow "sleep mode" recordings with background sound. A FastAPI server
(`dist/app/`) serves a web UI (`dist/app/ui/`) inside a pywebview window
(`dist/main.py`). The README covers features and installation.

## Writing scripts for it

Most requests will be to write something for the app to read, often a sleep
script on a subject being studied. Read these first; they hold what was
learned by testing, and the voice gets several obvious-looking things wrong:

- [docs/writing-for-read-aloud.md](docs/writing-for-read-aloud.md): numbers,
  units, symbols, acronyms and pronunciation, for any text.
- [docs/writing-sleep-scripts.md](docs/writing-sleep-scripts.md): markup,
  length, shape, style and accuracy for sleep scripts.

Check a script's length with `tools/estimate_sleep_script.py`. Scripts about
real people, or written for one person, are personal: this repository is
public, so keep them in a folder outside it.

## Pronunciation

`dist/app/logic/pronunciations.json` is a built-in list of science words the
voice mispronounces, each with its exact sounds. Add to it when a word comes
out wrong (`dist/app/logic/pronunciations.py` explains how), then run
`tests/test_pronunciations.py`.

## The installed app is a git clone: do not edit it

The installers put the app in its own git clone, which the app updates itself
from GitHub (Help > Check for Updates):

- Mac: `/Applications/LocalReader Pro.app/Contents/Resources/LocalReader-Pro`
- Windows: `%LOCALAPPDATA%\Programs\LocalReader Pro`

If the folder you are working in is one of those, it is the live app. Editing
its files makes the updater refuse to update, so change code in a separate
clone or a git worktree instead. The library and settings live outside the
app (`~/Library/Application Support/LocalReader Pro`, or
`%APPDATA%\LocalReader Pro` on Windows), reached through the links
`dist/userdata` and `dist/app/models`. Never delete through those links.

## Running and testing

- The app's Python is `venv/bin/python` (Mac) or `venv\Scripts\python.exe`
  (Windows), inside the installed app or the clone that has a `venv`.
- The UI is hard-coded to port 8000, which the running app holds. To test a
  change, start a separate copy on another port from the clone's `dist`
  folder: `python -m uvicorn app.server:app --host 127.0.0.1 --port 8771`.
  Give it an empty `dist/userdata` of its own, never the real library.
- The server refuses requests from other websites, so test requests need
  `Origin: http://127.0.0.1:<port>`.
- The voice engine is not thread-safe: every call into it goes through
  `state.engine_lock`.
- Tests: `tests/test_pronunciations.py`, and
  `installers/tests/check_install.py` for a whole installed copy. Pushing
  installer changes to `main` runs the installers on clean Windows and Mac
  machines (`.github/workflows/installers.yml`).

## Design rules

- Sleep mode is a separate mode of the Export dialog. Sleep features stay
  inside it, and normal reading and normal MP3 export keep working as they do.
- Everything runs locally. The app goes online only to download the voice
  model and FFmpeg, and to check for updates when asked.
- espeak-ng cuts its data path at about 160 bytes, so the installers refuse
  install folders that would make it longer.
- `installers/windows/install.ps1` runs on Windows PowerShell 5.1, which
  strips double quotes from arguments to programs: inside it, inline Python
  uses single quotes.
