"""
Settings > Azure voices: the key and region, the voice list, voice samples and
this month's usage. The voices themselves are in logic/azure_tts.py.
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional

from ..config import (
    azure_settings_file,
    azure_usage_file,
    azure_voices_file,
    azure_samples_dir,
)

# The logic modules are imported as top-level "logic", as the other routers do,
# so pronunciations is one module with one cache.
base_dir_parent = Path(__file__).parent.parent
if str(base_dir_parent) not in sys.path:
    sys.path.append(str(base_dir_parent))
from logic import azure_tts  # noqa: E402
from logic.azure_tts import AzureError  # noqa: E402

router = APIRouter()


class AzureSettingsUpdate(BaseModel):
    # None leaves a field as it is, so the page never has to send the key back.
    key: Optional[str] = None
    region: Optional[str] = None
    voice: Optional[str] = None
    use_for_exports: Optional[bool] = None


def settings() -> dict:
    return azure_tts.load_settings(azure_settings_file)


def _public(s: dict) -> dict:
    """The settings as the page sees them: whether a key is saved, never the key."""
    key = s.get("key", "")
    return {
        "configured": azure_tts.configured(s),
        "key_hint": f"...{key[-4:]}" if len(key) > 8 else "",
        "region": s.get("region", ""),
        "voice": s.get("voice", ""),
        "use_for_exports": s.get("use_for_exports", False),
    }


@router.get("/api/azure/settings")
def get_azure_settings():
    return _public(settings())


@router.post("/api/azure/settings")
def save_azure_settings(update: AzureSettingsUpdate):
    s = settings()
    changed_account = False
    for field, value in update.model_dump(exclude_none=True).items():
        if field in ("key", "region"):
            value = value.strip()
            changed_account |= value != s.get(field)
        s[field] = value
    if s["use_for_exports"] and not azure_tts.configured(s):
        raise HTTPException(status_code=400, detail="Add the key and region before choosing Azure for exports.")
    azure_tts.save_settings(azure_settings_file, s)
    if changed_account:
        # Another resource may be in another region with other voices.
        azure_voices_file.unlink(missing_ok=True)
    return _public(s)


@router.post("/api/azure/test")
def test_azure():
    """Check the saved key and region. Costs no characters."""
    try:
        voices = azure_tts.fetch_voices(settings())
    except AzureError as e:
        raise HTTPException(status_code=400, detail=str(e))
    azure_voices_file.write_text(json.dumps(voices), encoding="utf-8")
    return {"ok": True, "voices": len(voices), "english": len(azure_tts.english(voices))}


@router.get("/api/azure/voices")
def azure_voices(refresh: bool = False):
    """
    The English voices. Fetched from Azure once and kept, since the list
    rarely changes; refresh=true fetches it again.
    """
    if refresh or not azure_voices_file.exists():
        try:
            voices = azure_tts.fetch_voices(settings())
        except AzureError as e:
            raise HTTPException(status_code=400, detail=str(e))
        azure_voices_file.write_text(json.dumps(voices), encoding="utf-8")
    else:
        voices = json.loads(azure_voices_file.read_text(encoding="utf-8"))
    return azure_tts.english(voices)


VOICE_NAME = re.compile(r"[A-Za-z]{2,3}-[A-Za-z]{2,4}-[A-Za-z0-9:]+")


@router.get("/api/azure/sample/{voice}")
def azure_sample(voice: str):
    """
    A short sample of a voice. Made the first time it is asked for (about 150
    characters of the allowance) and kept, so playing it again costs nothing.
    """
    if not VOICE_NAME.fullmatch(voice):
        raise HTTPException(status_code=400, detail="Not a voice name")
    path = azure_samples_dir / f"{voice.replace(':', '_')}.wav"
    if not path.exists():
        try:
            audio = azure_tts.synthesize(
                settings(), azure_tts.SAMPLE_TEXT, voice, 1.0, usage_file=azure_usage_file
            )
        except AzureError as e:
            raise HTTPException(status_code=400, detail=str(e))
        azure_samples_dir.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        sf.write(str(tmp), np.clip(audio, -1, 1), azure_tts.SAMPLE_RATE, format="WAV", subtype="PCM_16")
        tmp.replace(path)
    return FileResponse(path, media_type="audio/wav")


@router.get("/api/azure/usage")
def azure_usage():
    return azure_tts.usage(azure_usage_file)
