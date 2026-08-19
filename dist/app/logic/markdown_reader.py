"""
Turn a Markdown file into readable pages.

Markdown read literally is unlistenable: "hash hash Introduction", "asterisk
asterisk important asterisk asterisk", forty seconds of a shell command spelled
out character by character. So the file is rendered to HTML and then walked to
produce prose, keeping what carries meaning aloud and dropping what does not.
"""
import re
from typing import List, Tuple

import markdown as _markdown
from bs4 import BeautifulSoup, NavigableString

# Roughly a screen of text. Markdown has no page breaks, so pages are invented;
# this is small enough to navigate and large enough not to fragment a section.
TARGET_PAGE_CHARS = 2500
# Once a page is at least this long, a new heading starts a fresh page, so
# sections tend to begin at the top of one.
HEADING_BREAK_AFTER = 1000

BLOCK_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "blockquote", "tr", "pre")


def _normalize(md_text: str) -> str:
    """
    Fix two things that are fine on screen and bad in the ear.

    Python-Markdown only starts a list when a blank line precedes it, so notes
    written as a heading followed immediately by dashes stay one paragraph and
    the bullet characters survive into the spoken text as "dash". A blank line
    is inserted so they parse as a real list.

    Task checkboxes are markup, not words. Read literally they come out as
    "bracket x bracket"; they are replaced with what they actually mean.
    """
    lines = md_text.split("\n")
    out = []
    bullet = re.compile(r"^(\s*)([-*+]|\d+\.)\s+")
    for i, line in enumerate(lines):
        if bullet.match(line):
            prev = out[-1] if out else ""
            if prev.strip() and not bullet.match(prev) and not prev.strip().startswith((">", "#", "|")):
                out.append("")
        out.append(line)
    text = "\n".join(out)

    text = re.sub(r"^(\s*(?:[-*+]|\d+\.)\s+)\[[xX]\]\s*", r"\1Done: ", text, flags=re.M)
    text = re.sub(r"^(\s*(?:[-*+]|\d+\.)\s+)\[~\]\s*", r"\1In progress: ", text, flags=re.M)
    text = re.sub(r"^(\s*(?:[-*+]|\d+\.)\s+)\[ \]\s*", r"\1Not started: ", text, flags=re.M)
    # the same markers used without a list, as in a plain checklist line
    text = re.sub(r"^\[[xX]\]\s*", "Done: ", text, flags=re.M)
    text = re.sub(r"^\[~\]\s*", "In progress: ", text, flags=re.M)
    text = re.sub(r"^\[ \]\s*", "Not started: ", text, flags=re.M)
    return text


def _clean(text: str) -> str:
    return re.sub(r"[ \t]+", " ", text.replace("\xa0", " ")).strip()


def _heading_text(el) -> str:
    # A heading is spoken, so it needs terminal punctuation or the TTS runs it
    # straight into the paragraph beneath it.
    t = _clean(el.get_text(" "))
    if t and t[-1] not in ".!?:;":
        t += "."
    return t


def _blocks(html: str) -> List[str]:
    soup = BeautifulSoup(html, "html.parser")

    # Code is the one thing that is strictly worse read aloud than skipped: a
    # command line becomes a minute of punctuation names. Replaced with a short
    # spoken marker so the listener knows something was there.
    for pre in soup.find_all("pre"):
        pre.replace_with(NavigableString("\n[CODE BLOCK]\n"))

    # Images cannot be heard; alt text is the only part worth keeping.
    for img in soup.find_all("img"):
        alt = _clean(img.get("alt") or "")
        img.replace_with(NavigableString(f" {alt} " if alt else " "))

    # A link's URL is noise; its text is the sentence.
    for a in soup.find_all("a"):
        a.replace_with(NavigableString(a.get_text(" ")))

    out: List[str] = []
    for el in soup.find_all(BLOCK_TAGS):
        # Skip nested blocks -- the outer one already carries the text.
        if el.find_parent(["li", "blockquote", "td", "th"]) and el.name != "li":
            continue

        if el.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            t = _heading_text(el)
            if t:
                out.append("\x00HEADING\x00" + t)
            continue

        if el.name == "tr":
            # A table row read as prose: cells separated by commas so the voice
            # pauses between them instead of running them together.
            cells = [_clean(c.get_text(" ")) for c in el.find_all(["td", "th"])]
            cells = [c for c in cells if c]
            if cells:
                row = ", ".join(cells)
                out.append(row if row.endswith((".", "!", "?")) else row + ".")
            continue

        if el.name == "li":
            t = _clean(el.get_text(" "))
            if t:
                out.append(t if t.endswith((".", "!", "?", ":", ";")) else t + ".")
            continue

        t = _clean(el.get_text(" "))
        if t:
            out.append(t)

    return out


def markdown_to_pages(md_text: str) -> Tuple[List[str], str]:
    """
    Render Markdown and split it into pages.

    Returns (pages, title). Title is the first heading if there is one.
    """
    html = _markdown.markdown(
        _normalize(md_text), extensions=["tables", "fenced_code", "sane_lists"]
    )
    blocks = _blocks(html)

    title = ""
    for b in blocks:
        if b.startswith("\x00HEADING\x00"):
            title = b.replace("\x00HEADING\x00", "").rstrip(".")
            break

    pages: List[str] = []
    current: List[str] = []
    length = 0

    for b in blocks:
        is_heading = b.startswith("\x00HEADING\x00")
        text = b.replace("\x00HEADING\x00", "")

        if is_heading and length >= HEADING_BREAK_AFTER:
            pages.append("\n\n".join(current))
            current, length = [], 0
        elif length + len(text) > TARGET_PAGE_CHARS and current:
            pages.append("\n\n".join(current))
            current, length = [], 0

        current.append(text)
        length += len(text) + 2

    if current:
        pages.append("\n\n".join(current))

    return (pages or [""], title)
