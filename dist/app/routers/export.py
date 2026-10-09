from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.responses import JSONResponse, FileResponse
from ..state import export_status, ffmpeg_status, kokoro
from ..config import (
    content_dir,
    library_file,
    userdata_dir,
    sleep_cache_dir,
    sleep_work_dir,
    sleep_sounds_dir,
    sleep_settings_file,
)
from ..models import ExportRequest, SleepExportRequest, SleepSettings
from ..utils import get_language_from_voice, safe_save_json
from .tts import phoneme_char_budget
import json
import re
import io
import os
import platform
import subprocess
import shutil
import threading
from dataclasses import replace
from typing import Optional
import numpy as np
import soundfile as sf
from pydub import AudioSegment
import sys
from pathlib import Path

# Fix paths for logic imports
base_dir_parent = Path(__file__).parent.parent
if str(base_dir_parent) not in sys.path:
    sys.path.append(str(base_dir_parent))

try:
    from logic.dependency_manager import FFMPEGInstaller, configure_pydub, get_ffmpeg_path
    from logic.smart_content_detector import filter_text_for_tts
    from logic.text_normalizer import apply_custom_pronunciations
    from logic.sleep_script import Pacing, plan_text, join_pages, estimate_seconds, take_seconds
    from logic.sleep_finish import (
        NOISES,
        Sound,
        finish,
        needs_finishing,
        estimate_seconds as finish_seconds,
    )
    from logic.sleep_render import (
        SAMPLE_RATE as SLEEP_SAMPLE_RATE,
        CHARS_PER_SECOND_AT_1X,
        Cancelled,
        SentenceCache,
        render as render_sleep,
        cache_usage,
        clear_cache,
    )
except ImportError:
    sys.path.append(str(base_dir_parent / "logic"))
    from dependency_manager import FFMPEGInstaller, configure_pydub, get_ffmpeg_path
    from smart_content_detector import filter_text_for_tts
    from text_normalizer import apply_custom_pronunciations
    from sleep_script import Pacing, plan_text, join_pages, estimate_seconds, take_seconds
    from sleep_finish import (
        NOISES,
        Sound,
        finish,
        needs_finishing,
        estimate_seconds as finish_seconds,
    )
    from sleep_render import (
        SAMPLE_RATE as SLEEP_SAMPLE_RATE,
        CHARS_PER_SECOND_AT_1X,
        Cancelled,
        SentenceCache,
        render as render_sleep,
        cache_usage,
        clear_cache,
    )

router = APIRouter()
ffmpeg_installer = None


@router.get("/api/ffmpeg/status")
async def get_ffmpeg_status():
    return ffmpeg_status


@router.post("/api/ffmpeg/install")
async def install_ffmpeg(background_tasks: BackgroundTasks):
    global ffmpeg_status, ffmpeg_installer

    if ffmpeg_status["is_downloading"]:
        return JSONResponse({"error": "Download already in progress"}, status_code=409)

    if ffmpeg_status["is_installed"]:
        return {"status": "already_installed"}

    def download_task():
        global ffmpeg_status, ffmpeg_installer
        ffmpeg_status["is_downloading"] = True
        ffmpeg_status["progress"] = 0
        ffmpeg_status["total"] = 0
        ffmpeg_status["error"] = None
        ffmpeg_status["message"] = "Starting download..."

        def progress_callback(current, total, message):
            ffmpeg_status["progress"] = current
            ffmpeg_status["total"] = total
            ffmpeg_status["message"] = message

        ffmpeg_installer = FFMPEGInstaller(progress_callback)
        success, error = ffmpeg_installer.install()

        if success:
            ffmpeg_status["is_installed"] = True
            ffmpeg_status["is_downloading"] = False
            ffmpeg_status["message"] = "Installation complete"
            try:
                configure_pydub()
            except Exception as e:
                print(f"Warning: Failed to configure pydub: {e}")
        else:
            ffmpeg_status["error"] = error
            ffmpeg_status["is_downloading"] = False

        ffmpeg_installer = None

    background_tasks.add_task(download_task)
    return {"status": "started"}


