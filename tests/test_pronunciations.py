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
models = next((m for m in candidates if (m / "kokoro.int8.onnx").exists()), candidates[0])
model, voices = models / "kokoro.int8.onnx", models / "voices.bin"
if model.exists() and voices.exists():
    from kokoro_onnx import Kokoro

    kokoro = Kokoro(str(model), str(voices))
    pronunciations.install(kokoro)
    samples, rate = kokoro.create(
        "Vagus nerve, diastole, and A T P: the glomerulus filters, and NADH carries electrons.", "af_bella", 1.0, "en-us"
    )
    check("the real engine speaks a sentence full of listed words", len(samples) > rate, f"{len(samples)} samples")
else:
    print("SKIP the real engine (no voice model downloaded)")

print(f"{failures} failure(s)")
sys.exit(1 if failures else 0)
