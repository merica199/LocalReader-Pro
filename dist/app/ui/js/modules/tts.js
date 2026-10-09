import { state } from "./state.js";
import { fetchJSON, fetchBlob, API_URL } from "./api.js";
import { showToast, stripHTML, renderIcons } from "./ui.js";
import { renderPage, getSentencesForPage, endsParagraph } from "./library.js";

// The output device can change out from under a live AudioContext: the machine
// sleeps and wakes, headphones are unplugged, a Bluetooth device connects. WebKit
// keeps the context bound to the device it was created against, so it stays
// "running", keeps firing ended events and advancing the text, and plays to
// nothing at all. An <audio> element follows the system default instead, which is
// why voice previews keep working while reading goes silent, and why changing the
// voice does not help but restarting the app does.
//
// A suspended context is a different failure and looks different: its clock stops
// and the text stops advancing with it. Text advancing without sound means the
// device went away, not that the context was suspended.
let audioDeviceStale = false;
let lastPlaybackStartedAt = 0;

if (navigator.mediaDevices && navigator.mediaDevices.addEventListener) {
  navigator.mediaDevices.addEventListener("devicechange", () => {
    audioDeviceStale = true;
    console.log("[WebAudio] Output devices changed; will rebuild context on next start");
  });
}

function buildAudioContext() {
  const Ctor = window.AudioContext || window.webkitAudioContext;
  state.audioContext = new Ctor();
  audioDeviceStale = false;
  try {
    state.audioContext.addEventListener("statechange", () =>
      console.log(`[WebAudio] context state -> ${state.audioContext.state}`),
    );
  } catch (e) {}
  console.log("[WebAudio] AudioContext initialized");
}

export function resetAudioContext() {
  const previous = state.audioContext;
  const previousRate = previous ? previous.sampleRate : null;
  state.currentAudioSource = null;
  buildAudioContext();
  // An AudioBuffer is not tied to the context that decoded it, so the cache can
  // survive a rebuild -- which is what makes rebuilding cheap enough to do on
  // every play. It only has to be dropped if the new context came up at a
  // different sample rate, where the old buffers would play at the wrong pitch.
  if (previousRate !== null && previousRate !== state.audioContext.sampleRate) {
    state.audioBufferCache.clear();
    console.log("[WebAudio] sample rate changed; audio cache cleared");
  }
  if (previous && previous.state !== "closed") {
    try { previous.close(); } catch (e) {}
  }
  console.log("[WebAudio] AudioContext rebuilt");
}

export function initAudioContext() {
  if (!state.audioContext || state.audioContext.state === "closed") {
    buildAudioContext();
  }
  // Not `=== "suspended"`: WebKit also reports "interrupted", which that check
  // silently skips, leaving the context unresumed.
  if (state.audioContext.state !== "running") {
    const r = state.audioContext.resume();
    if (r && r.catch) r.catch(() => {});
  }
}

// Use this wherever the user explicitly starts playback. Pressing play is what
// someone does when the sound has stopped, so it is the right place to recover a
// context whose output device has gone away.
export function ensureAudioContextForPlayback() {
  // Rebuild unconditionally. There is no way to ask a context whether its audio
  // is actually reaching a speaker -- a context bound to a departed output
  // device still reports "running" and still fires its ended events -- so the
  // failure cannot be detected, only pre-empted. Pressing play is exactly what
  // someone does when the sound has stopped, and with the buffer cache
  // surviving the swap a rebuild costs almost nothing, so it happens every time
  // rather than waiting on a heuristic.
  resetAudioContext();
  initAudioContext();
  lastPlaybackStartedAt = Date.now();
}

// A copy of the buffer with silence on the end, for the pause after a
// paragraph. Putting the pause in the audio, rather than waiting on a timer
// before the next sentence, keeps it inside the ended-event chain the race
// guards already cover: a timer still pending after a jump would start a
// second playback.
function withTrailingSilence(buffer, seconds) {
  const out = state.audioContext.createBuffer(
    buffer.numberOfChannels,
    buffer.length + Math.round(seconds * buffer.sampleRate),
    buffer.sampleRate,
  );
  for (let c = 0; c < buffer.numberOfChannels; c++) {
    out.getChannelData(c).set(buffer.getChannelData(c));
  }
  return out;
}

