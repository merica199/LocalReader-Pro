"""
Azure neural voices, for exports.

Kokoro runs on this computer and costs nothing; Azure's voices sound more
natural but run in Microsoft's cloud, under the user's own Azure Speech
resource. So they are used only where the wait is fine: MP3 exports and sleep
recordings. Reading aloud in the app always uses Kokoro.

Each request sends one sentence (or one paragraph, for a normal export) as
SSML and gets back raw 24 kHz, 16-bit mono samples, the same rate Kokoro
makes, so the rest of the export (pauses, leveling, the sentence cache,
finishing) does not know which voice made them.

Everything here is plain HTTPS with the resource's key, which the user enters
in Settings > Azure voices and which is kept in userdata/azure.json, never in
the app's own files.

Limits to know (learn.microsoft.com, "Speech service quotas and limits"):

- The free tier (F0) allows 20 requests a minute, and the free allowance is
  500,000 characters a month; past it, requests are refused until the next
  month, never charged. A paid resource (S0) allows 30 a second.
- A key holder cannot ask Azure how much of the month is used, so the app
  counts what it sends from this computer (userdata/azure_usage.json).

The pacer starts at full speed and, on the first "too many requests" answer,
holds to the free tier's 20 a minute for the rest of the session, so it suits
either tier without being told which.
"""
import json
import os
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional

import numpy as np
import requests

try:
    from logic import pronunciations
except ImportError:
    import pronunciations

SAMPLE_RATE = 24000
OUTPUT_FORMAT = "raw-24khz-16bit-mono-pcm"
FREE_CHARACTERS_PER_MONTH = 500_000
FREE_REQUESTS_PER_MINUTE = 20
# Measured October 2026 on eight sentences of sample-scripts/skin-histology.txt
# at rate 0%, silence trimmed: Ava 16.0, Emma 17.7, Andrew 14.9, Sonia 16.1
# (Multilingual voices but Sonia). Kokoro's figure is in sleep_render.
CHARS_PER_SECOND_AT_1X = 16.0
AGENT = "LocalReader-Pro"


class AzureError(Exception):
    """A problem worth showing the user as it is."""


# --- Settings ----------------------------------------------------------------


def load_settings(path: Path) -> Dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    return {
        "key": data.get("key", ""),
        "region": data.get("region", ""),
        "voice": data.get("voice", "en-US-AvaMultilingualNeural"),
        # Whether exports use Azure instead of the Kokoro voice.
        "use_for_exports": bool(data.get("use_for_exports", False)),
    }


def save_settings(path: Path, settings: Dict) -> None:
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    os.replace(tmp, path)
    try:
        # Only this user may read the key (no effect on Windows).
        os.chmod(path, 0o600)
    except OSError:
        pass


def configured(settings: Dict) -> bool:
    return bool(settings.get("key") and settings.get("region"))


def _host(region: str) -> str:
    region = region.strip().lower().replace(" ", "")
    if not region.isalnum():
        raise AzureError(f"'{region}' is not an Azure region name (it looks like eastus or westus2)")
    return f"https://{region}.tts.speech.microsoft.com"


# --- Usage -------------------------------------------------------------------

_usage_lock = threading.Lock()


def month() -> str:
    return datetime.now().strftime("%Y-%m")


def usage(path: Path) -> Dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    return {
        "month": month(),
        "characters": int(data.get(month(), 0)),
        "free_allowance": FREE_CHARACTERS_PER_MONTH,
    }


def _count(path: Optional[Path], characters: int) -> None:
    if not path or characters <= 0:
        return
    with _usage_lock:
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        data[month()] = int(data.get(month(), 0)) + characters
        Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")


def billed_characters(text: str) -> int:
    """
    About what Azure counts for a piece of text: its characters as read, plus
    the sounds of each <phoneme> tag, which Azure bills too.
    """
    count = len(pronunciations.plain(text))
    for ipa_word in pronunciations.used(text, "azure"):
        count += len(ipa_word[1])
    return count


# --- Pacing ------------------------------------------------------------------


class _Pacer:
    """Holds requests to the free tier's rate once Azure has asked for it."""

    def __init__(self):
        self.lock = threading.Lock()
        self.sent: deque = deque()
        self.limited = False

    def wait(self) -> None:
        with self.lock:
            if self.limited:
                while len(self.sent) >= FREE_REQUESTS_PER_MINUTE:
                    wait = 60.5 - (time.monotonic() - self.sent[0])
                    if wait <= 0:
                        self.sent.popleft()
                    else:
                        time.sleep(wait)
            self.sent.append(time.monotonic())
            while len(self.sent) > FREE_REQUESTS_PER_MINUTE:
                self.sent.popleft()

    def throttled(self) -> None:
        self.limited = True


