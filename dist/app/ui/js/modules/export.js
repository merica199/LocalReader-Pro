
import { state } from './state.js';
import { fetchJSON } from './api.js';
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

export function initExportDialog() {
    document.getElementById('exportModeNormal').onclick = () => setExportMode('normal');
    document.getElementById('exportModeSleep').onclick = () => setExportMode('sleep');
    document.getElementById('startExportBtn').onclick = beginExport;
    document.getElementById('clearSleepCacheBtn').onclick = clearSleepCache;
    document.getElementById('hideExportBtn').onclick = hideExport;
    document.getElementById('sleepSpeed').onchange = refreshSleepEstimate;
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
    try {
        const status = await fetchJSON(`/api/export/status?t=${Date.now()}`);
        if (status.is_exporting) {
            showRunning(status.mode === 'sleep' ? 'sleep' : 'normal');
            startExportPolling();
            return;
        }
    } catch (e) {
        console.error(e);
    }
    showOptions();
}

function showOptions() {
    runningMode = null;
    document.getElementById('exportTitle').textContent = 'Export Audio';
    document.getElementById('exportOptions').classList.remove('hidden');
    document.getElementById('exportRunning').classList.add('hidden');

    const totalChars = state.currentPages.join('').length;
    const estimatedMins = Math.ceil(Math.ceil((totalChars / 1000) * 15) / 60);
    document.getElementById('normalEstimate').textContent =
        `The whole document at reading pace. Estimated time: ~${estimatedMins} minute${estimatedMins !== 1 ? 's' : ''}`;
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

async function refreshSleepEstimate() {
    // Responses can arrive out of order when the speed is changed quickly;
    // only the latest request may write the estimate.
    const token = ++sleepEstimateToken;
    const estimate = document.getElementById('sleepEstimate');
    estimate.textContent = 'Estimating length...';
    refreshSleepCacheInfo();
    try {
        const speed = parseFloat(document.getElementById('sleepSpeed').value);
        const plan = await fetchJSON('/api/export/sleep/plan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(exportRequestBody(speed))
        });
        if (token !== sleepEstimateToken) return;
        const cached = plan.cached_pieces ? ` (${plan.cached_pieces} already rendered)` : '';
        estimate.textContent =
            `About ${formatDuration(plan.estimated_seconds)} long, ${plan.pieces} sentences${cached}. ` +
            `Rendering takes roughly ${formatDuration(plan.estimated_render_seconds)}.`;
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

async function beginExport() {
    try {
        if (exportMode === 'sleep') {
            const speed = parseFloat(document.getElementById('sleepSpeed').value);
            await fetchJSON('/api/export/sleep', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(exportRequestBody(speed))
            });
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
                const percent = status.total > 0 ? Math.round((status.progress / status.total) * 100) : 0;
                document.getElementById('exportProgress').textContent = `${percent}%`;
                document.getElementById('exportProgressBar').style.width = `${percent}%`;
                document.getElementById('exportStatus').textContent = sleep
                    ? `Sentence ${status.progress} of ${status.total}, ${formatDuration(status.audio_seconds)} recorded`
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