@router.post("/api/ffmpeg/cancel")
async def cancel_ffmpeg_download():
    global ffmpeg_installer
    if ffmpeg_installer:
        ffmpeg_installer.cancel()
        return {"status": "cancelled"}
    return {"status": "not_running"}


@router.post("/api/export/audio")
async def export_audio(request: ExportRequest, background_tasks: BackgroundTasks):
    global export_status
    if export_status["is_exporting"]:
        return JSONResponse({"error": "Export already in progress"}, status_code=409)

    # Access kokoro from state module
    import app.state as state_module

    if state_module.kokoro is None:
        raise HTTPException(status_code=503, detail="TTS Engine not initialized.")

    if not ffmpeg_status["is_installed"]:
        # Re-check in case it was installed externally
        installer = FFMPEGInstaller()
        if not installer.check_installed():
            raise HTTPException(
                status_code=503, detail="FFMPEG not installed. Please install it first."
            )
        else:
            ffmpeg_status["is_installed"] = True

    try:
        configure_pydub()
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to configure audio encoder: {str(e)}"
        )

    def export_task():
        global export_status
        export_status = {
            "is_exporting": True,
            "progress": 0,
            "total": 0,
            "error": None,
            "output_file": None,
        }

        try:
            content_file = content_dir / f"{request.doc_id}.json"
            if not content_file.exists():
                export_status["error"] = "Document not found"
                export_status["is_exporting"] = False
                return

            with open(content_file, "r") as f:
                doc_data = json.load(f)

            with open(library_file, "r") as f:
                library = json.load(f)

            doc_item = next(
                (item for item in library if item.get("id") == request.doc_id), None
            )
            if not doc_item:
                export_status["error"] = "Document metadata not found"
                export_status["is_exporting"] = False
                return

            chunks = []
            for page in doc_data.get("pages", []):
                page_paragraphs = [p.strip() for p in page.split("\n") if p.strip()]
                for para in page_paragraphs:
                    if len(para) > 500:
                        sentences = re.split(r"(?<=[.!?])\s+", para)
                        chunks.extend([s.strip() for s in sentences if s.strip()])
                    else:
                        chunks.append(para)

            export_status["total"] = len(chunks)
            audio_segments = []
            rules_data = [r.model_dump() for r in request.rules]

            for i, chunk in enumerate(chunks):
                if not export_status["is_exporting"]:
                    export_status["error"] = "Export cancelled"
                    return

                try:
                    filtered_text = filter_text_for_tts(chunk)
                    if not filtered_text or not re.search(
                        r"[a-zA-Z0-9]", filtered_text
                    ):
                        export_status["progress"] = i + 1
                        continue

                    processed_text = apply_custom_pronunciations(
                        filtered_text, rules_data, request.ignore_list
                    )

                    lang = get_language_from_voice(request.voice)

                    # Use state_module.kokoro
                    with state_module.engine_lock:
                        samples, sample_rate = state_module.kokoro.create(
                            processed_text,
                            voice=request.voice,
                            speed=float(request.speed),
                            lang=lang,
                        )

                    buffer = io.BytesIO()
                    sf.write(
                        buffer,
                        samples.flatten(),
                        sample_rate,
                        format="WAV",
                        subtype="PCM_16",
                    )
                    buffer.seek(0)
                    audio_segment = AudioSegment.from_wav(buffer)
                    audio_segments.append(audio_segment)
                    audio_segments.append(AudioSegment.silent(duration=300))

                except Exception as e:
                    print(f"Warning: Failed to process chunk {i}: {e}")

                export_status["progress"] = i + 1

            if not audio_segments:
                export_status["error"] = "No audio generated"
                export_status["is_exporting"] = False
                return

            final_audio = sum(audio_segments)
            safe_filename = re.sub(
                r"[^\w\s-]", "", doc_item.get("fileName", "export")
            ).replace(" ", "_")
            output_filename = f"{safe_filename}_{request.voice}.mp3"
            output_path = userdata_dir / output_filename

            final_audio.export(str(output_path), format="mp3", bitrate="128k")

            export_status["output_file"] = output_filename
            export_status["is_exporting"] = False

        except Exception as e:
            export_status["error"] = str(e)
            export_status["is_exporting"] = False

    background_tasks.add_task(export_task)
    return {"status": "started"}


