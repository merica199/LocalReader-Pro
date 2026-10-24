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

A list entry says a word one way everywhere, which is wrong for a word spelled
the same but said two ways: "cells live for weeks" and "a live vaccine". For
those, the text itself can say how one occurrence is read, written
[live](/lˈɪv/): the word as displayed, then its sounds between slashes, in the
engine's alphabet. It wins over both lists and is shown as just the word.
tools/check_heteronyms.py finds the words that need one.

Azure voices (logic/azure_tts.py) do not use these lists. They know far more
words than espeak-ng does and are left to say them their own way, unless an
entry in the lists' "azure" section says otherwise. Those entries are written
in the IPA Azure documents for the voice's language (stress mark at the start
of the syllable, no length marks for American English), not in the engine's
style, because Azure reads them as they are. A written pronunciation in the
text, [live](/lˈɪv/), applies to Azure too: azure_ipa() rewrites its sounds
into Azure's style.
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


def _read(path: Path, section: str = "kokoro") -> Tuple[Dict[str, str], Dict[str, str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if section == "azure":
        data = data.get("azure", {})
    words = {k.lower(): v for k, v in data.get("words", {}).items()}
    acronyms = dict(data.get("acronyms", {}))
    return words, acronyms


# The built-in list, as shipped.
WORDS, ACRONYMS = _read(BUILTIN_FILE)
AZURE_WORDS, AZURE_ACRONYMS = _read(BUILTIN_FILE, "azure")
BUILTIN = {"kokoro": (WORDS, ACRONYMS), "azure": (AZURE_WORDS, AZURE_ACRONYMS)}

# A pronunciation written into the text for one occurrence: [live](/lˈɪv/).
# Neither part may contain spaces, so the sleep planner's splitting at
# whitespace can never cut one in half.
OVERRIDE = r"\[(?P<shown>[^\[\]\s]+)\]\(/(?P<sounds>[^/\s()]+)/\)"
OVERRIDE_RE = re.compile(OVERRIDE)


def plain(text: str) -> str:
    """The text as displayed and counted: each written pronunciation becomes its word."""
    return OVERRIDE_RE.sub(lambda m: m["shown"], text)


def _alternation(words) -> str:
    if not words:
        return "(?!)"  # matches nothing
    # Longest first, so "glomeruli" is not matched as "glomerul" + "i".
    return "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True))


class _Table:
    def __init__(self, words: Dict[str, str], acronyms: Dict[str, str]):
        self.words = {k: v for k, v in words.items() if v}
        self.acronyms = {k: v for k, v in acronyms.items() if v}
        # A written pronunciation comes first, so a listed word inside one is
        # not matched on its own.
        self.pattern = re.compile(
            r"(?P<override>" + OVERRIDE + r")"
            r"|(?<![\w'])(?:(?P<acronym>" + _alternation(self.acronyms) + r")"
            r"|(?i:(?P<word>" + _alternation(self.words) + r")))"
            r"(?P<possessive>['’]s)?(?![\w'’])"
        )

    def ipa(self, match) -> str:
        if match["override"]:
            return match["sounds"]
        if match["acronym"]:
            return self.acronyms[match["acronym"]]
        return self.words[match["word"].lower()]


_cache = {
    section: {"stamp": None, "table": _Table(*lists), "warned": None}
    for section, lists in BUILTIN.items()
}


def _table(section: str = "kokoro") -> _Table:
    """The built-in list merged with the personal one, re-read when it changes."""
    cache = _cache[section]
    try:
        st = PERSONAL_FILE.stat()
        stamp = (st.st_mtime_ns, st.st_size)
    except OSError:
        stamp = None
    if stamp != cache["stamp"]:
        words, acronyms = (dict(d) for d in BUILTIN[section])
        if stamp is not None:
            try:
                personal_words, personal_acronyms = _read(PERSONAL_FILE, section)
                words.update(personal_words)
                acronyms.update(personal_acronyms)
            except Exception as e:  # a broken personal file must not stop reading
                if cache["warned"] != stamp:
                    print(f"[PRONUNCIATIONS] Ignoring {PERSONAL_FILE}: {e}")
                    cache["warned"] = stamp
        cache.update(stamp=stamp, table=_Table(words, acronyms))
    return cache["table"]


def lookup(word: str, section: str = "kokoro") -> Optional[str]:
    """The pronunciation the app will use for a word, or None for the voice's own reading."""
    table = _table(section)
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
    """
    phonemize(text, lang), with every listed word replaced by its entry and
    every written pronunciation by its sounds.
    """
    if not str(lang).startswith("en"):
        # The sounds are English ones; another language reads the plain word.
        return phonemize(plain(text), lang, *args, **kwargs)
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


def used(text: str, section: str = "kokoro") -> List[List[str]]:
    """
    The entries a text uses, for audio cache keys: changing an entry then
    regenerates only the audio that says that word, instead of everything.
    """
    table = _table(section)
    found = set()
    for m in table.pattern.finditer(text):
        # A written pronunciation is part of the text, which every key holds.
        if m["override"]:
            continue
        found.add((m["acronym"] or m["word"].lower(), table.ipa(m)))
    return [list(entry) for entry in sorted(found)]


def install(engine) -> None:
    """Route an engine's phonemization through the pronunciation lists."""
    tokenizer = engine.tokenizer
    original = getattr(tokenizer, "_phonemize_without_pronunciations", tokenizer.phonemize)
    tokenizer._phonemize_without_pronunciations = original
    tokenizer.phonemize = functools.partial(phonemize_with, original)


# --- Azure ---------------------------------------------------------------------
#
# Azure takes a word's sounds in an SSML <phoneme alphabet="ipa"> tag, in the
# IPA set it documents per language (learn.microsoft.com, "SSML phonetic
# alphabets"). The engine's alphabet differs in three ways that matter: it puts
# the stress mark right before the stressed vowel where IPA puts it at the
# start of the syllable; it writes American vowels with length marks Azure's
# American set does not use; and it has a few sounds of its own (ᵻ, ɐ, the flap
# ɾ). azure_ipa() rewrites all three. Entries in the "azure" sections are
# already in Azure's style and pass through unchanged.

_VOWELS = set("aeiouyæɑɒɐɔəɚɛɜɝɪʊʌᵻɨøœɵɘɤɯ")
_STRESS = "ˈˌ"
# Consonant pairs and triples that can start an English syllable, so a stress
# mark moved back from its vowel takes the whole onset with it: "ˌæbstɹˈækt"
# becomes "ˌæbˈstɹækt", not "ˌæbsˈtɹækt".
_ONSETS = {
    "spl", "spɹ", "stɹ", "skɹ", "skw", "spj", "skj",
    "pl", "pɹ", "bl", "bɹ", "tɹ", "dɹ", "kl", "kɹ", "gl", "gɹ", "fl", "fɹ", "θɹ",
    "ʃɹ", "sp", "st", "sk", "sm", "sn", "sl", "sw", "tw", "kw", "dw", "gw", "θw",
    "pj", "bj", "kj", "gj", "mj", "nj", "fj", "vj", "hj", "lj",
}
_COMMON = [("ɡ", "g"), ("ᵻ", "ɪ"), ("ɨ", "ɪ"), ("ɾ", "t"), ("ʔ", "t"), ("r", "ɹ"),
           ("n̩", "ən"), ("l̩", "əl"), ("ç", "h"), ("x", "k")]
# American: no length marks, the r-coloured vowel of "bird" is ɝ, ɐ is ə.
_AMERICAN = [("ɜːɹ", "ɝ"), ("ɜː", "ɝ"), ("ɜ", "ɝ"), ("ɐ", "ə"), ("ɒ", "ɑ"), ("ː", "")]
_BRITISH = [("ɐ", "ʌ")]


def _segments(ipa: str) -> List[str]:
    """Sounds, with tʃ and dʒ (one consonant each) kept together."""
    out: List[str] = []
    i = 0
    while i < len(ipa):
        if ipa[i:i + 2] in ("tʃ", "dʒ"):
            out.append(ipa[i:i + 2])
            i += 2
        else:
            out.append(ipa[i])
            i += 1
    return out


def _stress_to_syllable_start(ipa: str) -> str:
    out: List[str] = []
    for seg in _segments(ipa):
        if seg in _STRESS:
            out.append(seg)
            continue
        if out and out[-1] in _STRESS and seg[0] in _VOWELS:
            mark = out.pop()
            # The consonants since the last vowel, stress mark or space.
            cluster: List[str] = []
            while out and out[-1][0] not in _VOWELS and out[-1] not in _STRESS + " ː":
                cluster.insert(0, out.pop())
            onset = 0
            for size in (3, 2):
                if len(cluster) >= size and "".join(cluster[-size:]) in _ONSETS:
                    onset = size
                    break
            else:
                onset = min(1, len(cluster))
            out += cluster[:len(cluster) - onset] + [mark] + cluster[len(cluster) - onset:]
        out.append(seg)
    return "".join(out)


def azure_ipa(ipa: str, locale: str = "en-US") -> str:
    """The engine's sounds for a word, written the way Azure reads IPA."""
    # The engine's ɡ is a different character from Azure's g, and the onsets
    # above are written with Azure's.
    out = _stress_to_syllable_start(ipa.replace("ɡ", "g"))
    for old, new in _COMMON + (_BRITISH if locale.lower() == "en-gb" else _AMERICAN):
        out = out.replace(old, new)
    return out


def _xml(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def azure_ssml_text(text: str, locale: str = "en-US") -> str:
    """
    The text as SSML for an Azure voice: escaped, with every written
    pronunciation and every entry in the Azure lists in a <phoneme> tag, and
    everything else left for the voice to read its own way.
    """
    if not locale.lower().startswith("en"):
        return _xml(plain(text))
    table = _table("azure")
    out: List[str] = []
    last = 0
    for m in table.pattern.finditer(text):
        out.append(_xml(text[last:m.start()]))
        if m["override"]:
            ipa, shown = azure_ipa(m["sounds"], locale), m["shown"]
        else:
            ipa, shown = table.ipa(m), m["acronym"] or m["word"]
        if m["possessive"]:
            ipa, shown = azure_ipa(_possessive(ipa), locale), shown + m["possessive"]
        out.append(f'<phoneme alphabet="ipa" ph="{_xml(ipa)}">{_xml(shown)}</phoneme>')
        last = m.end()
    out.append(_xml(text[last:]))
    return "".join(out)
