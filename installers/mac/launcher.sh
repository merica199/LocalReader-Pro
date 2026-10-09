#!/bin/sh
# Launcher for LocalReader Pro.
#
# The whole app lives inside this bundle (Contents/Resources/LocalReader-Pro),
# so paths are derived from this script's own location -- the bundle can be
# moved or renamed without editing anything here.

HERE=$(cd "$(dirname "$0")" && pwd)
PROJECT="$HERE/../Resources/LocalReader-Pro"
PY="$PROJECT/venv/bin/python"
LOG="$HOME/Library/Logs/LocalReader-Pro.log"

# Launched from Finder there is no terminal, so keep a log we can read after a
# failure instead of losing stdout/stderr.
exec >>"$LOG" 2>&1
echo "=== launch $(date) ==="

fail() {
	echo "FATAL: $1"
	osascript -e "display alert \"LocalReader Pro\" message \"$1\" as critical"
	exit 1
}

[ -x "$PY" ] || fail "Python environment missing. Rebuild the venv inside the app bundle, then relaunch."
[ -f "$PROJECT/dist/main.py" ] || fail "Application files missing from this bundle."

# Single-instance check. main.py starts its server thread before testing the
# port, so a second instance does not fail -- it silently points its window at
# the first instance's backend.
#
# This MUST NOT invoke python. The venv's interpreter is the framework
# Python.app GUI stub, which blocks on startup when launched under launchd with
# no controlling terminal -- that hangs the launcher and bounces the Dock icon
# forever. lsof is a plain binary and is safe here.
if lsof -nP -iTCP:8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
	echo "port 8000 already serving; refusing second instance"
	osascript -e 'display alert "LocalReader Pro" message "LocalReader Pro is already running. Check your other windows, or quit the running copy before relaunching."' &
	exit 0
fi

# main.py anchors its own paths, but app.server is imported as a package
# relative to dist/, so run from there.
cd "$PROJECT/dist" || fail "Cannot enter $PROJECT/dist"
# -u: unbuffered, so the log above is written as it happens and survives a crash.
exec "$PY" -u main.py
