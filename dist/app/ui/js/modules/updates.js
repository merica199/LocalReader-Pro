import { fetchJSON } from './api.js';
import { showToast } from './ui.js';

// The Updates panel in the sidebar, the Help > Check for Updates menu item that
// opens it, and the "Update available" button at the top of the sidebar.
// Checking goes online when asked, or, if the user ticks "Check automatically"
// (off by default), a few seconds after the app opens and once a day while it
// stays open. A check only looks; installing always waits for a click.

const FIRST_CHECK_DELAY = 15 * 1000; // let the voice finish loading first
const DAY = 24 * 60 * 60 * 1000;
let dailyCheck = null;
let announced = null; // the newest version already announced this session

function formatDate(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? '' : d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

// "version 4.1.0", or the commit for versions from before VERSION existed.
function versionName(c) {
    if (!c) return '';
    return c.version ? `version ${c.version}` : `version ${c.hash}`;
}

function show(id, visible) {
    document.getElementById(id).classList.toggle('hidden', !visible);
}

async function showVersion() {
    try {
        const { commit } = await fetchJSON('/api/update/version');
        document.getElementById('updateVersion').textContent = commit
            ? `This copy: ${versionName(commit)}` + (commit.date ? `, ${formatDate(commit.date)}` : '')
            : '';
    } catch (e) {
        console.error(e);
    }
}

// Show or hide the "Update available" button (and the dot on the collapsed
// sidebar's tab), and announce a version once the first time it is seen.
function showAvailable(status, announce) {
    const available = Boolean(status && status.available);
    show('updateAvailableBtn', available);
    document.getElementById('sidebarExpandBtn')?.classList.toggle('has-update', available);
    const latest = status && status.latest && status.latest.hash;
    if (available && announce && latest && latest !== announced) {
        const which = status.latest.version && status.latest.version !== (status.current || {}).version
            ? `Version ${status.latest.version} is available` : 'An update is available';
        showToast(`${which}. Click "Update available" at the top of the sidebar to see what's new.`);
    }
    if (latest) announced = latest;
}

// The automatic check: says nothing unless there is an update.
async function quietCheck() {
    try {
        showAvailable(await fetchJSON(`/api/update/check?t=${Date.now()}`), true);
    } catch (e) {
        console.error(e); // offline, or GitHub did not answer: try again tomorrow
    }
}

function startAutomaticChecks(firstDelay) {
    clearInterval(dailyCheck);
    setTimeout(quietCheck, firstDelay);
    dailyCheck = setInterval(quietCheck, DAY);
}

function stopAutomaticChecks() {
    clearInterval(dailyCheck);
    dailyCheck = null;
}

async function setAutomatic(on) {
    try {
        await fetchJSON('/api/update/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ auto_check: on }),
        });
    } catch (e) {
        showToast('Could not save the update setting: ' + e.message, 'error');
        document.getElementById('autoUpdateCheck').checked = !on;
        return;
    }
    if (on) startAutomaticChecks(0);
    else stopAutomaticChecks();
}

async function initAutomaticChecks() {
    const box = document.getElementById('autoUpdateCheck');
    box.onchange = () => setAutomatic(box.checked);
    try {
        const { auto_check } = await fetchJSON('/api/update/settings');
        box.checked = auto_check;
        if (auto_check) startAutomaticChecks(FIRST_CHECK_DELAY);
    } catch (e) {
        console.error(e);
    }
}

async function checkForUpdates() {
    const button = document.getElementById('checkUpdatesBtn');
    const result = document.getElementById('updateResult');
    const list = document.getElementById('updateList');
    button.disabled = true;
    button.textContent = 'Checking...';
    show('applyUpdateBtn', false);
    show('updateList', false);
    try {
        const status = await fetchJSON(`/api/update/check?t=${Date.now()}`);
        showAvailable(status, false);
        list.replaceChildren();
        if (status.available) {
            const latest = status.latest || {};
            const current = status.current || {};
            result.textContent = (latest.version && latest.version !== current.version
                ? `Version ${latest.version} is available (you have ${current.version || 'an earlier version'})`
                : 'An update is available') +
                (latest.date ? `, ${formatDate(latest.date)}` : '') + '. What\'s new:';
            for (const c of status.commits.slice(0, 8)) {
                const li = document.createElement('li');
                li.textContent = c.subject;
                list.appendChild(li);
            }
            if (status.commits.length > 8) {
                const li = document.createElement('li');
                li.textContent = `and ${status.commits.length - 8} more`;
                list.appendChild(li);
            }
            show('updateList', true);
            if (status.can_update) {
                show('applyUpdateBtn', true);
            } else {
                const why = document.createElement('li');
                why.className = 'list-none -ml-4 mt-1 text-amber-400';
                why.textContent = status.reason;
                list.appendChild(why);
            }
        } else {
            result.textContent = status.reason ||
                `You have the latest version${status.current && status.current.version ? ` (${status.current.version})` : ''}.`;
        }
        show('updateResult', true);
    } catch (e) {
        result.textContent = 'Could not check: ' + e.message;
        show('updateResult', true);
    } finally {
        button.disabled = false;
        button.textContent = 'Check for updates';
    }
}

async function applyUpdate() {
    if (!confirm('Update now?\n\nLocalReader Pro will close, install the update, and open again. Playback and any export in progress will stop.')) {
        return;
    }
    const button = document.getElementById('applyUpdateBtn');
    button.disabled = true;
    button.textContent = 'Updating, the app will reopen...';
    try {
        await fetchJSON('/api/update/apply', { method: 'POST' });
    } catch (e) {
        button.disabled = false;
        button.textContent = 'Update and restart';
        showToast('Update failed: ' + e.message, 'error');
    }
}

// Check for Updates in the menu bar, and the Update available button: open
// Settings at its Updates section and check.
function openUpdates() {
    window.openSettings?.('updates');
    checkForUpdates();
}

// The outcome of an update applied before this launch, shown once.
async function reportLastUpdate() {
    try {
        const { result } = await fetchJSON('/api/update/last');
        if (!result) return;
        if (result.ok) {
            if (result.to && result.to !== result.from) {
                // The updater records commits; this copy now knows its number.
                const { commit } = await fetchJSON('/api/update/version');
                showToast(`Updated to ${versionName(commit) || result.to}`, 'success');
            }
        } else {
            showToast('Update failed: ' + result.error, 'error');
        }
    } catch (e) {
        console.error(e);
    }
}

export function initUpdates() {
    document.getElementById('checkUpdatesBtn').onclick = checkForUpdates;
    document.getElementById('applyUpdateBtn').onclick = applyUpdate;
    document.getElementById('updateAvailableBtn').onclick = openUpdates;
    window.openUpdates = openUpdates;
    showVersion();
    reportLastUpdate();
    initAutomaticChecks();
}
