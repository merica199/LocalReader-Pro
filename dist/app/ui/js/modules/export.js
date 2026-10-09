import { state } from './state.js';
import { fetchJSON, fetchBlob, API_URL } from './api.js';
import { showToast, renderIcons } from './ui.js';

let exportPollInterval = null;
let ffmpegPollInterval = null;

// "normal" or "sleep". Remembered for the session, so several sleep recordings
// in a row do not mean re-picking it each time; a fresh start is back to normal.
let exportMode = 'normal';
// Mode of the export the progress view is showing, or null when none is.
let runningMode = null;
// A sleep render can take an hour, so its dialog can be hidden while it runs;
// completion is then announced with a toast instead.
let exportHidden = false;
let sleepEstimateToken = 0;

// Sleep options are saved on the server (userdata/sleep_settings.json) as they
// change, so they are what the dialog opens with next time, across restarts.
let sleepDefaults = null;
let sleepSaveTimer = null;
let sleepEstimateTimer = null;
// The background picked before "Add a sound file..." was chosen, to go back to
// if the file picker is cancelled.
let lastBackground = 'brown';
let previewPoll = null;
let previewUrl = null;

const PAUSE_INPUTS = {
    sentence: 'sleepPauseSentence',
    paragraph: 'sleepPauseParagraph',
    ellipsis: 'sleepPauseEllipsis',
    clause: 'sleepPauseClause',
    lead_in: 'sleepPauseLeadIn',
    tail: 'sleepPauseTail',
};
const SOUND_INPUTS = {
    soften: 'sleepSoften',
    room: 'sleepRoom',
    background: 'sleepBackground',
    background_level: 'sleepBackgroundLevel',
    fade_in: 'sleepFadeIn',
    fade_out: 'sleepFadeOut',
    format: 'sleepFormat',
    bitrate: 'sleepBitrate',
};

function formatDuration(seconds) {
    const s = Math.max(0, Math.round(seconds));
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    return `${h}:${String(m).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
}

function exportRequestBody(speed) {
    return {
        doc_id: state.currentDoc.id,
        voice: document.getElementById('voiceSelect').value,
        speed,
        rules: state.rules,
        ignore_list: state.ignoreList
    };
}

function sleepRequestBody() {
    const settings = readSleepSettings();
    return { ...exportRequestBody(settings.speed), pacing: settings.pacing, sound: settings.sound };
}

// fetchJSON, but a refused request (422) names the field instead of
// "[object Object]".
async function postJSON(endpoint, body) {
    const res = await fetch(`${API_URL}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
        const detail = Array.isArray(data.detail)
            ? data.detail.map(d => `${(d.loc || []).slice(-1)[0]}: ${d.msg}`).join('; ')
            : data.detail || data.error;
        throw new Error(detail || `Request failed: ${res.status}`);
    }
    return data;
}

export function initExportDialog() {
    document.getElementById('exportModeNormal').onclick = () => setExportMode('normal');
    document.getElementById('exportModeSleep').onclick = () => setExportMode('sleep');
    document.getElementById('startExportBtn').onclick = beginExport;
    document.getElementById('clearSleepCacheBtn').onclick = clearSleepCache;
    document.getElementById('hideExportBtn').onclick = hideExport;
    document.getElementById('sleepPreviewBtn').onclick = startPreview;
    document.getElementById('sleepResetBtn').onclick = resetSleepSettings;
    document.getElementById('sleepRemoveSoundBtn').onclick = removeSleepSound;
    document.getElementById('sleepSoundFile').onchange = addSleepSound;
    document.querySelectorAll('[data-sleep]').forEach(el => el.addEventListener('change', onSleepChange));
    // The level reads out while the slider moves, not only when it is let go.
    document.getElementById('sleepBackgroundLevel').addEventListener('input', updateSleepLabels);
}

