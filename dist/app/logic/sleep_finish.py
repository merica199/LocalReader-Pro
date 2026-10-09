"""
Finish a sleep recording: soften the voice, put it in a small room, bring it to
a steady loudness, lay a background sound under it, fade the ends, and encode.

sleep_render.py writes the voice alone, sentence by sentence. Finishing is two
ffmpeg passes over that file: the first measures how loud the processed voice
is, the second applies everything and encodes. ffmpeg streams, so a
three-hour recording still never sits in memory.

The finishing ideas and their defaults come from docs/reference/sleepcast.py.
Where this differs, it says why.
"""
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
import soundfile as sf
from scipy.signal import lfilter

try:
    from logic.sleep_render import Cancelled
except ImportError:
    from sleep_render import Cancelled

VOICE_RATE = 24000
OUTPUT_RATE = 44100
# Peak ceiling of the finished file, kept under full scale so MP3 and AAC
# encoding cannot push it into clipping.
CEILING_DB = -1.0

# Low-pass cutoff in Hz. Kokoro's sibilants are bright; cutting the top end is
# what makes a voice sound softer and further away. "light" is the reference's.
SOFTEN = {"off": None, "light": 8500, "medium": 6000, "strong": 4000}

# (reverberation time in seconds, reverb level against the direct voice in dB).
# The reference used two fixed echoes (ffmpeg's aecho at 60 and 97 ms), which is
# a slapback more than a room; a decaying noise tail is how a room actually
# answers. Its two echoes sum to about -14.5 dB, between these two settings.
ROOMS = {"off": None, "subtle": (0.45, -16.0), "roomy": (0.9, -10.0)}

# ffmpeg noise colour and the low-pass that tames its top end. Brown is the
# reference's default and its 900 Hz cutoff. Two channels from different seeds
# give stereo noise that sounds wide in headphones instead of centred.
NOISES = {
    "brown": ("brown", 900),
    "pink": ("pink", 5000),
    "white": ("white", 8000),
}

FORMATS = {"mp3": "mp3", "m4a": "ipod", "wav": "wav"}


@dataclass(frozen=True)
class Sound:
    soften: str = "light"
    room: str = "subtle"
    # Integrated loudness target in LUFS, or None to leave the voice as rendered.
    # Sentences are already leveled to each other; this sets the whole file.
    loudness: Optional[float] = -22.0
    # "none", a NOISES key, or "file:<name>" for a sound in the sounds folder.
    background: str = "brown"
    # Background loudness relative to the voice, in LU (dB of loudness).
    background_level: float = -18.0
    fade_in: float = 3.0
    fade_out: float = 45.0
    format: str = "mp3"
    bitrate: int = 96


def needs_finishing(sound: Sound) -> bool:
    """False when the rendered voice track is already the requested file."""
    return bool(
        sound.format != "wav"
        or SOFTEN.get(sound.soften)
        or ROOMS.get(sound.room)
        or sound.loudness is not None
        or sound.background != "none"
        or sound.fade_in > 0
        or sound.fade_out > 0
    )


def make_room_ir(path: Path, seconds: float, level_db: float, seed: int = 7) -> None:
    """
    Write a stereo impulse response: the direct voice, then a room's tail.

    The tail is noise decaying by 60 dB over `seconds`, darkened so the high
    frequencies die first as they do on real walls, with different noise on
    each side so the room surrounds the voice instead of sitting on it.
    """
    rate = VOICE_RATE
    length = int(rate * seconds * 1.2)
    t = np.arange(length) / rate
    rng = np.random.default_rng(seed)
    tail = rng.standard_normal((length, 2)) * (10 ** (-3 * t / seconds))[:, None]
    # One-pole low-pass at about 3.5 kHz.
    pole = np.exp(-2 * np.pi * 3500 / rate)
    tail = lfilter([1 - pole], [1, -pole], tail, axis=0)
    # The first reflections arrive after the direct sound, not with it.
    predelay = int(0.012 * rate)
    tail[:predelay] = 0
    ramp = int(0.010 * rate)
    tail[predelay:predelay + ramp] *= np.linspace(0, 1, ramp)[:, None]
    tail /= np.sqrt(np.sum(tail ** 2, axis=0))
    ir = tail * 10 ** (level_db / 20)
    ir[0] += 1.0
    sf.write(str(path), ir.astype(np.float32), rate, subtype="FLOAT")


