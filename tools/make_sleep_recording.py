"""
Make a sleep recording from a script, through the running app, without
clicking through it.

Run with the app's own Python while LocalReader Pro is open:

    venv/bin/python tools/make_sleep_recording.py my-script.txt
    venv/bin/python tools/make_sleep_recording.py my-script.txt --preview
    venv/bin/python tools/make_sleep_recording.py my-script.txt --copy-to ~/Desktop

It does what a person would do in the app:

1. Adds the script to the library, named after the file. If a document with
   that name is already there, its text is replaced instead, so re-recording
   an edited script does not pile up copies.
2. Starts a sleep recording (Export Audio, Sleep mode) with the voice,
   pronunciation rules and ignore list from the Voice & Audio settings, and
   the sleep options last saved in the Export dialog.
3. Waits, printing progress, and prints where the finished file is.

If Azure voices are chosen for exports (Settings > Azure voices), the
recording is made in that Azure voice. A full Azure recording needs an
approved pronunciation check of this exact script first
(tools/pronunciation_check.py --azure --script, then --approve), so a month's
free allowance is never spent on words nobody has heard; a preview does not.
--kokoro records in the voice on this computer instead.

--preview makes only the first minute, like the dialog's Preview button.
--copy-to also copies the finished file to a folder. Sentences already made
for an earlier version are reused, so a re-recording after small edits is
quick. Exit code 0 on success.
"""
import argparse
import json
import shutil
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "dist" / "app"
USERDATA = APP.parent / "userdata"
sys.path.insert(0, str(APP))

from logic.text_reader import decode_text, text_to_pages  # noqa: E402
from logic import azure_checks  # noqa: E402

parser = argparse.ArgumentParser(description="Make a sleep recording through the running app.")
parser.add_argument("script", help="the script, a .txt file")
parser.add_argument("--preview", action="store_true", help="make only the first minute")
parser.add_argument("--copy-to", help="also copy the finished file to this folder")
parser.add_argument("--port", type=int, default=8000, help="the app's port (8000 unless testing)")
parser.add_argument("--kokoro", action="store_true", help="use the voice on this computer even if Azure is chosen")
args = parser.parse_args()

BASE = f"http://127.0.0.1:{args.port}"


def call(method, path, body=None):
    request = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        # The app refuses requests that do not come from its own page.
        headers={"Content-Type": "application/json", "Origin": BASE},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        try:
            detail = json.loads(detail).get("detail") or json.loads(detail).get("error") or detail
        except ValueError:
            pass
        sys.exit(f"The app refused: {detail}")


script = Path(args.script).expanduser()
if not script.is_file():
    sys.exit(f"No such file: {script}")

try:
    status = call("GET", "/api/system/status")
except urllib.error.URLError:
    sys.exit("LocalReader Pro is not running. Open it, wait for the green dot, and try again.")
azure = call("GET", "/api/azure/settings")
use_azure = azure.get("use_for_exports") and azure.get("configured") and not args.kokoro
if use_azure and not args.preview:
    why = azure_checks.problem(USERDATA / "azure_checks.json", script, azure["voice"])
    if why:
        approve = f"  python tools/pronunciation_check.py --approve \"{script}\""
        if why.startswith("the check was recorded"):
            sys.exit(f"Not recording in Azure yet: {why}.\nOnce someone has listened and every word is right:\n{approve}")
        sys.exit(
            f"Not recording in Azure yet: {why}.\n"
            f"Check its pronunciations first:\n"
            f"  python tools/pronunciation_check.py --azure --script \"{script}\" <its technical words>\n"
            f"then, once someone has listened and every word is right:\n{approve}"
        )
if not use_azure and not status.get("model_loaded"):
    sys.exit("LocalReader Pro's voice is not ready yet. Wait for the green dot and try again.")

# 1. Into the library, replacing a document of the same name.
pages = text_to_pages(decode_text(script.read_bytes()))
library = call("GET", "/api/library")
existing = next((item for item in library if item.get("fileName") == script.name), None)
doc_id = existing["id"] if existing else str(uuid.uuid4())
call("POST", "/api/library/content", {"id": doc_id, "pages": pages})
call("POST", "/api/library", {
    "id": doc_id,
    "fileName": script.name,
    "totalPages": len(pages),
    "currentPage": existing.get("currentPage", 0) if existing else 0,
    "lastSentenceIndex": existing.get("lastSentenceIndex", 0) if existing else 0,
    "lastAccessed": time.time(),
})
print(f"{'Updated' if existing else 'Added'} \"{script.name}\" in the library ({len(pages)} pages).")

# 2. The user's own voice, rules and saved sleep options.
settings = call("GET", "/api/settings")
sleep = call("GET", "/api/export/sleep/settings")["settings"]
request = {
    **sleep,
    "doc_id": doc_id,
    "provider": "azure" if use_azure else "kokoro",
    "voice": azure["voice"] if use_azure else (settings.get("voice_id") or "af_bella"),
    "rules": settings.get("pronunciationRules", []),
    "ignore_list": settings.get("ignoreList", []),
}
plan = call("POST", "/api/export/sleep/plan", request)
length = time.strftime("%H:%M:%S", time.gmtime(plan["estimated_seconds"]))
print(
    f"Voice {request['voice']}, speed {sleep['speed']}. About {length} long, "
    f"{plan['pieces']} pieces, {plan['cached_pieces']} already made."
)
if use_azure:
    usage = plan["azure_usage"]
    print(
        f"Azure: sends about {plan['azure_characters']:,} characters; about {usage['characters']:,} "
        f"of {usage['free_allowance']:,} used this month from this computer."
    )
    if plan["azure_characters"] + usage["characters"] > usage["free_allowance"]:
        print("That is more than the free allowance has left: Azure will refuse the rest, and the "
              "sentences made so far are kept, so it can be finished next month.")
if plan.get("needs_ffmpeg") and not plan.get("ffmpeg_installed"):
    sys.exit("FFmpeg is needed for these sound options and is not installed. Open Export Audio in the app once; it offers it.")

started = call("POST", "/api/export/sleep/preview" if args.preview else "/api/export/sleep", request)
if "error" in started:
    sys.exit(f"Could not start: {started['error']}")
print("Recording" + (" the first minute" if args.preview else "") + "...")

# 3. Wait for it.
last = None
while True:
    time.sleep(2)
    s = call("GET", "/api/export/status")
    if not s.get("is_exporting"):
        break
    phase = s.get("phase")
    line = (
        f"  sentence {s.get('progress')} of {s.get('total')}"
        if phase == "voice"
        else f"  finishing ({phase}): {round(100 * (s.get('phase_progress') or 0))}%"
    )
    if line != last and (phase != "voice" or s.get("progress", 0) % 50 == 0):
        print(line, flush=True)
        last = line

if s.get("error"):
    sys.exit(f"The recording failed: {s['error']}")
name = s.get("output_file")
made = (USERDATA / "sleep_work" / name) if args.preview else (USERDATA / name)
print(f"Done: {made}")
if s.get("audio_seconds"):
    print("Length: " + time.strftime("%H:%M:%S", time.gmtime(s["audio_seconds"])))
if args.copy_to:
    folder = Path(args.copy_to).expanduser()
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copy2(made, folder / name)
    print(f"Copied to: {folder / name}")
