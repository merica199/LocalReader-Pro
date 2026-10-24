"""
Record words the way the app will say them, so a person can check them by ear.

Run with the app's own Python:

    venv/bin/python tools/pronunciation_check.py                  every entry, built-in and personal
    venv/bin/python tools/pronunciation_check.py kinase diastole  just these words
    venv/bin/python tools/pronunciation_check.py --out ~/Desktop  where to save

It writes pronunciation-check.mp3 (a WAV if FFmpeg is missing), one word at a
time with a pause after each, and pronunciation-check.txt, which lists every
word with its time in the recording so a wrong one is easy to find.

Words are spoken through the same engine and built-in pronunciation list the
app uses, so a word that is not on the list comes out as the engine's own
guess: a quick way to find out whether a new word needs an entry.

Why this exists: an AI agent can read the sounds the engine produces, but it
cannot hear them. After adding or changing entries, record them and have a
person listen. Whoever knows the field best (for medical terms, a medical
student over anyone else) is the right judge.

Azure voices (Settings > Azure voices) read words their own way, so before a
script is recorded in one, its words are checked in that voice:

    venv/bin/python tools/pronunciation_check.py --azure --script my-script.txt renin kinase
    venv/bin/python tools/pronunciation_check.py --approve my-script.txt

--azure records the words named, plus every word in the script that is on a
pronunciation list or written with its sounds ([live](/lˈɪv/)), in the Azure
voice saved in Settings (or --voice), each one request at the free tier's
pace (20 a minute). It costs a few characters per word. --approve, once the
person has listened and every word is right, lets
tools/make_sleep_recording.py record that exact script (logic/azure_checks.py).
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

APP = Path(__file__).resolve().parent.parent / "dist" / "app"
sys.path.insert(0, str(APP))

from kokoro_onnx import Kokoro  # noqa: E402
from logic import pronunciations  # noqa: E402
from logic.dependency_manager import get_ffmpeg_path  # noqa: E402
from logic import azure_checks, azure_tts  # noqa: E402

GAP_SECONDS = 0.7
USERDATA = APP.parent / "userdata"
CHECKS = USERDATA / "azure_checks.json"

sys.stdout.reconfigure(encoding="utf-8")
parser = argparse.ArgumentParser(description="Record words for a listening check.")
parser.add_argument("words", nargs="*", help="words to record (default: every built-in entry)")
parser.add_argument("--out", default=".", help="folder to save into (default: the current folder)")
parser.add_argument("--voice", help="voice (default: af_bella, or the saved Azure voice with --azure)")
parser.add_argument("--speed", type=float, default=0.9)
parser.add_argument("--azure", action="store_true", help="record in an Azure voice")
parser.add_argument("--script", help="with --azure: the script to check, whose listed words are added")
parser.add_argument("--approve", metavar="SCRIPT", help="mark the script's Azure check as listened to and right")
args = parser.parse_args()

if args.approve:
    entry = azure_checks.approve(CHECKS, Path(args.approve).expanduser())
    if entry is None:
        sys.exit("No Azure check was recorded for this script as it is now. Record one with --azure --script first.")
    print(f"Approved: {entry['script']} in {entry['voice']} ({len(entry['words'])} words). It can be recorded now.")
    sys.exit(0)

if args.azure:
    azure = azure_tts.load_settings(USERDATA / "azure.json")
    if not azure_tts.configured(azure):
        sys.exit("Azure voices are not set up: add the key and region in Settings > Azure voices.")
    voice = args.voice or azure["voice"]
    words = list(args.words)
    if args.script:
        text = Path(args.script).expanduser().read_text(encoding="utf-8")
        # Every written pronunciation, and every word on either list (they
        # are the words known to be hard), in the order they first appear.
        found = [m["shown"] for m in pronunciations.OVERRIDE_RE.finditer(text)]
        plain_text = pronunciations.plain(text)
        for section in ("kokoro", "azure"):
            table = pronunciations._table(section)
            found += [m.group(0) for m in table.pattern.finditer(plain_text) if not m["override"]]
        for word in found:
            word = re.sub(r"['’]s$", "", word)
            if word.lower() not in {w.lower() for w in words}:
                words.append(word)
    if not words:
        sys.exit("Name the words to check, or give --script.")
    out = Path(args.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    print(f"Recording {len(words)} words in {voice} (about {len(words) * 3 // 60 + 1} min at the free tier's pace)...", flush=True)
    rate = azure_tts.SAMPLE_RATE
    gap = np.zeros(int(rate * GAP_SECONDS), dtype=np.float32)
    parts, lines, elapsed = [], [], 0.0
    # The written pronunciations from the script, so a word checked here is
    # said the way the script says it.
    marked = {}
    if args.script:
        marked = {m["shown"]: m.group(0) for m in pronunciations.OVERRIDE_RE.finditer(text)}
    for word in words:
        audio = azure_tts.synthesize(azure, marked.get(word, word) + ".", voice, args.speed,
                                     usage_file=USERDATA / "azure_usage.json")
        entry = pronunciations.lookup(word, "azure")
        note = "  (written in the script)" if word in marked else ("" if entry else "  (Azure's own reading)")
        lines.append(f"{int(elapsed // 60)}:{int(elapsed % 60):02d}  {word}{note}")
        parts += [audio, gap]
        elapsed += (len(audio) + len(gap)) / rate
    wav = out / "pronunciation-check.wav"
    sf.write(wav, np.concatenate(parts), rate)
    recording = wav
    ffmpeg = get_ffmpeg_path()
    if ffmpeg:
        mp3 = out / "pronunciation-check.mp3"
        subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", str(wav), "-b:a", "96k", str(mp3)], check=True)
        wav.unlink()
        recording = mp3
    (out / "pronunciation-check.txt").write_text(
        f"Each word in pronunciation-check, in the order spoken, in the Azure voice {voice}.\n"
        "Listen for wrong stress or wrong sounds, and note the time of any that sound off.\n\n"
        + "\n".join(lines) + "\n",
        encoding="utf-8",
    )
    if args.script:
        azure_checks.record(CHECKS, Path(args.script).expanduser(), voice, words)
    print(f"{len(words)} words, {elapsed / 60:.1f} minutes: {recording}")
    print(f"Word list with times: {out / 'pronunciation-check.txt'}")
    if args.script:
        print("When a person has listened and every word is right: --approve " + args.script)
    sys.exit(0)

args.voice = args.voice or "af_bella"

candidates = [
    APP / "models",
    Path.home() / "Library" / "Application Support" / "LocalReader Pro" / "models",
    Path.home() / "AppData" / "Roaming" / "LocalReader Pro" / "models",
]
# Either voice model will do (pronunciation is the same in both): an Intel or
# AMD install may have only the full-precision kokoro.onnx.
model = next(
    (m / name for m in candidates for name in ("kokoro.int8.onnx", "kokoro.onnx") if (m / name).exists()),
    None,
)
if model is None:
    sys.exit("The voice model is not downloaded yet. Open the app once, or run the installer.")

kokoro = Kokoro(str(model), str(model.parent / "voices.bin"))
pronunciations.install(kokoro)

table = pronunciations._table()  # the built-in list plus any personal entries
words = args.words or sorted(table.acronyms) + sorted(table.words)
lang = "en-gb" if args.voice.startswith("b") else "en-us"
out = Path(args.out).expanduser()
out.mkdir(parents=True, exist_ok=True)

parts, lines, elapsed = [], [], 0.0
gap = None
for word in words:
    audio, rate = kokoro.create(word + ".", args.voice, args.speed, lang)
    if gap is None:
        gap = np.zeros(int(rate * GAP_SECONDS), dtype=np.float32)
    on_list = pronunciations.lookup(word) is not None
    note = "" if on_list else "  (not on the list: the engine's own guess)"
    lines.append(f"{int(elapsed // 60)}:{int(elapsed % 60):02d}  {word}{note}")
    parts += [audio, gap]
    elapsed += (len(audio) + len(gap)) / rate

wav = out / "pronunciation-check.wav"
sf.write(wav, np.concatenate(parts), rate)
recording = wav
ffmpeg = get_ffmpeg_path()
if ffmpeg:
    mp3 = out / "pronunciation-check.mp3"
    subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", str(wav), "-b:a", "96k", str(mp3)], check=True)
    wav.unlink()
    recording = mp3

(out / "pronunciation-check.txt").write_text(
    "Each word in pronunciation-check, in the order spoken, with its time in the recording.\n"
    "Listen for wrong stress or wrong sounds, and note the time of any that sound off.\n\n"
    + "\n".join(lines)
    + "\n",
    encoding="utf-8",
)
print(f"{len(words)} words, {elapsed / 60:.1f} minutes: {recording}")
print(f"Word list with times: {out / 'pronunciation-check.txt'}")