export async function startExport() {
    if (!state.currentDoc) {
        showToast("No document selected");
        return;
    }
    if (!window.isEngineReady) {
        showToast("Voice engine not ready");
        return;
    }

    exportHidden = false;
    // Neither view until the status says which, so the last export's progress
    // does not flash up before the options replace it.
    document.getElementById('exportOptions').classList.add('hidden');
    document.getElementById('exportRunning').classList.add('hidden');
    document.getElementById('exportModal').classList.remove('hidden');

    // A sleep recording may still be rendering in the background; show it
    // rather than offering to start another.
    let status = {};
    try {
        status = await fetchJSON(`/api/export/status?t=${Date.now()}`);
        if (status.is_exporting && !status.preview) {
            showRunning(status.mode === 'sleep' ? 'sleep' : 'normal');
            startExportPolling();
            return;
        }
    } catch (e) {
        console.error(e);
    }
    await showOptions();
    if (status.is_exporting && status.preview) {
        exportMode = 'sleep';
        setExportMode('sleep');
        watchPreview();
    }
}

async function showOptions() {
    runningMode = null;
    document.getElementById('exportTitle').textContent = 'Export Audio';
    document.getElementById('exportOptions').classList.remove('hidden');
    document.getElementById('exportRunning').classList.add('hidden');

    const totalChars = state.currentPages.join('').length;
    const estimatedMins = Math.ceil(Math.ceil((totalChars / 1000) * 15) / 60);
    document.getElementById('normalEstimate').textContent =
        `The whole document at reading pace. Estimated time: ~${estimatedMins} minute${estimatedMins !== 1 ? 's' : ''}`;
    try {
        await loadSleepOptions();
    } catch (e) {
        console.error(e);
        document.getElementById('sleepEstimate').textContent = 'Could not load sleep options: ' + e.message;
    }
    setExportMode(exportMode);
    renderIcons();
}

function setExportMode(mode) {
    exportMode = mode;
    for (const [id, m] of [['exportModeNormal', 'normal'], ['exportModeSleep', 'sleep']]) {
        const button = document.getElementById(id);
        button.classList.toggle('border-blue-600', m === mode);
        button.classList.toggle('bg-blue-600/10', m === mode);
        button.classList.toggle('border-zinc-700', m !== mode);
    }
    document.getElementById('normalOptions').classList.toggle('hidden', mode !== 'normal');
    document.getElementById('sleepOptions').classList.toggle('hidden', mode !== 'sleep');
    if (mode === 'sleep') refreshSleepEstimate();
}

// --- Sleep options -----------------------------------------------------------

async function loadSleepOptions() {
    const [saved, sounds] = await Promise.all([
        fetchJSON(`/api/export/sleep/settings?t=${Date.now()}`),
        fetchJSON(`/api/export/sleep/sounds?t=${Date.now()}`),
    ]);
    sleepDefaults = saved.defaults;
    renderSoundList(sounds);
    applySleepSettings(saved.settings);
}

function renderSoundList(sounds) {
    const group = document.getElementById('sleepSoundList');
    group.replaceChildren();
    for (const sound of sounds) {
        const option = document.createElement('option');
        option.value = `file:${sound.name}`;
        option.textContent = sound.name.replace(/\.[^.]+$/, '');
        group.appendChild(option);
    }
    group.hidden = sounds.length === 0;
}

// Sets a select, adding the value as an option first if it is not one of the
// listed choices (a value saved by an older or newer version, say).
function setSelect(id, value, label = value) {
    const select = document.getElementById(id);
    const text = String(value);
    if (![...select.options].some(o => o.value === text)) {
        const option = document.createElement('option');
        option.value = text;
        option.textContent = label;
        select.appendChild(option);
    }
    select.value = text;
}