@router.get("/api/export/status")
async def get_export_status():
    return export_status


@router.post("/api/export/cancel")
async def cancel_export():
    global export_status
    if export_status["is_exporting"]:
        export_status["is_exporting"] = False
        return {"status": "cancelled"}
    return {"status": "not_running"}


@router.get("/api/export/download/{filename}")
async def download_export(filename: str):
    file_path = userdata_dir / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    media_type = MEDIA_TYPES.get(Path(filename).suffix.lower(), "audio/mpeg")
    return FileResponse(file_path, media_type=media_type, filename=filename)


# --- Sleep recordings ---
#
# A sleep recording is rendered one sentence at a time, with exact silence
# inserted between sentences rather than whatever the model leaves, and written
# to a WAV as it goes so a three-hour file never sits in memory. That voice
# track is then finished by two ffmpeg passes: softened, given a room, leveled,
# laid over a background sound, faded and encoded. See logic/sleep_script.py,
# logic/sleep_render.py and logic/sleep_finish.py.

# Held for the whole render, including the sentence still finishing after a
# cancel, so a second render cannot start until the first has really stopped.
_sleep_render_lock = threading.Lock()

# How much of the document a preview renders, in seconds of recording.
PREVIEW_SECONDS = 60
SOUND_EXTENSIONS = {
    ".mp3", ".m4a", ".aac", ".wav", ".flac", ".ogg", ".opus", ".aif", ".aiff", ".caf",
}
MEDIA_TYPES = {".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".wav": "audio/wav"}


def _require_engine():
    import app.state as state_module

    if state_module.kokoro is None:
        raise HTTPException(status_code=503, detail="TTS Engine not initialized.")
    return state_module


def _sleep_plan(request: SleepExportRequest):
    """Load a document and turn it into a sleep-recording plan."""
    state_module = _require_engine()
    if request.voice not in state_module.kokoro.get_voices():
        raise HTTPException(status_code=400, detail=f"Unknown voice: {request.voice}")

    content_file = content_dir / f"{request.doc_id}.json"
    if not content_file.exists():
        raise HTTPException(status_code=404, detail="Document not found")
    with open(content_file, "r") as f:
        pages = json.load(f).get("pages", [])
    with open(library_file, "r") as f:
        library = json.load(f)
    doc_item = next((item for item in library if item.get("id") == request.doc_id), None)
    if not doc_item:
        raise HTTPException(status_code=404, detail="Document metadata not found")

    # EPUBs are stored as the PDF they were converted to, so this covers both.
    keeps_paragraphs = not doc_item.get("fileName", "").lower().endswith(".pdf")
    text = filter_text_for_tts(join_pages(pages, keeps_paragraphs))
    pacing = Pacing(
        **request.pacing.model_dump(),
        # Within the model's phoneme limit too, which matters for CJK text.
        max_chars=min(Pacing().max_chars, phoneme_char_budget(text)),
    )
    rules_data = [r.model_dump() for r in request.rules]
    events = plan_text(
        text,
        pacing,
        transform=lambda s: apply_custom_pronunciations(s, rules_data, request.ignore_list),
    )
    if not any(kind == "say" for kind, _ in events):
        raise HTTPException(status_code=400, detail="That document has nothing to read aloud")
    return state_module, doc_item, events, pacing


def _sound_path(name: str) -> Path:
    """An added background sound, by bare file name only."""
    if not name or name != Path(name).name or name.startswith("."):
        raise HTTPException(status_code=400, detail="Bad sound name")
    return sleep_sounds_dir / name


def _sleep_sound(request: SleepExportRequest) -> Sound:
    background = request.sound.background
    if background.startswith("file:"):
        if not _sound_path(background[5:]).is_file():
            raise HTTPException(
                status_code=400, detail=f"Background sound not found: {background[5:]}"
            )
    elif background != "none" and background not in NOISES:
        raise HTTPException(status_code=400, detail=f"Unknown background: {background}")
    return Sound(**request.sound.model_dump())


def _sleep_ffmpeg(sound: Sound) -> Optional[str]:
    """The ffmpeg that finishes this recording, or None when it needs no finishing."""
    if not needs_finishing(sound):
        return None
    path = get_ffmpeg_path()
    if not path:
        raise HTTPException(
            status_code=400,
            detail="FFmpeg is needed for MP3, M4A and the sound options. "
            "Install it, or choose WAV with every sound option off.",
        )
    return path


def _sleep_cache(state_module, request: SleepExportRequest) -> SentenceCache:
    lang = get_language_from_voice(request.voice)
    return SentenceCache(
        sleep_cache_dir,
        [state_module.kokoro_model, request.voice, round(request.speed, 3), lang],
    )


def _empty(directory: Path) -> None:
    if directory.exists():
        for f in directory.iterdir():
            if f.is_file():
                f.unlink(missing_ok=True)


# Seconds of speech generated per second of rendering: measured at about 2 on an
# Apple Silicon Mac with the int8 model. Only for the estimate shown beforehand.
SLEEP_RENDER_SPEED = 2.0


@router.post("/api/export/sleep/plan")
def plan_sleep_recording(request: SleepExportRequest):
    """Estimate a sleep recording's length without generating anything."""
    state_module, _, events, pacing = _sleep_plan(request)
    sound = Sound(**request.sound.model_dump())
    cache = _sleep_cache(state_module, request)
    chars_per_second = CHARS_PER_SECOND_AT_1X * request.speed
    says = [text for kind, text in events if kind == "say"]
    uncached = [text for text in says if not cache.path(text).exists()]
    seconds = estimate_seconds(events, pacing, chars_per_second)
    return {
        "pieces": len(says),
        "cached_pieces": len(says) - len(uncached),
        "estimated_seconds": round(seconds),
        "estimated_render_seconds": round(
            sum(len(t) for t in uncached) / chars_per_second / SLEEP_RENDER_SPEED
            + finish_seconds(seconds, sound)
        ),
        "needs_ffmpeg": needs_finishing(sound),
        "ffmpeg_installed": bool(get_ffmpeg_path()),
    }


def _start_sleep_render(
    request: SleepExportRequest, background_tasks: BackgroundTasks, preview: bool
):
    global export_status
    if export_status["is_exporting"]:
        return JSONResponse({"error": "Export already in progress"}, status_code=409)
    if not _sleep_render_lock.acquire(blocking=False):
        # Cancelled, but the sentence it was generating has not finished yet.
        return JSONResponse(
            {"error": "The last sleep recording is still stopping; try again in a few seconds"},
            status_code=409,
        )

    try:
        # Checked before answering, so a bad document or a missing ffmpeg
        # fails here rather than after the progress view has opened.
        state_module, doc_item, events, pacing = _sleep_plan(request)
        sound = _sleep_sound(request)
        ffmpeg = _sleep_ffmpeg(sound)
    except Exception:
        _sleep_render_lock.release()
        raise

    chars_per_second = CHARS_PER_SECOND_AT_1X * request.speed
    if preview:
        # The opening minute, with the lead-in and fade-in as they will be (up
        # to 10 s, so a long lead-in does not make a preview of silence), and an
        # ending short enough to leave most of the minute to listen to.
        pacing = replace(pacing, lead_in=min(pacing.lead_in, 10.0), tail=min(pacing.tail, 2.0))
        sound = replace(sound, fade_in=min(sound.fade_in, 10.0), fade_out=min(sound.fade_out, 3.0))
        events = take_seconds(events, PREVIEW_SECONDS - pacing.lead_in, chars_per_second)
        out_path = sleep_work_dir / f"preview.{sound.format}"
        title = ""
    else:
        stem = Path(doc_item.get("fileName", "export")).stem
        safe_filename = re.sub(r"[^\w\s-]", "", stem).replace(" ", "_") or "export"
        out_path = userdata_dir / f"{safe_filename}_{request.voice}_sleep.{sound.format}"
        title = stem

    cache = _sleep_cache(state_module, request)
    model = state_module.kokoro_model
    lang = get_language_from_voice(request.voice)
    total = sum(1 for kind, _ in events if kind == "say")

    # This render's own status. The global is pointed at it for the status and
    # cancel routes, but writes go here, so a render still finishing after a
    # cancel can never touch the status of an export started after it.
    status = {
        "is_exporting": True,
        "mode": "sleep",
        "preview": preview,
        # "voice" while sentences are generated, then "measuring" and "mixing"
        # while ffmpeg finishes the file.
        "phase": "voice",
        "phase_progress": 0,
        "progress": 0,
        "total": total,
        "audio_seconds": 0,
        "retried": 0,
        "error": None,
        "output_file": None,
    }
    export_status = status

    def synth(text: str) -> np.ndarray:
        if state_module.kokoro_model != model:
            raise RuntimeError("The voice model was changed during the render")
        with state_module.engine_lock:
            samples, sample_rate = state_module.kokoro.create(
                text, voice=request.voice, speed=float(request.speed), lang=lang
            )
        if sample_rate != SLEEP_SAMPLE_RATE:
            raise RuntimeError(f"Unexpected sample rate {sample_rate}")
        return np.asarray(samples, dtype=np.float32).flatten()

    def progress(done: int, total: int, seconds: float):
        status["progress"] = done
        status["phase_progress"] = done / total if total else 1
        status["audio_seconds"] = round(seconds, 1)

    def finishing(phase: str, fraction: float):
        status["phase"] = phase
        status["phase_progress"] = round(fraction, 3)

    def render_task():
        # Three hours of voice is about 500 MB, so it is only an intermediate
        # when there is finishing to do.
        voice_path = sleep_work_dir / "voice.wav" if ffmpeg else out_path
        try:
            sleep_work_dir.mkdir(parents=True, exist_ok=True)
            _empty(sleep_work_dir)
            info = render_sleep(
                events,
                synth,
                voice_path,
                cache,
                pacing,
                chars_per_second=chars_per_second,
                on_progress=progress,
                cancelled=lambda: not status["is_exporting"],
            )
            for problem in info["problems"]:
                print(f"[SLEEP] Retried a sentence ({problem})")
            status["retried"] = info["retried"]
            if ffmpeg:
                finishing("measuring", 0)
                result = finish(
                    ffmpeg,
                    voice_path,
                    out_path,
                    info["seconds"],
                    sound,
                    sleep_work_dir,
                    sleep_sounds_dir,
                    title=title,
                    on_progress=finishing,
                    cancelled=lambda: not status["is_exporting"],
                )
                status["loudness"] = result["voice_loudness"]
            status["audio_seconds"] = round(info["seconds"], 1)
            status["output_file"] = out_path.name
        except Cancelled:
            status["error"] = "Export cancelled"
        except Exception as e:
            status["error"] = str(e)
        finally:
            if ffmpeg:
                voice_path.unlink(missing_ok=True)
            status["is_exporting"] = False
            _sleep_render_lock.release()

    background_tasks.add_task(render_task)
    return {"status": "started", "pieces": total}


@router.post("/api/export/sleep")
def export_sleep_recording(request: SleepExportRequest, background_tasks: BackgroundTasks):
    return _start_sleep_render(request, background_tasks, preview=False)


@router.post("/api/export/sleep/preview")
def preview_sleep_recording(request: SleepExportRequest, background_tasks: BackgroundTasks):
    """Render the first minute with every option applied, to listen to before committing."""
    return _start_sleep_render(request, background_tasks, preview=True)


@router.get("/api/export/sleep/preview/{name}")
def sleep_preview_audio(name: str):
    if not re.fullmatch(r"preview\.(mp3|m4a|wav)", name):
        raise HTTPException(status_code=404, detail="Not a preview")
    path = sleep_work_dir / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="No preview rendered")
    return FileResponse(path, media_type=MEDIA_TYPES[path.suffix])


