"""
Check an installed copy of LocalReader Pro end to end, without its window.

Run with the installed copy's own Python, after an installer has finished:

    <app>/venv/bin/python installers/tests/check_install.py <app>            (Mac)
    <app>\\venv\\Scripts\\python.exe installers\\tests\\check_install.py <app>  (Windows)

where <app> is the installed code folder (the one holding dist/ and venv/).
It starts the app's server on a spare port and checks that it speaks, renders
a sleep recording as MP3 with every sound option, refuses other websites, and
can check for updates. With --update it then applies a real update: it gives
the copy a private stand-in for GitHub one commit ahead, applies it through
the app, and checks the code moved; and that an update whose libraries cannot
install leaves the old version in place. The CI workflow
(.github/workflows/installers.yml) runs it on clean Mac and Windows machines.

Standard library only. Exit code 0 when every check passed.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

failures = 0


def check(name, ok, detail=""):
    global failures
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  [{detail}]"), flush=True)
    failures += not ok


class Server:
    def __init__(self, app: Path, python: str, port: int, env=None):
        self.base = f"http://127.0.0.1:{port}"
        # In the library folder, which git ignores, so the check leaves the
        # code untouched.
        self.log = open(app / "dist" / "userdata" / "check_install_server.log", "a")
        self.proc = subprocess.Popen(
            [python, "-m", "uvicorn", "app.server:app", "--host", "127.0.0.1", "--port", str(port)],
            cwd=str(app / "dist"), stdout=self.log, stderr=subprocess.STDOUT,
            env={**os.environ, **(env or {})},
        )

    def call(self, method, path, body=None, raw=None, headers=None, timeout=120):
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        h = headers or ({"Content-Type": "application/json"} if body is not None else {})
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                payload = r.read()
                ct = r.headers.get("Content-Type", "")
                return r.status, (json.loads(payload) if "json" in ct else payload)
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read() or b"{}")
            except ValueError:
                return e.code, {}

    def wait_ready(self, seconds=120):
        deadline = time.time() + seconds
        while time.time() < deadline:
            if self.proc.poll() is not None:
                return False
            try:
                status, body = self.call("GET", "/api/system/status", timeout=5)
                if status == 200 and body.get("voices"):
                    return True
            except (urllib.error.URLError, ConnectionError, TimeoutError):
                pass
            time.sleep(1)
        return False

    def stop(self):
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(20)
            except subprocess.TimeoutExpired:
                self.proc.kill()


def add_document(server: Server, name: str, text: str) -> str:
    boundary = uuid.uuid4().hex
    form = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{name}\"\r\n"
            f"Content-Type: text/plain\r\n\r\n").encode() + text.encode() + f"\r\n--{boundary}--\r\n".encode()
    status, conv = server.call("POST", "/api/convert/text", raw=form,
                               headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    check("a text document converts", status == 200 and conv.get("pages"), (status, conv))
    doc_id = str(uuid.uuid4())
    server.call("POST", "/api/library", {"id": doc_id, "fileName": name, "totalPages": len(conv["pages"]),
                                         "currentPage": 0, "lastSentenceIndex": 0,
                                         "lastAccessed": time.time() * 1000})
    server.call("POST", "/api/library/content", {"id": doc_id, "pages": conv["pages"]})
    return doc_id


def smoke(app: Path, python: str, port: int) -> None:
    server = Server(app, python, port)
    try:
        check("the server starts and loads the voice", server.wait_ready(), "see dist/userdata/check_install_server.log")
        if failures:
            return
        status, wav = server.call("POST", "/api/synthesize", {
            "text": "Hello from the installer check.", "voice": "af_heart", "speed": 1.0, "rules": []})
        check("it speaks (a WAV comes back)", status == 200 and wav[:4] == b"RIFF" and len(wav) > 20000,
              (status, len(wav) if isinstance(wav, bytes) else wav))

        doc_id = add_document(server, "check.txt", "The harbor is quiet tonight.\n\nRest now... and breathe.")
        request = {"doc_id": doc_id, "voice": "af_heart", "rules": [], "ignore_list": []}
        status, started = server.call("POST", "/api/export/sleep", request)
        check("a sleep recording starts with the default sound options", status == 200, (status, started))
        deadline, s = time.time() + 300, {}
        while time.time() < deadline:
            _, s = server.call("GET", "/api/export/status")
            if not s.get("is_exporting"):
                break
            time.sleep(1)
        out = app / "dist" / "userdata" / (s.get("output_file") or "missing")
        mp3 = out.read_bytes()[:3] if out.is_file() else b""
        check("it renders an MP3 with background, room and loudness (FFmpeg works)",
              s.get("error") is None and out.suffix == ".mp3" and mp3 in (b"ID3", b"\xff\xfb", b"\xff\xf3"),
              s)
        server.call("DELETE", f"/api/library/{doc_id}")

        status, _ = server.call("GET", "/api/library",
                                headers={"Origin": "https://some-website.example", "Sec-Fetch-Site": "cross-site"})
        check("requests from other websites are refused", status == 403, status)

        status, u = server.call("GET", "/api/update/check")
        check("it can check for updates", status == 200 and u.get("current") and not u.get("reason"), u)
    finally:
        server.stop()


def git(app: Path, *args) -> str:
    return subprocess.run(["git", "-C", str(app), *args], check=True, capture_output=True, text=True).stdout.strip()


def apply_and_wait(app: Path, python: str, port: int) -> dict:
    """Ask the app to update itself; return the updater's result."""
    result_file = app / "dist" / "userdata" / "update_result.json"
    result_file.unlink(missing_ok=True)
    server = Server(app, python, port, env={"LOCALREADER_NO_RELAUNCH": "1"})
    try:
        if not server.wait_ready():
            return {"ok": False, "error": "server did not start"}
        status, u = server.call("GET", "/api/update/check")
        check("the update check sees one new version", u.get("behind") == 1 and u.get("can_update"), u)
        status, applied = server.call("POST", "/api/update/apply")
        check("the app accepts the update and closes", status == 200, (status, applied))
        server.proc.wait(30)
    except subprocess.TimeoutExpired:
        check("the app closes for the update", False, "still running after 30 s")
    finally:
        server.stop()
    deadline = time.time() + 600
    while time.time() < deadline and not result_file.exists():
        time.sleep(1)
    return json.loads(result_file.read_text()) if result_file.exists() else {"ok": False, "error": "no result"}


