"""
Merge a personal pronunciation list into the app's built-in one.

A user's fixes start in their personal list (userdata/pronunciations.json), so
they work at once without changing the app. Once checked by ear, they belong in
the built-in list (dist/app/logic/pronunciations.json), which ships with the
app to everyone. This copies them across, in a clone of the repository that
will be committed:

    venv/bin/python tools/promote_pronunciations.py path/to/their/pronunciations.json

New words are added, changed words are updated, and an empty entry (a user
switching a built-in word off) removes it, in the engine's lists and in the
"azure" section alike. It prints every change, so it can
be reviewed before committing. Run tests/test_pronunciations.py afterwards.
The personal file is left as it is; once the user updates the app, its entries
are redundant and can be cleared.
"""
import json
import sys
from pathlib import Path

# On Windows, Python writes to a pipe in the old code page (usually
# Windows-1252), which has none of the phonetic symbols printed here: an
# agent would get a crash after the list was already written, with no record
# of what changed.
sys.stdout.reconfigure(encoding="utf-8")

BUILTIN = Path(__file__).resolve().parent.parent / "dist" / "app" / "logic" / "pronunciations.json"

if len(sys.argv) != 2:
    sys.exit(__doc__)

personal = json.loads(Path(sys.argv[1]).expanduser().read_text(encoding="utf-8"))
data = json.loads(BUILTIN.read_text(encoding="utf-8"))

changes = []
# The engine's lists at the top level, and Azure's in their own "azure"
# section (logic/pronunciations.py), each merged the same way.
for where, theirs, ours in (("", personal, data), ("azure ", personal.get("azure", {}), data.setdefault("azure", {}))):
    for section, fold in (("words", str.lower), ("acronyms", str)):
        built_in = ours.setdefault(section, {})
        for raw, ipa in theirs.get(section, {}).items():
            key = fold(raw)
            old = built_in.get(key)
            if not ipa:
                if old is not None:
                    del built_in[key]
                    changes.append(f"removed  {where}{key}  (was {old})")
            elif old != ipa:
                built_in[key] = ipa
                changes.append(f"{'changed' if old else 'added'}  {where}{key}  {ipa}" + (f"  (was {old})" if old else ""))
        ours[section] = dict(sorted(built_in.items()))

if not changes:
    print("Nothing to merge: the built-in list already has every entry.")
    sys.exit(0)
BUILTIN.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("\n".join(changes))
print(f"{len(changes)} change(s) written to {BUILTIN}")