function applySleepSettings(settings) {
    document.getElementById('sleepSpeed').value = settings.speed;
    for (const [key, id] of Object.entries(PAUSE_INPUTS)) {
        document.getElementById(id).value = settings.pacing[key];
    }
    const sound = settings.sound;
    for (const key of ['soften', 'room', 'format']) setSelect(SOUND_INPUTS[key], sound[key]);
    setSelect('sleepBitrate', sound.bitrate, `${sound.bitrate} kbps`);
    setSelect('sleepLoudness', sound.loudness === null ? '' : String(Math.round(sound.loudness)),
        `${sound.loudness} LUFS`);
    // An added sound that has since been removed falls back to the default.
    const background = document.getElementById('sleepBackground');
    background.value = sound.background;
    if (background.value !== sound.background) background.value = sleepDefaults.sound.background;
    lastBackground = background.value;
    for (const key of ['background_level', 'fade_in', 'fade_out']) {
        document.getElementById(SOUND_INPUTS[key]).value = sound[key];
    }
    updateSleepLabels();
}

// A number input's value, held to its min and max; a blank or unreadable
// entry becomes the default rather than an error.
function readNumber(id, fallback) {
    const input = document.getElementById(id);
    let value = parseFloat(input.value);
    if (!Number.isFinite(value)) value = fallback;
    if (input.min !== '') value = Math.max(parseFloat(input.min), value);
    if (input.max !== '') value = Math.min(parseFloat(input.max), value);
    if (String(value) !== input.value) input.value = value;
    return value;
}

function readSleepSettings() {
    const defaults = sleepDefaults;
    const pacing = {};
    for (const [key, id] of Object.entries(PAUSE_INPUTS)) {
        pacing[key] = readNumber(id, defaults.pacing[key]);
    }
    const loudness = document.getElementById('sleepLoudness').value;
    return {
        speed: readNumber('sleepSpeed', defaults.speed),
        pacing,
        sound: {
            soften: document.getElementById('sleepSoften').value,
            room: document.getElementById('sleepRoom').value,
            loudness: loudness === '' ? null : parseFloat(loudness),
            background: document.getElementById('sleepBackground').value,
            background_level: readNumber('sleepBackgroundLevel', defaults.sound.background_level),
            fade_in: readNumber('sleepFadeIn', defaults.sound.fade_in),
            fade_out: readNumber('sleepFadeOut', defaults.sound.fade_out),
            format: document.getElementById('sleepFormat').value,
            bitrate: parseInt(document.getElementById('sleepBitrate').value, 10),
        },
    };
}

function updateSleepLabels() {
    const level = parseFloat(document.getElementById('sleepBackgroundLevel').value);
    const background = document.getElementById('sleepBackground').value;
    document.getElementById('sleepBackgroundLevelVal').textContent =
        background === 'none' ? 'no background' : `${-level} dB below the voice`;
    document.getElementById('sleepBackgroundLevel').disabled = background === 'none';
    document.getElementById('sleepSoundActions').classList.toggle('hidden', !background.startsWith('file:'));
    document.getElementById('sleepBitrateRow').classList.toggle(
        'hidden', document.getElementById('sleepFormat').value === 'wav');
}

function onSleepChange(event) {
    if (event.target.id === 'sleepBackground') {
        if (event.target.value === '__add__') {
            event.target.value = lastBackground;
            document.getElementById('sleepSoundFile').click();
            return;
        }
        lastBackground = event.target.value;
    }
    updateSleepLabels();
    saveSleepSettingsSoon();
    clearTimeout(sleepEstimateTimer);
    sleepEstimateTimer = setTimeout(refreshSleepEstimate, 400);
}

function saveSleepSettingsSoon() {
    clearTimeout(sleepSaveTimer);
    sleepSaveTimer = setTimeout(async () => {
        try {
            await postJSON('/api/export/sleep/settings', readSleepSettings());
        } catch (e) {
            console.error('Saving sleep settings failed', e);
        }
    }, 400);
}

