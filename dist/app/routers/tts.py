from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
import numpy as np
import io
import re
import hashlib
import soundfile as sf
import concurrent.futures
from typing import Dict
import sys
import json
from pathlib import Path

# Add app logic to path for imports
base_dir_parent = Path(__file__).parent.parent
if str(base_dir_parent) not in sys.path:
    sys.path.append(str(base_dir_parent))

try:
    from logic.smart_content_detector import filter_text_for_tts
    from logic.text_normalizer import apply_custom_pronunciations
except ImportError:
    sys.path.append(str(base_dir_parent / "logic"))
    from smart_content_detector import filter_text_for_tts
    from text_normalizer import apply_custom_pronunciations

from ..state import audio_cache, kokoro
from ..models import SynthesisRequest
from ..utils import get_language_from_voice
from ..config import base_dir, preview_cache_dir
from kokoro_onnx import SAMPLE_RATE

router = APIRouter()

# One short line per language, used to audition a voice before committing to it.
# Every voice in a language reads the identical sentence so they can be compared
# directly, and each line is phrased to exercise a range of vowels and plosives.
PREVIEW_PHRASES = {
    "en-us": "Hello. This is what my voice sounds like when reading your books.",
    "en-gb": "Hello. This is what my voice sounds like when reading your books.",
    "fr-fr": "Bonjour. Voici ma voix lorsque je lis vos livres.",
    "es": "Hola. Asi suena mi voz cuando leo tus libros.",
    "it": "Ciao. Questa e la mia voce mentre leggo i tuoi libri.",
    "pt-br": "Ola. Esta e a minha voz quando leio os seus livros.",
    "ja": "こんにちは。これが本を読むときの私の声です。",
    "cmn": "你好。这是我朗读书籍时的声音。",
}
DEFAULT_PREVIEW_PHRASE = PREVIEW_PHRASES["en-us"]

# --- Helpers moved from server.py ---


def safe_concat(audio_list):
    clean_list = []
    for a in audio_list:
        if isinstance(a, np.ndarray):
            if a.ndim == 2:
                a = a.squeeze()
            if a.ndim > 2:
                a = a.flatten()
        clean_list.append(a)
    if not clean_list:
        return np.array([], dtype=np.float32)
    return np.concatenate(clean_list)


def graceful_chunk_for_tts(text, max_chars=200):
    """
    GemGem-inspired pre-chunking: split long text at natural boundaries
    before sending to Kokoro. Prevents garbling when sentences exceed
    MAX_PHONEME_LENGTH (~510 phonemes ≈ 200 chars at ~2.5x expansion).
    """
    if len(text) <= max_chars:
        return [text]

    chunks = []
    remaining = text
    while len(remaining) > max_chars:
        truncated = remaining[:max_chars]
        # Find the last natural break before the limit
        last_break = max(
            truncated.rfind(". "),
            truncated.rfind("! "),
            truncated.rfind("? "),
            truncated.rfind("; "),
            truncated.rfind(", "),
        )

        if last_break > max_chars * 0.3:  # At least 30% preserved
            chunks.append(remaining[: last_break + 1].strip())
            remaining = remaining[last_break + 1 :].strip()
        else:
            # Fallback: split at last space to avoid mid-word cuts
            last_space = truncated.rfind(" ")
            if last_space > max_chars * 0.5:
                chunks.append(remaining[:last_space].strip())
                remaining = remaining[last_space:].strip()
            else:
                # Hard split (very rare — no spaces in 200 chars)
                chunks.append(remaining[:max_chars].strip())
                remaining = remaining[max_chars:].strip()

    if remaining.strip():
        chunks.append(remaining.strip())
    return chunks


