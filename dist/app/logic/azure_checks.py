"""
The record that a script's pronunciations were checked by ear in an Azure
voice, before a recording spends the month's allowance on it.

tools/pronunciation_check.py --azure records the script's words in the voice
and notes it here (userdata/azure_checks.json); --approve marks that a person
listened and the words are right. tools/make_sleep_recording.py refuses a full
Azure recording until the exact script, voice and Azure pronunciation list
have an approved check. Any change to one of them means checking again, which
costs a few hundred characters instead of a whole recording.

Agents use these tools; a person exporting from the app's own dialog is not
stopped, but the dialog shows what the export will cost first.
"""
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

try:
    from logic import pronunciations
except ImportError:
    import pronunciations


def script_hash(script: Path) -> str:
    return hashlib.sha256(Path(script).read_bytes()).hexdigest()


def list_hash() -> str:
    """The Azure pronunciation entries in force, built-in and personal."""
    table = pronunciations._table("azure")
    data = json.dumps([sorted(table.words.items()), sorted(table.acronyms.items())], ensure_ascii=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _load(path: Path) -> Dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def record(path: Path, script: Path, voice: str, words: List[str]) -> None:
    checks = _load(path)
    checks[script_hash(script)] = {
        "script": Path(script).name,
        "voice": voice,
        "lists": list_hash(),
        "words": words,
        "recorded": datetime.now().isoformat(timespec="seconds"),
        "approved": None,
    }
    Path(path).write_text(json.dumps(checks, indent=2, ensure_ascii=False), encoding="utf-8")


def approve(path: Path, script: Path) -> Optional[Dict]:
    """Mark the script's latest check as listened to. None if there is none for this exact text."""
    checks = _load(path)
    entry = checks.get(script_hash(script))
    if entry is None:
        return None
    entry["approved"] = datetime.now().isoformat(timespec="seconds")
    Path(path).write_text(json.dumps(checks, indent=2, ensure_ascii=False), encoding="utf-8")
    return entry


def problem(path: Path, script: Path, voice: str) -> Optional[str]:
    """Why this script may not be recorded in this voice yet, or None when it may."""
    entry = _load(path).get(script_hash(script))
    if entry is None:
        return "its pronunciations have not been checked in Azure since it last changed"
    if entry["voice"] != voice:
        return f"it was checked in {entry['voice']}, not {voice}"
    if entry["lists"] != list_hash():
        return "the Azure pronunciation list has changed since the check"
    if not entry["approved"]:
        return "the check was recorded but nobody has confirmed listening to it"
    return None
