"""
Check for and apply updates to an installed copy.

The installers make every installed copy a git clone that follows a branch on
GitHub, so an update is a fast-forward to what that branch has. Checking goes
online only when asked; nothing runs in the background.

Applying needs the app closed (on Windows a running program's files cannot be
replaced), so a separate process, installers/update.py, waits for this one to
exit, installs any libraries the update changed, moves the code forward, and
starts the app again. It records the outcome in userdata/update_result.json,
which the next launch reports and clears.
"""
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..config import base_dir, userdata_dir

router = APIRouter()

# dist/app -> dist -> the repository
REPO = base_dir.parent.parent
RESULT_FILE = userdata_dir / "update_result.json"
LOG_FILE = userdata_dir / "update.log"
# On Windows the app runs without a console, and every git call would otherwise
# flash a console window.
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# Called to close the app before an update is applied. main.py points it at
# the window; without one (the server run on its own) the process just exits.
quit_app = None


def find_git() -> Optional[str]:
    """git on PATH, or where its installers put it when PATH does not say."""
    found = shutil.which("git")
    if found:
        return found
    candidates = [Path("/usr/bin/git"), Path("/opt/homebrew/bin/git"), Path("/usr/local/bin/git")]
    if sys.platform == "win32":
        for root in (os.environ.get("ProgramFiles"), os.environ.get("LOCALAPPDATA")):
            if root:
                candidates += [Path(root) / "Git" / "cmd" / "git.exe",
                               Path(root) / "Programs" / "Git" / "cmd" / "git.exe"]
    return next((str(c) for c in candidates if c.is_file()), None)


def _git(git: str, *args: str, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(
        [git, "-C", str(REPO), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        creationflags=NO_WINDOW,
    )


def _commit(git: str, ref: str) -> Dict:
    out = _git(git, "log", "-1", "--format=%h%x09%cI", ref).stdout.strip()
    short, _, date = out.partition("\t")
    return {"hash": short, "date": date}


def update_status(fetch: bool) -> Dict:
    """Where this copy stands against the branch it follows."""
    status: Dict = {"available": False, "can_update": False, "reason": None,
                    "behind": 0, "ahead": 0, "commits": [], "current": None, "latest": None}
    git = find_git()
    if not git:
        status["reason"] = "Git is not installed, so this copy cannot update itself."
        return status
    if not (REPO / ".git").exists():
        status["reason"] = ("This copy was not installed from a git clone. Clone the "
                            "repository and run its installer to get updates.")
        return status
    status["current"] = _commit(git, "HEAD")
    upstream = _git(git, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    if upstream.returncode != 0:
        status["reason"] = "This copy does not follow a branch on GitHub."
        return status
    upstream = upstream.stdout.strip()
    remote, _, branch = upstream.partition("/")
    if fetch:
        try:
            fetched = _git(git, "fetch", "--quiet", remote, branch, timeout=90)
        except subprocess.TimeoutExpired:
            status["reason"] = "GitHub did not answer in time. Try again later."
            return status
        if fetched.returncode != 0:
            status["reason"] = "Could not reach GitHub: " + (fetched.stderr.strip() or "unknown error")[-300:]
            return status
    counts = _git(git, "rev-list", "--left-right", "--count", f"HEAD...{upstream}").stdout.split()
    status["ahead"], status["behind"] = (int(counts[0]), int(counts[1])) if len(counts) == 2 else (0, 0)
    status["latest"] = _commit(git, upstream)
    log = _git(git, "log", "--format=%h%x09%s", f"HEAD..{upstream}").stdout.strip()
    status["commits"] = [
        {"hash": h, "subject": s} for h, _, s in (line.partition("\t") for line in log.splitlines())
    ]
    status["available"] = status["behind"] > 0
    changed = _git(git, "status", "--porcelain", "--untracked-files=no").stdout.strip()
    if status["available"]:
        if status["ahead"]:
            status["reason"] = ("This copy has its own changes that are not on GitHub, so it "
                                "cannot be moved forward automatically.")
        elif changed:
            status["reason"] = ("Files in this copy have been edited, so an update could "
                                "overwrite them. Undo the edits or update by hand.")
        else:
            status["can_update"] = True
    return status


def relaunch_command() -> Optional[Dict]:
    """How the updater starts the app again, or None when it cannot."""
    # Tests apply updates to a scratch install while the real app holds the
    # port; starting the scratch one would only show "already running".
    if os.environ.get("LOCALREADER_NO_RELAUNCH"):
        return None
    if sys.platform == "darwin":
        # Installed copies live at <name>.app/Contents/Resources/LocalReader-Pro.
        bundle = REPO.parents[2] if len(REPO.parents) > 2 else None
        if bundle and bundle.suffix == ".app":
            return {"args": ["open", str(bundle)], "cwd": None}
        return None
    if sys.platform == "win32":
        pythonw = REPO / "venv" / "Scripts" / "pythonw.exe"
        if pythonw.is_file():
            return {"args": [str(pythonw), str(REPO / "dist" / "main.py")], "cwd": str(REPO / "dist")}
    return None


@router.get("/api/update/check")
def check_for_update():
    return update_status(fetch=True)


@router.post("/api/update/apply")
def apply_update():
    status = update_status(fetch=True)
    if not status["can_update"]:
        return JSONResponse({"error": status["reason"] or "Already up to date"}, status_code=409)
    updater = REPO / "installers" / "update.py"
    if not updater.is_file():
        return JSONResponse({"error": "The updater is missing from this copy."}, status_code=500)

    userdata_dir.mkdir(parents=True, exist_ok=True)
    RESULT_FILE.unlink(missing_ok=True)
    args = [
        sys.executable, str(updater),
        "--repo", str(REPO),
        "--git", find_git(),
        "--pid", str(os.getpid()),
        "--result", str(RESULT_FILE),
        "--log", str(LOG_FILE),
        "--relaunch", json.dumps(relaunch_command()),
    ]
    if sys.platform == "win32":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP | NO_WINDOW
        subprocess.Popen(args, creationflags=flags, close_fds=True,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.Popen(args, start_new_session=True, close_fds=True,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def close():
        # Long enough for this reply to reach the window first.
        time.sleep(1.0)
        if quit_app:
            try:
                quit_app()
            except Exception as e:
                print(f"[UPDATE] Closing the window failed: {e}")
        # The updater waits for this process to end, so it must end even if
        # closing the window did not take it down.
        time.sleep(3.0)
        os._exit(0)

    threading.Thread(target=close, daemon=True).start()
    return {"status": "restarting", "updating_to": status["latest"]}


@router.get("/api/update/last")
def last_update_result():
    """The outcome of the update applied before this launch, reported once."""
    if not RESULT_FILE.exists():
        return {"result": None}
    try:
        result = json.loads(RESULT_FILE.read_text())
    except Exception:
        result = {"ok": False, "error": "The update left an unreadable result."}
    RESULT_FILE.unlink(missing_ok=True)
    return {"result": result}


@router.get("/api/update/version")
def current_version():
    """What this copy is, without going online."""
    git = find_git()
    if git and (REPO / ".git").exists():
        return {"commit": _commit(git, "HEAD")}
    return {"commit": None}