@router.get("/api/export/sleep/settings")
def get_sleep_settings():
    """The options last used, and the defaults to reset them to."""
    saved = SleepSettings()
    if sleep_settings_file.exists():
        try:
            saved = SleepSettings.model_validate_json(sleep_settings_file.read_text())
        except Exception:
            # Unreadable, or out of range after an update: start from defaults.
            pass
    return {"settings": saved.model_dump(), "defaults": SleepSettings().model_dump()}


@router.post("/api/export/sleep/settings")
def save_sleep_settings(settings: SleepSettings):
    safe_save_json(sleep_settings_file, settings.model_dump())
    return {"status": "ok"}


@router.get("/api/export/sleep/sounds")
def list_sleep_sounds():
    if not sleep_sounds_dir.exists():
        return []
    return [
        {"name": f.name, "bytes": f.stat().st_size}
        for f in sorted(sleep_sounds_dir.iterdir(), key=lambda f: f.name.lower())
        if f.is_file() and f.suffix.lower() in SOUND_EXTENSIONS
    ]


@router.post("/api/export/sleep/sounds")
def add_sleep_sound(file: UploadFile = File(...)):
    """Keep a sound file (rain, waves...) to loop under sleep recordings."""
    name = re.sub(r"[^\w .()-]", "_", Path(file.filename or "").name).strip(" .")
    stem, ext = Path(name).stem, Path(name).suffix.lower()
    if not stem or ext not in SOUND_EXTENSIONS:
        raise HTTPException(
            status_code=400, detail="Choose an audio file: MP3, M4A, WAV, FLAC, OGG or AIFF"
        )
    sleep_sounds_dir.mkdir(parents=True, exist_ok=True)
    dest, n = sleep_sounds_dir / name, 2
    while dest.exists():
        dest, n = sleep_sounds_dir / f"{stem} ({n}){ext}", n + 1
    part = dest.with_name(dest.name + ".part")
    try:
        with open(part, "wb") as out:
            shutil.copyfileobj(file.file, out, 1024 * 1024)
        ffmpeg = get_ffmpeg_path()
        if ffmpeg:
            # A file with the right extension but no audio ffmpeg can decode
            # would only fail later, an hour into a render.
            check = subprocess.run(
                [ffmpeg, "-hide_banner", "-v", "error", "-t", "1", "-i", str(part),
                 "-map", "0:a:0", "-f", "null", "-"],
                capture_output=True,
                timeout=60,
            )
            if check.returncode != 0:
                raise HTTPException(status_code=400, detail="That file has no audio that can be read")
        os.replace(part, dest)
    finally:
        part.unlink(missing_ok=True)
    return {"name": dest.name, "bytes": dest.stat().st_size}