function resetSleepSettings() {
    if (!sleepDefaults) return;
    applySleepSettings(sleepDefaults);
    saveSleepSettingsSoon();
    refreshSleepEstimate();
}

async function addSleepSound(event) {
    const file = event.target.files[0];
    event.target.value = '';
    if (!file) return;
    const status = document.getElementById('sleepPreviewStatus');
    status.textContent = `Adding ${file.name}...`;
    try {
        const form = new FormData();
        form.append('file', file);
        const res = await fetch(`${API_URL}/api/export/sleep/sounds`, { method: 'POST', body: form });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.detail || `Request failed: ${res.status}`);
        renderSoundList(await fetchJSON(`/api/export/sleep/sounds?t=${Date.now()}`));
        document.getElementById('sleepBackground').value = `file:${data.name}`;
        lastBackground = `file:${data.name}`;
        status.textContent = `Added ${data.name}. It loops under the voice for the whole recording.`;
        updateSleepLabels();
        saveSleepSettingsSoon();
        refreshSleepEstimate();
    } catch (e) {
        status.textContent = '';
        showToast('Could not add that sound: ' + e.message);
    }
}

async function removeSleepSound() {
    const select = document.getElementById('sleepBackground');
    if (!select.value.startsWith('file:')) return;
    const name = select.value.slice(5);
    if (!confirm(`Remove "${name}" from your background sounds?`)) return;
    try {
        await fetchJSON(`/api/export/sleep/sounds/${encodeURIComponent(name)}`, { method: 'DELETE' });
    } catch (e) {
        showToast('Could not remove it: ' + e.message);
        return;
    }
    renderSoundList(await fetchJSON(`/api/export/sleep/sounds?t=${Date.now()}`));
    select.value = sleepDefaults.sound.background;
    lastBackground = select.value;
    updateSleepLabels();
    saveSleepSettingsSoon();
}

async function refreshSleepEstimate() {
    if (!sleepDefaults || !state.currentDoc) return;
    // Responses can arrive out of order when options change quickly; only the
    // latest request may write the estimate.
    const token = ++sleepEstimateToken;
    const estimate = document.getElementById('sleepEstimate');
    estimate.textContent = 'Estimating length...';
    refreshSleepCacheInfo();
    try {
        const plan = await postJSON('/api/export/sleep/plan', sleepRequestBody());
        if (token !== sleepEstimateToken) return;
        const cached = plan.cached_pieces ? ` (${plan.cached_pieces} already rendered)` : '';
        const ffmpeg = plan.needs_ffmpeg && !plan.ffmpeg_installed
            ? ' These options need FFmpeg, which will be offered when you start.' : '';
        estimate.textContent =
            `About ${formatDuration(plan.estimated_seconds)} long, ${plan.pieces} sentences${cached}. ` +
            (plan.estimated_render_seconds < 60
                ? 'Rendering takes under a minute.'
                : `Rendering takes roughly ${formatDuration(plan.estimated_render_seconds)}.`) + ffmpeg;
    } catch (e) {
        if (token === sleepEstimateToken) estimate.textContent = 'Could not estimate: ' + e.message;
    }
}

async function refreshSleepCacheInfo() {
    try {
        const usage = await fetchJSON(`/api/export/sleep/cache?t=${Date.now()}`);
        document.getElementById('sleepCacheInfo').textContent =
            `Sentence cache: ${Math.round(usage.bytes / 1e6)} MB`;
    } catch (e) {
        console.error(e);
    }
}

async function clearSleepCache() {
    if (!confirm('Delete every cached sleep-recording sentence?\n\nExporting again will generate them from scratch.')) {
        return;
    }
    try {
        const res = await fetchJSON('/api/export/sleep/cache/clear', { method: 'POST' });
        showToast(`Cleared ${Math.round(res.bytes / 1e6)} MB`);
    } catch (e) {
        showToast("Could not clear the cache: " + e.message);
    }
    refreshSleepEstimate();
}

