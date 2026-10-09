"""
Apply an update to an installed copy of LocalReader Pro, once the app has exited.

Started by the app's Update button (dist/app/routers/update.py), never by hand.
It uses only the standard library, because it runs with the app's own Python
while that environment's libraries may be replaced.

Order matters. Libraries are installed from the new version's requirements
before the code moves, so a failed install leaves the old version intact and
working; the code moves only after its libraries are in place.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def log(path: Path, message: str) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {message}\n")


def wait_for_exit(pid: int, timeout: float) -> bool:
    """True once the process has exited."""
    deadline = time.time() + timeout
    if sys.platform == "win32":
        import ctypes

        SYNCHRONIZE = 0x00100000
        handle = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE, False, pid)
        if not handle:
            return True  # already gone
        try:
            # WAIT_OBJECT_0 is 0.
            return ctypes.windll.kernel32.WaitForSingleObject(handle, int(timeout * 1000)) == 0
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    while time.time() < deadline:
        try:
            os.kill(pid, 0)  # on Unix, signal 0 only asks whether it exists
        except ProcessLookupError:
            return True
        except PermissionError:
            pass
        time.sleep(0.2)
    return False


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repo", required=True)
    p.add_argument("--git", required=True)
    p.add_argument("--pid", type=int, required=True)
    p.add_argument("--result", required=True)
    p.add_argument("--log", required=True)
    p.add_argument("--relaunch", default="null")
    a = p.parse_args()
    repo, result_file, log_file = Path(a.repo), Path(a.result), Path(a.log)
    relaunch = json.loads(a.relaunch)

    def git(*args, check=True):
        r = subprocess.run([a.git, "-C", str(repo), *args], capture_output=True, text=True,
                           creationflags=NO_WINDOW)
        if check and r.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr.strip()[-400:]}")
        return r.stdout.strip()

    def finish(result: dict) -> int:
        result_file.write_text(json.dumps(result))
        log(log_file, json.dumps(result))
        if relaunch:
            try:
                flags = 0
                if sys.platform == "win32":
                    flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
                subprocess.Popen(relaunch["args"], cwd=relaunch.get("cwd"), creationflags=flags,
                                 close_fds=True, stdin=subprocess.DEVNULL,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                log(log_file, "relaunched")
            except Exception as e:
                log(log_file, f"relaunch failed: {e}")
        return 0 if result.get("ok") else 1

    log(log_file, f"waiting for the app (pid {a.pid}) to exit")
    if not wait_for_exit(a.pid, 60):
        # Nothing has changed yet, so no relaunch: the app is still running.
        result = {"ok": False, "error": "The app did not close, so nothing was updated."}
        result_file.write_text(json.dumps(result))
        log(log_file, json.dumps(result))
        return 1

    try:
        upstream = git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
        before = git("rev-parse", "--short", "HEAD")
        ahead, behind = (int(n) for n in git("rev-list", "--left-right", "--count",
                                             f"HEAD...{upstream}").split())
        if behind == 0:
            return finish({"ok": True, "from": before, "to": before, "note": "Already up to date"})
        if ahead or git("status", "--porcelain", "--untracked-files=no"):
            return finish({"ok": False, "error": "This copy changed since the check; nothing was updated."})

        old_req = git("show", "HEAD:dist/requirements.txt", check=False)
        new_req = git("show", f"{upstream}:dist/requirements.txt", check=False)
        if new_req and new_req != old_req:
            log(log_file, "requirements changed; installing libraries")
            with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
                f.write(new_req + "\n")
            try:
                pip = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
                     "-r", f.name],
                    capture_output=True, text=True, creationflags=NO_WINDOW,
                )
            finally:
                os.unlink(f.name)
            log(log_file, pip.stdout[-4000:] + pip.stderr[-4000:])
            if pip.returncode != 0:
                return finish({"ok": False, "error": "Installing the update's libraries failed, "
                               "so the app was left as it was. Details are in userdata/update.log."})

        git("merge", "--ff-only", upstream)
        after = git("rev-parse", "--short", "HEAD")
        return finish({"ok": True, "from": before, "to": after, "count": behind})
    except Exception as e:
        return finish({"ok": False, "error": str(e)})


if __name__ == "__main__":
    sys.exit(main())