export function playAudioBuffer(audioBuffer, trailingSilence = 0) {
  if (state.currentAudioSource) {
    try {
      // Detaching onended BEFORE stop() is required, not tidiness. stop()
      // fires the ended event, so leaving the handler attached makes the
      // outgoing source run the "sentence finished" path on its way out:
      // currentSentenceIndex++ and another playNext(). The result is a second
      // playback racing the one being started here -- audible as two sentences
      // overlapping -- plus a skipped sentence from the extra increment.
      // stopPlayback() and jumpToSentence() already do this.
      state.currentAudioSource.onended = null;
      state.currentAudioSource.stop();
      state.currentAudioSource.disconnect();
    } catch (e) {}
  }

  // Create new source node
  const source = state.audioContext.createBufferSource();
  source.buffer =
    trailingSilence > 0 ? withTrailingSilence(audioBuffer, trailingSilence) : audioBuffer;
  source.connect(state.audioContext.destination);

  source.onended = async () => {
    state.currentAudioSource = null;
    state.currentSentenceIndex++;
    console.log(`Sentence ended, moving to ${state.currentSentenceIndex}`);
    // playNext() restarts read-ahead once the next sentence is playing.
    await playNext();
  };

  state.currentAudioSource = source;
  source.start(0);
  console.log(`[WebAudio] Playing buffer: ${audioBuffer.duration.toFixed(2)}s`);
}

export function stopPlayback() {
  state.isPlaying = false;
  // Update UI directly for speed
  const playIcon = document.getElementById("playIcon");
  if (playIcon) {
    playIcon.setAttribute("data-lucide", "play");
    renderIcons();
  }

  if (state.currentAudioSource) {
    try {
      state.currentAudioSource.onended = null; // Prevent triggering 'playNext' on stop
      state.currentAudioSource.stop();
      state.currentAudioSource.disconnect();
    } catch (e) {}
    state.currentAudioSource = null;
  }
}

// Incremented on every playNext() entry. Each call keeps its own token and must
// still hold the newest one to be allowed to start audio. The sentence-index
// check alone is not enough: two calls can share a target index (a natural
// ended-event landing at the same moment as a jump timer, say) and both pass it,
// so both start playback and the sentences are heard on top of each other.
let playToken = 0;

