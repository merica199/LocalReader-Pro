import { fetchJSON, fetchBlob } from './api.js';
import { showToast, renderIcons } from './ui.js';

// Settings > Azure voices: the user's own Azure Speech key and region, the
// voice used for exports, and whether exports use it. The server keeps the key
// (userdata/azure.json) and never sends it back; the page only learns whether
// one is saved. See routers/azure.py and docs/azure-voices.md.

// The latest saved settings, as the server reports them. Read by the Export
// dialog (modules/export.js) to know whether Azure can be offered.
export const azureState = { configured: false, voice: '', use_for_exports: false, voices: [] };

let sampleAudio = null;

async function postSettings(update) {
    const saved = await fetchJSON('/api/azure/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(update),
    });
    Object.assign(azureState, saved);
    return saved;
}

export async function loadAzureSettings() {
    try {
        Object.assign(azureState, await fetchJSON(`/api/azure/settings?t=${Date.now()}`));
    } catch (e) {
        console.error('[Azure]', e);
    }
    return azureState;
}

// The voice's name as people say it ("Ava"), from the list when it is loaded.
export function azureVoiceLabel(name = azureState.voice) {
    const v = azureState.voices.find(v => v.ShortName === name);
    return v ? `${v.DisplayName} (${v.LocaleName})` : name;
}

function describeVoice(v) {
    if (!v) return '';
    const parts = [v.Gender, v.LocaleName];
    if (v.VoiceType === 'NeuralHD') parts.push('HD');
    if (/Multilingual/.test(v.ShortName)) parts.push('also speaks other languages');
    if (v.StyleList && v.StyleList.length) parts.push(`styles: ${v.StyleList.join(', ')}`);
    return parts.filter(Boolean).join(' · ');
}

function renderVoices() {
    const select = document.getElementById('azureVoiceSelect');
    select.replaceChildren();
    const groups = new Map();
    for (const v of azureState.voices) {
        if (!groups.has(v.LocaleName)) {
            const group = document.createElement('optgroup');
            group.label = v.LocaleName;
            groups.set(v.LocaleName, group);
            select.appendChild(group);
        }
        const option = document.createElement('option');
        option.value = v.ShortName;
        option.textContent = `${v.DisplayName}${v.VoiceType === 'NeuralHD' ? ' (HD)' : ''} · ${v.Gender}`;
        groups.get(v.LocaleName).appendChild(option);
    }
    select.value = azureState.voice;
    if (select.value !== azureState.voice && select.options.length) {
        // The saved voice is not offered in this region: keep it visible.
        const option = document.createElement('option');
        option.value = option.textContent = azureState.voice;
        select.prepend(option);
        select.value = azureState.voice;
    }
    showVoiceInfo();
}

function showVoiceInfo() {
    const name = document.getElementById('azureVoiceSelect').value;
    document.getElementById('azureVoiceInfo').textContent =
        describeVoice(azureState.voices.find(v => v.ShortName === name));
}

async function loadVoices(refresh = false) {
    azureState.voices = await fetchJSON(`/api/azure/voices?refresh=${refresh}&t=${Date.now()}`);
    renderVoices();
}

async function refreshUsage() {
    try {
        const u = await fetchJSON(`/api/azure/usage?t=${Date.now()}`);
        document.getElementById('azureUsage').textContent =
            `This month, from this computer: about ${u.characters.toLocaleString()} of the ` +
            `${u.free_allowance.toLocaleString()} free characters. Azure itself is the final word: ` +
            `other computers using the same key are not counted here.`;
    } catch (e) {
        console.error('[Azure]', e);
    }
}

async function showPanel() {
    const configured = azureState.configured;
    document.getElementById('azureVoicePanel').classList.toggle('hidden', !configured);
    document.getElementById('azureRegion').value = azureState.region || '';
    document.getElementById('azureKey').placeholder = azureState.key_hint
        ? `saved (ending ${azureState.key_hint.slice(3)}); type a new one to replace it` : '';
    document.getElementById('azureUseForExports').checked = azureState.use_for_exports;
    if (!configured) return;
    try {
        await loadVoices();
    } catch (e) {
        document.getElementById('azureStatus').textContent = e.message;
    }
    refreshUsage();
}

async function saveAndTest() {
    const status = document.getElementById('azureStatus');
    const key = document.getElementById('azureKey').value.trim();
    const region = document.getElementById('azureRegion').value.trim();
    status.textContent = 'Testing...';
    try {
        await postSettings({ ...(key ? { key } : {}), region });
        const result = await fetchJSON('/api/azure/test', { method: 'POST' });
        document.getElementById('azureKey').value = '';
        status.textContent = `Connected. ${result.english} English voices in this region.`;
        await showPanel();
    } catch (e) {
        status.textContent = e.message;
    }
}

function resetSample() {
    if (sampleAudio) {
        sampleAudio.pause();
        URL.revokeObjectURL(sampleAudio.src);
        sampleAudio = null;
    }
    const btn = document.getElementById('azureSampleBtn');
    btn.disabled = false;
    btn.innerHTML = '<i data-lucide="play" class="w-4 h-4"></i>';
    renderIcons();
}

async function playSample() {
    const btn = document.getElementById('azureSampleBtn');
    if (sampleAudio) {
        resetSample();
        return;
    }
    const voice = document.getElementById('azureVoiceSelect').value;
    btn.disabled = true;
    btn.innerHTML = '<i data-lucide="loader-circle" class="w-4 h-4 animate-spin"></i>';
    renderIcons();
    try {
        const blob = await fetchBlob(`/api/azure/sample/${encodeURIComponent(voice)}`);
        sampleAudio = new Audio(URL.createObjectURL(blob));
        sampleAudio.addEventListener('ended', resetSample);
        btn.disabled = false;
        btn.innerHTML = '<i data-lucide="square" class="w-4 h-4"></i>';
        renderIcons();
        await sampleAudio.play();
        refreshUsage();
    } catch (e) {
        resetSample();
        showToast('Could not play the sample: ' + e.message);
    }
}

export async function setAzureForExports(on) {
    await postSettings({ use_for_exports: on });
    document.getElementById('azureUseForExports').checked = azureState.use_for_exports;
}

export function initAzure() {
    document.getElementById('azureSaveBtn').onclick = saveAndTest;
    document.getElementById('azureSampleBtn').onclick = playSample;
    document.getElementById('azureRefreshVoicesBtn').onclick = async () => {
        try {
            await loadVoices(true);
            showToast(`${azureState.voices.length} English voices`);
        } catch (e) {
            showToast(e.message);
        }
    };
    document.getElementById('azureVoiceSelect').onchange = async (e) => {
        resetSample();
        showVoiceInfo();
        try {
            await postSettings({ voice: e.target.value });
        } catch (err) {
            showToast(err.message);
        }
    };
    document.getElementById('azureUseForExports').onchange = async (e) => {
        try {
            await setAzureForExports(e.target.checked);
        } catch (err) {
            e.target.checked = false;
            showToast(err.message);
        }
    };
    // Loaded when the section is opened, so the app never goes online for it
    // until someone looks at Azure voices.
    document.querySelector('.settings-nav-btn[data-settings-section="azure"]')
        .addEventListener('click', async () => {
            await loadAzureSettings();
            showPanel();
        });
    loadAzureSettings();
}
