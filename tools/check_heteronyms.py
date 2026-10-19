"""
Find the words in a script that are spelled the same but said two ways, and
show which way the voice will say each one.

Run with the app's own Python:

    venv/bin/python tools/check_heteronyms.py my-script.txt [more.txt ...]
    venv/bin/python tools/check_heteronyms.py my-script.txt --word live --word lead

"Cells live for weeks" and "a live vaccine" spell "live" the same. The voice
engine (espeak-ng) picks a reading from the words around it and often picks
the wrong one. Tested: "red blood cells live for about four months" gets the
sound of "a live concert", "lead poisoning" gets "leed", and "the heart
contracts" and "pressure increases" get the noun's stress.

For each such word in the script (the list is tools/heteronyms.json), it
prints the line, the sentence as the voice receives it, which reading the
voice will use, and what to write for the other one. Whoever wrote the script
decides which meaning each sentence has. A wrong one is fixed by writing its
pronunciation into the script, for example [live](/lˈɪv/), which the app reads
with those sounds and displays as just the word. Run the check again
afterwards: a fixed word shows as written.

The script is read the way a sleep recording reads it: the same sentence
splitting, the built-in and personal pronunciation lists, and the
pronunciation rules saved in the app's settings. A written pronunciation that
uses a sound the voice model does not have, or markup that looks like one but
is not, is reported as an error (exit code 1).

To add a word to tools/heteronyms.json, take each reading's sounds from the
engine's own output where it produces them (phonemize a sentence using that
reading, such as "to contract" and "a contract"), so that the check recognizes
them in its output.
"""
import argparse
import json
import re
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "dist" / "app"
sys.path.insert(0, str(APP))

from kokoro_onnx.tokenizer import Tokenizer  # noqa: E402
from logic import pronunciations  # noqa: E402
from logic.sleep_script import plan_text  # noqa: E402
from logic.text_reader import decode_text  # noqa: E402
from logic.text_normalizer import apply_custom_pronunciations  # noqa: E402

LIST = Path(__file__).with_name("heteronyms.json")
HETERONYMS = {w: r for w, r in json.loads(LIST.read_text(encoding="utf-8")).items() if not w.startswith("_")}

_WORDS = "|".join(re.escape(w) for w in sorted(HETERONYMS, key=len, reverse=True))
# A written pronunciation, or one of the words on its own.
FIND_RE = re.compile(
    r"(?P<override>" + pronunciations.OVERRIDE + r")|(?<![\w'’])(?P<word>" + _WORDS + r")(?![\w'’])",
    re.IGNORECASE,
)
# Something shaped like a written pronunciation that is not one: a space
# inside, or the slashes missing.
NEAR_MISS_RE = re.compile(r"\[[^\[\]]+\]\s*\([^)]*\)")
PUNCTUATION = ".,;:!?\"'“”‘’()"


def occurrences(text):
    """The heteronyms in a text, in order: (word as written, its sounds if written, start)."""
    found = []
    for m in FIND_RE.finditer(text):
        if m["override"]:
            if m["shown"].lower() in HETERONYMS:
                found.append((m["shown"], m["sounds"], m.start()))
        else:
            found.append((m["word"], None, m.start()))
    return found


def stressless(sounds):
    return re.sub("[ˈˌ]", "", sounds)


def stress_at(sounds):
    i = sounds.find("ˈ")
    return len(stressless(sounds[:i])) if i >= 0 else None


def reading_of(token, readings):
    """Which reading a word in the engine's output is, or None."""
    for r in readings:
        if r["sounds"] == token:
            return r
    same = [r for r in readings if stressless(r["sounds"]) == stressless(token)]
    if len(same) == 1:
        return same[0]
    # The readings differ only in stress: match where the stress falls.
    return next((r for r in same if stress_at(r["sounds"]) == stress_at(token)), None)


def written_as(word, reading):
    return f"[{word}](/{reading['sounds']}/)"