export async function playNext() {
  const myToken = ++playToken;
  const targetIndex = state.currentSentenceIndex;
  if (!state.isPlaying || !window.isEngineReady) {
    // isEngineReady is global/window for now
    stopPlayback();
    return;
  }

  const text = state.readingSentences[state.currentSentenceIndex];
  if (!text || typeof text !== "string") {
    if (state.readingPageIndex < state.currentPages.length - 1) {
      state.readingPageIndex++;
      state.currentSentenceIndex = 0;
      // The cache is not cleared here. It used to be, to prevent stale
      // cross-page hits, which also threw away the next page's audio that
      // read-ahead had just generated. Keys now include the sentence text and
      // settings (see audioKey), so a stale hit cannot happen.
      state.readingSentences = await getSentencesForPage(
        state.readingPageIndex,
      );

      // If auto-scroll is on, force the view to follow the reader
      if (state.autoScrollEnabled) {
        state.viewPageIndex = state.readingPageIndex;
        await renderPage();
      } else if (state.viewPageIndex === state.readingPageIndex) {
        // If we aren't following but happen to be viewing the same page, just refresh highlights
        await renderPage();
      }
      await playNext();
    } else {
      stopPlayback();
    }
    return;
  }

  // Update UI Highlight (only if viewing the reading page)
  if (state.viewPageIndex === state.readingPageIndex) {
    state.sentenceElements.forEach(
      (el, i) =>
        (el.className = `sentence ${i === state.currentSentenceIndex ? "active-sentence" : ""}`),
    );
    const active = state.sentenceElements[state.currentSentenceIndex];
    if (active && state.autoScrollEnabled)
      active.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  const currentSentencePreview = document.getElementById(
    "currentSentencePreview",
  );
  if (currentSentencePreview)
    currentSentencePreview.textContent = stripHTML(text);

  saveProgress();

  const cleanText = stripHTML(text);
  console.log(
    `Synthesizing sentence ${state.currentSentenceIndex}: "${cleanText.substring(0, 30)}..."`,
  );

  const pageIndex = state.readingPageIndex;
  const trailingSilence = paragraphPauseAfter(pageIndex, targetIndex, text);
  const cached = state.audioBufferCache.get(audioKey(pageIndex, targetIndex, text));

  if (cached) {
    // The page-advance branch above awaits, so even the cache-hit path can be
    // reached after a newer call has taken over.
    if (myToken !== playToken) {
      console.log(`[TTS] Discarding cache hit - superseded`);
      return;
    }
    console.log(`[WebAudio] CACHE HIT - Playing cached buffer instantly`);
    initAudioContext(); // this path never went through the synthesis branch
    playAudioBuffer(cached, trailingSilence);
    readAhead();
    return;
  }

  try {
    // Joins the request if read-ahead is already generating this sentence.
    const audioBuffer = await requestAudio(pageIndex, targetIndex, text);

    // Generating and decoding are async, so the state can move on before we
    // get here: a page turn or a click on another sentence lands in that
    // window. Re-check against the same target rather than starting audio the
    // reader has already moved past. The audio stays cached either way: the
    // work is done, and it stays useful on the way back.
    if (
      !state.isPlaying ||
      state.readingPageIndex !== pageIndex ||
      state.currentSentenceIndex !== targetIndex ||
      myToken !== playToken
    ) {
      console.log(
        `[TTS] Discarding decoded audio - superseded (index ${state.currentSentenceIndex} vs ${targetIndex}, token ${myToken} vs ${playToken})`,
      );
      return;
    }

    playAudioBuffer(audioBuffer, trailingSilence);
    readAhead();
  } catch (e) {
    console.error("Synthesis error:", e);
    showToast(e.message);
    stopPlayback();
  }
}

export function togglePlayback() {
  const playIcon = document.getElementById("playIcon");
  if (state.isPlaying) {
    stopPlayback();
  } else {
    ensureAudioContextForPlayback();
    state.isPlaying = true;
    if (playIcon) {
      playIcon.setAttribute("data-lucide", "pause");
      renderIcons();
    }
    playNext();
  }
}

export async function jumpToSentence(i) {
  // 1. Stop current audio immediately and kill its listeners
  if (state.currentAudioSource) {
    try {
      state.currentAudioSource.onended = null;
      state.currentAudioSource.stop();
      state.currentAudioSource.disconnect();
    } catch (e) {}
    state.currentAudioSource = null;
  }

  // 2. Clear existing jump timer to prevent overlapping jumps
  if (state.jumpTimer) {
    clearTimeout(state.jumpTimer);
    state.jumpTimer = null;
  }

  state.currentSentenceIndex = i;
  await renderPage(); // Update UI highlight and content

  // Ensure state reflects that we are intended to be playing
  if (!state.isPlaying) {
    ensureAudioContextForPlayback();
    state.isPlaying = true;
    const playIcon = document.getElementById("playIcon");
    if (playIcon) {
      playIcon.setAttribute("data-lucide", "pause");
      renderIcons();
    }
  }

  // Generate during the wait below instead of after it. The wait lets a run of
  // clicks or arrow presses settle on one sentence; it used to pass with
  // nothing happening, so the new sentence started generating only once it
  // was over.
  readAhead();

  // 3. Buffer for 2 seconds then start playing
  console.log(`[TTS] Buffering 2 seconds for jump to index ${i}...`);
  state.jumpTimer = setTimeout(() => {
    state.jumpTimer = null;
    playNext();
  }, 2000);
}

export async function saveProgress() {
  if (state.currentDoc) {
    // Optimistic UI
    const statusEl = document.getElementById("bookmarkStatus");
    if (statusEl) {
      statusEl.classList.remove("opacity-0");
      statusEl.classList.add("animate-pulse");
      setTimeout(() => {
        statusEl.classList.remove("animate-pulse");
        // Optional: Fade out after 2s if desired, or keep it visible as "Last saved..."
      }, 1000);
    }

    try {
      await fetchJSON(`/api/library`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...state.currentDoc,
          currentPage: state.readingPageIndex,
          lastSentenceIndex: state.currentSentenceIndex,
          lastAccessed: Date.now(),
        }),
      });
    } catch (e) {
      console.error("Save progress failed", e);
    }
  }
}