def run_ffmpeg(
    args: List[str],
    duration: float,
    on_progress: Optional[Callable[[float], None]] = None,
    cancelled: Callable[[], bool] = lambda: False,
) -> str:
    """Run ffmpeg, reporting progress as a fraction of `duration`. Returns its log."""
    with tempfile.TemporaryFile() as log:
        proc = subprocess.Popen(
            [*args[:1], "-hide_banner", "-nostats", "-progress", "pipe:1", *args[1:]],
            stdout=subprocess.PIPE,
            stderr=log,
            stdin=subprocess.DEVNULL,
            text=True,
        )
        try:
            for line in proc.stdout:
                if cancelled():
                    proc.terminate()
                    proc.wait()
                    raise Cancelled()
                if line.startswith("out_time_us=") and on_progress and duration > 0:
                    try:
                        done = int(line.split("=", 1)[1]) / 1e6
                    except ValueError:
                        continue
                    on_progress(min(1.0, max(0.0, done / duration)))
            code = proc.wait()
        except BaseException:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
            raise
        log.seek(0)
        text = log.read().decode("utf-8", "replace")
    if code != 0:
        raise RuntimeError("ffmpeg failed: " + text.strip()[-600:])
    return text


def integrated_loudness(log: str) -> float:
    """The integrated loudness from an ebur128 summary in ffmpeg's log."""
    found = re.findall(r"I:\s+(-?[\d.]+|-inf) LUFS", log)
    if not found:
        raise RuntimeError("ffmpeg did not report a loudness")
    return float(found[-1]) if found[-1] != "-inf" else -70.0


def voice_chain(sound: Sound, stereo: bool, ir_input: Optional[int]) -> str:
    """Filters from the raw voice track to the processed voice, ending in [voice]."""
    steps = ["[0:a]highpass=f=60"]
    if SOFTEN.get(sound.soften):
        steps.append(f"lowpass=f={SOFTEN[sound.soften]}")
    if stereo:
        steps.append("pan=stereo|c0=c0|c1=c0")
    chain = ",".join(steps)
    if ir_input is not None:
        # irnorm=-1: the impulse response is already scaled as intended.
        chain += f"[dry];[dry][{ir_input}:a]afir=irnorm=-1:irgain=1"
    return chain + "[voice]"


def background_source(sound: Sound, sounds_dir: Path) -> Tuple[List[str], Optional[str]]:
    """(extra ffmpeg input arguments, filter source producing stereo [bg_raw])."""
    if sound.background == "none":
        return [], None
    if sound.background.startswith("file:"):
        path = sounds_dir / sound.background[5:]
        if not path.is_file():
            raise RuntimeError(f"Background sound not found: {path.name}")
        # Looped for as long as the voice runs.
        return ["-stream_loop", "-1", "-i", str(path)], (
            f"aresample={OUTPUT_RATE},aformat=channel_layouts=stereo"
        )
    color, cutoff = NOISES[sound.background]
    side = (
        f"anoisesrc=color={color}:sample_rate={OUTPUT_RATE}:amplitude=0.5:seed={{seed}},"
        f"lowpass=f={cutoff}"
    )
    return [], (
        f"{side.format(seed=11)}[bgl];{side.format(seed=23)}[bgr];"
        f"[bgl][bgr]join=inputs=2:channel_layout=stereo"
    )


