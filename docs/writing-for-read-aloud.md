# Writing text for LocalReader Pro to read aloud

Rules for any text written to be read by this app, in normal reading, MP3
export or sleep mode. Every example below was checked by running it through the
app's own text cleanup and the voice engine, and reading the sounds that came
out. For sleep scripts, read this first, then
[writing-sleep-scripts.md](writing-sleep-scripts.md).

## How the voice reads

The voice (Kokoro, with the espeak-ng engine turning letters into sounds) reads
one sentence at a time and decides how to say each word from its spelling. It
knows common English and common acronyms (DNA, MRI, HIV). It guesses at
everything else, and for Latin anatomy, drug names, eponyms and unfamiliar
acronyms it often guesses wrong. Capital letters and hyphens do not change
where it puts the stress.

Before the voice sees the text, the app tidies it for PDFs. One of those steps
joins single letters separated by spaces back into a word, because broken PDFs
produce "W o r d". So **"A T P" with spaces does not work**: it becomes "ATP".

## Numbers, units and symbols

| Write | Not | Because the voice says |
|---|---|---|
| twenty thousand | 20,000 | "twenty, zero zero zero" |
| one and a half, one point five | 1.5 | "one, five", with the point as a pause |
| three to five days | 3-5 days | "three dash five" |
| a fifth | 1/5 | "one slash five" |
| meters per second | m/s | "M slash S" |
| milligrams, milliliters | mg, mL | "M G", "M L" |
| about twenty | ~20 | "tilde twenty" |
| becomes, leads to | → | "right arrow" |
| for example, that is | e.g., i.e. | "E, G", "I, E" |
| calcium ions, sodium and potassium | Ca2+, Na+ and K+ | "kah two plus", "nah plus" |
| type four collagen | type IV collagen | "type Roman four" |
| carbon dioxide | CO2 | listed, so it reads "C O two", but the name sounds better |

Plain whole numbers (206, 2026), percentages (10%), degrees (37 °C), pH, "T3",
"vitamin B12" and Greek letters (α, β) all read correctly. "Dr." reads as
"doctor", followed by a short pause.

## Acronyms

Write them normally: "ATP", "NADH", "ECG". The app has the common biology and
medical ones in its pronunciation list, read as letters. For one that the voice
reads as a word and the list does not have, write the letters joined by hyphens
("S-G-L-T") or add it to the list. Never use spaces between the letters (see
above).

## Pronunciation

The app carries a built-in list of about 230 science words the voice gets
wrong, from "diastole" to "glomerulus" to "kinase". Each entry gives the exact
sounds, so the voice says them correctly in every mode. The list is
[dist/app/logic/pronunciations.json](../dist/app/logic/pronunciations.json),
and [dist/app/logic/pronunciations.py](../dist/app/logic/pronunciations.py)
explains how to add a word. After any change, run
`venv/bin/python tests/test_pronunciations.py`.

To find out whether the voice says a word correctly, run it through the engine
and read the sounds (IPA, the International Phonetic Alphabet):

```bash
venv/bin/python -c "from kokoro_onnx.tokenizer import Tokenizer; print(Tokenizer().phonemize('glomerulus', 'en-us'))"
```

The stress mark `ˈ` comes right before the stressed vowel. Rewriting the word's
spelling in the text is not a reliable fix: the engine still guesses the
stress. A user can also add a personal respelling in the app's Rules tab, which
wins over the built-in list for that word.

## Punctuation

- Keep sentences short, under about 200 characters. A longer one is split at a
  comma before the voice reads it, and long inputs are where a voice drifts.
- Commas are the pauses the voice actually makes. A semicolon or colon works
  too.
- In sleep mode, quotation marks are dropped and dashes and brackets become
  commas. In normal reading they are read as written, so prefer commas there as
  well.
- An abbreviation with a period (Dr., Mr., etc.) does not end the sentence. A
  single capital letter with a period does not either, so initials are safe.
