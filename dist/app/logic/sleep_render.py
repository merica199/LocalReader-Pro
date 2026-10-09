"""
Render a sleep-recording plan to a WAV file, one sentence at a time.

Three hours of 24 kHz speech is about 500 MB even as 16-bit samples, so nothing
here holds the recording: each sentence and each silence is written to the file
as soon as it exists, and memory never holds more than one sentence.

Every sentence is cached on disk as it is generated. A render that crashes or is
cancelled picks up where it stopped the next time the same document is
exported, and re-exporting with different pauses regenerates nothing.
"""
import hashlib
import json
import os
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
import soundfile as sf

try:
    from logic.sleep_script import Event, Pacing, ensure_end, split_middle
except ImportError:
    from sleep_script import Event, Pacing, ensure_end, split_middle

SAMPLE_RATE = 24000
# Per-sentence loudness target, as RMS in dB below full scale. Leveling every
# sentence to the same loudness is what stops one from jumping out of the dark.
LEVEL_DB = -23.0
# Measured on the int8 model with af_heart: 16.3 to 20.0 characters per second
# at speed 1.0 (mean 18.0), 15.1 to 19.3 at 0.9. The reference script's 13 was a
# figure for a different engine.
CHARS_PER_SECOND_AT_1X = 18.0
# Bump when trim() or the stored format changes, so stale audio is not reused.
CACHE_VERSION = 1

Synth = Callable[[str], np.ndarray]


class Cancelled(Exception):
    pass


def silence(seconds: float) -> np.ndarray:
    return np.zeros(int(round(seconds * SAMPLE_RATE)), np.float32)


