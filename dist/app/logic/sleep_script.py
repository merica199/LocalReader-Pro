"""
Turn a document into a sleep-recording plan: what to say, and how long to stay
silent between the things said.

Read-aloud lets the model pace itself, and a model given a passage rushes
through its punctuation. Here the model only ever sees one short sentence, and
every pause in the recording is silence inserted afterwards, so the pacing is
exact and holds for the whole three hours.

Scripts written for sleep recordings can mark up their pacing:

    blank line      paragraph pause
    ... or the ellipsis character
                    soft pause in the middle of a thought
    [pause 6]       exactly that many seconds of silence
    # comment       the whole line is skipped

The ideas, and the default pause lengths, come from docs/reference/sleepcast.py.
"""
import re
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple, Union


@dataclass(frozen=True)
class Pacing:
    """Pause lengths, in seconds."""

    sentence: float = 1.0
    paragraph: float = 2.6
    ellipsis: float = 1.1
    # Between the pieces of a sentence too long to send to the model at once.
    clause: float = 0.3
    lead_in: float = 3.0
    tail: float = 8.0
    # Longest piece sent to the model in one call. Long inputs are where a
    # model drifts, so a long sentence is split at a clause instead.
    max_chars: int = 220


# ("say", text) or ("pause", seconds)
Event = Tuple[str, Union[str, float]]

PAUSE_RE = re.compile(r"\[\s*pause\s+(\d+(?:\.\d+)?)\s*s?\s*\]", re.I)
ELLIPSIS_RE = re.compile(r"\s*(?:\.{3,}|…)\s*")
# Latin sentence punctuation ends a sentence only before whitespace, so "3.5"
# stays whole. CJK text has no spaces, so its full-width marks end one outright.
SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+|(?<=[。！？])")
# Where an over-long sentence may be split, best first. Whitespace is the last
# resort and has no minimum piece length.
CLAUSE_SPLITS = (r"[;:]\s+|[；：]", r",\s+|[，、]", r"\s+")
END_PUNCT_RE = re.compile(r"[.!?,;:。！？，；：、]$")
# A letter or digit in any script; a piece without one has nothing to say.
SPEAKABLE_RE = re.compile(r"[^\W_]")
# A page that ends like this ends a sentence (allowing a closing quote/bracket).
SENTENCE_ENDED_RE = re.compile(
    r"(?:[.!?。！？…]|\[\s*pause[^\]]*\])[\"'”’)\]]*\s*$", re.I
)
ABBREVIATIONS = {
    "mr.", "mrs.", "ms.", "dr.", "st.", "mt.", "vs.", "etc.", "e.g.", "i.e.",
    "jr.", "sr.", "no.", "approx.", "prof.",
}


def normalize(text: str) -> str:
    """Rewrite the punctuation a voice model reads badly into commas it reads well."""
    text = text.replace("…", "...")
    # Quotation marks have no sound; read aloud they only disturb the rhythm.
    text = re.sub(r"[“”„\"]", "", text)
    text = re.sub(r"[‘’]", "'", text)
    # Dashes and brackets are pauses on the page; a comma is the pause a model
    # actually produces.
    text = re.sub(r"\s*(?:\u2014|\u2013|--)\s*|\s+-\s+", ", ", text)
    text = re.sub(r"\s*[()\[\]{}]\s*", ", ", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r",(\s*,)+", ",", text)
    text = re.sub(r",\s*([.!?;:])", r"\1", text)
    text = re.sub(r"^[,;:\s]+", "", text)
    return text.strip()


def split_sentences(text: str) -> List[str]:
    out: List[str] = []
    for part in SENTENCE_END_RE.split(text):
        part = part.strip()
        if not part:
            continue
        last_word = out[-1].split()[-1] if out else ""
        # "Dr. Smith" and "J. R. Tolkien" are not sentence ends.
        if last_word.lower() in ABBREVIATIONS or re.fullmatch(r"[A-Z]\.", last_word):
            out[-1] += " " + part
        else:
            out.append(part)
    return out


def split_middle(text: str) -> Optional[Tuple[str, str]]:
    """Split at the clause boundary nearest the middle, or None if there is none."""
    mid = len(text) / 2
    for pattern in CLAUSE_SPLITS:
        cuts = [m.end() for m in re.finditer(pattern, text) if 0 < m.end() < len(text)]
        balanced = [c for c in cuts if min(c, len(text) - c) >= 20]
        cuts = balanced or (cuts if pattern is CLAUSE_SPLITS[-1] else [])
        if cuts:
            c = min(cuts, key=lambda x: abs(x - mid))
            return text[:c].strip(), text[c:].strip()
    return None


