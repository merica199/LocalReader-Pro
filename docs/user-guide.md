# LocalReader Pro user guide

LocalReader Pro reads your documents aloud in a natural voice that runs
entirely on your computer, and turns them into audio files: ordinary MP3s at
reading pace, or slow, calm sleep recordings with background sound.

This guide covers every feature and how to use it. Every setting, with its
default, its range and exactly what it affects, is in the
[settings reference](settings-reference.md), so this guide stays readable as
the settings grow.

On GitHub, the list icon at the top right of this page opens a clickable
outline, and Ctrl+F (Cmd+F on a Mac) searches it.

## Contents

1. [Getting started](#1-getting-started)
2. [The window at a glance](#2-the-window-at-a-glance)
3. [Your library](#3-your-library)
4. [Reading](#4-reading)
5. [Voice and audio](#5-voice-and-audio)
6. [Pronunciation](#6-pronunciation)
7. [Exporting audio](#7-exporting-audio)
8. [Sleep recordings](#8-sleep-recordings)
9. [Sleep timer](#9-sleep-timer)
10. [Updates](#10-updates)
11. [Where your files are](#11-where-your-files-are)
12. [Working with Claude](#12-working-with-claude)
13. [Troubleshooting and known issues](#13-troubleshooting-and-known-issues)

## 1. Getting started

**Installing.** Follow [Installation](../README.md#-installation) in the
README. On Windows you download the ZIP and double-click the installer; on a
Mac you clone the repository and double-click the installer. Either way it
sets up everything, including the voice.

**First launch.** Open LocalReader Pro from the Desktop or Start menu shortcut
(Windows) or from Applications (Mac). The window takes a few seconds to appear
the first time. The small dot at the top right of the left panel shows the
voice engine's state:

| Dot | Meaning |
|---|---|
| Green | Ready |
| Yellow, pulsing | Loading the voice |
| Blue, pulsing | Downloading the voice |
| Red | No voice yet: click **Setup Voice Engine** |

The installers download the voice for you, so you normally see green straight
away. If you see **Setup Voice Engine**, click it: it downloads the voice
(about 115 MB on a Mac with an Apple processor, about 340 MB on an Intel or
AMD computer) and the upload button appears when it is done.

## 2. The window at a glance

- **Left panel (sidebar):** the upload button, text size, the Export Audio
  button, and three tabs: Library, Rules and Ignore. The panel icon at its top collapses it; a small tab on the
  left edge brings it back. Drag its edge to make it wider or narrower.
- **Reader (middle):** the open document, a page at a time, with the page
  controls and search at the top.
- **Player bar (bottom):** play and pause, skip, and the sentence being read.
- **A round button on the right edge:** opens the **Sleep Timer**.
- **Settings:** a full-window page with three sections: **Voice & Audio**,
  **Processing Mode** and **Updates**. Open it from the menus (on a Mac,
  **LocalReader Pro > Settings...**; on Windows, **File > Settings**) or with
  Cmd+comma on a Mac, Ctrl+comma on Windows. Esc or the X closes it.
- **Menus:** on a Mac, the menu bar at the top of the screen; on Windows, the
  menu along the top of the window.

## 3. Your library

### Adding documents

Click **Upload Book (PDF/EPUB/MD/TXT)**, or drag a file anywhere onto the
window. Each format is handled differently:

| Format | How it is read | Notes |
|---|---|---|
| Text (`.txt`) | As written, split into pages of about 2,500 characters | Best for scripts: blank lines are kept, so paragraph pauses work |
| Markdown (`.md`) | Formatting removed, headings read as sentences, links as their text, code blocks as "code block" | Named after its first heading |
| PDF | Text extracted page by page | Blank lines are lost, so no paragraph pauses. A scanned PDF has no text to read |
| EPUB | Converted to a PDF, then read like one | Shows up in the library as a `.pdf`. Copy-protected books cannot be read |

Uploading the same file twice makes two entries. The app keeps only the
extracted text, not your original file.

### Opening, resuming and deleting

- **Open** a document by clicking it. It opens where you left off: the page and
  the sentence.
- **Progress is saved** every time a sentence starts playing. Turning pages
  without playing does not move your place.
- **Smart start:** if a book is still on its first page, the app skips ahead to
  where the real content starts (past the title pages and contents), and says
  so.
- **Delete** a document with the red X that appears when you hover over it.
  This removes it from the library; any audio you exported from it stays.

## 4. Reading

### Playing

- **Play / pause:** the big blue button, or the Space bar.
- **Skip:** the arrows either side of it, or the Left and Right arrow keys, move
  one sentence back or forward. Skipping forward past the last sentence goes
  on to the next page.
- **Jump to any sentence:** click it. Reading starts there after a short
  pause.

Skipping and clicking a sentence both start playback, even when paused.

The line in the player bar shows the sentence being read. The chevron at its
right hides the player; a **Show Player** button brings it back.

### Moving around

- **Pages:** the arrows and page number at the top, or scroll past the bottom
  or top of a page. Typing a page number and pressing Enter jumps there.
- **Follow along:** while it reads, the view turns pages with the voice. If you
  scroll or turn pages yourself, it stops following so you can look around.
  **Back to Reading** (above the player) returns you to the sentence being
  read.
- **Text size:** the slider in the left panel, from 12 to 24.

### Search

The magnifying glass at the top, or Ctrl+F (Cmd+F on a Mac), searches the open
document. Type at least two letters; results show the page and the words
around each match. Clicking one shows that page with the matches highlighted;
it does not move your reading place.

### Keyboard and menus

| Key | Action |
|---|---|
| Space | Play / pause |
| Left / Right arrow | Previous / next sentence |
| Ctrl+F or Cmd+F | Search |
| Cmd+comma (Mac) or Ctrl+comma (Windows) | Open or close Settings |
| Esc | Close Settings |

Keys do nothing while you are typing in a box. After dragging a slider, click
somewhere in the reader before using them, or they move the slider instead.

The **Playback** menu has Play / Pause and the sentence skips; **Document** has
the page arrows and **Reload Interface** (refreshes the window if something
looks stuck). **Settings** and **Check for Updates** are where each system
keeps them: on a Mac, both in the **LocalReader Pro** menu; on Windows,
**Settings** in **File** (with **Exit**) and **Check for Updates** in **Help**.
The menus show no shortcut beside Settings, but Cmd+comma or Ctrl+comma works.

### Page headers and footers

PDFs often repeat a title or page number at the top or bottom of every page.
**Header & Footer Mode** in Settings, Voice & Audio, can hide them or dim them so they are
not read. See the [settings reference](settings-reference.md#header--footer-mode).

## 5. Voice and audio

**Voice & Audio** is the first section of Settings:

- **Voice Selection:** about fifty voices, grouped by language, each labelled
  with its accent and gender. The play button beside the list plays a short
  sample of the selected voice.
- **Playback Speed:** how fast the voice reads, for reading and normal MP3
  export. Sleep recordings have their own speed.
- **Header & Footer Mode:** see above.
- **Pause Settings:** how long the voice pauses at commas, sentence ends,
  paragraphs and so on, while reading. Shown open; the header folds them away.

Changing the voice stops reading; press play to continue with the new one.
Every option is explained in the [settings reference](settings-reference.md#voice--audio).

**Processing Mode** (the second section of Settings) chooses between two versions of
the voice: **Standard**, compressed to a quarter of the size and the default, and
**Full precision**, uncompressed. Both run on your computer's processor; neither
uses a graphics card. Which is faster depends on the processor, so the app picks
for you: Standard on Apple processors, Full precision on Intel and AMD, where it
is several times faster. The green box under the choice says which suits this
computer, with a button to switch to it. See the [settings reference](settings-reference.md#processing-mode).

## 6. Pronunciation

### Science words are built in

The voice works out how to say a word it does not know from its spelling, and
for anatomy, physiology, biochemistry and drug names it often guesses wrong.
LocalReader Pro corrects about 230 of them automatically (diastole,
glomerulus, vagus, kinase, ATP, NADH and many more), in reading, MP3 export
and sleep recordings alike. You do not need to do anything.

### Check them by ear

> The built-in pronunciations were written by an AI from its own knowledge and
> checked against the voice engine's phonetic output, but an AI cannot hear the
> result. **A person needs to listen to them.** The person who knows the
> subject best is the right judge: for medical terms, a medical student over
> anyone else. Anything wrong is a one-line fix.

**The easy way: ask Claude.** With Claude open in the app's folder (see
[Working with Claude](#12-working-with-claude)), say:

> Make me a pronunciation check recording of the built-in words and put it on
> my Desktop.

You get `pronunciation-check.mp3` (about six minutes, every word spoken one at
a time) and `pronunciation-check.txt`, which lists each word with its time in
the recording. Listen with the list open, and for any word that sounds wrong,
tell Claude the word and how it should sound ("glomerulus sounds wrong, it's
glo-MER-yu-lus"). Claude fixes it in your personal list, records it again,
and you check once more. You can also ask it to check particular words: "how
will it say renin and angiotensin?" Claude looks each word up in published
pronunciations before fixing anything, and asks you when sources disagree.

**If you use a terminal,** the same recording is one command from the app's
folder (`venv\Scripts\python.exe` on Windows):

```bash
venv/bin/python tools/pronunciation_check.py --out ~/Desktop
```

Name words after the command to record just those. A word not on any list
comes out as the voice's own guess, which tells you whether it needs an entry.

### Your personal pronunciation list

Fixes you make go in a personal list, `pronunciations.json` in your library
folder ([where that is](#11-where-your-files-are)). It is yours: updates never
change it, and it wins over the built-in list, so a word you fix is right from
the next sentence on, with no restart. It can also switch off a built-in entry
that is wrong.

The built-in list is shared: it ships to everyone who installs or updates the
app, and it keeps growing. Fixes that would help everyone belong there. To
share yours, send your personal `pronunciations.json` to the app's maintainer
(merica199 on GitHub); once they are added, they arrive in your next update
and your personal copies are no longer needed.

### Words said two ways

Some words are spelled the same but said differently depending on what they
mean: "cells **live** for weeks" and "a **live** vaccine", "**lead**
poisoning" and "this can **lead** to swelling", "a **contract**" and "muscles
**contract**". The voice picks one reading from the words around it and is
often wrong: it reads "red blood cells live for about four months" like "a
live concert". A pronunciation list cannot fix these, since it would say the
word one way everywhere.

Instead, a `.txt` file can say how a single occurrence is read:
`[live](/lˈɪv/)`, the word followed by its sounds between slashes. The app
says it with those sounds and shows just the word.

**The easy way: ask Claude.** When it writes a sleep script, Claude checks
every one of these words before recording. If you hear one wrong, tell it
("'live' sounded like 'live concert'") and it fixes that spot in the script
and records it again. With a terminal, the check is
`venv/bin/python tools/check_heteronyms.py my-script.txt`
([details](writing-for-read-aloud.md#words-spelled-the-same-but-said-two-ways)).

### Your own rules (Rules tab)

The **Rules** tab replaces words with something easier to say before the voice
reads them: an abbreviation spelled out, a name respelled, a symbol turned into
a word.

1. Click **+**.
2. Fill in **Original Text** (what is in the document) and **Replacement Text**
   (what to say instead).
3. Choose the options: **Match Case** (only exactly that capitalization) and
   **Whole Word** (not inside longer words; on by default).
4. Click **Done**.

Rules save as you type and apply to reading and both kinds of export. Your rule
for a word wins over the built-in list. Note that **Use Pattern Matching** does
not work yet: rules always match the text literally.

### Words to skip (Ignore tab)

The **Ignore** tab lists text the voice should skip, such as a running title
or a watermark. Click **+**, type the text, and press Enter. It is removed
wherever it appears, even inside longer words, so prefer longer, specific
phrases.

## 7. Exporting audio

Click **Export Audio** (left panel, once a document is open) and choose a mode:

- **Normal:** the whole document as an MP3 at reading pace, in the current
  voice and Playback Speed.
- **Sleep mode:** a slow, calm recording with long pauses, background sound and
  gentle fades. See [Sleep recordings](#8-sleep-recordings).

Both always export the whole document from the first page. If FFmpeg (the
audio encoder) is missing, the app offers it first; on Windows it downloads it,
on a Mac it must be installed with Homebrew (the installer does this).

**Normal export** shows its progress and, when done, the file name and an
**Open Folder** button. Closing the dialog during a normal export cancels it.

Exported files are saved in your library folder; **Open Folder** opens it. See
[Where your files are](#11-where-your-files-are).

## 8. Sleep recordings

Sleep mode turns a document into the kind of slow, soothing narration made for
falling asleep to: every sentence followed by real silence, long pauses
between paragraphs, background noise underneath, the voice softened and placed
in a gentle room, and long fades in and out. It works on any document, but it
is at its best with a script written for it.

### Writing a script

A sleep script is a plain `.txt` file with a little markup:

| Markup | Effect |
|---|---|
| a blank line | a paragraph pause |
| `...` | a soft pause in the middle of a thought |
| `[pause 6]` | exactly that many seconds of silence |
| a line starting with `#` | skipped (notes to yourself) |
| `[live](/lˈɪv/)` | that word said with those sounds ([why](#words-said-two-ways)) |

[Writing sleep scripts](writing-sleep-scripts.md) explains how to write one
that works (length, shape, style and accuracy), and
[sample-scripts/skin-histology.txt](../sample-scripts/skin-histology.txt) is a
nine-minute example. A Claude agent can write one for you on whatever you are
studying; see [Working with Claude](#12-working-with-claude). If the script
has technical words that are not on the built-in list, check them by ear
first ([how](#check-them-by-ear)).

### Making the recording

1. Upload the script with **Upload Book**.
2. Open it, click **Export Audio**, and choose **Sleep mode**.
3. Set the options, or leave the defaults:
   - **Speed** (0.9 by default; slower is sleepier).
   - **Pauses:** the silence after sentences, at blank lines and at `...`, and
     before and after the voice.
   - **Sound:** the background (brown, pink or white noise, or a sound file of
     your own), how loud it is, how much to soften the voice, the room, the
     loudness, and the fades.
   - **File:** MP3, M4A or WAV, and the quality.
4. Click **Preview the first minute** to hear it with every option applied.
   Change something and preview again to compare.
5. Read the estimate line: how long the recording will be and how long it will
   take to make.
6. Click **Start export**.

Every option is in the [settings reference](settings-reference.md#sleep-mode),
and they are remembered for next time. **Reset to defaults** puts them all
back.

**While it renders,** you can keep reading in the app, or click **Keep
rendering in the background** and close the dialog; a message tells you when it
is finished. Closing the dialog with the X asks whether to stop. Stopping loses
nothing: every finished sentence is saved, so exporting again picks up where it
stopped.

**Making changes is quick.** Each spoken sentence is saved as it is made.
Exporting again after changing the pauses or the sound only re-mixes the
recording. Editing a few sentences of the script re-voices only those. Changing
the voice or the speed re-voices everything. The saved sentences take about
170 MB per hour of speech; **Clear cache** under the estimate frees the space.

### Your own background sounds

In **Background**, choose **Add a sound file...** and pick an audio file (MP3,
M4A, WAV, FLAC, OGG or AIFF): rain, a fan, waves. It loops under the voice for
the whole recording and appears under **Your sounds** from then on.
**Remove this sound** deletes it.

### Getting it onto your phone

A long recording is too big to email (an hour and a half at the default
quality is about 65 MB). On an iPhone, AirDrop it from the Mac, save it to
Files, and play it in a player app such as VLC, which keeps playing with the
screen locked. On Android, copy it over with a cable or through a cloud drive.

## 9. Sleep timer

The lower round button on the right edge opens the **Sleep Timer**. Set hours
and minutes and click **Start Timer**; the button then shows the time left.
**Stop Timer** cancels it.

**When the time is up, the timer closes the whole app,** not just the
playback, and stops any export in progress (a sleep recording keeps its
finished sentences and can be resumed).

## 10. Updates

The app checks for updates when you ask: **Check for Updates** in the menus
(the **LocalReader Pro** menu on a Mac, **Help** on Windows), which opens
Settings at **Updates** and checks, or **Check for updates** in that section.
It lists what changed.

**To be told about updates instead,** tick **Check automatically** in
Settings > Updates. The app then checks shortly after it opens and once a day while
it stays open. When there is an update, a green **Update available** button
appears at the top of the left panel (and a dot on its tab, if the panel is
collapsed), with a message the first time. Click it to see what changed. It is
off by default because it goes online without being asked: GitHub sees your
computer's internet address, and nothing else is sent. Nothing ever installs
until you click **Update and restart**. **Update and restart** closes the app, installs the
update, and opens it again; your library and settings are untouched. If an
update cannot be installed, the app is left as it was, and the next time it
opens it tells you what went wrong.

## 11. Where your files are

Your library, settings, saved sentences and exported audio live outside the
app, so updating or reinstalling never touches them:

- **Mac:** `~/Library/Application Support/LocalReader Pro/userdata`
- **Windows:** `%APPDATA%\LocalReader Pro\userdata`

Exported recordings are saved directly in that folder (**Open Folder** in the
Export dialog opens it). To back up everything that matters, copy the
`userdata` folder. Uninstalling is covered in the
[README](../README.md#uninstalling).

## 12. Working with Claude

The app comes set up for Claude Code. Claude can write sleep scripts, record
them, check and fix pronunciations, and change settings for you, all from
plain requests; you never need a terminal.

**Setting it up:** open Claude Code in the app's own folder:

- **Windows:** `%LOCALAPPDATA%\Programs\LocalReader Pro` (paste it into the
  folder picker; Windows fills in the rest)
- **Mac:** `/Applications/LocalReader Pro.app/Contents/Resources/LocalReader-Pro`

Claude reads its instructions from [CLAUDE.md](../CLAUDE.md) in that folder,
including how to work there without changing the app, so updates keep
working. Keep LocalReader Pro open while Claude records anything.

**Things you can ask:**

| Ask | What happens |
|---|---|
| "Write me a 90 minute sleep script about the cranial nerves." | Claude writes it in the style of the sample, times it to the length, checks every technical word, and saves it in `Documents/Sleep scripts` |
| "Here are my lecture notes, make a sleep script from them." | The same, following what your course emphasizes |
| "Record it." | It adds the script to your library and makes the sleep recording with your voice and settings, then tells you where the file is. A 90 minute recording takes about 45 minutes to make |
| "Make a one-minute preview first." | Just the first minute, to try a voice or setting |
| "Make me a pronunciation check." | A recording of every built-in word, to listen to ([why](#check-them-by-ear)) |
| "Renin sounded wrong, it should be REE-nin." | It fixes the word in your personal list and records it for you to check |
| "'Live' sounded like 'live concert'." | It fixes each wrong one in the script and records it again ([why](#words-said-two-ways)) |
| "Make the recordings slower and sleepier." | It changes the sleep settings for you |
| "Something's not working." | It looks into it and writes up the problem for you to send |

Scripts and recordings stay on your computer, outside the app's folder. The
app's repository is public, so Claude never puts your scripts in it.

## 13. Troubleshooting and known issues

### Troubleshooting

| What you see | What to do |
|---|---|
| Red dot and **Setup Voice Engine** | Click it to download the voice. If it fails, the button simply comes back: check your internet connection and try again |
| No sound when pressing play | Press pause and play again; the app rebuilds its audio output each time, which fixes it after sleep or a headphone change |
| Space or the arrows move a slider | Click in the reader first, then use the keys |
| The window looks frozen or unstyled | **Document > Reload Interface**. The window's styling is loaded from the internet, so without a connection it can look plain until you are back online |
| Export says FFmpeg is needed | Accept the download (Windows), or run the installer again (Mac) |
| A word is mispronounced | Add a rule for it, or add it to the built-in list ([how](writing-for-read-aloud.md#pronunciation)) |

### Known issues

These are how the app behaves today; they are on the list to fix.

- **Sleep timer:** it closes the whole app when the time is up, not just the
  playback.
- **Rules:** **Use Pattern Matching** has no effect. A backslash in a
  replacement can make the rules for that sentence silently stop applying.
- **Processing Mode:** both choices run on the processor, not a graphics card.
  Switching takes effect the next time the app opens, unless the chosen voice
  still needs downloading.
- **Header & Footer Mode:** it affects reading only; both kinds of export still
  read headers and page numbers. While it is on, paragraph pauses stop working,
  and it can drop a line made only of letters that look like Roman numerals
  ("mix", "civil").
- **Paragraph pauses** never happen in PDFs or EPUBs while reading, because
  their blank lines are lost.
- **Period Pause** pauses at every period, including in "3.5" and "Dr.".
- **Ignore list** entries are removed even inside longer words.
- **Words said two ways** ("live", "lead", "contract", "increases") are often
  read with the wrong meaning. Text files can mark the right reading
  ([how](#words-said-two-ways)); PDFs, EPUBs and Markdown cannot.
- **Normal export** names the file with "pdf" stuck to the title
  ("Bookpdf_af_bella.mp3"), replaces an earlier export of the same document
  without asking, and is always MP3 at 128 kbps.
- **Search:** Escape does not close it while the search box is selected, and
  match highlights stay on until the app is reopened.
- **Language button:** switching language while a document is open blanks the
  title until you reopen the document.
- **EPUB:** chapters can come out of order, and any conversion error says only
  "Conversion failed".
- **Voices:** one Japanese voice (Alpha) is hidden by mistake.
- **Messages:** every message appears in red, even good news, and setup errors
  are not shown.
