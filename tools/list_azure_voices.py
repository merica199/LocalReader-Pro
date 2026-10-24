"""
Write docs/azure-voice-list.md: every English Azure voice, from Azure itself.

Run with the app's own Python, with Azure voices set up (Settings > Azure
voices), in a clone of the repository:

    venv/bin/python tools/list_azure_voices.py

Listing voices is free (no characters). The list is the one for the region in
the saved settings; most regions offer the same English voices, but not all.
"""
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "dist" / "app"
sys.path.insert(0, str(APP))

from logic import azure_tts  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
settings = azure_tts.load_settings(APP.parent / "userdata" / "azure.json")
if not azure_tts.configured(settings):
    sys.exit("Azure voices are not set up: add the key and region in Settings > Azure voices.")
voices = azure_tts.english(azure_tts.fetch_voices(settings))

rows = []
for v in voices:
    notes = []
    if v.get("VoiceType") == "NeuralHD":
        notes.append("HD")
    if "Multilingual" in v["ShortName"]:
        notes.append("multilingual")
    if v.get("StyleList"):
        notes.append("styles: " + ", ".join(v["StyleList"]))
    rows.append(f"| {v['DisplayName']} | `{v['ShortName']}` | {v.get('Gender', '')} | {'; '.join(notes)} |")

by_accent = {}
for v in voices:
    by_accent.setdefault(v["LocaleName"], []).append(v)

out = [
    "# Azure voices: the English list",
    "",
    f"Every English voice Azure offered in the {settings['region']} region on {date.today():%B %-d, %Y}: "
    f"{len(voices)} voices. Written by `tools/list_azure_voices.py`; run it again to refresh. "
    "The app's own voice picker (Settings > Azure voices) always shows the current list for your region, "
    "with a sample of each.",
    "",
    "How to read it:",
    "",
    "- **Name** is what to pick in the app; the code next to it is the voice's full name, which the "
    "tools and the settings file use.",
    "- **Multilingual** voices also speak other languages, and are among Azure's newest and most natural.",
    "- **HD** voices are Azure's highest-quality ones. They worked on the free tier when this was written.",
    "- **Styles** are speaking styles a voice offers (for example whispering). The app does not use them yet.",
    "",
    "Setting up and choosing a voice: [Azure voices](azure-voices.md).",
    "",
    "## Contents",
    "",
]
for accent, vs in by_accent.items():
    anchor = accent.lower().replace(" ", "-").replace("(", "").replace(")", "")
    out.append(f"- [{accent}](#{anchor}) ({len(vs)})")
for accent, vs in by_accent.items():
    out += ["", f"## {accent}", "", "| Name | Full name | Gender | Notes |", "|---|---|---|---|"]
    for v in vs:
        out.append(rows[voices.index(v)])
out.append("")
path = ROOT / "docs" / "azure-voice-list.md"
path.write_text("\n".join(out), encoding="utf-8")
print(f"{len(voices)} English voices written to {path}")
