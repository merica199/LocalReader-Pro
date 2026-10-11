# Writing sleep scripts

How to write a script for the Export dialog's Sleep mode: a slow, calm,
lecture-style story about a real subject, the kind of thing sleep-story
podcasts do, made to fit whatever is being studied right now. Read
[writing-for-read-aloud.md](writing-for-read-aloud.md) first; everything there
applies here too.

[sample-scripts/skin-histology.txt](../sample-scripts/skin-histology.txt) is a
nine-minute example that uses every kind of markup.

## The markup

Write plain text, saved as a `.txt` file (UTF-8). Sleep mode reads four kinds
of markup:

| Markup | Effect |
|---|---|
| a blank line | a paragraph pause, 2.6 seconds by default |
| `...` | a soft pause in the middle of a thought, 1.1 seconds |
| `[pause 6]` | exactly that many seconds of silence |
| a line starting with `#` | skipped; use it for notes and a header |

Each sentence end adds a 1 second pause. Every default can be changed in the
Export dialog's Pauses section.

Upload scripts as `.txt` or `.md`, not PDF. A PDF loses the blank lines, and
with them every paragraph pause.

## Length

At the usual sleep speeds (0.8 to 0.9) with the default pauses, a script runs
at about 110 words a minute. An hour is about 6,500 words; a two-hour recording
about 13,000.

To check a draft, run it through the same estimate the Export dialog shows,
using the speed and pauses last saved there:

```bash
venv/bin/python tools/estimate_sleep_script.py my-script.txt
```

Long scripts are easiest to write in parts (one per chapter) and time
together: the tool accepts several files and adds them up.

## Shape

What works, from the recordings made so far:

1. **An opening that settles the listener.** Welcome them, say there is nothing
   to remember and no test at the end, and lead two slow breaths:
   `Take a slow breath in... hold it, just for a moment... and let it all go.`
   Then `[pause 6]`.
2. **One gentle thread through the whole thing.** A character living through
   the subject works well: a student's first year, one body system a month,
   with small scenes between the lessons (walking to class in the snow, making
   soup, the exam). The thread is what makes it a story instead of a lecture.
3. **Chapters, each ending with `[pause 8]`.** Inside a chapter, use
   `[pause 3]` to `[pause 6]` between sections.
4. **Bring the listener's body into it now and then.** When the script explains
   the diaphragm, invite a slow breath. When it explains the vagus nerve, note
   that their own heart is slowing. It is calming, and it ties the facts to
   something felt.
5. **An ending that winds all the way down.** Shorter sentences, more ellipses,
   longer silences (`[pause 10]`, then 12, then 15), then a final "Goodnight."
   Silence after the last line is trimmed, so end on words.

## Style

- Slow and warm, present tense. Short, plain sentences, mostly 10 to 25 words.
- Real, specific facts, delivered gently: "about a hundred thousand beats a
  day", not "a lot". Comparisons to everyday things help ("about the size of a
  closed fist").
- Repeat small refrains: "Lub... dub." A mnemonic read slowly works beautifully
  ("Three, four, and five, keep the diaphragm alive").
- Nothing alarming, urgent or suspenseful. Disease and injury can come up, but
  briefly and calmly.
- No lists, no questions that expect an answer, no "as we will see later".
- Follow the read-aloud rules for numbers, acronyms and symbols. In particular,
  never put spaces between the letters of an acronym.

## Accuracy

The point is to fit what is being studied, so the facts have to be right. A
calm, confident voice makes a wrong fact easy to absorb.

- Check every number and claim. Prefer a rounded number that is certainly
  right ("about a million nephrons in each kidney") over a precise one that
  might not be.
- When something is debated or only shown in animals, say so in passing ("in
  studies of mice").
- Leave out anything uncertain rather than hedging it at length.

## Pronunciation

Check every technical word before recording. The app's built-in list covers
about 230 common science words, and anything else can be checked in a few
seconds; [writing-for-read-aloud.md](writing-for-read-aloud.md#pronunciation)
shows how. Add the words it gets wrong to the list, so every later script gets
them right too.

## Recording it

1. In the app, click **Upload Book** and choose the script.
2. Open it, click **Export Audio (MP3)**, and choose **Sleep mode**.
3. Click **Preview** to hear the first minute with the chosen voice and sound.
4. Export. A long script takes a while; the dialog shows progress.

Each spoken sentence is saved as it is made. Exporting again after changing
pauses, background sound, room or loudness only re-mixes, which takes a couple
of minutes. Editing a few sentences re-voices only those. Changing the voice
or the speed re-voices everything.

## Where scripts live

Scripts written about real people, or for one person, are personal. This
repository is public, so keep them in a folder of their own outside it. Only
general examples belong in `sample-scripts/`.