def split_long(text: str, max_chars: int) -> List[str]:
    if len(text) <= max_chars:
        return [text]
    halves = split_middle(text)
    if not halves:
        return [text]
    return split_long(halves[0], max_chars) + split_long(halves[1], max_chars)


def ensure_end(text: str, mark: str) -> str:
    # A piece with no closing mark is read with a rising, unfinished contour.
    return text if END_PUNCT_RE.search(text) else text + mark


def _add_pause(events: List[Event], seconds: float, explicit: bool = False) -> None:
    # Nothing before the first words: the lead-in covers that, unless a script
    # asks for silence there itself.
    if seconds <= 0 or (not events and not explicit):
        return
    # Pauses that meet merge into the longer one rather than adding up, so a
    # [pause 6] at the end of a paragraph is six seconds, not 8.6.
    if events and events[-1][0] == "pause":
        events[-1] = ("pause", max(events[-1][1], seconds))
    else:
        events.append(("pause", seconds))


def plan_text(
    text: str,
    pacing: Pacing = Pacing(),
    transform: Optional[Callable[[str], str]] = None,
) -> List[Event]:
    """
    Turn text into a list of things to say and silences between them.

    transform is applied to each piece just before it is checked for anything
    speakable, which is where the reader's pronunciation rules go.
    """
    events: List[Event] = []
    lines = [ln for ln in text.replace("\r\n", "\n").split("\n") if not ln.lstrip().startswith("#")]
    for para in re.split(r"\n\s*\n", "\n".join(lines)):
        if not para.strip():
            continue
        for i, piece in enumerate(PAUSE_RE.split(para)):
            if i % 2 == 1:  # the seconds captured from a [pause N]
                _add_pause(events, float(piece), explicit=True)
                continue
            phrases = [p for p in ELLIPSIS_RE.split(normalize(piece)) if p.strip()]
            for j, phrase in enumerate(phrases):
                if j > 0:
                    _add_pause(events, pacing.ellipsis)
                sentences = split_sentences(phrase)
                for k, sentence in enumerate(sentences):
                    if k > 0:
                        _add_pause(events, pacing.sentence)
                    pieces = split_long(sentence, pacing.max_chars)
                    for m, sub in enumerate(pieces):
                        if m > 0:
                            _add_pause(events, pacing.clause)
                        if transform:
                            sub = transform(sub).strip()
                        if not SPEAKABLE_RE.search(sub):
                            continue
                        # A piece that the next one continues ends on a comma,
                        # so it is not read as the end of a sentence.
                        continues = m < len(pieces) - 1 or (
                            k == len(sentences) - 1 and j < len(phrases) - 1
                        )
                        events.append(("say", ensure_end(sub, "," if continues else ".")))
        _add_pause(events, pacing.paragraph)
    while events and events[-1][0] == "pause":
        events.pop()
    return events


def join_pages(pages: List[str], keeps_paragraphs: bool) -> str:
    """
    Join a document's pages back into one text.

    Pages are a display convenience. Text and Markdown are cut into pages
    between paragraphs, so a page that ends a sentence ends a paragraph. A PDF's
    pages end wherever the printed page did, often mid-sentence, and its
    extracted text keeps no paragraph breaks, so there a page turn is never a
    pause of its own.
    """
    text = ""
    for page in pages:
        page = page.strip()
        if not page:
            continue
        if text:
            ends_paragraph = keeps_paragraphs and SENTENCE_ENDED_RE.search(text)
            text += "\n\n" if ends_paragraph else "\n"
        text += page
    return text


def estimate_seconds(events: List[Event], pacing: Pacing, chars_per_second: float) -> float:
    speech = sum(len(v) for k, v in events if k == "say") / chars_per_second
    silence = sum(v for k, v in events if k == "pause")
    return pacing.lead_in + speech + silence + pacing.tail


def take_seconds(events: List[Event], seconds: float, chars_per_second: float) -> List[Event]:
    """The opening of a plan, about `seconds` long: what a preview renders."""
    taken: List[Event] = []
    elapsed = 0.0
    for kind, value in events:
        if elapsed >= seconds:
            break
        taken.append((kind, value))
        elapsed += value if kind == "pause" else len(value) / chars_per_second
    while taken and taken[-1][0] == "pause":
        taken.pop()
    return taken