// Asks for FFmpeg first when the options need it. Returns false if the
// download dialog was shown instead.
async function sleepFfmpegReady(body) {
    const plan = await postJSON('/api/export/sleep/plan', body);
    if (plan.needs_ffmpeg && !plan.ffmpeg_installed) {
        document.getElementById('exportModal').classList.add('hidden');
        showFFMPEGDownloadModal();
        return false;
    }
    return true;
}

function describeSleepProgress(status) {
    const percent = `${Math.round((status.phase_progress || 0) * 100)}%`;
    if (status.phase === 'measuring') return `Finishing: measuring loudness, ${percent}`;
    if (status.phase === 'mixing') return `Finishing: mixing and encoding, ${percent}`;
    return `Sentence ${status.progress} of ${status.total}, ${formatDuration(status.audio_seconds)} recorded`;
}

// --- Preview -----------------------------------------------------------------
// The first minute with every option applied, played in the dialog, so a change
// can be heard in seconds instead of after a whole render. Its sentences land
// in the same cache, so the full render reuses them.

function setPreviewBusy(busy) {
    document.getElementById('sleepPreviewBtn').disabled = busy;
    document.getElementById('sleepPreviewBtn').textContent = busy ? 'Rendering preview...' : 'Preview the first minute';
    document.getElementById('startExportBtn').disabled = busy;
    document.getElementById('startExportBtn').classList.toggle('opacity-50', busy);
}

async function startPreview() {
    const status = document.getElementById('sleepPreviewStatus');
    const audio = document.getElementById('sleepPreviewAudio');
    audio.pause();
    try {
        const body = sleepRequestBody();
        if (!(await sleepFfmpegReady(body))) return;
        await postJSON('/api/export/sleep/preview', body);
    } catch (e) {
        status.textContent = 'Preview failed: ' + e.message;
        return;
    }
    status.textContent = 'Starting preview...';
    watchPreview();
}

function watchPreview() {
    setPreviewBusy(true);
    clearInterval(previewPoll);
    previewPoll = setInterval(async () => {
        const status = document.getElementById('sleepPreviewStatus');
        let s;
        try {
            s = await fetchJSON(`/api/export/status?t=${Date.now()}`);
        } catch (e) {
            return;
        }
        if (s.is_exporting) {
            status.textContent = 'Preview: ' + describeSleepProgress(s);
            return;
        }
        clearInterval(previewPoll);
        previewPoll = null;
        setPreviewBusy(false);
        if (s.error) {
            status.textContent = s.error === 'Export cancelled' ? 'Preview stopped' : 'Preview failed: ' + s.error;
        } else if (s.preview && s.output_file) {
            await playPreview(s.output_file);
        }
    }, 500);
}

async function playPreview(file) {
    const status = document.getElementById('sleepPreviewStatus');
    try {
        const blob = await fetchBlob(`/api/export/sleep/preview/${file}?t=${Date.now()}`);
        if (previewUrl) URL.revokeObjectURL(previewUrl);
        previewUrl = URL.createObjectURL(blob);
        const audio = document.getElementById('sleepPreviewAudio');
        audio.src = previewUrl;
        audio.classList.remove('hidden');
        status.textContent = 'Preview ready. Change an option and preview again to compare.';
        audio.play().catch(() => {});
    } catch (e) {
        status.textContent = 'Could not load the preview: ' + e.message;
    }
}

// --- Running an export -------------------------------------------------------

