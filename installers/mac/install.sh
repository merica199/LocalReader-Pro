#!/bin/bash
# Install LocalReader Pro on a Mac. Run by double-clicking "Install on Mac.command"
# at the top of the repository.
#
# What it does, in order:
#   1. Homebrew, Python 3.12 and FFmpeg, installing whichever is missing.
#   2. The app in /Applications (or ~/Applications when /Applications is not
#      writable). The code inside it is its own git clone of this repository,
#      following the same branch on GitHub, which is what lets the app update
#      itself (Help > Check for Updates). This folder can be deleted afterwards.
#   3. Your library and settings in ~/Library/Application Support/LocalReader Pro,
#      outside the app, so reinstalling or deleting the app never touches them.
#   4. The Python libraries, in a private environment inside the app.
#   5. The voice model (about 115 MB), unless it is already there.
#
# Running it again is safe: it repairs what is missing and moves an existing
# install forward to this folder's version, and it never deletes your library.
# Running it from inside an installed app (where the code already lives) only
# refreshes that install.
#
# For tests: LOCALREADER_APP and LOCALREADER_DATA override the two locations,
# and LOCALREADER_UNATTENDED=1 answers yes to every question and does not open
# the app at the end.

set -euo pipefail

APP_NAME="LocalReader Pro"
SRC="$(cd "$(dirname "$0")/../.." && pwd -P)"
UNATTENDED="${LOCALREADER_UNATTENDED:-0}"
DATA="${LOCALREADER_DATA:-$HOME/Library/Application Support/$APP_NAME}"
PY_FORMULA="python@3.12"

step() { printf '\n==> %s\n' "$1"; }
note() { printf '    %s\n' "$1"; }
pause_to_close() { [ "$UNATTENDED" = 1 ] || read -r -p $'\nPress Return to close this window.' _ || true; }
fail() {
	printf '\nInstall stopped: %s\n' "$1" >&2
	pause_to_close
	exit 1
}
ask() {
	[ "$UNATTENDED" = 1 ] && return 0
	local reply
	read -r -p "$1 [Y/n] " reply || reply=n
	case "$reply" in [nN]*) return 1 ;; *) return 0 ;; esac
}
trap 'fail "an unexpected error on line $LINENO (see the messages above)"' ERR

[ "$(uname)" = Darwin ] || fail "this installer is for macOS. On Windows, use \"Install on Windows.bat\"."

printf '%s installer\n' "$APP_NAME"
printf 'Installing from: %s\n' "$SRC"

