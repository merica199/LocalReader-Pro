# Linux installer: not written yet

`Install on Linux.sh` at the top of the repository is a placeholder. A real
installer would follow the same steps as the Mac and Windows ones
(`installers/mac/install.sh`, `installers/windows/install.ps1`):

1. **System packages.** Python 3.12 with `venv`, FFmpeg, and what pywebview
   needs to draw a window: GTK with WebKit2GTK (on Debian and Ubuntu,
   `python3-gi gir1.2-webkit2-4.1`), or Qt. The package names differ by
   distribution, which is most of the work.
2. **The code** in `~/.local/share/LocalReader Pro`, as its own git clone
   following the same branch on GitHub, so the in-app updater works.
3. **Library and settings** in `~/.local/share/LocalReader Pro Data` (or
   `$XDG_DATA_HOME`), linked into `dist/userdata` and `dist/app/models`.
4. **Python libraries** in a `venv` inside the code folder, from
   `dist/requirements.txt`. pywebview on GTK needs the system `gi` package,
   so the environment is made with `--system-site-packages`.
5. **The voice model**, through `dist/app/logic/downloader.py`.
6. **A launcher**: a `.desktop` file in `~/.local/share/applications` that
   runs `venv/bin/python dist/main.py`, with `assets/icon.png` as its icon.
7. **Updates**: `relaunch_command()` in `dist/app/routers/update.py` needs a
   Linux branch that starts the app the way the `.desktop` file does.

Until then, the manual steps in the main README work on Linux.