async function beginExport() {
    try {
        if (exportMode === 'sleep') {
            const body = sleepRequestBody();
            if (!(await sleepFfmpegReady(body))) return;
            await postJSON('/api/export/sleep', body);
            document.getElementById('sleepPreviewAudio').pause();
            // Reading stays available: the render takes the engine one
            // sentence at a time, so read-aloud just waits its turn.
            showRunning('sleep');
        } else {
            const status = await fetchJSON(`/api/ffmpeg/status?t=${Date.now()}`);
            if (!status.is_installed) {
                document.getElementById('exportModal').classList.add('hidden');
                showFFMPEGDownloadModal();
                return;
            }
            const speed = parseFloat(document.getElementById('speedRange').value);
            await fetchJSON(`/api/export/audio`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(exportRequestBody(speed))
            });
            showRunning('normal');
            document.getElementById('playBtn').disabled = true;
        }
        startExportPolling();
    } catch (e) {
        console.error(e);
        showToast("Export failed: " + e.message);
    }
}

function showRunning(mode) {
    runningMode = mode;
    document.getElementById('exportTitle').textContent =
        mode === 'sleep' ? 'Rendering Sleep Recording' : 'Exporting Audio';
    document.getElementById('exportOptions').classList.add('hidden');
    document.getElementById('exportRunning').classList.remove('hidden');
    document.getElementById('exportComplete').classList.add('hidden');
    document.getElementById('exportError').classList.add('hidden');
    document.getElementById('exportProgress').textContent = '0%';
    document.getElementById('exportProgressBar').style.width = '0%';
    document.getElementById('exportStatus').textContent = 'Initializing export...';
    document.getElementById('hideExportBtn').classList.toggle('hidden', mode !== 'sleep');
}

function hideExport() {
    exportHidden = true;
    document.getElementById('exportModal').classList.add('hidden');
}

function startExportPolling() {
    if (exportPollInterval) clearInterval(exportPollInterval);
    exportPollInterval = setInterval(async () => {
        try {
            const status = await fetchJSON(`/api/export/status?t=${Date.now()}`);
            const sleep = status.mode === 'sleep';
            if (status.error) {
                clearInterval(exportPollInterval);
                document.getElementById('exportError').classList.remove('hidden');
                document.getElementById('exportErrorMsg').textContent = status.error;
                document.getElementById('exportStatus').textContent = 'Export failed';
                document.getElementById('hideExportBtn').classList.add('hidden');
                document.getElementById('playBtn').disabled = false;
                if (exportHidden) showToast("Sleep recording failed: " + status.error);
                return;
            }

            if (status.is_exporting) {
                // A sleep render shows each phase's own progress: sentences,
                // then the two finishing passes.
                const fraction = sleep
                    ? status.phase_progress || 0
                    : (status.total > 0 ? status.progress / status.total : 0);
                const percent = Math.round(fraction * 100);
                document.getElementById('exportProgress').textContent = `${percent}%`;
                document.getElementById('exportProgressBar').style.width = `${percent}%`;
                document.getElementById('exportStatus').textContent = sleep
                    ? describeSleepProgress(status)
                    : `Processing paragraph ${status.progress} of ${status.total}...`;
            } else if (status.output_file) {
                clearInterval(exportPollInterval);
                document.getElementById('exportProgress').textContent = '100%';
                document.getElementById('exportProgressBar').style.width = '100%';
                document.getElementById('exportStatus').textContent = sleep
                    ? `Sleep recording complete: ${formatDuration(status.audio_seconds)} long`
                    : 'Export complete!';

                document.getElementById('exportFilePath').textContent = `./userdata/${status.output_file}`;
                document.getElementById('exportComplete').classList.remove('hidden');
                document.getElementById('hideExportBtn').classList.add('hidden');
                document.getElementById('playBtn').disabled = false;
                renderIcons();
                if (exportHidden) showToast(`Sleep recording saved: ${status.output_file}`);

                // Store output file in DOM for the "Open Folder" button
                document.getElementById('exportModal').dataset.outputFile = status.output_file;
            }
        } catch (e) {
            console.error("Export polling error:", e);
        }
    }, 1000);
}

