"""
Check the Azure voice support that works without going online: how
pronunciations are rewritten for Azure, the SSML sent, the character count,
the sentence cache keys, and the pronunciation-check record that
tools/make_sleep_recording.py requires before an Azure recording.

Run with the app's own Python, from anywhere:

    venv/bin/python tests/test_azure.py

Exit code 0 when every check passed. Nothing here contacts Azure.
"""
import json
import sys
import tempfile
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "dist" / "app"
sys.path.insert(0, str(APP))

from logic import azure_checks, azure_tts, pronunciations  # noqa: E402
from logic.sleep_render import SentenceCache  # noqa: E402

failures = 0


def check(name, ok, detail=""):
    global failures
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  [{detail}]"))
    failures += not ok


tmp = Path(tempfile.mkdtemp())
pronunciations.PERSONAL_FILE = tmp / "pronunciations.json"

# --- The engine's sounds, rewritten for Azure -------------------------------

cases = {
    "ɹˈiːnɪn": "ˈɹinɪn",  # stress moves to the syllable start; no length marks
    "lˈɪv": "ˈlɪv",
    "ˌæbstɹˈækt": "ˌæbˈstɹækt",  # the whole onset "stɹ" moves with it
    "əsˌiːɾəmˈɪnəfən": "əˌsitəˈmɪnəfən",  # the flap ɾ becomes t
    "bˈɜːd": "ˈbɝd",  # American r-coloured vowel
    "ˈæktʃuːəl": "ˈæktʃuəl",  # tʃ stays one sound
    "ɡlˈuːkoʊs": "ˈglukoʊs",
    "ˌeɪtˌiːpˈiː": "ˌeɪˌtiˈpi",
}
wrong = {k: pronunciations.azure_ipa(k) for k, v in cases.items() if pronunciations.azure_ipa(k) != v}
check("the engine's sounds are rewritten into Azure's American IPA", not wrong, wrong)
again = {v: pronunciations.azure_ipa(v) for v in cases.values() if pronunciations.azure_ipa(v) != v}
check("rewriting Azure IPA again changes nothing", not again, again)
check("British voices keep length marks", pronunciations.azure_ipa("bˈɜːd", "en-GB") == "ˈbɜːd",
      pronunciations.azure_ipa("bˈɜːd", "en-GB"))

# --- SSML --------------------------------------------------------------------

out = pronunciations.azure_ssml_text('Cells [live](/lˈɪv/) for weeks & "rest" <here>.')
check(
    "a written pronunciation becomes a phoneme tag, and the rest is escaped",
    out == 'Cells <phoneme alphabet="ipa" ph="ˈlɪv">live</phoneme> for weeks &amp; &quot;rest&quot; &lt;here&gt;.',
    out,
)
check(
    "the engine's own list is not sent to Azure",
    "phoneme" not in pronunciations.azure_ssml_text("The renin and the glomerulus."),
)
pronunciations.PERSONAL_FILE.write_text(
    json.dumps({"azure": {"words": {"renin": "ˈɹinɪn"}, "acronyms": {"ATP": "ˌeɪˌtiˈpi"}}}), encoding="utf-8"
)
out = pronunciations.azure_ssml_text("Renin's role, and ATP but not atp.")
check(
    "an Azure list entry is sent as written, possessive and capitals kept, acronyms case-sensitive",
    out == '<phoneme alphabet="ipa" ph="ˈɹinɪnz">Renin\'s</phoneme> role, and '
           '<phoneme alphabet="ipa" ph="ˌeɪˌtiˈpi">ATP</phoneme> but not atp.',
    out,
)
check("lookup() reads the Azure section separately", pronunciations.lookup("renin", "azure") == "ˈɹinɪn"
      and pronunciations.lookup("renin") != "ˈɹinɪn")
ssml = azure_tts.ssml("Hello there.", "en-GB-SoniaNeural", 0.9)
check(
    "speed becomes a prosody rate, and the voice's language is used",
    'xml:lang="en-GB"' in ssml and 'rate="-10%"' in ssml and '<voice name="en-GB-SoniaNeural">' in ssml,
    ssml,
)
check("speed 1 is rate +0%", 'rate="+0%"' in azure_tts.ssml("Hi.", "en-US-AvaMultilingualNeural", 1.0))
check(
    "the character count is the text as read plus the sounds Azure is given",
    azure_tts.billed_characters("Renin rises.") == len("Renin rises.") + len("ˈɹinɪn"),
    azure_tts.billed_characters("Renin rises."),
)

# --- Sentence cache ------------------------------------------------------------

kokoro = SentenceCache(tmp, ["model.onnx", "af_heart", 0.9, "en-us"])
azure = SentenceCache(tmp, ["azure", "en-US-AvaMultilingualNeural", 0.9], section="azure")
check("Azure and Kokoro sentences never share a cache entry", kokoro.path("Renin rises.") != azure.path("Renin rises."))
before = azure.path("Renin rises.")
pronunciations.PERSONAL_FILE.write_text(json.dumps({"azure": {"words": {"renin": "ˈɹɛnɪn"}}}), encoding="utf-8")
check("changing an Azure entry makes the sentences that use it new", azure.path("Renin rises.") != before)
check("and leaves the others alone", azure.path("The kidney rests.") == SentenceCache(
    tmp, ["azure", "en-US-AvaMultilingualNeural", 0.9], section="azure").path("The kidney rests."))

# --- The check a recording requires -------------------------------------------

checks = tmp / "azure_checks.json"
script = tmp / "script.txt"
script.write_text("Renin rises.\n", encoding="utf-8")
voice = "en-US-AvaMultilingualNeural"
check("no check: refused", azure_checks.problem(checks, script, voice) is not None)
azure_checks.record(checks, script, voice, ["renin"])
check("recorded but not approved: refused", "nobody has confirmed" in (azure_checks.problem(checks, script, voice) or ""))
azure_checks.approve(checks, script)
check("approved: allowed", azure_checks.problem(checks, script, voice) is None)
check("another voice: refused", azure_checks.problem(checks, script, "en-GB-SoniaNeural") is not None)
pronunciations.PERSONAL_FILE.write_text(json.dumps({"azure": {"words": {"renin": "ˈɹinɪn"}}}), encoding="utf-8")
check("Azure list changed since: refused", "list has changed" in (azure_checks.problem(checks, script, voice) or ""))
azure_checks.record(checks, script, voice, ["renin"])
azure_checks.approve(checks, script)
script.write_text("Renin rises slowly.\n", encoding="utf-8")
check("script edited since: refused", azure_checks.problem(checks, script, voice) is not None)
check("approving an edited script without a new check does nothing", azure_checks.approve(checks, script) is None)

# --- Settings -------------------------------------------------------------------

settings_file = tmp / "azure.json"
check("no settings file: not configured", not azure_tts.configured(azure_tts.load_settings(settings_file)))
azure_tts.save_settings(settings_file, {"key": "k" * 32, "region": "eastus", "voice": voice, "use_for_exports": True})
check("saved settings read back", azure_tts.load_settings(settings_file)["region"] == "eastus")
if sys.platform != "win32":
    check("only this user can read the key", settings_file.stat().st_mode & 0o077 == 0, oct(settings_file.stat().st_mode))
try:
    azure_tts._host("east us; rm")
    check("a region name with odd characters is refused", False)
except azure_tts.AzureError:
    check("a region name with odd characters is refused", True)

print(f"{failures} failure(s)")
sys.exit(1 if failures else 0)
