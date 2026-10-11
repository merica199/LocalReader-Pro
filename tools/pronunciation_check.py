"""
Record words the way the app will say them, so a person can check them by ear.

Run with the app's own Python:

    venv/bin/python tools/pronunciation_check.py                  every built-in entry
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
"""
import argparse
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

GAP_SECONDS = 0.7

parser = argparse.ArgumentParser(description="Record words for a listening check.")
parser.add_argument("words", nargs="*", help="words to record (default: every built-in entry)")
parser.add_argument("--out", default=".", help="folder to save into (default: the current folder)")
parser.add_argument("--voice", default="af_bella")
parser.add_argument("--speed", type=float, default=0.9)
args = parser.parse_args()

candidates = [
    APP / "models",
    Path.home() / "Library" / "Application Support" / "LocalReader Pro" / "models",
    Path.home() / "AppData" / "Roaming" / "LocalReader Pro" / "models",
]
models = next((m for m in candidates if (m / "kokoro.int8.onnx").exists()), None)
if models is None:
    sys.exit("The voice model is not downloaded yet. Open the app once, or run the installer.")

kokoro = Kokoro(str(models / "kokoro.int8.onnx"), str(models / "voices.bin"))
pronunciations.install(kokoro)

words = args.words or sorted(pronunciations.ACRONYMS) + sorted(pronunciations.WORDS)
lang = "en-gb" if args.voice.startswith("b") else "en-us"
out = Path(args.out).expanduser()
out.mkdir(parents=True, exist_ok=True)

parts, lines, elapsed = [], [], 0.0
gap = None
for word in words:
    audio, rate = kokoro.create(word + ".", args.voice, args.speed, lang)
    if gap is None:
        gap = np.zeros(int(rate * GAP_SECONDS), dtype=np.float32)
    on_list = word in pronunciations.ACRONYMS or word.lower() in pronunciations.WORDS
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