// --- Read-ahead -------------------------------------------------------------
// Generation runs ahead of playback by time, not by sentence count. It used to
// generate two sentences ahead, which is only a few seconds of audio when they
// are short, while a long sentence behind them takes about ten seconds to
// generate (Kokoro runs at roughly 1.4 to 2 times real time). Measured: 7 to 12
// seconds of silence every time two short sentences came before a long one.
const READ_AHEAD_SECONDS = 30;
// Also capped in sentences, so a run of very short ones cannot queue up work
// that jumping elsewhere would throw away.
const READ_AHEAD_MAX_SENTENCES = 12;
let readAheadRunning = false;

// Sentences being generated right now, by key. Playback that reaches a
// sentence read-ahead is still generating waits for that request rather than
// sending a second one.
const pendingAudio = new Map();

// The paragraph pause is added by the client after the clip, so it is not sent
// to the server, where it would only split the server's cache.
function serverPauseSettings() {
  const { paragraph, ...rest } = state.pauseSettings;
  return rest;
}

// Everything that changes a sentence's audio, including its text. A key can
// therefore never return audio for different words or old settings, which is
// what lets audio survive a page turn instead of being thrown away at each one.
function audioKey(pageIndex, sentenceIndex, text) {
  return JSON.stringify([
    pageIndex,
    sentenceIndex,
    document.getElementById("voiceSelect").value,
    document.getElementById("speedRange").value,
    serverPauseSettings(),
    state.rules,
    state.ignoreList,
    text,
  ]);
}

function cacheAudio(key, audioBuffer) {
  state.audioBufferCache.delete(key);
  state.audioBufferCache.set(key, audioBuffer);
  // Oldest first, which is behind the reader: read-ahead only adds ahead of it.
  while (state.audioBufferCache.size > state.MAX_AUDIO_CACHE) {
    state.audioBufferCache.delete(state.audioBufferCache.keys().next().value);
  }
}

function requestAudio(pageIndex, sentenceIndex, text) {
  const key = audioKey(pageIndex, sentenceIndex, text);
  const cached = state.audioBufferCache.get(key);
  if (cached) return Promise.resolve(cached);
  if (pendingAudio.has(key)) return pendingAudio.get(key);

  const request = (async () => {
    const res = await fetch(`${API_URL}/api/synthesize`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text: stripHTML(text),
        voice: document.getElementById("voiceSelect").value,
        speed: parseFloat(document.getElementById("speedRange").value),
        rules: state.rules,
        ignore_list: state.ignoreList,
        pause_settings: serverPauseSettings(),
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Synthesis failed");
    }
    const arrayBuffer = await (await res.blob()).arrayBuffer();
    initAudioContext();
    const audioBuffer = await state.audioContext.decodeAudioData(arrayBuffer);
    cacheAudio(key, audioBuffer);
    return audioBuffer;
  })();
  pendingAudio.set(key, request);
  request.catch(() => {}).finally(() => pendingAudio.delete(key));
  return request;
}

// The first sentence without audio yet, starting from the current one, or null
// once `seconds` of audio past the current sentence is ready. Looks at most one
// page ahead.
async function nextSentenceToGenerate(seconds) {
  let pageIndex = state.readingPageIndex;
  let sentences = state.readingSentences || [];
  let index = state.currentSentenceIndex;
  let ahead = 0;
  let count = 0;
  while (ahead < seconds && count < READ_AHEAD_MAX_SENTENCES) {
    if (index >= sentences.length) {
      if (pageIndex !== state.readingPageIndex || pageIndex >= state.currentPages.length - 1) {
        return null;
      }
      pageIndex += 1;
      index = 0;
      try {
        sentences = await getSentencesForPage(pageIndex);
      } catch (e) {
        return null;
      }
      continue;
    }
    const text = sentences[index];
    if (text && typeof text === "string") {
      const buffer = state.audioBufferCache.get(audioKey(pageIndex, index, text));
      if (!buffer) return { pageIndex, index, text };
      if (pageIndex !== state.readingPageIndex || index > state.currentSentenceIndex) {
        ahead += buffer.duration;
        count += 1;
      }
    }
    index += 1;
  }
  return null;
}