def main():
    # On Windows, Python writes to a pipe in the old code page (usually
    # Windows-1252), which has none of these phonetic symbols: an agent
    # reading the output would get a crash at the first one.
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Check how a script's heteronyms will be read.")
    parser.add_argument("scripts", nargs="+", help="script files (.txt)")
    parser.add_argument("--word", action="append", default=[], help="check only this word (repeatable)")
    args = parser.parse_args()
    only = {w.lower() for w in args.word}
    unknown_words = only - set(HETERONYMS)
    if unknown_words:
        print(f"Not on the list in {LIST.name}: {', '.join(sorted(unknown_words))}")

    tokenizer = Tokenizer()
    vocab = set(tokenizer.vocab)
    settings = {}
    try:
        settings = json.loads((APP.parent / "userdata" / "settings.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    rules, ignore = settings.get("pronunciationRules", []), settings.get("ignoreList", [])
    voice = settings.get("voice_id") or "af_bella"
    if voice[:1] not in "ab":
        sys.exit(f"The voice {voice} is not an English one; this check is for English.")
    lang = "en-gb" if voice.startswith("b") else "en-us"
    if lang == "en-gb":
        print("Your voice is British; the readings listed are American, so some may not be recognized.\n")

    errors = 0
    for name in args.scripts:
        # Decoded the way the app opens a text file (byte order mark, UTF-8, then Windows-1252).
        text = decode_text(Path(name).read_bytes())
        lines = [(n, line) for n, line in enumerate(text.replace("\r\n", "\n").split("\n"), 1)
                 if not line.lstrip().startswith("#")]

        # Written pronunciations the voice cannot say, anywhere in the script.
        for n, line in lines:
            for m in pronunciations.OVERRIDE_RE.finditer(line):
                missing = sorted(set(m["sounds"]) - vocab)
                if missing:
                    errors += 1
                    print(f"{name}:{n}: ERROR {m.group(0)} uses sounds the voice model does not have: {' '.join(missing)}")
            for m in NEAR_MISS_RE.finditer(line):
                if not pronunciations.OVERRIDE_RE.fullmatch(m.group(0)):
                    errors += 1
                    print(f"{name}:{n}: ERROR {m.group(0)} is not read as a pronunciation. "
                          "Write [word](/sounds/), with no spaces.")

        # Each heteronym's line, found in the same order the plan meets them.
        line_of = [n for n, line in lines for _ in occurrences(line)]
        report, written, by_voice = [], 0, 0
        index = 0
        for kind, piece in plan_text(text):
            if kind != "say":
                continue
            found = occurrences(piece)
            if not found:
                continue
            spoken = pronunciations.phonemize_with(
                tokenizer.phonemize, apply_custom_pronunciations(piece, rules, ignore), lang
            )
            tokens = [t.strip(PUNCTUATION) for t in spoken.split()]
            used = -1
            for word, sounds, start in found:
                line = line_of[index] if index < len(line_of) else "?"
                index += 1
                readings = HETERONYMS[word.lower()]
                if only and word.lower() not in only:
                    continue
                shown = pronunciations.plain(piece)
                position = len(piece[:start].split())
                if sounds is not None:
                    written += 1
                    # Its sounds are in the output too; later words start after them.
                    spots = [i for i, t in enumerate(tokens) if i > used and t == sounds]
                    if spots:
                        used = min(spots, key=lambda i: abs(i - position))
                    r = reading_of(sounds, readings)
                    report.append(f"line {line}  {word}: written {written_as(word, {'sounds': sounds})}"
                                  + (f", {r['meaning']}" if r else ", not one of the listed readings"))
                    continue
                by_voice += 1
                listed = pronunciations.lookup(word)
                if listed:
                    r = reading_of(listed, readings)
                    said = f"your pronunciation list says {listed} everywhere" + (f", {r['meaning']}" if r else "")
                    others = [x for x in readings if x is not r]
                else:
                    # The engine writes about one word per word of text, so the
                    # reading nearest this word's position is this word's.
                    candidates = [(i, reading_of(t, readings)) for i, t in enumerate(tokens) if i > used]
                    candidates = [(i, r) for i, r in candidates if r]
                    if candidates:
                        i, r = min(candidates, key=lambda c: abs(c[0] - position))
                        used = i
                        said = f"the voice says {r['sounds']}, {r['meaning']}"
                        others = [x for x in readings if x is not r]
                    else:
                        said = f"could not tell which reading the voice uses; it says: {spoken}"
                        others = readings
                fixes = "; ".join(f"for {x['meaning']}, write {written_as(word, x)}" for x in others)
                report.append(f"line {line}  {word}: {said}\n    {shown}\n    {fixes}")

        print(f"{name}: {written + by_voice} heteronyms, {written} written out, {by_voice} left to the voice")
        if report:
            print()
            print("\n\n".join(report))
            print()
        if by_voice:
            print("For each one left to the voice, check that the reading it uses is the meaning in that sentence.")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