@router.delete("/api/export/sleep/sounds/{name}")
def delete_sleep_sound(name: str):
    path = _sound_path(name)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Sound not found")
    path.unlink()
    return {"status": "deleted"}


@router.get("/api/export/sleep/cache")
def sleep_cache_status():
    return cache_usage(sleep_cache_dir)


@router.post("/api/export/sleep/cache/clear")
def clear_sleep_cache():
    if _sleep_render_lock.locked():
        return JSONResponse(
            {"error": "A sleep recording is rendering; it needs its cache"}, status_code=409
        )
    return {"status": "cleared", **clear_cache(sleep_cache_dir)}


@router.post("/api/export/open-location/{filename}")
async def open_file_location(filename: str):
    try:
        file_path = userdata_dir / filename
        abs_file_path = file_path.absolute()

        if not abs_file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")

        folder_path = abs_file_path.parent
        if not folder_path.exists():
            folder_path.mkdir(parents=True, exist_ok=True)

        system = platform.system()
        folder_str = str(folder_path)

        if system == "Windows":
            os.startfile(folder_str)
        elif system == "Darwin":
            subprocess.Popen(["open", folder_str])
        elif system == "Linux":
            subprocess.Popen(["xdg-open", folder_str])
        else:
            raise HTTPException(status_code=501, detail="Platform not supported")

        return {"status": "opened", "folder": folder_str}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