// Keeps generating until enough audio is ready ahead of the reader. Safe to
// call any time: only one loop runs, and it re-reads the reading position on
// every pass, so a jump or a page turn simply redirects it.
async function readAhead() {
  if (readAheadRunning) return;
  readAheadRunning = true;
  try {
    while (state.isPlaying || warming) {
      const next = await nextSentenceToGenerate(
        state.isPlaying ? READ_AHEAD_SECONDS : WARM_UP_SECONDS,
      );
      if (!next) break;
      try {
        await requestAudio(next.pageIndex, next.index, next.text);
      } catch (e) {
        // Playback reports it if it reaches that sentence.
        console.error("[ReadAhead] Generation failed:", e);
        break;
      }
    }
  } finally {
    readAheadRunning = false;
    warming = false;
  }
}

// --- Warm-up -------------------------------------------------------------------
// Pressing play used to be the first moment anything was generated. With short
// sentences first and a long one soon after, playback caught up with the
// generator and stopped for several seconds (measured: 4.6 s) before the long
// one. Opening a document is a strong sign that play comes next, so the start
// of what play would read is generated then, while nothing is playing. It is
// the read-ahead loop with a smaller budget, so pressing play mid-warm-up
// carries straight on, and play finds the audio in the same cache.
const WARM_UP_SECONDS = 20;
let warming = false;
let warmUpTimer = null;

export function warmUp() {
  clearTimeout(warmUpTimer);
  // A moment's wait, so clicking through documents or dragging a setting does
  // not start generating for each one on the way.
  warmUpTimer = setTimeout(() => {
    if (state.isPlaying || !state.currentDoc || !window.isEngineReady) return;
    warming = true;
    readAhead();
  }, 1000);
}

// --- Paragraph pause ---------------------------------------------------------
// For settings saved before the paragraph pause existed.
const DEFAULT_PARAGRAPH_PAUSE_MS = 1200;
// The server already ends each clip with the pause for its final mark, so a
// paragraph only needs the difference added.
const END_MARK_PAUSE = {
  ".": "period", "\u3002": "period",
  "?": "question", "\uff1f": "question",
  "!": "exclamation", "\uff01": "exclamation",
};

