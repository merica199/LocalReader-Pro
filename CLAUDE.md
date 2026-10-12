# LocalReader Pro: notes for Claude

A desktop app that reads documents aloud with a voice running entirely on this
computer (Kokoro, through kokoro_onnx and espeak-ng), and exports MP3s,
including slow "sleep mode" recordings with background sound. A FastAPI server
(`dist/app/`) serves a web UI (`dist/app/ui/`) inside a pywebview window
(`dist/main.py`). The README covers installation;
[docs/user-guide.md](docs/user-guide.md) covers every feature and
[docs/settings-reference.md](docs/settings-reference.md) every setting, both
taken from the code. Read them before answering how something works.

## Who you are probably working for

Most people using this repository with Claude are not programmers. They use
the app to make sleep recordings, often about what they are studying, and they
talk to you in plain words: "write me an hour on the cranial nerves", "the
word 'renin' sounded wrong", "make the recording". So:

- **Do the work yourself.** Never ask them to run a command, open a terminal,
  or edit a file. Every procedure below is something you carry out.
- **Speak plainly.** Say what you did and where the result is, with the full
  path to any file. No jargon without a plain explanation.
- **Ask only what you need.** A topic is enough to start a script; use the
  defaults below for anything they did not say.
- **Tell them before anything slow.** A long recording takes a while to make
  (see "Make the recording"); say roughly how long, and run it in the
  background.

## Where things are

| | Windows | Mac |
|---|---|---|
| The installed app (a git clone) | `%LOCALAPPDATA%\Programs\LocalReader Pro` | `/Applications/LocalReader Pro.app/Contents/Resources/LocalReader-Pro` |
| The app's Python | `<app>\venv\Scripts\python.exe` | `<app>/venv/bin/python` |
| Library, settings, recordings | `%APPDATA%\LocalReader Pro\userdata` | `~/Library/Application Support/LocalReader Pro/userdata` |
| Personal pronunciations | `<userdata>\pronunciations.json` | `<userdata>/pronunciations.json` |
| Scripts and finished recordings | `Documents\Sleep scripts` (create it) | `~/Documents/Sleep scripts` (create it) |

Inside the installed app, `dist/userdata` is a link to the userdata folder.
On Windows, Claude Code's shell is usually Git Bash: write paths with forward
slashes, for example `"$LOCALAPPDATA/Programs/LocalReader Pro/venv/Scripts/python.exe"`.
Every command below is shown from the app's folder; quote paths, since they
contain spaces.

Below, `python` means the app's Python, never another Python on the computer:
only the app's has the voice and its libraries.

## Requests and exactly how to handle them

### "Write me a sleep script about ..."

1. Read [docs/writing-sleep-scripts.md](docs/writing-sleep-scripts.md) and
   [docs/writing-for-read-aloud.md](docs/writing-for-read-aloud.md) first,
   every time. They hold what testing showed; the voice gets several
   obvious-looking things wrong.
2. Defaults when they did not say: **about 90 minutes**, one gentle story
   thread through the topic, the shape and style in the sleep guide, and
   [sample-scripts/skin-histology.txt](sample-scripts/skin-histology.txt) as
   the model for tone.
3. If they give lecture notes, slides or a reading list, read them and follow
   their emphasis and terminology: the script should match what is being
   taught. Ask for them if the topic is one course's material and none were
   given; otherwise write from your own knowledge.
4. **Accuracy is not optional.** The listener may be studying this. Check
   every fact and number; prefer a rounded number that is certainly right;
   leave out anything uncertain.
5. Write it in parts (one per chapter) and time it as you go:
   `python tools/estimate_sleep_script.py part1.txt part2.txt ...`
   (several files are timed as one recording). Adjust until it is within a
   few minutes of the length asked for, then join the parts into one `.txt`.
6. **Check every technical word** before calling the script done (see
   "Check how words are said"): run them all through
   `tools/lookup_pronunciation.py`, and fix every one the engine gets wrong in
   the personal list. Record the new fixes for the person to hear.
7. Save the script in the scripts folder, named for the topic
   (`cranial-nerves.txt`). Never in this repository: it is public.
8. Tell them where it is and how long it runs, and offer to record it.

### "Make the recording" / "Record it"

The app must be open (the green dot showing). Then:

```bash
python tools/make_sleep_recording.py "<script.txt>" --copy-to "<scripts folder>"
```

It adds the script to the app's library (replacing an earlier version of the
same file instead of adding a copy), records it with their chosen voice,
pronunciation rules and saved sleep settings, and copies the finished file to
the scripts folder. Add `--preview` to make only the first minute, for
trying a new voice or setting.