def update(app: Path, python: str, port: int) -> None:
    original_origin = git(app, "remote", "get-url", "origin")
    branch = git(app, "rev-parse", "--abbrev-ref", "HEAD")
    start = git(app, "rev-parse", "HEAD")
    with tempfile.TemporaryDirectory() as tmp:
        remote = Path(tmp) / "remote.git"
        work = Path(tmp) / "work"
        subprocess.run(["git", "clone", "--quiet", "--bare", str(app), str(remote)], check=True)
        subprocess.run(["git", "clone", "--quiet", "--branch", branch, str(remote), str(work)], check=True)
        ident = ["-c", "user.name=check", "-c", "user.email=check@example.invalid"]
        try:
            git(app, "remote", "set-url", "origin", str(remote))
            git(app, "fetch", "--quiet", "origin")

            # A good update, which also changes the requirements file, so the
            # library step runs (and installs nothing new).
            req = work / "dist" / "requirements.txt"
            req.write_text(req.read_text() + "\n# check_install: requirements changed\n")
            subprocess.run(["git", "-C", str(work), *ident, "commit", "--quiet", "-am", "Check: a good update"], check=True)
            subprocess.run(["git", "-C", str(work), "push", "--quiet", "origin", branch], check=True)
            good = git(work, "rev-parse", "HEAD")
            result = apply_and_wait(app, python, port)
            check("a good update applies", result.get("ok") and git(app, "rev-parse", "HEAD") == good, result)

            # An update whose libraries cannot install must change nothing.
            req.write_text(req.read_text() + "localreader-no-such-package==1.0\n")
            subprocess.run(["git", "-C", str(work), *ident, "commit", "--quiet", "-am", "Check: a broken update"], check=True)
            subprocess.run(["git", "-C", str(work), "push", "--quiet", "origin", branch], check=True)
            result = apply_and_wait(app, python, port)
            check("a broken update is refused and the app is left as it was",
                  not result.get("ok") and git(app, "rev-parse", "HEAD") == good, result)
        finally:
            # Back to where it started, following its real origin again.
            git(app, "remote", "set-url", "origin", original_origin)
            git(app, "reset", "--quiet", "--hard", start)
            git(app, "fetch", "--quiet", "origin")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("app", help="the installed code folder (holding dist/ and venv/)")
    p.add_argument("--port", type=int, default=8770)
    p.add_argument("--update", action="store_true", help="also apply a real update")
    a = p.parse_args()
    app = Path(a.app).resolve()
    smoke(app, sys.executable, a.port)
    if a.update and not failures:
        update(app, sys.executable, a.port)
    print(f"\n{failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