def synthesize_with_pauses(
    text: str, voice: str, speed: float, pause_settings: Dict[str, int]
):
    import app.state as state_module

    lang = get_language_from_voice(voice)
    segments = re.split(r"([,\.!\?:;。，！？：；、]+|\n)", text)
    sample_rate = SAMPLE_RATE
    plan = []
    last_was_punctuation = False

    char_map = {
        ",": "comma",
        "，": "comma",
        "、": "comma",
        ".": "period",
        "。": "period",
        "?": "question",
        "？": "question",
        "!": "exclamation",
        "！": "exclamation",
        ":": "colon",
        "：": "colon",
        ";": "semicolon",
        "；": "semicolon",
    }

    for i, segment in enumerate(segments):
        clean_segment = segment.strip()
        if segment == "\n":
            if not last_was_punctuation:
                ms = pause_settings.get("newline", 300) or 300
                plan.append({"type": "silence", "ms": ms})
            last_was_punctuation = False
            continue

        if not clean_segment:
            continue

        if re.match(r"^[,\.!\?:;。，！？：；、]+$", clean_segment):
            last_char = clean_segment[-1]
            pause_ms = 0

            vocab_key = char_map.get(last_char)
            if vocab_key:
                pause_ms = pause_settings.get(vocab_key, 300)

            plan.append({"type": "silence", "ms": pause_ms})
            last_was_punctuation = True
        else:
            if re.search(
                r"[a-zA-Z0-9\u3000-\u303f\u3040-\u309f\u30a0-\u30ff\uff00-\uff9f\u4e00-\u9faf\u3400-\u4dbf]",
                clean_segment,
            ):
                # GemGem-style pre-chunking for long segments
                sub_chunks = graceful_chunk_for_tts(clean_segment)
                for sc_idx, sub_chunk in enumerate(sub_chunks):
                    plan.append(
                        {"type": "tts", "text": sub_chunk, "index": f"{i}_{sc_idx}"}
                    )
                last_was_punctuation = False

    tts_tasks = [p for p in plan if p["type"] == "tts"]
    audio_map = {}

    if tts_tasks and state_module.kokoro:
        # Synthesized one at a time on purpose. This previously ran on a
        # ThreadPoolExecutor(max_workers=4), but espeak-ng phonemization is not
        # thread-safe (see state.engine_lock), so the chunks came back holding
        # each other's words and the assembled sentence was scrambled. The
        # executor also never bought much: onnxruntime already parallelizes a
        # single inference across cores.
        for t in tts_tasks:
            idx = t["index"]
            try:
                with state_module.engine_lock:
                    samples, _ = state_module.kokoro.create(
                        t["text"], voice=voice, speed=speed, lang=lang
                    )
                audio_map[idx] = samples.flatten()
            except Exception as e:
                print(f"Segment {idx} failed: {e}")
                audio_map[idx] = None

    final_segments = []
    for item in plan:
        if item["type"] == "silence":
            pause_samples = int((item["ms"] / 1000.0) * sample_rate)
            if pause_samples > 0:
                final_segments.append(np.zeros(pause_samples, dtype=np.float32))
        elif item["type"] == "tts":
            audio = audio_map.get(item["index"])
            if audio is not None:
                final_segments.append(audio)

    if final_segments:
        return safe_concat(final_segments), sample_rate
    return np.zeros(int(sample_rate * 0.1), dtype=np.float32), sample_rate


def generate_cache_key(text, voice, speed, pause_settings, rules, ignore_list):
    lang = get_language_from_voice(voice)
    cache_data = {
        "text": text,
        "voice": voice,
        "language": lang,
        "speed": speed,
        "pause_settings": pause_settings,
        "rules": [str(r) for r in rules],
        "ignore_list": sorted(ignore_list),
    }
    cache_string = json.dumps(cache_data, sort_keys=True)
    return hashlib.md5(cache_string.encode("utf-8")).hexdigest()


# --- API Endpoints ---


@router.get("/api/voices/available")
async def get_voices():
    import app.state as state_module

    if not state_module.kokoro:
        return {"categories": {}}

    try:
        raw_voices = state_module.kokoro.get_voices()

        # Group into categories
        categories = {}

        # Helper to get easy readable name
        def get_voice_name(vid):
            # e.g. af_bella -> Bella
            parts = vid.split("_")
            if len(parts) > 1:
                return parts[1].title()
            return vid

        # Helper for language labels
        def get_lang_label(code):
            maps = {
                "en-us": "English (US)",
                "en-gb": "English (UK)",
                "fr-fr": "French",
                "es": "Spanish",
                "cmn": "Chinese (Mandarin)",
                "it": "Italian",
                "pt-br": "Portuguese (Brazil)",
                "ja": "Japanese",
            }
            return maps.get(code, "Other")

        for voice in raw_voices:
            # Assuming voice is just a string ID based on previous code usage.
            # If it's an object, we adjust. Kokoro usually returns list of strings.
            voice_id = voice if isinstance(voice, str) else voice.get("id")

            # Filter out voices with Indian accents as requested (handles prefixes like v0_alpha)
            if voice_id.lower().split("_")[-1] in ["alpha", "beta", "omega", "psi"]:
                continue

            lang_code = get_language_from_voice(voice_id)
            label = get_lang_label(lang_code)

            if lang_code not in categories:
                categories[lang_code] = {"label": label, "voices": []}

            categories[lang_code]["voices"].append(
                {"id": voice_id, "name": get_voice_name(voice_id)}
            )

        # Sort voices within categories
        for code in categories:
            categories[code]["voices"].sort(key=lambda x: x["name"])

        return {"categories": categories}

    except Exception as e:
        # print(f"[DEBUG] Error processing voices: {e}")
        return {"categories": {}}