export async function cancelExport() {
    document.getElementById('sleepPreviewAudio').pause();
    if (previewPoll) {
        // Closing the dialog drops a preview still rendering: it is quick to
        // redo, and would otherwise block a real export until it finished.
        clearInterval(previewPoll);
        previewPoll = null;
        setPreviewBusy(false);
        document.getElementById('sleepPreviewStatus').textContent = '';
        fetchJSON(`/api/export/cancel`, { method: 'POST' }).catch(console.error);
    }
    // Before an export starts, the close button only closes.
    if (runningMode) {
        const status = await fetchJSON(`/api/export/status?t=${Date.now()}`).catch(() => ({}));
        if (status.is_exporting) {
            if (runningMode === 'sleep' &&
                !confirm('Stop rendering the sleep recording?\n\nSentences already rendered stay cached, so exporting it again picks up where it stopped.')) {
                return;
            }
            fetchJSON(`/api/export/cancel`, { method: 'POST' }).catch(console.error);
        }
        if (exportPollInterval) clearInterval(exportPollInterval);
        document.getElementById('playBtn').disabled = false;
    }
    document.getElementById('exportModal').classList.add('hidden');
}

function showFFMPEGDownloadModal() {
    const modal = document.getElementById('ffmpegModal');
    modal.classList.remove('hidden');
    document.getElementById('ffmpegDownloadSection').classList.add('hidden');
    document.getElementById('ffmpegComplete').classList.add('hidden');
    document.getElementById('ffmpegError').classList.add('hidden');
    document.getElementById('startFFMPEGDownload').classList.remove('hidden');
    renderIcons();
}

export async function startFFMPEGDownload() {
    try {
        await fetchJSON(`/api/ffmpeg/install`, { method: 'POST' });

        document.getElementById('startFFMPEGDownload').classList.add('hidden');
        document.getElementById('ffmpegDownloadSection').classList.remove('hidden');
        document.getElementById('ffmpegProgress').textContent = '0%';
        document.getElementById('ffmpegStatus').textContent = 'Starting download...';

        startFFMPEGPolling();
    } catch (e) {
        document.getElementById('ffmpegError').classList.remove('hidden');
        document.getElementById('ffmpegErrorMsg').textContent = e.message;
    }
}

function startFFMPEGPolling() {
    if (ffmpegPollInterval) clearInterval(ffmpegPollInterval);
    ffmpegPollInterval = setInterval(async () => {
        try {
            const status = await fetchJSON(`/api/ffmpeg/status?t=${Date.now()}`);
            if (status.error) {
                clearInterval(ffmpegPollInterval);
                document.getElementById('ffmpegError').classList.remove('hidden');
                document.getElementById('ffmpegErrorMsg').textContent = status.error;
                return;
            }

            if (status.is_downloading) {
                const percent = status.total > 0 ? Math.round((status.progress / status.total) * 100) : 0;
                document.getElementById('ffmpegProgress').textContent = `${percent}%`;
                document.getElementById('ffmpegProgressBar').style.width = `${percent}%`;
                document.getElementById('ffmpegStatus').textContent = status.message || 'Downloading...';
            } else if (status.is_installed) {
                clearInterval(ffmpegPollInterval);
                document.getElementById('ffmpegDownloadSection').classList.add('hidden');
                document.getElementById('ffmpegComplete').classList.remove('hidden');
                renderIcons();
                setTimeout(() => {
                    document.getElementById('ffmpegModal').classList.add('hidden');
                    startExport();
                }, 1000);
            }
        } catch (e) { console.error("FFMPEG polling error:", e); }
    }, 500);
}

export function openExportLocation() {
    const outputFile = document.getElementById('exportModal').dataset.outputFile;
    if (outputFile) {
        fetchJSON(`/api/export/open-location/${outputFile}`, { method: 'POST' })
            .then(() => {
                showToast("Opening folder...");
                setTimeout(() => document.getElementById('exportModal').classList.add('hidden'), 1000);
            })
            .catch(e => showToast("Error: " + e.message));
    }
}
