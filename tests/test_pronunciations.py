"""
Check the built-in science pronunciations (dist/app/logic/pronunciations.py).

Run with the app's own Python, from anywhere:

    venv/bin/python tests/test_pronunciations.py

It checks that every entry uses only sounds the voice model knows, that the
entries are put into the engine's output in the right places (and nowhere
else), and, when the voice model is downloaded, that the engine speaks a
sentence full of them. Exit code 0 when every check passed.
"""
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "dist" / "app"
sys.path.insert(0, str(APP))

from kokoro_onnx.tokenizer import Tokenizer  # noqa: E402
from logic import pronunciations  # noqa: E402
from logic.pronunciations import ACRONYMS, WORDS, phonemize_with  # noqa: E402
from logic.text_normalizer import apply_custom_pronunciations  # noqa: E402

# Never read a real personal list: every check below is about the built-in one
# unless it says otherwise.
pronunciations.PERSONAL_FILE = Path(__file__).parent / "no-personal-list.json"

failures = 0


def check(name, ok, detail=""):
    global failures
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  [{detail}]"))
    failures += not ok


tokenizer = Tokenizer()
plain = tokenizer.phonemize


def spoken(text, lang="en-us"):
    return phonemize_with(plain, text, lang)


# Every entry must survive tokenizing whole: a sound the model has no token for
# is silently dropped, and the word comes out with a piece missing.
unknown = {
    word: sorted(set(ipa) - set(tokenizer.vocab) - {" "})
    for word, ipa in {**WORDS, **ACRONYMS}.items()
    if set(ipa) - set(tokenizer.vocab) - {" "}
}
check(f"all {len(WORDS) + len(ACRONYMS)} entries use only sounds the voice model knows", not unknown, unknown)

stressless = [w for w, ipa in {**WORDS, **ACRONYMS}.items() if "ˈ" not in ipa]
check("every entry marks its stressed syllable", not stressless, stressless)

# Each listed word, alone and mid-sentence, comes out as its entry.
wrong = []
for word, ipa in WORDS.items():
    if spoken(word) != ipa:
        wrong.append(word)
    if ipa not in spoken(f"Look at the {word} again."):
        wrong.append(f"{word} mid-sentence")
for word, ipa in ACRONYMS.items():
    if spoken(f"It makes {word} slowly.") .find(ipa) < 0:
        wrong.append(word)
check("every entry replaces the engine's guess, alone and mid-sentence", not wrong, wrong[:10])

check(
    "a sentence with no listed words is exactly what the engine says on its own",
    spoken("The heart is about the size of a closed fist.") == plain("The heart is about the size of a closed fist."),
)

out = spoken("Blood flows into the glomerulus, a tuft of capillaries.")
check(
    "punctuation after a listed word stays attached to it",
    WORDS["glomerulus"] + "," in out and " ," not in out,
    out,
)

check("capitalized words match too", WORDS["diastole"] in spoken("Diastole is the resting phase."))
check(
    "acronyms match only as written",
    ACRONYMS["AMP"] in spoken("It makes AMP.") and spoken("Turn up the amp.") == plain("Turn up the amp."),
)
check("possessives get their s sound", WORDS["henle"] + "z" in spoken("the loop of Henle's tubule"))
check(
    "a listed word inside a longer word is left alone",
    spoken("the epidermis") == plain("the epidermis"),
    spoken("the epidermis"),
)
check("other languages are untouched", spoken("le vagus", "fr-fr") == plain("le vagus", "fr-fr"))

# The user's own rules run on the text first, so their respelling wins.
rules = [{"original": "diastole", "replacement": "dye ass toe lee", "match_case": False, "word_boundary": True}]
check(
    "a user's own rule for a word wins over the built-in entry",
    WORDS["diastole"] not in spoken(apply_custom_pronunciations("Diastole begins.", rules, [])),
)


# Saved audio is keyed on the entries a sentence uses, so changing one entry
# regenerates only the sentences that say that word.
check(
    "used() names exactly the entries a text uses",
    pronunciations.used("The vagus nerve, ATP, atp, and the heart.")
    == [["ATP", ACRONYMS["ATP"]], ["vagus", WORDS["vagus"]]],
    pronunciations.used("The vagus nerve, ATP, atp, and the heart."),
)

import hashlib  # noqa: E402
import json  # noqa: E402
import tempfile  # noqa: E402

