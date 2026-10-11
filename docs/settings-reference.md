# LocalReader Pro settings reference

Every setting in the app: where it is, its default and range, and exactly what
it affects. The [user guide](user-guide.md) explains how to use the features;
this page is for looking things up.

Settings are saved as you change them and kept when the app restarts, unless
noted. Reading settings are in `userdata/settings.json`, sleep recording
settings in `userdata/sleep_settings.json`
([where userdata is](user-guide.md#11-where-your-files-are)).

## Contents

- [What affects what](#what-affects-what)
- [Voice & Audio](#voice--audio)
- [Processing Mode](#processing-mode)
- [Text Size and language](#text-size-and-language)
- [Rules and Ignore](#rules-and-ignore)
- [Normal export](#normal-export)
- [Sleep mode](#sleep-mode)
- [Sleep Timer](#sleep-timer)

## What affects what

The app has three ways of producing speech, and each setting reaches only some
of them:

| Setting | Reading aloud | Normal export | Sleep export |
|---|---|---|---|
| Voice | yes | yes | yes |
| Playback Speed | yes | yes | no (has its own Speed) |
| Pause Settings | yes | no | no (has its own Pauses) |
| Header & Footer Mode | yes | no | no |
| Rules | yes | yes | yes |
| Ignore list | yes | yes | yes |
| Built-in science pronunciations | yes | yes | yes |
| Processing Mode (which voice model) | yes | yes | yes |
| Sleep mode options | no | no | yes |

## Voice & Audio

Opened with the upper round button on the right edge of the window.

### Voice Selection

- **What it is:** the voice, from the voices built into the voice pack, grouped
  by language: English (UK), English (US), Chinese (Mandarin), Spanish,
  French, Italian, Japanese, Portuguese (Brazil). Each is labelled "Name
  (Region Gender)", for example "Bella (American Female)".
- **Default:** Bella (American Female).
- **The play button** beside it plays a fixed sample sentence in that voice, at
  normal speed. Click again to stop.
- **Changing it** stops reading and clears saved reading audio, so press play
  to continue in the new voice. Sleep recordings keep their saved sentences
  per voice, so switching back to a voice reuses what was already made.
- The voice decides the reading language: an English text read by a French
  voice comes out in a French accent.

### Playback Speed

| | |
|---|---|
| Type | slider |
| Range | 0.5x to 3.0x, in steps of 0.05 |
| Default | 1.00x |
| Affects | reading aloud and normal export |

The voice itself speaks faster or slower (no pitch change). The sentence
already playing finishes at the old speed. The tick marks under the slider are
evenly spaced, so "1.0x" and "2.0x" are not exactly at those values; read the
number above the slider.

### Header & Footer Mode

| Option | Effect |
|---|---|
| Show All (default) | Everything is shown and read |
| Hide | Repeated headers, footers and page numbers are removed from the page and not read |
| Dim | They are shown faded and small, and not read |

Detection compares the top and bottom few lines of each page with its
neighbours: a line that repeats (90% the same) or looks like a page number
("12", "xii", "Page 12", "12 of 300") counts. It affects reading only; both
kinds of export read every line. While Hide or Dim is on, paragraph pauses do
not happen (a known issue).

### Pause Settings

A collapsible section, closed by default. Each slider sets the silence, in
milliseconds (thousandths of a second), at that punctuation mark while reading
aloud. Normal export and sleep export ignore them.

| Slider | Range | Default |
|---|---|---|
| Comma Pause | 0 to 1000 | 0 |
| Period Pause | 0 to 1500 | 600 |
| Question Pause | 0 to 1500 | 600 |
| Exclamation Pause | 0 to 1500 | 600 |
| Colon Pause | 0 to 1500 | 0 |
| Semicolon Pause | 0 to 1500 | 0 |
| Paragraph Pause | 0 to 3000 | 1200 |

All in steps of 50.

- **At 0, the voice makes its own pause** and reads the sentence in one piece,
  with natural phrasing. This is why commas, colons and semicolons default to
  0.
- **Above 0, the sentence is cut at that mark** and exact silence is inserted,
  which costs a little of the natural intonation across the sentence.
- **Period Pause** applies at every period, including inside "3.5" and after
  "Dr.".
- **Paragraph Pause** is the total silence after the last sentence of a
  paragraph (it includes that sentence's own end pause). A paragraph ends at a
  blank line, and for text and Markdown files at the end of a page. PDFs and
  EPUBs lose their blank lines, so this does not apply to them.

## Processing Mode

Bottom of the left panel.

| Option | Model file | Size |
|---|---|---|
| High Performance (CPU), the default | `kokoro.int8.onnx`, compressed | about 87 MB |
| High Quality (GPU) | `kokoro.onnx`, full precision | about 309 MB |

- **Both run on the processor.** The labels are historical: neither uses a
  graphics card. The larger model can sound slightly different; the smaller one
  is faster and uses less memory.
- **The ✓ and ✗ marks below it** show which model files are downloaded, not
  which one is in use.
- **Switching** to a model that is downloaded takes effect the next time the
  app opens. Switching to one that is not shows **Setup Voice Engine**, which
  downloads it and switches straight away.
- Saved sleep sentences are kept per model, so switching models re-voices a
  sleep recording.

## Text Size and language

- **Text Size** (left panel, once a document is open): 12 to 24, default 16.
  Changes the reader text and the sentence line in the player.
- **Language button** (top of the left panel, shows "EN"): each click switches
  the interface between English, Spanish, French and Chinese. It changes the
  labels and voice descriptions, not the voice or what is read. Parts of the
  app (the Export dialog, Updates and messages) are English only.
- **Sidebar width** (drag its edge, 200 to 600 pixels) and the collapsed or
  hidden state of the sidebar and player are not saved.

## Rules and Ignore

### Rules (pronunciation rules)

Each rule has:

| Field | Meaning | Default |
|---|---|---|
| Original Text | The text to find | empty |
| Replacement Text | What to say instead | empty |
| Match Case | Only that exact capitalization | off |
| Whole Word | Only whole words, not inside longer ones | on |
| Use Pattern Matching | Intended for patterns; currently has no effect | off |

Rules run in list order, each on the result of the ones before, after the
Ignore list. They change what is spoken, not what is shown. A rule for a word
on the built-in science list wins over the built-in entry.

### Ignore

Each entry is text removed before speaking, wherever it appears, in any
capitalization, including inside longer words.

### Built-in science pronunciations

About 230 biology, chemistry and medical words and acronyms with their exact
pronunciation, in
[dist/app/logic/pronunciations.json](../dist/app/logic/pronunciations.json).
English voices only. Words match in any capitalization, acronyms only exactly
as written ("ATP", not "atp"), and possessives ("Henle's") are handled. Adding
to it, and checking the result by ear, is explained in
[writing for read-aloud](writing-for-read-aloud.md#pronunciation).

## Normal export

**Export Audio**, then **Normal**. It has no settings of its own; it uses the
current Voice, Playback Speed, Rules and Ignore list.

- Reads the whole document from the first page, each line or long sentence in
  one piece with 0.3 seconds of silence after it.
- Always MP3, 128 kbps.
- Saved as `<document name>_<voice>.mp3` in the userdata folder, replacing an
  earlier export of the same document and voice.
- Estimate shown: about 15 seconds of export time per 1,000 characters.

## Sleep mode

**Export Audio**, then **Sleep mode**. These settings are saved as you change
them (the dialog says "Settings are remembered"). **Reset to defaults** puts
them all back, except your added background sounds. A blank or out-of-range
number is corrected to the nearest allowed value when saved.

Sleep mode uses the Voice, Rules and Ignore list. It ignores Playback Speed,
Pause Settings and Header & Footer Mode.

### Speed

| | |
|---|---|
| Range | 0.5 to 1.5, in steps of 0.05 |
| Default | 0.9 |

Slower than reading speed by default. Changing it re-voices the whole
recording.

### Pauses (seconds)

| Setting | Default | Range | Step |
|---|---|---|---|
| After a sentence | 1.0 | 0 to 60 | 0.1 |
| At a blank line (paragraph) | 2.6 | 0 to 60 | 0.1 |
| At `...` (soft pause) | 1.1 | 0 to 60 | 0.1 |
| Inside a sentence split for length | 0.3 | 0 to 10 | 0.05 |
| Before the voice starts | 3.0 | 0 to 600 | 0.5 |
| After the voice ends | 8.0 | 0 to 3600 | 1 |

- The voice reads one sentence at a time and every pause is real silence, so
  the pacing is exact for the whole recording.
- A sentence longer than about 220 characters is split at the comma nearest its
  middle, with the "split for length" pause between the halves.
- Pauses that meet do not add up: the longer one wins. A `[pause N]` in the
  script sets an exact silence.
- After the voice ends, the background keeps playing until the fade out
  finishes.
- In a PDF or EPUB, a page break is not a paragraph pause.

Changing pauses never re-voices anything; exporting again only re-mixes.

### Sound

| Setting | Options | Default |
|---|---|---|
| Background | None; Brown noise (deep); Pink noise (like rain); White noise (hiss); your own sounds | Brown noise |
| Background level | 40 to 6 dB below the voice, in steps of 1 | 18 dB below |
| Soften the voice | Off; Light (8.5 kHz); Medium (6 kHz); Strong (4 kHz) | Light |
| Room | Off (dry); Subtle; Roomy | Subtle |
| Loudness | As rendered; Quiet (-26 LUFS); Normal (-22 LUFS); Louder (-18 LUFS) | Normal |
| Fade in (seconds) | 0 to 600, in steps of 0.5 | 3 |
| Fade out (seconds) | 0 to 1800, in steps of 1 | 45 |

- **Background:** the noises are generated, in stereo, and filtered to be
  gentle: brown noise is a low rumble, pink is softer and brighter like rain,
  white is a hiss. **Add a sound file...** adds your own (MP3, M4A, AAC, WAV,
  FLAC, OGG, Opus or AIFF), which loops under the voice; **Remove this sound**
  deletes it.
- **Background level** is relative to the voice: "18 dB below" stays 18 dB
  below whatever the loudness setting. Every 10 dB lower sounds roughly half as
  loud.
- **Soften the voice** is a low-pass filter: it rounds off the bright top end of
  the voice, more at each step. The number is where it starts cutting.
- **Room** adds a short, quiet reverberation, as if the voice were in a small
  room: Subtle is about half a second, Roomy almost a second and stronger.
- **Loudness** evens out the whole recording to a target loudness, measured in
  LUFS (Loudness Units relative to Full Scale, the standard measure of how loud
  audio sounds). A lower number is quieter. As rendered skips it.
- **Fades** bring the whole recording, background included, in and out
  gradually.

Everything except the plain voice in WAV needs FFmpeg, which the app offers
when it is missing.

### File

| Setting | Options | Default |
|---|---|---|
| Format | MP3; M4A (AAC); WAV (uncompressed) | MP3 |
| Quality | 64 kbps (smallest); 96 kbps; 128 kbps; 192 kbps | 96 kbps |

Quality is hidden for WAV. For speech with soft background noise, 96 kbps is
plenty: about 43 MB per hour. M4A is slightly better quality at the same size
and plays everywhere Apple does. WAV is very large: over 600 MB per hour with any sound option on.

Saved as `<document name>_<voice>_sleep.<format>` in the userdata folder.

### Preview, estimate and cache

- **Preview the first minute** makes about 60 seconds with every option
  applied (the lead-in, fades and tail shortened so the minute is mostly
  voice) and plays it in the dialog. The sentences it makes are saved, so the
  full export reuses them.
- **The estimate line** shows the recording's length, how many pieces it has
  and how many are already made, and roughly how long making it will take.
  "Sentences" there counts pieces, so a long sentence split in two counts
  twice.
- **Sentence cache** shows the space the saved sentences use (about 170 MB per
  hour of speech). **Clear cache** deletes them all; the next export makes
  them again from scratch. It cannot be cleared while a recording is being
  made.

## Sleep Timer

The lower round button on the right edge.

| Setting | Range | Default |
|---|---|---|
| Hours | 0 to 12 | 0 |
| Minutes | 0 to 59 | 30 |

**Start Timer** starts it (at least one minute); the button then shows the time
left, and **Stop Timer** cancels it. When it runs out it **closes the whole
app**, including any export in progress. It is not saved: it ends if the app
is closed.
