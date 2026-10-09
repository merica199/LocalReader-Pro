#!/usr/bin/env python3
"""
sleepcast.py - turn plain-text scripts into long, calm, sleep-story audio.

The key idea: the TTS model only ever speaks ONE short sentence at a time.
Every pause is real silence inserted by this script, so pacing is exact and
consistent no matter which engine you use (that's what most TTS readers get wrong).

Script markup (plain .txt, UTF-8):
    blank line        paragraph break           (--para-pause, default 2.6 s)
    ... or the ellipsis character
                      soft pause mid-thought     (--ellipsis-pause, default 1.1 s)
    [pause 6]         explicit silence, in seconds
    # comment         lines starting with # are ignored
Sentence ends get --sentence-pause (default 1.0 s). Dashes and parentheses are
turned into commas, quotation marks are dropped, and over-long sentences are split
at ; : or , so the model never gets a sentence long enough to go off the rails.

Examples:
    # check pacing and estimated length without generating anything
    python sleepcast.py part1.txt part2.txt part3.txt --dry-run

    # render just the first 15 lines to tune the voice quickly
    python sleepcast.py part1.txt --preview 15 -o preview.mp3 --voice calm_ref.wav

    # full three-hour episode from three scripts
    python sleepcast.py part1.txt part2.txt part3.txt -o tonight.mp3 --voice calm_ref.wav

Every generated sentence is cached in .sleepcast_cache/, so if a long run crashes
or you Ctrl+C it, just run the same command again and it picks up where it left off.
Changing pauses, background, tempo or loudness reuses the cache (no regeneration).

Requirements: Python 3.10+, numpy, soundfile, ffmpeg on PATH, plus one engine:
    chatterbox  pip install chatterbox-tts        (local, GPU recommended, voice cloning)
    kokoro      pip install kokoro                (local, light; what Local Reader uses)
    elevenlabs  set ELEVENLABS_API_KEY, pass a voice ID with --voice (paid API)
    dummy       no install; beeps instead of speech, for testing timing
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf

# ---------------------------------------------------------------- script parsing

PAUSE_RE = re.compile(r"\[\s*pause\s+(\d+(?:\.\d+)?)\s*s?\s*\]", re.I)
ELLIPSIS_RE = re.compile(r"\s*(?:\.{3,}|\u2026)\s*")
END_PUNCT_RE = re.compile(r"[.!?,;:]$")
ABBREV = {"mr.", "mrs.", "ms.", "dr.", "st.", "mt.", "vs.", "etc.", "e.g.", "i.e.",
          "jr.", "sr.", "no.", "approx."}


def normalize(text):
    """Clean up punctuation that TTS engines tend to mangle."""
    text = text.replace("\u2026", "...")
    text = re.sub(r"[\u201c\u201d\u201e\"]", "", text)            # drop double quotes
    text = re.sub(r"[\u2018\u2019]", "'", text)                   # curly apostrophes
    text = re.sub(r"\s*(?:\u2014|\u2013|--)\s*", ", ", text)      # dashes -> commas
    text = re.sub(r"\s*[()\[\]{}]\s*", ", ", text)                # brackets -> commas
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)                  # no space before punct
    text = re.sub(r",(\s*,)+", ",", text)                         # ", ," -> ","
    text = re.sub(r",\s*([.!?;:])", r"\1", text)                  # ",." -> "."
    text = re.sub(r"^[,;:\s]+", "", text)
    return text.strip()


def split_sentences(text):
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", text) if p.strip()]
    out = []
    for p in parts:
        if out and out[-1].split()[-1].lower() in ABBREV:
            out[-1] += " " + p
        else:
            out.append(p)
    return out


def split_long(s, max_chars):
    """Split an over-long sentence at the clause boundary nearest its middle."""
    if len(s) <= max_chars:
        return [s]
    mid = len(s) / 2
    for pat in (r"[;:]\s+", r",\s+", r"\s+"):
        cuts = [m.end() for m in re.finditer(pat, s) if 0 < m.end() < len(s)]
        good = [c for c in cuts if min(c, len(s) - c) >= 20]
        cuts = good or (cuts if pat == r"\s+" else [])
        if cuts:
            c = min(cuts, key=lambda x: abs(x - mid))
            return split_long(s[:c].strip(), max_chars) + split_long(s[c:].strip(), max_chars)
    return [s]


def ensure_end(s, ch):
    return s if END_PUNCT_RE.search(s) else s + ch


def add_pause(events, secs, explicit=False):
    if secs <= 0 or (not events and not explicit):
        return
    if events and events[-1][0] == "pause":
        events[-1] = ("pause", max(events[-1][1], secs))
    else:
        events.append(("pause", secs))


def parse_script(raw, a):
    """Return a list of ("say", text) and ("pause", seconds) events."""
    events = []
    lines = [ln for ln in raw.replace("\r\n", "\n").split("\n") if not ln.lstrip().startswith("#")]
    for para in re.split(r"\n\s*\n", "\n".join(lines)):
        if not para.strip():
            continue
        for i, piece in enumerate(PAUSE_RE.split(para)):
            if i % 2 == 1:                                   # captured [pause N]
                add_pause(events, float(piece), explicit=True)
                continue
            phrases = [p for p in ELLIPSIS_RE.split(normalize(piece)) if p.strip()]
            for j, phrase in enumerate(phrases):
                if j > 0:
                    add_pause(events, a.ellipsis_pause)
                sentences = split_sentences(phrase)
                for k, sent in enumerate(sentences):
                    if k > 0:
                        add_pause(events, a.sentence_pause)
                    subs = split_long(sent, a.max_chars)
                    for m, sub in enumerate(subs):
                        if m > 0:
                            add_pause(events, a.clause_pause)
                        if not re.search(r"[A-Za-z0-9]", sub):
                            continue
                        trailing = m < len(subs) - 1 or (
                            k == len(sentences) - 1 and j < len(phrases) - 1)
                        events.append(("say", ensure_end(sub, "," if trailing else ".")))
        add_pause(events, a.para_pause)
    return events


# ---------------------------------------------------------------- TTS backends

def file_fingerprint(path):
    return hashlib.sha1(Path(path).read_bytes()).hexdigest()[:16]


class DummyBackend:
    """Beeps with roughly speech-like timing. Lets you test the pipeline with no model."""
    sr = 24000

    def __init__(self, a):
        pass

    def signature(self):
        return ["dummy"]

    def synth(self, text, attempt):
        n = int(self.sr * max(0.4, len(text) / 13.5))
        t = np.arange(n) / self.sr
        env = 0.5 - 0.5 * np.cos(2 * np.pi * t / t[-1])
        tone = np.sin(2 * np.pi * 180 * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 3 * t))
        return (0.3 * env * tone).astype(np.float32)


class ChatterboxBackend:
    def __init__(self, a):
        import torch
        from chatterbox.tts import ChatterboxTTS
        self.torch, self.a = torch, a
        dev = a.device or ("cuda" if torch.cuda.is_available()
                           else "mps" if torch.backends.mps.is_available() else "cpu")
        print(f"Loading Chatterbox on {dev} ...")
        self.model = ChatterboxTTS.from_pretrained(device=dev)
        self.sr = self.model.sr
        if a.voice:
            self.model.prepare_conditionals(a.voice, exaggeration=a.exaggeration)

    def signature(self):
        a = self.a
        voice = file_fingerprint(a.voice) if a.voice else None
        return ["chatterbox", voice, a.exaggeration, a.cfg_weight, a.temperature, a.seed]

    def synth(self, text, attempt):
        self.torch.manual_seed(self.a.seed + attempt)
        wav = self.model.generate(text, exaggeration=self.a.exaggeration,
                                  cfg_weight=self.a.cfg_weight, temperature=self.a.temperature)
        return wav.squeeze().detach().cpu().numpy().astype(np.float32)


class KokoroBackend:
    sr = 24000

    def __init__(self, a):
        from kokoro import KPipeline
        self.pipe = KPipeline(lang_code=a.kokoro_lang)
        self.voice, self.speed = a.voice or "af_heart", a.kokoro_speed

    def signature(self):
        return ["kokoro", self.voice, self.speed]

    def synth(self, text, attempt):
        parts = []
        for _, _, audio in self.pipe(text, voice=self.voice, speed=self.speed):
            if audio is not None:
                parts.append(audio.detach().cpu().numpy() if hasattr(audio, "detach") else np.asarray(audio))
        return np.concatenate(parts).astype(np.float32) if parts else np.zeros(0, np.float32)


class ElevenLabsBackend:
    sr = 24000

    def __init__(self, a):
        self.key = os.environ.get("ELEVENLABS_API_KEY")
        if not self.key:
            sys.exit("Set the ELEVENLABS_API_KEY environment variable.")
        if not a.voice:
            sys.exit("For elevenlabs, --voice must be an ElevenLabs voice ID.")
        self.a = a

    def signature(self):
        a = self.a
        return ["elevenlabs", a.voice, a.el_model, a.el_stability, a.el_similarity, a.el_speed]

    def synth(self, text, attempt):
        import urllib.error
        import urllib.request
        a = self.a
        body = json.dumps({
            "text": text,
            "model_id": a.el_model,
            "voice_settings": {"stability": a.el_stability, "similarity_boost": a.el_similarity,
                               "style": 0.0, "speed": a.el_speed},
        }).encode()
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{a.voice}?output_format=pcm_24000"
        for tries in range(6):
            req = urllib.request.Request(url, data=body, method="POST", headers={
                "xi-api-key": self.key, "Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    data = r.read()
                break
            except urllib.error.HTTPError as e:
                if e.code in (429, 500, 502, 503, 504) and tries < 5:
                    time.sleep(2 ** tries * 2)
                    continue
                raise RuntimeError(f"ElevenLabs error {e.code}: {e.read()[:300]!r}")
        return np.frombuffer(data, dtype="<i2").astype(np.float32) / 32768.0


BACKENDS = {"chatterbox": ChatterboxBackend, "kokoro": KokoroBackend,
            "elevenlabs": ElevenLabsBackend, "dummy": DummyBackend}
DEFAULT_TEMPO = {"chatterbox": 0.93, "kokoro": 1.0, "elevenlabs": 1.0, "dummy": 1.0}


# ---------------------------------------------------------------- audio helpers

def silence(secs, sr):
    return np.zeros(int(round(secs * sr)), np.float32)


def trim(a, sr, thresh_db=-42.0, pad=0.05):
    """Strip the uneven leading/trailing silence models add, so our pauses stay exact."""
    if a.size == 0:
        return a
    env = np.abs(a)
    idx = np.where(env > env.max() * 10 ** (thresh_db / 20))[0]
    if idx.size == 0:
        return a[:0]
    s, e = max(0, idx[0] - int(pad * sr)), min(a.size, idx[-1] + int(pad * sr))
    out = a[s:e].copy()
    f = min(int(0.012 * sr), out.size // 2)
    if f > 0:
        out[:f] *= np.linspace(0, 1, f)
        out[-f:] *= np.linspace(1, 0, f)
    return out


def level(a, target_db):
    """Even out sentence-to-sentence volume so nothing suddenly jumps out."""
    if a.size == 0:
        return a
    rms = float(np.sqrt(np.mean(a ** 2))) + 1e-9
    out = a * float(np.clip(10 ** (target_db / 20) / rms, 0.4, 2.5))
    peak = float(np.abs(out).max())
    return out * (0.95 / peak) if peak > 0.95 else out


def plausible(a, sr, text, cps):
    """Catch the classic long-form TTS failures: babbling, looping, or truncation."""
    dur, expect = a.size / sr, len(text) / cps
    if not np.isfinite(a).all():
        return False, "invalid samples"
    if dur > max(5.0, expect * 3.0):
        return False, f"too long ({dur:.1f}s, expected ~{expect:.1f}s)"
    if len(text) > 15 and dur < expect * 0.3:
        return False, f"too short ({dur:.1f}s, expected ~{expect:.1f}s)"
    return True, ""


def fmt(secs):
    secs = int(secs)
    return f"{secs // 3600}:{secs % 3600 // 60:02d}:{secs % 60:02d}"


# ---------------------------------------------------------------- rendering

def get_chunk(text, backend, a, cache_dir, sig):
    path = cache_dir / (hashlib.sha1(json.dumps([sig, text]).encode()).hexdigest() + ".npy")
    if path.exists():
        return np.load(path), True
    best, best_err = None, None
    for attempt in range(a.retries + 1):
        audio = trim(backend.synth(text, attempt), backend.sr)
        ok, why = plausible(audio, backend.sr, text, a.chars_per_sec)
        if ok:
            best = audio
            break
        err = abs(audio.size / backend.sr - len(text) / a.chars_per_sec)
        if best is None or err < best_err:
            best, best_err = audio, err
        print(f"    attempt {attempt + 1}: {why}" + (", retrying" if attempt < a.retries else ", keeping best"))
    np.save(path, best.astype(np.float32))
    return best, False


def render(events, backend, a, wav_path):
    sr, sig = backend.sr, backend.signature()
    cache = Path(a.cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    total = sum(1 for k, _ in events if k == "say")
    done = synth_n = written = 0
    synth_t = 0.0
    with sf.SoundFile(str(wav_path), "w", samplerate=sr, channels=1, subtype="PCM_16") as out:
        def put(x):
            nonlocal written
            out.write(x)
            written += len(x)

        put(silence(a.lead_in, sr))
        for kind, val in events:
            if kind == "pause":
                put(silence(val, sr))
                continue
            t0 = time.time()
            audio, cached = get_chunk(val, backend, a, cache, sig)
            if not cached:
                synth_n += 1
                synth_t += time.time() - t0
            done += 1
            put(level(audio, a.chunk_db))
            if not cached or done % 100 == 0 or done == total:
                eta = synth_t / synth_n * (total - done) if synth_n else 0
                print(f"[{done}/{total}] {fmt(written / sr)} of voice | ETA ~{fmt(eta)} | {val[:60]}")
        put(silence(a.tail, sr))
    return written / sr


def ffmpeg(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("ffmpeg failed:\n" + r.stderr[-2500:])
    return r


def finish(voice_wav, out, voice_secs, a):
    """Slow slightly, warm up the tone, add room + background, normalize, fade."""
    ff = shutil.which("ffmpeg")
    if not ff:
        print(f"ffmpeg not found; leaving the raw voice track at {voice_wav}")
        return False
    chain = []
    if abs(a.tempo - 1.0) > 1e-3:
        chain.append(f"atempo={a.tempo}")
    chain += ["highpass=f=60", f"lowpass=f={a.lowpass}"]
    if a.reverb:
        chain.append("aecho=0.85:0.9:60|97:0.16|0.10")
    pre = ",".join(chain)

    print("Measuring loudness ...")
    r = ffmpeg([ff, "-hide_banner", "-nostats", "-i", str(voice_wav), "-af",
                f"{pre},loudnorm=I={a.lufs}:TP=-3:LRA=11:print_format=json", "-f", "null", "-"])
    m = json.loads(r.stderr[r.stderr.rindex("{"):r.stderr.rindex("}") + 1])
    norm = (f"loudnorm=I={a.lufs}:TP=-3:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
            f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:"
            f"offset={m['target_offset']}:linear=true")

    cmd = [ff, "-y", "-hide_banner", "-nostats", "-i", str(voice_wav)]
    graph = f"[0:a]{pre},{norm},aresample=44100,aformat=channel_layouts=mono[v]"
    has_bg = bool(a.ambience) or a.noise != "none"
    if a.ambience:
        cmd += ["-stream_loop", "-1", "-i", a.ambience]
        graph += f";[1:a]aresample=44100,aformat=channel_layouts=mono,volume={a.bg_db}dB[b]"
    elif a.noise != "none":
        cmd += ["-f", "lavfi", "-i", f"anoisesrc=color={a.noise}:sample_rate=44100:amplitude=0.6"]
        graph += f";[1:a]lowpass=f=900,volume={a.bg_db}dB[b]"
    if has_bg:
        graph += ";[v][b]amix=inputs=2:duration=first:normalize=0[m]"
    dur = voice_secs / a.tempo
    fade = min(a.fade_out, dur / 4)
    graph += (f";{'[m]' if has_bg else '[v]'}afade=t=in:d=4,"
              f"afade=t=out:st={max(0.0, dur - fade):.2f}:d={fade:.2f}[out]")
    cmd += ["-filter_complex", graph, "-map", "[out]"]
    ext = out.suffix.lower()
    if ext == ".mp3":
        cmd += ["-c:a", "libmp3lame", "-b:a", "96k"]
    elif ext in (".m4a", ".aac"):
        cmd += ["-c:a", "aac", "-b:a", "96k"]
    cmd.append(str(out))
    print("Mixing and encoding ...")
    ffmpeg(cmd)
    return True


# ---------------------------------------------------------------- CLI

def parse_args():
    p = argparse.ArgumentParser(description="Generate sleep-story audio from text scripts.",
                                formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("scripts", nargs="+", help="one or more .txt scripts, joined in order")
    p.add_argument("-o", "--out", default="sleepcast.mp3", help="output file (.mp3, .m4a or .wav)")
    p.add_argument("--backend", choices=BACKENDS, default="chatterbox")
    p.add_argument("--voice", help="chatterbox: reference .wav to clone (10-20 s of calm speech); "
                                   "kokoro: voice name; elevenlabs: voice ID")
    g = p.add_argument_group("pacing (seconds)")
    g.add_argument("--sentence-pause", type=float, default=1.0)
    g.add_argument("--para-pause", type=float, default=2.6)
    g.add_argument("--ellipsis-pause", type=float, default=1.1)
    g.add_argument("--clause-pause", type=float, default=0.3, help="between pieces of a split long sentence")
    g.add_argument("--file-pause", type=float, default=6.0, help="between script files")
    g.add_argument("--lead-in", type=float, default=3.0)
    g.add_argument("--tail", type=float, default=8.0)
    g.add_argument("--max-chars", type=int, default=220, help="longest piece sent to the model at once")
    g = p.add_argument_group("sound")
    g.add_argument("--tempo", type=float, help="time-stretch the voice (pauses stretch too); "
                                               "default 0.93 for chatterbox, 1.0 otherwise")
    g.add_argument("--lowpass", type=int, default=8500, help="Hz; lower = darker, softer voice")
    g.add_argument("--no-reverb", dest="reverb", action="store_false")
    g.add_argument("--noise", choices=["brown", "pink", "white", "none"], default="brown")
    g.add_argument("--ambience", help="audio file to loop underneath instead of noise (rain, waves...)")
    g.add_argument("--bg-db", type=float, default=-20.0, help="background level adjustment in dB (higher = louder)")
    g.add_argument("--lufs", type=float, default=-22.0, help="target loudness of the voice")
    g.add_argument("--chunk-db", type=float, default=-23.0, help="per-sentence RMS leveling target")
    g.add_argument("--fade-out", type=float, default=45.0)
    g = p.add_argument_group("chatterbox")
    g.add_argument("--device", help="cuda / mps / cpu (auto if omitted)")
    g.add_argument("--exaggeration", type=float, default=0.3, help="lower = calmer delivery")
    g.add_argument("--cfg-weight", type=float, default=0.3, help="lower = slower, more deliberate pacing")
    g.add_argument("--temperature", type=float, default=0.7)
    g.add_argument("--seed", type=int, default=7)
    g = p.add_argument_group("kokoro")
    g.add_argument("--kokoro-lang", default="a", help="a = American English, b = British English")
    g.add_argument("--kokoro-speed", type=float, default=0.9)
    g = p.add_argument_group("elevenlabs")
    g.add_argument("--el-model", default="eleven_multilingual_v2")
    g.add_argument("--el-stability", type=float, default=0.75)
    g.add_argument("--el-similarity", type=float, default=0.75)
    g.add_argument("--el-speed", type=float, default=0.9)
    g = p.add_argument_group("run")
    g.add_argument("--dry-run", action="store_true", help="show the plan and estimated length; no audio")
    g.add_argument("--preview", type=int, metavar="N", help="only render the first N spoken pieces")
    g.add_argument("--retries", type=int, default=2, help="regenerate a sentence that comes out wrong")
    g.add_argument("--chars-per-sec", type=float, default=13.0, help="speaking-rate estimate for checks")
    g.add_argument("--cache-dir", default=".sleepcast_cache")
    g.add_argument("--keep-wav", action="store_true", help="keep the raw voice-only .wav")
    return p.parse_args()


def main():
    a = parse_args()
    if a.tempo is None:
        a.tempo = DEFAULT_TEMPO[a.backend]

    per_file, events = [], []
    for i, f in enumerate(a.scripts):
        ev = parse_script(Path(f).read_text(encoding="utf-8"), a)
        per_file.append((f, ev))
        if i > 0:
            add_pause(events, a.file_pause)
        for kind, val in ev:
            add_pause(events, val, explicit=True) if kind == "pause" else events.append((kind, val))
    while events and events[-1][0] == "pause":
        events.pop()
    if not events:
        sys.exit("No speakable text found.")

    def estimate(ev):
        speech = sum(len(v) for k, v in ev if k == "say") / a.chars_per_sec
        pauses = sum(v for k, v in ev if k == "pause")
        return (speech + pauses) / a.tempo

    if a.dry_run:
        for f, ev in per_file:
            says = [v for k, v in ev if k == "say"]
            words = sum(len(s.split()) for s in says)
            print(f"{f}: {len(says)} pieces, {words} words, ~{fmt(estimate(ev))} estimated")
        print(f"TOTAL: ~{fmt(estimate(events) + (a.lead_in + a.tail) / a.tempo)} estimated "
              f"(rough; calibrate --chars-per-sec after a preview)")
        plan = Path(a.out).with_suffix(".plan.txt")
        plan.write_text("\n".join(f"say   {v}" if k == "say" else f"      ... {v:.1f}s"
                                  for k, v in events), encoding="utf-8")
        print(f"Full sentence-by-sentence plan written to {plan}")
        return

    if a.preview:
        n, cut = 0, len(events)
        for i, (k, _) in enumerate(events):
            n += k == "say"
            if n == a.preview:
                cut = i + 1
                break
        events = events[:cut]

    backend = BACKENDS[a.backend](a)
    out = Path(a.out)
    wav = out.with_suffix(".voice.wav")
    t0 = time.time()
    voice_secs = render(events, backend, a, wav)
    if finish(wav, out, voice_secs, a):
        if not a.keep_wav:
            wav.unlink()
        print(f"Done: {out}  ({fmt(voice_secs / a.tempo)} long, took {fmt(time.time() - t0)})")


if __name__ == "__main__":
    main()