from logic.sleep_render import SentenceCache  # noqa: E402

cache = SentenceCache(Path(tempfile.gettempdir()), ["model", "voice", 0.9, "en-us"])


def old_key(text):
    return hashlib.sha1(json.dumps([cache.signature, text]).encode("utf-8")).hexdigest()


check(
    "a saved sleep sentence with no listed words keeps the key it had before the list existed",
    cache.path("The heart is about the size of a fist.").stem == old_key("The heart is about the size of a fist."),
)
check(
    "a saved sleep sentence with a listed word gets a new key",
    cache.path("The vagus nerve slows it.").stem != old_key("The vagus nerve slows it."),
)


# The personal list in userdata wins over the built-in one, can switch an entry
# off, is picked up as soon as it changes, and a broken one is ignored.
personal = Path(tempfile.mkdtemp()) / "pronunciations.json"
pronunciations.PERSONAL_FILE = personal
personal.write_text(json.dumps({"words": {"diastole": "dˈaɪəstˌoʊl", "kreb": "kɹˈɛb"}, "acronyms": {"ATP": ""}}), encoding="utf-8")
check("a personal entry wins over the built-in one", spoken("diastole") == "dˈaɪəstˌoʊl", spoken("diastole"))
check("a personal entry adds a new word", pronunciations.lookup("Kreb") == "kɹˈɛb")
check("an empty personal entry switches a built-in one off", spoken("ATP") == plain("ATP"), spoken("ATP"))
personal.write_text(json.dumps({"words": {"diastole": "dˈaɪəstˌoʊliː"}}), encoding="utf-8")
check("an edited personal list is picked up without restarting", spoken("diastole") == "dˈaɪəstˌoʊliː", spoken("diastole"))
personal.write_text("{ not json", encoding="utf-8")
check("a broken personal list is ignored, not fatal", spoken("diastole") == WORDS["diastole"], spoken("diastole"))
personal.unlink()
check("with no personal list, the built-in one applies", spoken("ATP") == ACRONYMS["ATP"])


# A pronunciation written into the text, [word](/sounds/), for words spelled
# the same but said two ways.
from logic.pronunciations import plain as shown_as  # noqa: E402
from logic.sleep_script import Pacing, estimate_seconds, plan_text  # noqa: E402

out = spoken("Red blood cells [live](/lˈɪv/) for about four months.")
check(
    "a written pronunciation replaces the engine's guess",
    "lˈɪv" in out and "lˈaɪv" not in out and "[" not in out,
    out,
)
check(
    "without one, the engine guesses this live wrong (why the markup exists)",
    "lˈaɪv" in spoken("Red blood cells live for about four months."),
)
out = spoken("The [vagus](/vˈɑːɡəs/) nerve.")
check("a written pronunciation wins over a list entry", "vˈɑːɡəs" in out and WORDS["vagus"] not in out, out)
out = spoken("Cells [live](/lˈɪv/), then die.")
check("punctuation after a written pronunciation stays attached to it", "lˈɪv," in out and " ," not in out, out)
check(
    "it is displayed and counted as just the word",
    shown_as("Cells [live](/lˈɪv/) and [Lead](/lˈɛd/).") == "Cells live and Lead.",
)
check(
    "another language reads the plain word, not the markup",
    spoken("le [live](/lˈɪv/)", "fr-fr") == plain("le live", "fr-fr"),
)
check(
    "markup with a space inside is left alone",
    spoken("[live](/l ɪv/)") == plain("[live](/l ɪv/)"),
)
check("used() leaves written pronunciations out of cache keys", pronunciations.used("[vagus](/vˈɑːɡəs/)") == [])

events = plan_text("Cells [live](/lˈɪv/) for weeks (about four), [then](/ðˈɛn/) die.\n\nPlatelets [live](/lˈɪv/).")
said = [v for k, v in events if k == "say"]
check(
    "a sleep recording keeps written pronunciations while its brackets become pauses",
    said == ["Cells [live](/lˈɪv/) for weeks, about four, [then](/ðˈɛn/) die.", "Platelets [live](/lˈɪv/)."],
    said,
)
check(
    "a sleep recording's length counts a written pronunciation as its word",
    estimate_seconds(plan_text("Cells [live](/lˈɪv/) long."), Pacing(), 18.0)
    == estimate_seconds(plan_text("Cells live long."), Pacing(), 18.0),
)

