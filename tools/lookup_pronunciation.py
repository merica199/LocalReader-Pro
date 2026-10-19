"""
Look up how words are pronounced, and compare with what the app will say.

Run with the app's own Python (it needs the internet):

    venv/bin/python tools/lookup_pronunciation.py renin glomerulus
    venv/bin/python tools/lookup_pronunciation.py --audit

For each word it prints:

- the published pronunciations on Wiktionary, in IPA (the International
  Phonetic Alphabet), labelled US or UK where Wiktionary says;
- the app's entry, from the built-in or personal list, if it has one;
- the engine's own guess, which is what the voice says without an entry.

--audit checks every word in the built-in and personal lists against
Wiktionary and prints only the ones that disagree on where the main stress
falls or on how many syllables there are. Those are the entries to look at
first; everything else matches a published pronunciation. Acronyms are skipped,
since letters are read as letters.

Comparing is rough on purpose. Wiktionary marks stress at the start of a
syllable and the engine before the vowel, transcriptions differ in detail, and
many words have more than one accepted pronunciation, so a flag means "look at
this", not "this is wrong". The final check is still a person listening
(tools/pronunciation_check.py).

Wiktionary's text is CC BY-SA. Individual pronunciations are facts and fine to
use; do not copy its pages wholesale.
"""
import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

# On Windows, Python writes to a pipe in the old code page (usually
# Windows-1252), which has none of the phonetic symbols printed here: an
# agent reading the output would get a crash at the first one.
sys.stdout.reconfigure(encoding="utf-8")

APP = Path(__file__).resolve().parent.parent / "dist" / "app"
sys.path.insert(0, str(APP))

from kokoro_onnx.tokenizer import Tokenizer  # noqa: E402
from logic import pronunciations  # noqa: E402

API = "https://en.wiktionary.org/w/api.php"
AGENT = "LocalReaderPro-pronunciation-lookup/1.0 (https://github.com/merica199/LocalReader-Pro)"


def wiktionary(word):
    """[(label, ipa)] from the English section of the word's Wiktionary page."""
    found = []
    for title in dict.fromkeys([word, word.lower()]):
        query = urllib.parse.urlencode(
            {"action": "parse", "page": title, "prop": "wikitext", "format": "json", "formatversion": 2, "redirects": 1}
        )
        request = urllib.request.Request(f"{API}?{query}", headers={"User-Agent": AGENT})
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                text = json.load(response).get("parse", {}).get("wikitext", "")
        except Exception:
            continue
        english = re.split(r"\n==[^=]", text.split("==English==", 1)[1])[0] if "==English==" in text else ""
        for template in re.findall(r"\{\{IPA\|en\|([^}]*)\}\}", english):
            parts = template.split("|")
            label = next((p[2:] for p in parts if p.startswith("a=")), "")
            for ipa in parts:
                if ipa.startswith("/") or ipa.startswith("["):
                    found.append((label, ipa))
        if found:
            break
        time.sleep(0.2)
    return found


DIPHTHONGS = ("eɪ", "aɪ", "ɔɪ", "oʊ", "aʊ", "əʊ", "ɪə", "ɛə", "ʊə")
VOWELS = set("aeiouæɑɒɔəɚɛɜɝɪʊʌɐᵻɨyøœɵɘɤ")


def syllables(ipa):
    """[(stress, nucleus)] where stress is 1 for main, 2 for secondary, 0 for none."""
    ipa = re.sub(r"[/\[\]().‿ ]", "", ipa).replace("ː", "").replace("ˑ", "")
    ipa = ipa.replace("r", "ɹ").replace("ɝ", "ɜɹ").replace("g", "ɡ")
    out, stress, i = [], 0, 0
    while i < len(ipa):
        c = ipa[i]
        if c == "ˈ":
            stress = 1
        elif c == "ˌ":
            stress = stress or 2
        elif c in VOWELS:
            nucleus = next((d for d in DIPHTHONGS if ipa.startswith(d, i)), c)
            out.append((stress, nucleus))
            stress = 0
            i += len(nucleus)
            continue
        i += 1
    return out


def shape(ipa):
    syl = syllables(ipa)
    main = next((n for n, (s, _) in enumerate(syl) if s == 1), None)
    return len(syl), main


def agrees(ours, published):
    """Same syllable count (one either way for syllabic consonants) and main stress."""
    count, main = shape(ours)
    p_count, p_main = shape(published)
    return main == p_main and abs(count - p_count) <= 1


parser = argparse.ArgumentParser(description="Look up and compare pronunciations.")
parser.add_argument("words", nargs="*")
parser.add_argument("--audit", action="store_true", help="check every listed word against Wiktionary")
args = parser.parse_args()
if not args.words and not args.audit:
    sys.exit(__doc__)

engine = Tokenizer()

if args.audit:
    table = pronunciations._table()
    flagged, missing = 0, []
    for word in sorted(table.words):
        published = wiktionary(word)
        time.sleep(0.3)
        if not published:
            missing.append(word)
            continue
        us = [ipa for label, ipa in published if label in ("US", "GA", "General American", "")] or [ipa for _, ipa in published]
        if any(agrees(table.words[word], ipa) for ipa in us):
            continue
        flagged += 1
        print(f"{word}\n  app:        {table.words[word]}")
        for label, ipa in published:
            print(f"  wiktionary: {ipa}" + (f"  ({label})" if label else ""))
    print(f"\n{len(table.words)} words checked: {flagged} disagree, {len(missing)} not on Wiktionary.")
    if missing:
        print("Not on Wiktionary (check another way): " + ", ".join(missing))
    sys.exit(0)

for word in args.words:
    print(word)
    published = wiktionary(word)
    for label, ipa in published:
        print(f"  wiktionary:   {ipa}" + (f"  ({label})" if label else ""))
    if not published:
        print("  wiktionary:   (no pronunciation found)")
    entry = pronunciations.lookup(word)
    print(f"  app's entry:  {entry or '(none)'}")
    print(f"  engine alone: {engine.phonemize(word, 'en-us')}")
    if entry and published and not any(agrees(entry, ipa) for _, ipa in published):
        print("  note: the app's entry disagrees with Wiktionary on stress or syllables")
    if not entry and published and not any(agrees(engine.phonemize(word, "en-us"), ipa) for _, ipa in published):
        print("  note: the engine's guess disagrees with Wiktionary; this word probably needs an entry")