- **How long it takes:** voicing runs at about twice real time on a recent
  computer, so a 90-minute script takes roughly 45 minutes, plus a couple of
  minutes to mix. Sentences already voiced for an earlier version are reused,
  so a re-recording after small edits is quick. The tool prints an estimate
  before it starts. Run it in the background and tell them.
- **If it says the app is not running**, ask them to open LocalReader Pro and
  wait for the green dot.
- **If it says FFmpeg is missing**, ask them to click Export Audio in the app
  once; it offers the download.
- They can also do all of this themselves in the app (Export Audio, then Sleep
  mode); the [user guide](docs/user-guide.md#8-sleep-recordings) explains it.

### "Check how words are said" / "Make me a pronunciation check"

Use everything you have, in this order. Never write a pronunciation from
memory alone when a published one can be found, and **you cannot hear the
voice**, so a person listening is always the last step.

1. **Look it up, and see what the voice will say**, in one step:

   ```bash
   python tools/lookup_pronunciation.py renin angiotensin
   ```

   For each word it prints the published pronunciations on Wiktionary (IPA,
   the International Phonetic Alphabet, labelled US or GA for American, UK or
   RP for British), the app's entry if it has one, and the engine's own guess,
   with a note when they disagree. It needs the internet.
2. **When Wiktionary has nothing** (common for eponyms, Latin muscle names,
   plurals and newer drugs), search the web: "<word> pronunciation", the
   Merriam-Webster medical dictionary, MedlinePlus, university anatomy
   pronunciation guides, or the singular form for a plural. Use what you find
   to decide; do not copy pages.
3. **Choose the right pronunciation.** Prefer American medical usage. When
   sources give more than one accepted pronunciation (Purkinje as
   pur-KIN-jee or pur-kin-JAY), say so and ask which one their course uses:
   the person's ear and their professors are the authority. Only fall back on
   your own knowledge when nothing published can be found, and say that you
   did.
4. **Write it in the engine's style.** Published IPA marks stress at the start
   of a syllable; the engine puts the stress mark right before the stressed
   vowel, and writes some sounds its own way (ɹ for r, ɚ, ᵻ). Phonemize a
   word with the same sounds to see how it writes them, and match that.
5. Record words for a person to hear, with a list of each word's time in the
   recording:

   ```bash
   python tools/pronunciation_check.py renin kinase --out "<Desktop>"
   ```

   With no words named it records every entry, built-in and personal (about
   six minutes).
6. **Then tell them, plainly and before anything else:** "Please listen to
   pronunciation-check.mp3 on your Desktop. It's <N> minutes, and
   pronunciation-check.txt gives each word's time in the recording. I wrote
   every pronunciation from my own knowledge, checked against the engine's
   phonetic output, but I can't hear the result. You're the better judge of
   how these words should sound. Anything wrong is a one-line fix." For
   medical terms, a medical student's ear beats your reading every time.

### "The word X sounded wrong" / fixing a pronunciation

Fixes go in the **personal list**, `<userdata>/pronunciations.json`, never in
the app's own files: editing the installed app makes its updater refuse to
update. The personal list wins over the built-in one, takes effect
immediately (no restart), and survives updates.

1. Find the right pronunciation as in "Check how words are said": look it up
   (`tools/lookup_pronunciation.py`, then the web), and ask the person how it
   should sound when sources disagree or you are unsure. Their ear and their
   course are the authority.
2. Write the IPA in the engine's own style (step 4 there).
3. Add it to the personal list, creating the file if needed:

   ```json
   {
     "words": { "renin": "ɹˈiːnɪn" },
     "acronyms": { "GLUT4": "ɡlˈuːt fˈɔːɹ" }
   }
   ```

   `words` match any capitalization; `acronyms` only as written. An empty
   value (`"ROS": ""`) switches a built-in entry off, for when the built-in
   one is wrong.
4. Check it reads back as intended (`tools/lookup_pronunciation.py <word>`
   shows the app's entry now in use), then record it and ask them to listen
   (steps 5 and 6 there).
5. Words that need it everywhere should reach the shared list: see "Share
   pronunciation fixes".

Rules in the app's Rules tab are the other way to change pronunciation:
replacing a word with a respelling. Use them for names and abbreviations
(spelling something out); use the personal list for science words, since a
respelling cannot control where the stress goes.

### "Share pronunciation fixes" / sending them to everyone

The built-in list, `dist/app/logic/pronunciations.json`, ships with the app to
everyone who installs or updates it, and is meant to keep growing. A user's
personal fixes reach it like this:

1. They send their personal list (`<userdata>/pronunciations.json`) to the
   repository's owner (merica199 on GitHub). Offer to find the file for them.
2. In a clone of the repository (not an installed app), the owner's agent
   runs `python tools/promote_pronunciations.py <their file>`, which adds,
   updates or removes entries and prints every change; then
   `python tests/test_pronunciations.py`,
   `python tools/lookup_pronunciation.py --audit` (flags any entry that
   disagrees with Wiktionary), a listening check of the changed words, and a
   commit.
3. After their next update, those entries are in the built-in list, and the
   personal copies can be cleared.

### "Change the voice" / "Make it slower" / other settings

- **Voice, and reading speed:** Voice & Audio in the app (the upper round
  button on the right edge). Sleep recordings use the voice chosen there.
- **Sleep recording options** (speed, pauses, background sound, fades, file
  format): the Export dialog's Sleep mode, where they are saved. You can also
  change them for the person: `GET /api/export/sleep/settings`, change the
  fields, `POST /api/export/sleep/settings` with the whole `settings` object
  (the app must be running; send `Origin: http://127.0.0.1:8000`). Every
  option and its range is in [the settings reference](docs/settings-reference.md#sleep-mode).
- Slower and sleepier: sleep Speed 0.8, longer pauses after sentences
  (1.2 to 1.5 seconds) and paragraphs (3 to 4).

### "How do I get it on my phone?"

See [Getting it onto your phone](docs/user-guide.md#getting-it-onto-your-phone).
Known so far: AirPlay to an older Apple TV (third generation and earlier)
works through Apple's own players (Music, Photos, YouTube's) but not VLC's
audio; a recording of an hour or more is too big to email.

### "Update the app"

Help > Check for Updates in the app, or the Updates box on the left panel's
Settings tab. Never update it with git yourself: the updater also installs the
libraries a new version needs.

To be told about updates, they can tick **Check automatically** in the
Updates box (off by default, since it goes online unasked); an **Update
available** button then appears at the top of the left panel when there is
one. If they ask you to turn it on, `POST /api/update/settings` with
`{"auto_check": true}` while the app is running (send
`Origin: http://127.0.0.1:8000`).

### "Something isn't working"

1. Look before changing anything. The [user guide's known issues](docs/user-guide.md#known-issues)
   and the GitHub issues for this repository list problems already known.
2. On a Mac, the app's output is logged to `~/Library/Logs/LocalReader-Pro.log`.
   On Windows the app runs without a console and keeps no log; ask what the
   screen showed, and check `<userdata>/update.log` for update problems.
3. Do not edit the installed app to fix it. Write a short, plain description
   (what they did, what happened, what they expected, any error text) for
   them to send to the repository's owner.

## Working on the app itself

Changes to the app are made in a separate clone, never in an installed copy,
and reach users as updates.

- **The installed app is a git clone that updates itself.** Editing its files
  makes the updater refuse to update. Running its tools is fine.
- The library and settings live outside the app (the userdata folder), reached
  through the links `dist/userdata` and `dist/app/models`. Never delete through
  those links.
- **Testing:** the UI is hard-coded to port 8000, which the running app holds.
  Start a separate copy on another port from the clone's `dist` folder:
  `python -m uvicorn app.server:app --host 127.0.0.1 --port 8771`, with an
  empty `dist/userdata` of its own, never the real library. The server
  refuses requests from other websites, so test requests need
  `Origin: http://127.0.0.1:<port>`. The tools take `--port` for this.
- The voice engine is not thread-safe: every call into it goes through
  `state.engine_lock`.
- Tests: `tests/test_pronunciations.py`, and
  `installers/tests/check_install.py` for a whole installed copy. Pushing
  installer changes to `main` runs the installers on clean Windows and Mac
  machines (`.github/workflows/installers.yml`).

## Design rules

- When a feature or setting changes, update the user guide and the settings
  reference in the same change, and the user guide's Known issues list when a
  bug is fixed or found. They describe what the app does, not what it should
  do.
- Sleep mode is a separate mode of the Export dialog. Sleep features stay
  inside it, and normal reading and normal MP3 export keep working as they do.
- Everything runs locally. The app goes online only to download the voice
  model and FFmpeg, and to check for updates: when asked, or automatically if
  the user turns that on (off by default). It never installs an update
  without the user's click.
- Scripts and recordings about real people, or for one person, are personal.
  This repository is public: keep them out of it.
- espeak-ng cuts its data path at about 160 bytes, so the installers refuse
  install folders that would make it longer.
- `installers/windows/install.ps1` runs on Windows PowerShell 5.1, which
  strips double quotes from arguments to programs: inside it, inline Python
  uses single quotes.