function paragraphPauseAfter(pageIndex, sentenceIndex, text) {
  if (!endsParagraph(pageIndex, sentenceIndex)) return 0;
  const wanted = state.pauseSettings.paragraph ?? DEFAULT_PARAGRAPH_PAUSE_MS;
  const mark = stripHTML(text).replace(/["'\u201d\u2019)\]\s]+$/, "").slice(-1);
  const already = state.pauseSettings[END_MARK_PAUSE[mark]] || 0;
  return Math.max(0, wanted - already) / 1000;
}

// --- Voice preview ---------------------------------------------------------
// Plays a short sample of the selected voice so it can be auditioned without
// starting a document. Deliberately uses a plain Audio element rather than the
// shared AudioContext: a preview is incidental, and routing it through the
// reading pipeline would mean tearing down and rebuilding playback state.
let previewAudio = null;
let previewVoice = null;

export function initVoicePreview() {
  const btn = document.getElementById("voicePreviewBtn");
  const select = document.getElementById("voiceSelect");
  if (!btn || !select) return;

  const setIcon = (name, extra = "") => {
    btn.innerHTML = `<i data-lucide="${name}" class="w-4 h-4 ${extra}"></i>`;
    if (window.lucide) window.lucide.createIcons();
  };

  const reset = () => {
    if (previewAudio) {
      previewAudio.pause();
      if (previewAudio.dataset.url) URL.revokeObjectURL(previewAudio.dataset.url);
      previewAudio = null;
    }
    previewVoice = null;
    btn.disabled = false;
    setIcon("play");
  };

  btn.addEventListener("click", async () => {
    const voice = select.value;
    if (!voice) return;

    // A second click on the voice that is already playing stops it.
    if (previewAudio && previewVoice === voice) {
      reset();
      return;
    }
    reset();

    btn.disabled = true;
    setIcon("loader-circle", "animate-spin");

    try {
      const res = await fetch(`/api/voices/preview/${encodeURIComponent(voice)}`);
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${res.status}`);
      }

      const url = URL.createObjectURL(await res.blob());
      const audio = new Audio(url);
      audio.dataset.url = url;
      previewAudio = audio;
      previewVoice = voice;

      audio.addEventListener("ended", reset);
      audio.addEventListener("error", reset);

      btn.disabled = false;
      setIcon("square");
      await audio.play();
    } catch (err) {
      console.error("[VoicePreview]", err);
      reset();
    }
  });

  // Switching voices invalidates whatever is currently playing.
  select.addEventListener("change", reset);
}

export async function loadVoices() {
  const voiceSelect = document.getElementById("voiceSelect");
  try {
    const currentVoice = voiceSelect.value;
    const data = await fetchJSON(`/api/voices/available`);
    const categories = data.categories || {};

    voiceSelect.innerHTML = "";
    const sortedKeys = Object.keys(categories).sort((a, b) => {
      if (a.startsWith("en") && !b.startsWith("en")) return -1;
      if (!a.startsWith("en") && b.startsWith("en")) return 1;
      return a.localeCompare(b);
    });

    sortedKeys.forEach((langCode) => {
      const category = categories[langCode];
      const group = document.createElement("optgroup");
      // Try to translate the language code using loaded translations, fallback to label from backend
      group.label = state.translations?.languages?.[langCode] || category.label;
      category.voices.forEach((voice) => {
        // Filter out voices with Indian accents as requested (handles prefixes like v0_alpha)
        const voiceId = voice.id.toLowerCase();
        const cleanId = voiceId.includes("_")
          ? voiceId.split("_").pop()
          : voiceId;
        if (["alpha", "beta", "omega", "psi"].includes(cleanId)) return;

        const option = document.createElement("option");
        option.value = voice.id;

        // Dynamic label generation
        let label = voice.name;
        const attrs = state.translations?.voice_attributes || {};

        // Helper to get attributes
        const getAttrs = (vid) => {
          if (vid.startsWith("af_")) return [attrs.american, attrs.female];
          if (vid.startsWith("am_")) return [attrs.american, attrs.male];
          if (vid.startsWith("bf_")) return [attrs.british, attrs.female];
          if (vid.startsWith("bm_")) return [attrs.british, attrs.male];
          if (vid.startsWith("ff_")) return [attrs.french, attrs.female];
          if (vid.startsWith("jf_")) return [attrs.japanese, attrs.female];
          if (vid.startsWith("jm_")) return [attrs.japanese, attrs.male];
          if (vid.startsWith("ef_")) return [attrs.spanish, attrs.female];
          if (vid.startsWith("em_")) return [attrs.spanish, attrs.male];
          if (vid.startsWith("zf_")) return [attrs.chinese, attrs.female];
          if (vid.startsWith("zm_")) return [attrs.chinese, attrs.male];
          if (vid.startsWith("if_")) return [attrs.italian, attrs.female];
          if (vid.startsWith("im_")) return [attrs.italian, attrs.male];
          if (vid.startsWith("pf_")) return [attrs.portuguese, attrs.female];
          if (vid.startsWith("pm_")) return [attrs.portuguese, attrs.male];

          if (vid === "santa") return [attrs.spanish, attrs.male];

          return [];
        };

        const [region, gender] = getAttrs(voice.id);
        if (region && gender) {
          label = `${voice.name} (${region} ${gender})`;
        } else {
          // Fallback to legacy static list if available, or just name
          label = state.translations?.voices?.[voice.id] || voice.name;
        }

        option.textContent = label;
        group.appendChild(option);
      });
      voiceSelect.appendChild(group);
    });

    if (currentVoice) {
      const exists = Array.from(voiceSelect.options).some(
        (opt) => opt.value === currentVoice,
      );
      if (exists) voiceSelect.value = currentVoice;
    }

    if (voiceSelect.options.length === 0) {
      const option = document.createElement("option");
      option.textContent = "No voices found (Download Engine)";
      option.disabled = true;
      voiceSelect.appendChild(option);
    }
    return true;
  } catch (error) {
    console.error("Error loading voices:", error);
    voiceSelect.innerHTML = "<option disabled>Error loading voices</option>";
    return false;
  }
}