# --- Where the app goes --------------------------------------------------------
# A repository that already sits inside an app bundle is that install (the
# layout this app has always used), so it is refreshed where it is.
case "$SRC" in
*.app/Contents/Resources/*)
	APP="${SRC%%.app/Contents/Resources/*}.app"
	IN_PLACE=1
	;;
*)
	IN_PLACE=0
	if [ -n "${LOCALREADER_APP:-}" ]; then
		APP="$LOCALREADER_APP"
	elif [ -w /Applications ]; then
		APP="/Applications/$APP_NAME.app"
	else
		# Standard accounts cannot write to /Applications.
		APP="$HOME/Applications/$APP_NAME.app"
	fi
	;;
esac
if [ "$IN_PLACE" = 1 ]; then REPO="$SRC"; else REPO="$APP/Contents/Resources/LocalReader-Pro"; fi
note "App: $APP"
note "Your library and settings: $DATA"

git -C "$SRC" rev-parse --git-dir >/dev/null 2>&1 ||
	fail "this folder is not a git clone, so the installed app could not update itself. Download it with: git clone https://github.com/merica199/LocalReader-Pro.git"

# --- 1. Homebrew, Python, FFmpeg -----------------------------------------------
step "Checking for Homebrew, Python 3.12 and FFmpeg"
BREW="$(command -v brew || true)"
for candidate in /opt/homebrew/bin/brew /usr/local/bin/brew; do
	[ -z "$BREW" ] && [ -x "$candidate" ] && BREW="$candidate"
done
if [ -z "$BREW" ]; then
	note "Homebrew (the standard Mac package manager) is not installed. It provides"
	note "Python and FFmpeg here. Its installer will ask for your Mac password."
	ask "Install Homebrew now?" || fail "Homebrew is needed. Install it from https://brew.sh and run this again."
	if [ "$UNATTENDED" = 1 ]; then export NONINTERACTIVE=1; fi
	/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
	for candidate in /opt/homebrew/bin/brew /usr/local/bin/brew; do
		[ -x "$candidate" ] && BREW="$candidate"
	done
	[ -n "$BREW" ] || fail "Homebrew did not install."
fi
for formula in "$PY_FORMULA" ffmpeg; do
	if "$BREW" list --versions "$formula" >/dev/null 2>&1; then
		note "$formula: installed"
	else
		note "$formula: installing (this can take a few minutes)"
		"$BREW" install "$formula"
	fi
done
PY="$("$BREW" --prefix "$PY_FORMULA")/bin/python3.12"
[ -x "$PY" ] || fail "Python 3.12 is not where Homebrew said it would be ($PY)."

# --- 2. The code ---------------------------------------------------------------
step "Placing the app"
if [ "$IN_PLACE" = 1 ]; then
	note "Already installed here; refreshing this install."
elif [ -d "$REPO/.git" ]; then
	note "Found an existing install; moving it forward to this folder's version."
	[ -z "$(git -C "$REPO" status --porcelain --untracked-files=no)" ] ||
		fail "files inside the installed app have been edited ($REPO). Undo those edits, or move the app to the Trash (your library is kept separately) and run this again."
	git -C "$REPO" fetch --quiet "$SRC" HEAD
	if git -C "$REPO" merge-base --is-ancestor FETCH_HEAD HEAD; then
		note "The installed app is already this version or newer."
	else
		git -C "$REPO" merge --ff-only --quiet FETCH_HEAD ||
			fail "the installed app and this folder have different changes. Move the app to the Trash (your library is kept separately) and run this again."
	fi
else
	if [ -e "$APP" ]; then
		# Left by an install that was interrupted, or something else entirely.
		if [ -f "$APP/Contents/Info.plist" ] && ! grep -q "com.localreaderpro.app" "$APP/Contents/Info.plist"; then
			fail "$APP exists but was not made by this installer. Move it to the Trash and run this again."
		fi
		if [ -d "$REPO/dist/userdata" ] && [ ! -L "$REPO/dist/userdata" ]; then
			fail "$APP holds a library from an older manual install. Move $REPO/dist/userdata somewhere safe and run this again."
		fi
		rm -rf "$REPO"
	fi
	BRANCH="$(git -C "$SRC" rev-parse --abbrev-ref HEAD)"
	[ "$BRANCH" != HEAD ] || fail "this clone is not on a branch. Run: git -C \"$SRC\" checkout main"
	ORIGIN="$(git -C "$SRC" remote get-url origin 2>/dev/null || true)"
	[ -n "$ORIGIN" ] || fail "this clone has no 'origin' remote to update from."
	mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
	git clone --quiet --branch "$BRANCH" "$SRC" "$REPO"
	# Updates come from where this folder was cloned from, not from this folder.
	git -C "$REPO" remote set-url origin "$ORIGIN"
	note "Copied the code ($BRANCH, following $ORIGIN)."
fi

# --- 3. Library and settings, outside the app ----------------------------------
step "Connecting your library"
mkdir -p "$DATA/userdata" "$DATA/models"
link_data() {
	# $1: path inside the app, $2: where the data really lives
	local inside="$1" outside="$2"
	if [ -L "$inside" ]; then
		[ "$(readlink "$inside")" = "$outside" ] && return 0
		rm "$inside"
	elif [ -d "$inside" ]; then
		# A real folder here holds data from before the split: move it out once.
		if [ -n "$(ls -A "$outside")" ]; then
			fail "both $inside and $outside contain data. Move one of them aside and run this again."
		fi
		cp -Rp "$inside/." "$outside/"
		rm -rf "$inside"
	fi
	ln -s "$outside" "$inside"
}
link_data "$REPO/dist/userdata" "$DATA/userdata"
link_data "$REPO/dist/app/models" "$DATA/models"
note "Library: $DATA/userdata"

# --- 4. Python libraries --------------------------------------------------------
step "Installing Python libraries (the first time takes a few minutes)"
VENV="$REPO/venv"
if [ -x "$VENV/bin/python" ] && "$VENV/bin/python" -c 'import sys; sys.exit(sys.version_info[:2] != (3, 12))' 2>/dev/null; then
	note "Using the existing environment."
else
	[ ! -e "$VENV" ] || [ -f "$VENV/pyvenv.cfg" ] || fail "$VENV exists and is not a Python environment."
	rm -rf "$VENV"
	"$PY" -m venv "$VENV"
fi
"$VENV/bin/python" -m pip install --quiet --disable-pip-version-check --upgrade pip
# The filter only hides lines about what is already there; pipefail keeps
# pip's own exit status, and grep finding nothing to print is not a failure.
"$VENV/bin/python" -m pip install --disable-pip-version-check -r "$REPO/dist/requirements.txt" 2>&1 |
	{ grep -vE '^(Requirement already satisfied|  Using cached)' || true; }
"$VENV/bin/python" -c 'import kokoro_onnx, webview, fastapi' || fail "the Python libraries did not install correctly."
# The speech engine (espeak-ng) keeps the path to its data in a 160-byte buffer
# and cuts anything longer, after which every sentence fails. Installing under
# a long folder name or a long account name can go past it.
ESPEAK_DATA_LEN="$("$VENV/bin/python" -c 'import espeakng_loader; print(len(str(espeakng_loader.get_data_path()).encode()))')"
[ "$ESPEAK_DATA_LEN" -lt 150 ] ||
	fail "the app's folder path is too long for the speech engine ($ESPEAK_DATA_LEN characters to its data, limit 150). Install somewhere shorter: LOCALREADER_APP=/path/to/LocalReader\ Pro.app"

# --- 5. Voice model -------------------------------------------------------------
step "Voice model"
if [ -f "$DATA/models/kokoro.int8.onnx" ] && [ -f "$DATA/models/voices.bin" ]; then
	note "Already downloaded."
else
	note "Downloading (about 115 MB)..."
	(cd "$REPO/dist/app" && "$VENV/bin/python" -c 'from logic.downloader import download_kokoro_model; download_kokoro_model("cpu")') ||
		fail "the voice model did not download. Check the internet connection and run this again."
fi

# --- 6. The app bundle ------------------------------------------------------------
step "Finishing the app"
put() {
	# Copy only when different, so an install that is in use is not disturbed.
	cmp -s "$1" "$2" 2>/dev/null || cp "$1" "$2"
}
put "$REPO/installers/mac/Info.plist" "$APP/Contents/Info.plist"
put "$REPO/installers/mac/launcher.sh" "$APP/Contents/MacOS/LocalReaderPro"
chmod 755 "$APP/Contents/MacOS/LocalReaderPro"
put "$REPO/assets/AppIcon.icns" "$APP/Contents/Resources/AppIcon.icns"
touch "$APP"
LSREGISTER=/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister
[ -x "$LSREGISTER" ] && "$LSREGISTER" -f "$APP" >/dev/null 2>&1 || true

trap - ERR
step "Done"
note "$APP_NAME is installed at $APP"
if [ "$IN_PLACE" = 0 ]; then
	note "This folder ($SRC) is no longer needed and can be deleted."
fi
note "Updates: in the app, Help > Check for Updates."
if lsof -nP -iTCP:8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
	note "$APP_NAME is running. Quit it and open it again to use this version."
elif [ "$UNATTENDED" != 1 ] && ask "Open $APP_NAME now?"; then
	open "$APP"
fi
pause_to_close