@router.get("/api/voices/preview/{voice_id}")
async def preview_voice(voice_id: str):
    """
    Return a short spoken sample of one voice, so a voice can be auditioned
    without committing to it and starting a document.

    Samples are rendered once and cached on disk. Generating one costs roughly
    a second, but only the first time a given voice is requested.
    """
    import app.state as state_module

    if state_module.kokoro is None:
        raise HTTPException(status_code=503, detail="TTS engine not initialized.")

    # Reject anything that is not a plain voice id before it reaches the
    # filesystem -- this value becomes a filename below.
    if not re.fullmatch(r"[A-Za-z0-9_]+", voice_id or ""):
        raise HTTPException(status_code=400, detail="Invalid voice id.")

    if voice_id not in state_module.kokoro.get_voices():
        raise HTTPException(status_code=404, detail=f"Unknown voice: {voice_id}")

    cache_path = preview_cache_dir / f"{voice_id}.wav"

    if cache_path.exists():
        audio_bytes = cache_path.read_bytes()
    else:
        lang = get_language_from_voice(voice_id)
        phrase = PREVIEW_PHRASES.get(lang, DEFAULT_PREVIEW_PHRASE)
        try:
            # Always 1.0x: the preview shows the voice, while the speed slider
            # is a separate setting the listener is already able to hear.
            with state_module.engine_lock:
                samples, sample_rate = state_module.kokoro.create(
                    phrase, voice=voice_id, speed=1.0, lang=lang
                )
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Could not render preview: {e}"
            )

        buffer = io.BytesIO()
        sf.write(
            buffer,
            np.asarray(samples, dtype=np.float32).flatten(),
            sample_rate,
            format="WAV",
            subtype="PCM_16",
        )
        audio_bytes = buffer.getvalue()

        # A failed write costs a re-render next time, which is not worth
        # failing the request over.
        try:
            cache_path.write_bytes(audio_bytes)
        except Exception as e:
            print(f"[WARNING] Could not cache preview for {voice_id}: {e}")

    return StreamingResponse(
        io.BytesIO(audio_bytes),
        media_type="audio/wav",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/api/locale/{lang}")
async def get_locale(lang: str):
    locale_dir = base_dir / "locales"
    file_path = locale_dir / f"{lang}.json"
    if not file_path.exists():
        file_path = locale_dir / "en.json"
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


@router.post("/api/synthesize")
async def synthesize(request: SynthesisRequest):
    import app.state as state_module

    if state_module.kokoro is None:
        raise HTTPException(status_code=503, detail="TTS Engine not initialized.")

    try:
        text = filter_text_for_tts(request.text)
        rules_data = [r.model_dump() for r in request.rules]
        text = apply_custom_pronunciations(text, rules_data, request.ignore_list)
    except Exception:
        text = filter_text_for_tts(request.text)

    try:
        voices = state_module.kokoro.get_voices()
        selected_voice = request.voice if request.voice in voices else "af_sky"
        pause_settings = request.pause_settings or {}

        cache_key = generate_cache_key(
            text,
            selected_voice,
            float(request.speed or 1.0),
            pause_settings,
            request.rules,
            request.ignore_list,
        )

        cached_audio = audio_cache.get(cache_key)
        if cached_audio:
            return StreamingResponse(
                io.BytesIO(cached_audio),
                media_type="audio/wav",
                headers={"Content-Length": str(len(cached_audio))},
            )

        has_pause_settings = pause_settings and isinstance(pause_settings, dict)
        punctuation_chars = [
            ",",
            ".",
            "!",
            "?",
            ":",
            ";",
            "\n",
            "。",
            "，",
            "！",
            "？",
            "：",
            "；",
            "、",
        ]
        has_punctuation = any(p in text for p in punctuation_chars)
        lang = get_language_from_voice(selected_voice)

        if not re.search(
            r"[a-zA-Z0-9\u3000-\u303f\u3040-\u309f\u30a0-\u30ff\uff00-\uff9f\u4e00-\u9faf\u3400-\u4dbf]",
            text,
        ):
            samples = np.zeros(int(24000 * 0.1), dtype=np.float32)
            sample_rate = 24000
        else:
            if has_pause_settings and has_punctuation:
                samples, sample_rate = synthesize_with_pauses(
                    text, selected_voice, float(request.speed or 1.0), pause_settings
                )
            else:
                # GemGem-style pre-chunking for direct synthesis path
                sub_chunks = graceful_chunk_for_tts(text)
                if len(sub_chunks) == 1:
                    with state_module.engine_lock:
                        samples, sample_rate = state_module.kokoro.create(
                            text,
                            voice=selected_voice,
                            speed=float(request.speed or 1.0),
                            lang=lang,
                        )
                else:
                    chunk_audios = []
                    sample_rate = SAMPLE_RATE
                    for chunk in sub_chunks:
                        with state_module.engine_lock:
                            chunk_samples, sr = state_module.kokoro.create(
                                chunk,
                                voice=selected_voice,
                                speed=float(request.speed or 1.0),
                                lang=lang,
                            )
                        chunk_audios.append(chunk_samples.flatten())
                        sample_rate = sr
                    samples = safe_concat(chunk_audios)

        buffer = io.BytesIO()
        sf.write(buffer, samples.flatten(), sample_rate, format="WAV", subtype="PCM_16")
        audio_bytes = buffer.getvalue()

        audio_cache.put(cache_key, audio_bytes)

        return StreamingResponse(
            io.BytesIO(audio_bytes),
            media_type="audio/wav",
            headers={"Content-Length": str(len(audio_bytes))},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