def trim(audio: np.ndarray, thresh_db: float = -42.0, pad: float = 0.05) -> np.ndarray:
    """
    Strip the silence the model leaves at each end, so the inserted pauses are
    the real gaps. Kokoro leaves 0.03 to 0.05 s before speech and 0.07 to
    0.25 s after it, varying sentence to sentence.
    """
    if audio.size == 0:
        return audio
    env = np.abs(audio)
    loud = np.where(env > env.max() * 10 ** (thresh_db / 20))[0]
    if loud.size == 0 or env.max() == 0:
        return audio[:0]
    start = max(0, loud[0] - int(pad * SAMPLE_RATE))
    end = min(audio.size, loud[-1] + int(pad * SAMPLE_RATE))
    out = audio[start:end].astype(np.float32, copy=True)
    # A 12 ms fade at each cut, so cutting mid-waveform does not click.
    fade = min(int(0.012 * SAMPLE_RATE), out.size // 2)
    if fade > 0:
        out[:fade] *= np.linspace(0, 1, fade, dtype=np.float32)
        out[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)
    return out


def level(audio: np.ndarray, target_db: float = LEVEL_DB) -> np.ndarray:
    if audio.size == 0:
        return audio
    rms = float(np.sqrt(np.mean(audio.astype(np.float64) ** 2))) + 1e-9
    # Bounded, so a sentence that is mostly breath is not boosted into hiss.
    out = audio * float(np.clip(10 ** (target_db / 20) / rms, 0.4, 2.5))
    peak = float(np.abs(out).max())
    return out * (0.95 / peak) if peak > 0.95 else out


def plausible(audio: np.ndarray, text: str, chars_per_second: float) -> Tuple[bool, str]:
    """Does this look like the text spoken once, at roughly the expected length?"""
    duration, expected = audio.size / SAMPLE_RATE, len(text) / chars_per_second
    if audio.size == 0:
        # Kokoro returns a tenth of a second of silence when synthesis throws,
        # which trims to nothing.
        return False, "no audio"
    if not np.isfinite(audio).all():
        return False, "invalid samples"
    if duration > max(5.0, expected * 3.0):
        return False, f"too long ({duration:.1f}s, expected ~{expected:.1f}s)"
    if len(text) > 15 and duration < expected * 0.3:
        return False, f"too short ({duration:.1f}s, expected ~{expected:.1f}s)"
    return True, ""


def speak(text: str, synth: Synth, chars_per_second: float, clause_pause: float) -> Tuple[np.ndarray, str]:
    """
    Synthesize one piece and check it, returning (audio, problem).

    Kokoro is deterministic: the same text returns the same samples every time,
    so asking again for a bad result returns the same bad result. A failed piece
    is retried instead as two halves split at its middle clause, which is
    different input. Whichever attempt lands nearest the expected length is
    kept. problem is empty when the first attempt was fine.
    """
    audio = trim(synth(text))
    ok, problem = plausible(audio, text, chars_per_second)
    if ok:
        return audio, ""

    attempts = [audio]
    halves = split_middle(text)
    if halves:
        first = trim(synth(ensure_end(halves[0], ",")))
        second = trim(synth(halves[1]))
        joined = np.concatenate([first, silence(clause_pause), second])
        if plausible(joined, text, chars_per_second)[0]:
            return joined, problem
        attempts.append(joined)

    expected = len(text) / chars_per_second
    best = min(attempts, key=lambda a: abs(a.size / SAMPLE_RATE - expected))
    return best, problem


class SentenceCache:
    """
    One file per spoken piece, keyed by everything that changes its sound.

    Stored trimmed but before leveling, as 16-bit samples: leveling can then
    change without regenerating anything, and 16-bit halves the disk cost
    (about 170 MB per hour of speech).
    """

    def __init__(self, directory: Path, signature: List):
        self.directory = Path(directory)
        self.signature = [CACHE_VERSION, *signature]

    def path(self, text: str) -> Path:
        key = hashlib.sha1(json.dumps([self.signature, text]).encode("utf-8")).hexdigest()
        return self.directory / f"{key}.npy"

    def get(self, text: str) -> Optional[np.ndarray]:
        path = self.path(text)
        if not path.exists():
            return None
        try:
            return np.load(path).astype(np.float32) / 32767.0
        except Exception:
            # A damaged entry is worth one regeneration, not a failed render.
            return None

    def put(self, text: str, audio: np.ndarray) -> np.ndarray:
        """
        Store audio and return it exactly as get() will return it later, so a
        sentence sounds identical whether it was just generated or loaded on a
        resumed render.
        """
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.path(text)
        samples = (np.clip(audio, -1.0, 1.0) * 32767.0).astype(np.int16)
        # Written aside and renamed into place, so a crash mid-write cannot
        # leave a truncated entry that a resumed render would trust.
        tmp = path.with_name(path.name + ".tmp")
        with open(tmp, "wb") as f:
            np.save(f, samples)
        os.replace(tmp, path)
        return samples.astype(np.float32) / 32767.0


def cache_usage(directory: Path) -> Dict[str, int]:
    files = list(Path(directory).glob("*.npy")) if Path(directory).exists() else []
    return {"files": len(files), "bytes": sum(f.stat().st_size for f in files)}


def clear_cache(directory: Path) -> Dict[str, int]:
    usage = cache_usage(directory)
    if Path(directory).exists():
        for f in Path(directory).iterdir():
            if f.suffix in (".npy", ".tmp"):
                f.unlink(missing_ok=True)
    return usage


def render(
    events: List[Event],
    synth: Synth,
    out_path: Path,
    cache: SentenceCache,
    pacing: Pacing = Pacing(),
    chars_per_second: float = CHARS_PER_SECOND_AT_1X,
    on_progress: Optional[Callable[[int, int, float], None]] = None,
    cancelled: Callable[[], bool] = lambda: False,
) -> Dict:
    """
    Write the plan to out_path. The file is built as out_path + ".part" and
    renamed only when complete, so a crash never leaves a file that looks done.
    """
    out_path = Path(out_path)
    part = out_path.with_name(out_path.name + ".part")
    total = sum(1 for kind, _ in events if kind == "say")
    done = generated = retried = written = 0
    problems: List[str] = []

    try:
        # format is explicit: soundfile infers it from the extension, and
        # ".part" is not one it knows.
        with sf.SoundFile(
            str(part), "w", samplerate=SAMPLE_RATE, channels=1, format="WAV", subtype="PCM_16"
        ) as out:

            def put(samples: np.ndarray) -> None:
                nonlocal written
                out.write(samples)
                written += samples.size

            put(silence(pacing.lead_in))
            for kind, value in events:
                if cancelled():
                    raise Cancelled()
                if kind == "pause":
                    put(silence(value))
                    continue
                audio = cache.get(value)
                if audio is None:
                    audio, problem = speak(value, synth, chars_per_second, pacing.clause)
                    audio = cache.put(value, audio)
                    generated += 1
                    if problem:
                        retried += 1
                        problems.append(f"{problem}: {value[:60]}")
                done += 1
                put(level(audio))
                if on_progress:
                    on_progress(done, total, written / SAMPLE_RATE)
            put(silence(pacing.tail))
        os.replace(part, out_path)
    except BaseException:
        part.unlink(missing_ok=True)
        raise

    return {
        "seconds": written / SAMPLE_RATE,
        "pieces": total,
        "generated": generated,
        "retried": retried,
        "problems": problems,
    }
