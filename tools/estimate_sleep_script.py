"""
Estimate how long a sleep script will run, the way the app's Export dialog does.

Run with the app's own Python:

    venv/bin/python tools/estimate_sleep_script.py my-script.txt [more.txt ...]

It uses the speed and pauses saved in the app's sleep settings (the last ones
used in the Export dialog), or the defaults if there are none yet. Several
files are timed as one recording, the way they would be if joined into one.

When Azure voices are chosen for exports (Settings > Azure voices), it times
the script at Azure's pace instead, and says how many characters of the
month's free allowance it will use and how long the free tier takes to make it.
"""
import json
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "dist" / "app"
sys.path.insert(0, str(APP))

from logic.pronunciations import plain  # noqa: E402
from logic.sleep_script import Pacing, plan_text, estimate_seconds  # noqa: E402
from logic.sleep_render import CHARS_PER_SECOND_AT_1X  # noqa: E402
from logic import azure_tts  # noqa: E402

if len(sys.argv) < 2:
    sys.exit(__doc__)

settings_file = APP.parent / "userdata" / "sleep_settings.json"
try:
    settings = json.loads(settings_file.read_text())
    speed, pacing = settings["speed"], Pacing(**settings["pacing"])
    source = "your saved sleep settings"
except (OSError, KeyError, ValueError):
    speed, pacing = 0.9, Pacing()
    source = "the default sleep settings"
azure = azure_tts.load_settings(APP.parent / "userdata" / "azure.json")
use_azure = azure["use_for_exports"] and azure_tts.configured(azure)
chars_per_second = (azure_tts.CHARS_PER_SECOND_AT_1X if use_azure else CHARS_PER_SECOND_AT_1X) * speed

total = pacing.lead_in + pacing.tail
billed = pieces = 0
for name in sys.argv[1:]:
    events = plan_text(Path(name).read_text(encoding="utf-8"), pacing)
    seconds = estimate_seconds(events, pacing, chars_per_second) - pacing.lead_in - pacing.tail
    total += seconds
    spoken = sum(len(plain(text)) for kind, text in events if kind == "say")
    billed += sum(azure_tts.billed_characters(text) for kind, text in events if kind == "say")
    pieces += sum(1 for kind, _ in events if kind == "say")
    print(f"{Path(name).name}: {seconds / 60:.1f} min ({spoken:,} spoken characters)")
voice = f"the Azure voice {azure['voice']}" if use_azure else "the voice on this computer"
print(f"Total: {total / 60:.1f} min, using {source} (speed {speed}) and {voice}.")
if use_azure:
    print(
        f"Azure: about {billed:,} characters of the {azure_tts.FREE_CHARACTERS_PER_MONTH:,} free each month, "
        f"and about {pieces / azure_tts.FREE_REQUESTS_PER_MINUTE:.0f} min to make on the free tier "
        f"({pieces} sentences at {azure_tts.FREE_REQUESTS_PER_MINUTE} a minute)."
    )