def finish(
    ffmpeg: str,
    voice_wav: Path,
    out_path: Path,
    duration: float,
    sound: Sound,
    work_dir: Path,
    sounds_dir: Path,
    title: str = "",
    on_progress: Optional[Callable[[str, float], None]] = None,
    cancelled: Callable[[], bool] = lambda: False,
) -> Dict:
    """
    Turn the voice track into the finished file at out_path, built as
    out_path + ".part" and renamed when complete. on_progress gets a phase
    ("measuring" or "mixing") and the fraction of it done.
    """
    out_path = Path(out_path)
    work_dir.mkdir(parents=True, exist_ok=True)
    report = (lambda phase: (lambda f: on_progress(phase, f))) if on_progress else (lambda p: None)

    room = ROOMS.get(sound.room)
    has_bg = sound.background != "none"
    stereo = bool(room) or has_bg
    inputs = ["-i", str(voice_wav)]
    ir_input = None
    if room:
        ir = work_dir / "room.wav"
        make_room_ir(ir, *room)
        inputs += ["-i", str(ir)]
        ir_input = 1
    chain = voice_chain(sound, stereo, ir_input)

    # Pass 1: how loud is the processed voice?
    log = run_ffmpeg(
        # dualmono: a mono file plays from both speakers or earpieces, so it is
        # heard 3 dB louder than the meter's one-speaker reading. Without it a
        # mono file and a stereo one at the same target would differ by 3 dB.
        [ffmpeg, *inputs, "-filter_complex",
         f"{chain};[voice]ebur128=framelog=quiet:dualmono={'false' if stereo else 'true'}[m]",
         "-map", "[m]", "-f", "null", "-"],
        duration, report("measuring"), cancelled,
    )
    measured = integrated_loudness(log)
    gain = (sound.loudness - measured) if sound.loudness is not None else 0.0
    voice_loudness = measured + gain

    graph = f"{chain};[voice]volume={gain:.2f}dB,aresample={OUTPUT_RATE}[v]"
    bg_inputs, bg_source = background_source(sound, sounds_dir)
    bg_loudness = None
    if bg_source:
        # The background is set relative to the voice, so measure it too. A
        # minute of it is enough: noise is steady, and a loop repeats itself.
        if bg_inputs:
            probe = [ffmpeg, "-t", "60", *bg_inputs[2:], "-filter_complex",
                     f"[0:a]{bg_source},ebur128=framelog=quiet[m]"]
        else:
            probe = [ffmpeg, "-filter_complex",
                     f"{bg_source},atrim=duration=60,ebur128=framelog=quiet[m]"]
        bg_loudness = integrated_loudness(
            run_ffmpeg([*probe, "-map", "[m]", "-f", "null", "-"], 0, None, cancelled)
        )
        bg_gain = voice_loudness + sound.background_level - bg_loudness
        bg_in = f"[{len(inputs) // 2}:a]" if bg_inputs else ""
        graph += (
            f";{bg_in}{bg_source},volume={bg_gain:.2f}dB[bg]"
            ";[v][bg]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[v]"
        )
        inputs += bg_inputs

    tail = []
    if sound.fade_in > 0:
        tail.append(f"afade=t=in:st=0:d={min(sound.fade_in, duration):.2f}")
    if sound.fade_out > 0:
        fade = min(sound.fade_out, duration)
        tail.append(f"afade=t=out:st={duration - fade:.2f}:d={fade:.2f}")
    # Catches the occasional peak that the gain pushed past the ceiling;
    # level=0 stops it turning everything else up to meet it.
    tail.append(f"alimiter=limit={10 ** (CEILING_DB / 20):.4f}:level=0:latency=1")
    graph += ";[v]" + ",".join(tail) + "[out]"

    fmt = sound.format
    codec = {
        "mp3": ["-c:a", "libmp3lame", "-b:a", f"{sound.bitrate}k"],
        "m4a": ["-c:a", aac_encoder(ffmpeg), "-b:a", f"{sound.bitrate}k"],
        "wav": ["-c:a", "pcm_s16le"],
    }[fmt]
    part = out_path.with_name(out_path.name + ".part")
    try:
        run_ffmpeg(
            [ffmpeg, "-y", *inputs, "-filter_complex", graph, "-map", "[out]",
             # The background input loops forever; the voice decides the length.
             "-t", f"{duration:.3f}",
             *codec, *(["-metadata", f"title={title}"] if title else []),
             "-f", FORMATS[fmt], str(part)],
            duration, report("mixing"), cancelled,
        )
        os.replace(part, out_path)
    finally:
        part.unlink(missing_ok=True)

    return {
        "voice_loudness": round(voice_loudness, 1),
        "measured_loudness": round(measured, 1),
        "background_loudness": round(bg_loudness, 1) if bg_loudness is not None else None,
        "channels": 2 if stereo else 1,
    }


_aac = {}


def aac_encoder(ffmpeg: str) -> str:
    """Apple's AAC encoder where ffmpeg has it (better at low bitrates), else ffmpeg's."""
    if ffmpeg not in _aac:
        try:
            out = subprocess.run(
                [ffmpeg, "-hide_banner", "-encoders"], capture_output=True, text=True, timeout=20
            ).stdout
        except Exception:
            out = ""
        _aac[ffmpeg] = "aac_at" if re.search(r"\saac_at\s", out) else "aac"
    return _aac[ffmpeg]


# Speed of each pass, as seconds of recording processed per second, measured
# on an Apple Silicon Mac. Only for the estimate shown before a render.
MEASURE_SPEED = 1500.0
MIX_SPEED = 120.0


def estimate_seconds(duration: float, sound: Sound) -> float:
    if not needs_finishing(sound):
        return 0.0
    return duration / MEASURE_SPEED + duration / MIX_SPEED