_pacer = _Pacer()


# --- Requests ----------------------------------------------------------------


def _explain(response: requests.Response) -> str:
    text = (response.text or "").strip()[:300]
    if response.status_code == 401:
        return ("Azure refused the key. Check the key and region in Settings > Azure voices: "
                "the region must be the one the Speech resource was created in.")
    if response.status_code == 403:
        return ("Azure refused the request. On the free tier this usually means this month's "
                f"500,000 characters are used up; they come back on the 1st. ({text or 'no detail'})")
    if response.status_code == 400:
        return f"Azure could not read the request ({text or 'no detail'}). A written pronunciation may use a sound Azure does not know."
    return f"Azure answered {response.status_code}: {text or response.reason}"


def _post(settings: Dict, ssml: str, cancelled: Callable[[], bool] = lambda: False) -> bytes:
    url = _host(settings["region"]) + "/cognitiveservices/v1"
    headers = {
        "Ocp-Apim-Subscription-Key": settings["key"],
        "Content-Type": "application/ssml+xml",
        "X-Microsoft-OutputFormat": OUTPUT_FORMAT,
        "User-Agent": AGENT,
    }
    delay = 5.0
    for attempt in range(8):
        if cancelled():
            raise AzureError("Cancelled")
        _pacer.wait()
        try:
            response = requests.post(url, data=ssml.encode("utf-8"), headers=headers, timeout=60)
        except requests.RequestException as e:
            if attempt >= 3:
                raise AzureError(f"Could not reach Azure: {e}")
            time.sleep(delay)
            continue
        if response.status_code == 200:
            return response.content
        if response.status_code == 429 or response.status_code >= 500:
            if response.status_code == 429:
                _pacer.throttled()
            retry_after = response.headers.get("Retry-After", "")
            time.sleep(float(retry_after) if retry_after.isdigit() else delay)
            delay = min(delay * 2, 60)
            continue
        raise AzureError(_explain(response))
    raise AzureError("Azure kept answering 'too many requests' or a server error; try again later.")


def ssml(text: str, voice: str, speed: float = 1.0) -> str:
    locale = voice[:5]
    rate = round((speed - 1.0) * 100)
    body = pronunciations.azure_ssml_text(text, locale)
    return (
        f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="{locale}">'
        f'<voice name="{voice}"><prosody rate="{rate:+d}%">{body}</prosody></voice></speak>'
    )


def synthesize(
    settings: Dict,
    text: str,
    voice: str,
    speed: float = 1.0,
    usage_file: Optional[Path] = None,
    cancelled: Callable[[], bool] = lambda: False,
) -> np.ndarray:
    """One piece of text as float samples at 24 kHz."""
    if not configured(settings):
        raise AzureError("Azure voices are not set up: add the key and region in Settings > Azure voices.")
    audio = _post(settings, ssml(text, voice, speed), cancelled)
    _count(usage_file, billed_characters(text))
    return np.frombuffer(audio, dtype="<i2").astype(np.float32) / 32768.0


def test(settings: Dict) -> Dict:
    """Check the key and region by listing the voices, which costs no characters."""
    voices = fetch_voices(settings)
    return {"ok": True, "voices": len(voices)}


# --- Voices ------------------------------------------------------------------

_VOICE_FIELDS = ("ShortName", "DisplayName", "LocalName", "Gender", "Locale", "LocaleName",
                 "VoiceType", "StyleList", "SecondaryLocaleList")


def fetch_voices(settings: Dict) -> List[Dict]:
    """Every voice the region offers. Listing voices is free."""
    if not configured(settings):
        raise AzureError("Add the key and region first.")
    try:
        response = requests.get(
            _host(settings["region"]) + "/cognitiveservices/voices/list",
            headers={"Ocp-Apim-Subscription-Key": settings["key"], "User-Agent": AGENT},
            timeout=30,
        )
    except requests.RequestException as e:
        raise AzureError(f"Could not reach Azure: {e}")
    if response.status_code != 200:
        raise AzureError(_explain(response))
    return [{k: v.get(k) for k in _VOICE_FIELDS if k in v} for v in response.json()]


def english(voices: List[Dict]) -> List[Dict]:
    """The English voices, American first, then British, then the rest by accent."""
    order = {"en-US": 0, "en-GB": 1}
    found = [v for v in voices if str(v.get("Locale", "")).startswith("en-")]
    return sorted(found, key=lambda v: (order.get(v["Locale"], 2), v["Locale"], v["ShortName"]))


SAMPLE_TEXT = (
    "Tonight we are going to take a slow, quiet tour of the skin. "
    "Deep in the epidermis, the stratum basale rests on its thin basement membrane."
)