# The heteronym list behind tools/check_heteronyms.py, and the tool itself.
TOOLS = APP.parent.parent / "tools"
heteronyms = {
    w: r
    for w, r in json.loads((TOOLS / "heteronyms.json").read_text(encoding="utf-8")).items()
    if not w.startswith("_")
}
bad = {
    w: sorted(set(r["sounds"]) - set(tokenizer.vocab))
    for w, readings in heteronyms.items()
    for r in readings
    if set(r["sounds"]) - set(tokenizer.vocab)
}
check(f"all {len(heteronyms)} heteronyms' readings use only sounds the voice model knows", not bad, bad)
check(
    "every heteronym has two different readings, each with its stress marked",
    all(
        len(r) >= 2 and len({x["sounds"] for x in r}) == len(r) and all("ˈ" in x["sounds"] for x in r)
        for r in heteronyms.values()
    ),
)

import subprocess  # noqa: E402

script = Path(tempfile.mkdtemp()) / "script.txt"
script.write_text(
    "# How cells live is a comment.\n"
    "Red blood cells live for about four months. These cells live in the marrow.\n\n"
    "The red cells read it. Platelets [live](/lˈɪv/) ten days, and lead poisoning hurts.\n",
    encoding="utf-8",
)
run = subprocess.run([sys.executable, str(TOOLS / "check_heteronyms.py"), str(script)], capture_output=True, text=True)
report = run.stdout
check(
    "the heteronym check reports each reading the voice will use, with its line",
    run.returncode == 0
    and "line 2  live: the voice says lˈaɪv" in report
    and "line 2  live: the voice says lˈɪv" in report
    and "line 4  read: the voice says ɹˈiːd" in report
    and "line 4  live: written [live](/lˈɪv/)" in report
    and "line 4  lead: the voice says lˈiːd" in report
    and "write [lead](/lˈɛd/)" in report
    and "5 heteronyms, 1 written out, 4 left to the voice" in report,
    report or run.stderr,
)
script.write_text("Cells [live](/lˈɪvж/) long, and [live](lɪv) too.\n", encoding="utf-8")
run = subprocess.run([sys.executable, str(TOOLS / "check_heteronyms.py"), str(script)], capture_output=True, text=True)
check(
    "the heteronym check fails on sounds the model lacks and on broken markup",
    run.returncode == 1 and "does not have: ж" in run.stdout and "is not read as a pronunciation" in run.stdout,
    run.stdout or run.stderr,
)


class FakeEngine:
    tokenizer = Tokenizer()


engine = FakeEngine()
pronunciations.install(engine)
pronunciations.install(engine)
check(
    "installing twice wraps the engine once",
    engine.tokenizer.phonemize("vagus") == WORDS["vagus"]
    and engine.tokenizer._phonemize_without_pronunciations("vagus") == plain("vagus"),
)

# End to end with the real model, when it is downloaded: inside the app, or in
# the data folder a Mac or Windows install keeps it in.
candidates = [
    APP / "models",
    Path.home() / "Library" / "Application Support" / "LocalReader Pro" / "models",
    Path.home() / "AppData" / "Roaming" / "LocalReader Pro" / "models",
]
# Either model will do; an Intel or AMD install may have only kokoro.onnx.
model = next(
    (m / name for m in candidates for name in ("kokoro.int8.onnx", "kokoro.onnx") if (m / name).exists()),
    candidates[0] / "kokoro.int8.onnx",
)
voices = model.parent / "voices.bin"
if model.exists() and voices.exists():
    from kokoro_onnx import Kokoro

    kokoro = Kokoro(str(model), str(voices))
    pronunciations.install(kokoro)
    samples, rate = kokoro.create(
        "Vagus nerve, diastole, and A T P: the glomerulus filters, and NADH carries electrons.", "af_bella", 1.0, "en-us"
    )
    check("the real engine speaks a sentence full of listed words", len(samples) > rate, f"{len(samples)} samples")
    samples, rate = kokoro.create("Red blood cells [live](/lˈɪv/) for about four months.", "af_bella", 1.0, "en-us")
    check("the real engine speaks a sentence with a written pronunciation", len(samples) > rate, f"{len(samples)} samples")
else:
    print("SKIP the real engine (no voice model downloaded)")

print(f"{failures} failure(s)")
sys.exit(1 if failures else 0)
