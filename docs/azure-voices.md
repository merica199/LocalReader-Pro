# Azure voices

LocalReader Pro's own voice (Kokoro) runs on your computer and costs nothing.
Microsoft Azure's neural voices sound more natural: steadier, with emphasis
that follows the meaning of the sentence. The app can use one of them for
**exports**: normal MP3s and sleep recordings. Reading aloud in the app always
uses the voice on your computer.

This page is for anyone setting it up, and for an AI agent (Claude) helping
them. Every setting is also in the
[settings reference](settings-reference.md#azure-voices), and every English
voice is in the [voice list](azure-voice-list.md).

## Contents

- [What changes when you use it](#what-changes-when-you-use-it)
- [Setting it up](#setting-it-up)
- [Gotchas](#gotchas)
- [Choosing a voice](#choosing-a-voice)
- [Making an export](#making-an-export)
- [Pronunciation](#pronunciation)
- [For agents: recording a script in an Azure voice](#for-agents-recording-a-script-in-an-azure-voice)
- [Your files](#your-files)
- [Turning it off](#turning-it-off)
- [When something goes wrong](#when-something-goes-wrong)
- [How it works](#how-it-works)

## What changes when you use it

- **The text of each export is sent to Azure**, one sentence at a time, under
  your own Azure Speech resource. Microsoft's terms for that resource apply.
  Nothing else leaves the computer: not your library, not other documents.
- **It has a monthly allowance.** Azure's free tier gives 500,000 characters a
  month, about eight 90-minute sleep recordings. Past that, Azure refuses
  further requests until the 1st of the next month; it does not start charging
  you.
- **It takes about as long as the local voice.** The free tier answers 20
  requests a minute, one per sentence, so a 90-minute sleep recording (about
  900 sentences) takes roughly 45 minutes. A paid resource is much faster.
- **It needs the internet** for the whole export.

## Setting it up

You need an Azure account with a subscription (a free or student account
works), and about ten minutes.

1. In the Azure portal, **create a Speech resource** (Azure AI services,
   "Speech service") on the **Free F0** pricing tier, in any region your
   subscription allows. The region decides which voices you get; the app
   shows the ones yours offers.
2. On the resource's **Keys and Endpoint** page, copy **Key 1** and the
   **Location/Region** (a short name such as `eastus` or `northcentralus`).
3. In LocalReader Pro, open **Settings > Azure voices**, paste the key and the
   region, and click **Save and test**. It confirms the connection and loads
   the voices (this costs nothing).
4. Pick a voice, play its sample, and tick **Use this voice for exports**.

An agent with the Azure CLI (command-line tool) signed in can do steps 1 and
2 with `az cognitiveservices account create --kind SpeechServices --sku F0`
and `az cognitiveservices account keys list`. Creating the resource is a
change in the person's Azure account: ask them first. Never paste the key into
a chat, a file in this repository, or anywhere but the Settings page or the
settings file (see [Your files](#your-files)).

## Gotchas

These came up in real setups:

- **"Resource was disallowed by Azure" when creating the resource.** Some
  subscriptions, including **Azure for Students**, only allow certain regions
  (an Azure Policy assignment called "Allowed resource deployment regions").
  Pick another region and try again. To see the allowed list:
  `az policy assignment list --query "[].parameters"`. One student
  subscription allowed only westus2, westus3, southcentralus, northcentralus
  and mexicocentral.
- **A second free resource may be refused.** If Azure will not create another
  Free F0 Speech resource in the same subscription, reuse the one you have.
- **The key and the region go together.** A key from a resource in one region
  is refused in another. "Azure refused the key" almost always means the
  region is wrong, or the key was copied with a character missing.
- **The app's character count covers this computer only.** Azure does not let
  a key holder ask how much of the month is used, so the app counts what it
  sends. If the same key is used on two computers, each counts only its own.
  The Azure portal (the resource's **Metrics**, "Synthesized Characters")
  shows the real total.
- **Signing in to the Azure CLI on a computer that also has a work account.**
  Use a separate CLI profile so the two never mix: set `AZURE_CONFIG_DIR` to
  another folder (for example `~/.azure-personal`) for the personal account's
  commands. If the device-code sign-in shows "success" in the browser but the
  command keeps waiting, stop it and run it again.
- **HD voices** (marked HD in the list) worked on the free tier when this was
  written (October 2026).

## Choosing a voice

**Settings > Azure voices** lists every English voice your region offers,
grouped by accent, with a line under the picker saying what kind of voice it
is. The play button plays a short sample: the first time, Azure makes it
(about 150 characters of the allowance) and the app keeps it, so playing it
again is instant and free. **Refresh the voice list** fetches the list again;
Azure adds voices from time to time.

Good places to start for sleep recordings: **Ava Multilingual** and **Emma
Multilingual** (American), **Andrew Multilingual** (American, male), and
**Sonia** (British). The full list is in [azure-voice-list.md](azure-voice-list.md).

## Making an export

Open a document and click **Export Audio**. The **Voice** menu at the top of
the dialog chooses between the voice on this computer and your Azure voice;
it starts on whichever **Use this voice for exports** says, and changing it
there changes that setting too. Everything else works as usual:
[normal export](user-guide.md#7-exporting-audio),
[sleep mode](user-guide.md#8-sleep-recordings), preview, pauses, background
sound, resuming after a stop.

Before you start, the estimate line says how many characters the export will
send to Azure and how many this computer has used this month. Sentences
already made for an earlier version are reused and cost nothing, so
re-recording after editing a few sentences only pays for those.

## Pronunciation

Azure voices know far more words than the local voice, including most medical
and scientific terms, so the app lets them read in their own way:

- **The app's built-in science pronunciations are not used for Azure.** They
  exist to correct the local voice's guesses, and Azure's own readings are
  usually right.
- **Words written with their sounds** in a script, `[live](/lˈɪv/)`, are used:
  the app rewrites the sounds into the form Azure takes. Use them for words
  spelled the same but said two ways (see
  [Words said two ways](user-guide.md#words-said-two-ways)).
- **When Azure says a word wrong,** add it to the `azure` section of your
  personal pronunciation list (`userdata/pronunciations.json`):

  ```json
  {
    "words": { "renin": "ɹˈiːnɪn" },
    "azure": {
      "words": { "purkinje": "pɚˈkɪndʒi" },
      "acronyms": {}
    }
  }
  ```

  Azure entries are written in Azure's IPA (International Phonetic Alphabet)
  for the voice's language, which differs from the local voice's style: the
  stress mark goes at the start of the stressed syllable, and American English
  has no length marks (`i`, not `iː`). Microsoft's table of sounds is
  "SSML phonetic alphabets" on learn.microsoft.com. The entries outside the
  `azure` section are for the local voice and are untouched.
- **You cannot fix pronunciation by ear without listening.** Before a long
  recording, record the script's hard words in the voice and listen (the next
  section). The free allowance makes this matter: a whole recording with a
  wrong word costs far more than checking first.

## For agents: recording a script in an Azure voice

When a person asks for a sleep recording and Azure voices are chosen for
exports, the order is fixed, and the tools enforce the last step:

1. **Write and time the script** as usual. `tools/estimate_sleep_script.py`
   uses Azure's pace when Azure is chosen, and prints the characters the
   recording will use and how long the free tier takes to make it. Make sure
   it fits what is left of the month.
2. **Mark every word spelled the same but said two ways.** Run
   `tools/check_heteronyms.py`; for every word it lists, write the intended
   reading into the script as `[word](/sounds/)`, even where the local voice's
   reading is right. You cannot hear how Azure reads them, so do not leave
   them to it.
3. **Check the technical words in the Azure voice:**

   ```bash
   python tools/pronunciation_check.py --azure --script "<script.txt>" <every technical word> --out "<Desktop>"
   ```

   It records the words you name, plus every word in the script that is on a
   pronunciation list or written with its sounds, in the chosen Azure voice,
   and writes a list of each word's time. It costs a few characters per word.
   Then ask the person to listen, exactly as for the local voice. Fix each
   wrong word in the `azure` section of their personal list (or, for a word
   said two ways, in the script), and run the check again.
4. **When the person says every word is right:**

   ```bash
   python tools/pronunciation_check.py --approve "<script.txt>"
   ```

5. **Record it:** `python tools/make_sleep_recording.py "<script.txt>" --copy-to "<scripts folder>"`.
   It refuses a full Azure recording until this exact script, voice and Azure
   pronunciation list have an approved check, and says what is missing. Any
   change to the script after approval means checking again (a few hundred
   characters, not a whole recording). `--preview` makes the first minute
   without a check; `--kokoro` records in the local voice instead.

## Your files

All in the app's userdata folder (see
[Where your files are](user-guide.md#11-where-your-files-are)), never in the
app's own folder, so updates keep them:

| File | What it holds |
|---|---|
| `azure.json` | The key, region, chosen voice, and whether exports use it. Only your user account can read it. |
| `azure_voices.json` | The voice list as Azure last sent it. |
| `azure_usage.json` | Characters sent from this computer, per month. |
| `azure_checks.json` | The scripts whose pronunciations were checked, and which were approved. |
| `voice_previews/azure/` | The voice samples, one per voice played. Safe to delete; they are made again when played. |

## Turning it off

Untick **Use this voice for exports**, or choose the local voice in the Export
dialog. To stop using Azure altogether, delete the Speech resource in the
Azure portal (its key stops working at once) and delete `azure.json`.

## When something goes wrong

| What you see | What it means |
|---|---|
| Azure refused the key | The key or the region is wrong; copy both again from Keys and Endpoint. |
| Azure refused the request (403) | Usually the month's free characters are used up. They come back on the 1st; sentences already made are kept, so exporting again then finishes the recording. |
| Azure could not read the request (400) | Usually a written pronunciation uses a sound Azure does not know. Check the `[word](/sounds/)` markup and the `azure` entries. |
| Could not reach Azure | No internet, or Azure is down. Nothing is lost; export again later. |
| Azure kept answering "too many requests" | Azure is busy. The app already waits and retries; try again later. |

## How it works

For anyone changing the app: `dist/app/logic/azure_tts.py` sends each sentence
as SSML (Speech Synthesis Markup Language) to the region's text-to-speech
endpoint with the key, and gets back raw 24 kHz audio, the same rate as the
local voice, so pauses, leveling, the sentence cache and sleep finishing work
unchanged. Speed becomes an SSML prosody rate. It paces itself to the free
tier's 20 requests a minute once Azure first answers "too many requests", and
retries busy or failed requests. `dist/app/routers/azure.py` serves the
settings page; `logic/pronunciations.py` turns written pronunciations and the
`azure` entries into SSML `<phoneme>` tags (`azure_ipa`, `azure_ssml_text`);
`logic/azure_checks.py` keeps the record the recording tool requires. The
sentence cache keys Azure sentences by voice, speed and the Azure entries they
use, apart from the local voice's. Tests: `tests/test_azure.py` (offline).
