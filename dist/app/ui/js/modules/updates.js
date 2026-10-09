import { fetchJSON } from './api.js';
import { showToast } from './ui.js';

// The Updates panel in the sidebar, and the Help > Check for Updates menu item
// that opens it. Checking goes online only when asked (routers/update.py).

function formatDate(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? '' : d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

function show(id, visible) {
    document.getElementById(id).classList.toggle('hidden', !visible);
}

async function showVersion() {
    try {
        const { commit } = await fetchJSON('/api/update/version');
        document.getElementById('updateVersion').textContent = commit
            ? `This copy: ${commit.hash}, ${formatDate(commit.date)}`
            : '';
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
        list.replaceChildren();
        if (status.available) {
            const n = status.behind;
            result.textContent = `${n} update${n === 1 ? '' : 's'} available` +
                (status.latest ? ` (${formatDate(status.latest.date)})` : '') + ':';
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
            result.textContent = status.reason || 'You have the latest version.';
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
        showToast('Update failed: ' + e.message);
    }
}

// Help > Check for Updates: bring the panel into view and check.
function openUpdates() {
    const sidebar = document.querySelector('.sidebar');
    if (sidebar && sidebar.classList.contains('collapsed')) {
        document.getElementById('sidebarExpandBtn')?.click();
    }
    document.getElementById('updatesPanel').scrollIntoView({ behavior: 'smooth', block: 'center' });
    checkForUpdates();
}

// The outcome of an update applied before this launch, shown once.
async function reportLastUpdate() {
    try {
        const { result } = await fetchJSON('/api/update/last');
        if (!result) return;
        if (result.ok) {
            if (result.to && result.to !== result.from) showToast(`Updated to ${result.to}`);
        } else {
            showToast('Update failed: ' + result.error);
        }
    } catch (e) {
        console.error(e);
    }
}

export function initUpdates() {
    document.getElementById('checkUpdatesBtn').onclick = checkForUpdates;
    document.getElementById('applyUpdateBtn').onclick = applyUpdate;
    window.openUpdates = openUpdates;
    showVersion();
    reportLastUpdate();
}
