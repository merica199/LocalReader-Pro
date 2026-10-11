"""
Pronunciations for science words the voice engine gets wrong.

The engine (espeak-ng, inside kokoro_onnx) works out how to say a word it does
not know from its spelling, and for Latin anatomy, eponyms, drug names and
acronyms it often guesses wrong: "diastole" as die-a-stole, "ATP" as aptee.
Respelling a word in the text cannot fix that reliably, because the engine also
guesses where the stress goes, and capital letters or hyphens do not steer it.
So each entry is the word's pronunciation in the engine's own phonetic
alphabet, and install() puts it straight into the engine's output in place of
the guess. Every reading path goes through the engine's tokenizer, so live
reading, MP3 export and sleep recordings all get the same pronunciations, on
either model.

Two lists, in the same format:

- pronunciations.json, next to this file: the built-in list, part of the app.
- userdata/pronunciations.json: the user's personal list, kept with their
  library so updates never touch it and editing it never blocks an update.
  Its entries win over the built-in ones, and an entry whose value is an
  empty string switches a built-in entry off. It is read again whenever it
  changes, so an edit takes effect without restarting the app.

"words" match in any capitalization; "acronyms" only exactly as written, so
"AMP" is read as letters and "amp" is left alone. A possessive ('s) is
handled. The user's own rules (the Rules tab) are applied to the text before
it reaches the engine, so a word they respell no longer matches here and their
version wins.

To add a word: find a published pronunciation (tools/lookup_pronunciation.py
looks it up on Wiktionary), phonemize a word with the same sounds to see how
the engine writes them, then add the entry and
run tests/test_pronunciations.py, which checks every entry uses only sounds the
voice model knows. Then record it with tools/pronunciation_check.py and have a
person listen.
"""
import functools
import json
import os
import re
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

BUILTIN_FILE = Path(__file__).with_name("pronunciations.json")
PERSONAL_FILE = Path(
    os.environ.get("LOCALREADER_PERSONAL_PRONUNCIATIONS")
    or Path(__file__).absolute().parent.parent.parent / "userdata" / "pronunciations.json"
)


def _read(path: Path) -> Tuple[Dict[str, str], Dict[str, str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    words = {k.lower(): v for k, v in data.get("words", {}).items()}
    acronyms = dict(data.get("acronyms", {}))
    return words, acronyms


# The built-in list, as shipped.
WORDS, ACRONYMS = _read(BUILTIN_FILE)


def _alternation(words) -> str:
    if not words:
        return "(?!)"  # matches nothing
    # Longest first, so "glomeruli" is not matched as "glomerul" + "i".
    return "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True))


class _Table:
    def __init__(self, words: Dict[str, str], acronyms: Dict[str, str]):
        self.words = {k: v for k, v in words.items() if v}
        self.acronyms = {k: v for k, v in acronyms.items() if v}
        self.pattern = re.compile(
            r"(?<![\w'])(?:(?P<acronym>" + _alternation(self.acronyms) + r")"
            r"|(?i:(?P<word>" + _alternation(self.words) + r")))"
            r"(?P<possessive>['’]s)?(?![\w'’])"
        )

    def ipa(self, match) -> str:
        if match["acronym"]:
            return self.acronyms[match["acronym"]]
        return self.words[match["word"].lower()]


_cache = {"stamp": None, "table": _Table(WORDS, ACRONYMS), "warned": None}


def _table() -> _Table:
    """The built-in list merged with the personal one, re-read when it changes."""
    try:
        st = PERSONAL_FILE.stat()
        stamp = (st.st_mtime_ns, st.st_size)
    except OSError:
        stamp = None
    if stamp != _cache["stamp"]:
        words, acronyms = dict(WORDS), dict(ACRONYMS)
        if stamp is not None:
            try:
                personal_words, personal_acronyms = _read(PERSONAL_FILE)
                words.update(personal_words)
                acronyms.update(personal_acronyms)
            except Exception as e:  # a broken personal file must not stop reading
                if _cache["warned"] != stamp:
                    print(f"[PRONUNCIATIONS] Ignoring {PERSONAL_FILE}: {e}")
                    _cache["warned"] = stamp
        _cache.update(stamp=stamp, table=_Table(words, acronyms))
    return _cache["table"]


def lookup(word: str) -> Optional[str]:
    """The pronunciation the app will use for a word, or None for the engine's guess."""
    table = _table()
    return table.acronyms.get(word) or table.words.get(word.lower())


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
    table = _table()
    pieces: List[str] = []
    last = 0
    for m in table.pattern.finditer(text):
        before = text[last:m.start()]
        if before.strip():
            pieces.append(phonemize(before, lang, *args, **kwargs).strip())
        ipa = table.ipa(m)
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
    table = _table()
    found = set()
    for m in table.pattern.finditer(text):
        found.add((m["acronym"] or m["word"].lower(), table.ipa(m)))
    return [list(entry) for entry in sorted(found)]


def install(engine) -> None:
    """Route an engine's phonemization through the pronunciation lists."""
    tokenizer = engine.tokenizer
    original = getattr(tokenizer, "_phonemize_without_pronunciations", tokenizer.phonemize)
    tokenizer._phonemize_without_pronunciations = original
    tokenizer.phonemize = functools.partial(phonemize_with, original)
