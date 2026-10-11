"""
Built-in pronunciations for science words the voice engine gets wrong.

The engine (espeak-ng, inside kokoro_onnx) works out how to say a word it does
not know from its spelling, and for Latin anatomy, eponyms, drug names and
acronyms it often guesses wrong: "diastole" as die-a-stole, "ATP" as aptee.
Respelling a word in the text cannot fix that reliably, because the engine also
guesses where the stress goes, and capital letters or hyphens do not steer it.
So each entry in pronunciations.json is the word's pronunciation in the
engine's own phonetic alphabet, and install() puts it straight into the
engine's output in place of the guess. Every reading path goes through the
engine's tokenizer, so live reading, MP3 export and sleep recordings all get
the same pronunciations, on either model.

"words" match in any capitalization; "acronyms" only exactly as written, so
"AMP" is read as letters and "amp" is left alone. A possessive ('s) is
handled. The user's own rules (the Rules tab) are applied to the text before
it reaches the engine, so a word they respell no longer matches here and their
version wins.

To add a word: phonemize the correct pronunciation's parts, or another word
that rhymes, to see how the engine writes those sounds, then add the entry and
run tests/test_pronunciations.py, which checks every entry uses only sounds the
voice model knows.
"""
import functools
import json
import re
from pathlib import Path
from typing import Callable, Dict, List

DATA = Path(__file__).with_name("pronunciations.json")
_raw = DATA.read_bytes()
_data = json.loads(_raw.decode("utf-8"))

WORDS: Dict[str, str] = {k.lower(): v for k, v in _data["words"].items()}
ACRONYMS: Dict[str, str] = dict(_data["acronyms"])



def _alternation(words) -> str:
    # Longest first, so "glomeruli" is not matched as "glomerul" + "i".
    return "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True))


_PATTERN = re.compile(
    r"(?<![\w'])(?:(?P<acronym>" + _alternation(ACRONYMS) + r")"
    r"|(?i:(?P<word>" + _alternation(WORDS) + r")))"
    r"(?P<possessive>['’]s)?(?![\w'’])"
)

_VOICELESS = ("p", "t", "k", "f", "θ")
_SIBILANT = ("s", "z", "ʃ", "ʒ", "tʃ", "dʒ")
_PUNCTUATION_START = re.compile(r"^[,.;:!?)\]]")


def _possessive(ipa: str) -> str:
    """Add the 's sound the way English does after the word's last sound."""
    if ipa.endswith(_SIBILANT):
        return ipa + "ᵻz"
    if ipa.endswith(_VOICELESS):
        return ipa + "s"
    return ipa + "z"


def phonemize_with(phonemize: Callable[..., str], text: str, lang: str = "en-us", *args, **kwargs) -> str:
    """phonemize(text, lang), with every listed word replaced by its entry."""
    if not str(lang).startswith("en"):
        return phonemize(text, lang, *args, **kwargs)
    pieces: List[str] = []
    last = 0
    for m in _PATTERN.finditer(text):
        before = text[last:m.start()]
        if before.strip():
            pieces.append(phonemize(before, lang, *args, **kwargs).strip())
        ipa = ACRONYMS[m["acronym"]] if m["acronym"] else WORDS[m["word"].lower()]
        pieces.append(_possessive(ipa) if m["possessive"] else ipa)
        last = m.end()
    if last == 0:
        return phonemize(text, lang, *args, **kwargs)
    rest = text[last:]
    if rest.strip():
        pieces.append(phonemize(rest, lang, *args, **kwargs).strip())

    out = ""
    for piece in pieces:
        if not piece:
            continue
        # Punctuation that followed a listed word attaches to it, as the
        # engine writes it, instead of standing apart after a space.
        joiner = "" if not out or _PUNCTUATION_START.match(piece) else " "
        out += joiner + piece
    return out


def used(text: str) -> List[List[str]]:
    """
    The entries a text uses, for audio cache keys: changing an entry then
    regenerates only the audio that says that word, instead of everything.
    """
    found = set()
    for m in _PATTERN.finditer(text):
        word = m["acronym"] or m["word"].lower()
        found.add((word, ACRONYMS.get(word) or WORDS[word]))
    return [list(entry) for entry in sorted(found)]


def install(engine) -> None:
    """Route an engine's phonemization through the built-in pronunciations."""
    tokenizer = engine.tokenizer
    original = getattr(tokenizer, "_phonemize_without_pronunciations", tokenizer.phonemize)
    tokenizer._phonemize_without_pronunciations = original
    tokenizer.phonemize = functools.partial(phonemize_with, original)
