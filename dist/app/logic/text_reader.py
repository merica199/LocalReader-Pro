"""
Turn a plain text file into readable pages.

Plain text does not go through the Markdown reader. Ordinary prose is full of
things Markdown takes as syntax: an indented quotation is a code block and gets
dropped, a line starting "#1" becomes a heading, and "<before>" is swallowed as
an HTML tag. Here the text is kept as written; the only work is decoding it and
cutting it into pages.

Line breaks inside a paragraph are left alone. The front end already joins a
line to the next unless it ends a sentence, which suits both hard-wrapped text
(a Project Gutenberg book) and one-paragraph-per-line text (a notes export).
"""
import codecs
import re
from typing import List

# Matches the Markdown reader, so pages feel the same size across formats.
TARGET_PAGE_CHARS = 2500

# Coarsest boundary first: an oversized piece is split at paragraphs, then at
# lines, then at sentence ends, then at any whitespace.
SPLITS = (
    (re.compile(r"\n\s*\n"), "\n\n"),
    (re.compile(r"\n"), "\n"),
    (re.compile(r"(?<=[.!?])\s+"), " "),
    (re.compile(r"\s+"), " "),
)

# C0 controls other than tab and newline. Form feed is handled separately.
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0e-\x1f\x7f]")


def decode_text(raw: bytes) -> str:
    """
    Decode a text file's bytes.

    A byte order mark is trusted first: Notepad's "Unicode" and PowerShell's
    redirection both write UTF-16 with one, and decoding that as UTF-8 fails.
    Then UTF-8, then Windows-1252, which is what an older Windows file almost
    always is; reading it as Latin-1 instead turns its curly quotes and dashes
    into control characters. Latin-1 is the last resort because it never fails.
    """
    if raw.startswith(codecs.BOM_UTF8):
        return raw[len(codecs.BOM_UTF8):].decode("utf-8", errors="replace")
    if raw.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return raw.decode("utf-16", errors="replace")
    for encoding in ("utf-8", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")


def _normalize(text: str) -> str:
    # Windows and classic Mac line endings, or "\n\n" never matches a paragraph.
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # A form feed is a page break in older text files; treat it as a paragraph.
    text = text.replace("\f", "\n\n")
    text = _CONTROL.sub("", text).replace("\t", " ").replace("\xa0", " ")
    lines = [re.sub(r" {2,}", " ", line).strip() for line in text.split("\n")]
    # Any run of blank lines is one paragraph break.
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _chunks(text: str, limit: int, level: int = 0) -> List[str]:
    """
    Split text into pieces no longer than limit, packing as much as fits.

    A piece too long for one page is split at the next finer boundary, so a
    page break falls between paragraphs where it can and mid-paragraph only
    when a single paragraph is longer than a page.
    """
    if len(text) <= limit:
        return [text]
    if level == len(SPLITS):
        # No whitespace at all for a whole page; nothing better than a hard cut.
        return [text[i:i + limit] for i in range(0, len(text), limit)]

    pattern, joiner = SPLITS[level]
    out: List[str] = []
    current = ""
    for part in pattern.split(text):
        for piece in _chunks(part, limit, level + 1):
            if not piece:
                continue
            if current and len(current) + len(joiner) + len(piece) > limit:
                out.append(current)
                current = piece
            else:
                current = current + joiner + piece if current else piece
    if current:
        out.append(current)
    return out


def text_to_pages(text: str) -> List[str]:
    """Split plain text into pages near TARGET_PAGE_CHARS."""
    text = _normalize(text)
    if not text:
        return [""]
    return _chunks(text, TARGET_PAGE_CHARS)
