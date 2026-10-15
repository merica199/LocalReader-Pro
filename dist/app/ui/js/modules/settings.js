import { renderIcons } from './ui.js';

// Settings: a full-window view in place of a settings tab and a voice drawer.
// It is opened from the menu bar (dist/main.py calls window.openSettings), by
// Cmd+comma on a Mac or Ctrl+comma elsewhere, and by Help > Check for Updates
// (straight to the Updates section). The controls inside it keep the ids they
// had in the sidebar and drawer, so the code that loads and saves them in
// app.js and updates.js is unchanged.

const view = () => document.getElementById('settingsView');

export function isSettingsOpen() {
    return !view().classList.contains('hidden');
}

function showSection(name) {
    const v = view();
    if (!v.querySelector(`section[data-settings-section="${name}"]`)) name = 'voice';
    v.querySelectorAll('[data-settings-section]').forEach(el => {
        el.classList.toggle('active', el.dataset.settingsSection === name);
    });
    v.querySelector('.settings-main').scrollTop = 0;
}

export function openSettings(section = 'voice') {
    showSection(section);
    view().classList.remove('hidden');
    renderIcons();
    view().querySelector('.settings-nav-btn.active')?.focus();
}

export function closeSettings() {
    view().classList.add('hidden');
}

// The page's own idea of the platform, for settings marked only-windows or
// only-mac. The window is a system web view (WebKit on a Mac, Edge WebView2
// on Windows), so its user agent names the operating system.
function markPlatform() {
    const ua = navigator.userAgent;
    const root = document.documentElement;
    if (/Windows/.test(ua)) root.classList.add('platform-windows');
    else if (/Macintosh|Mac OS X/.test(ua)) root.classList.add('platform-mac');
}

export function initSettings() {
    markPlatform();
    view().querySelectorAll('.settings-nav-btn').forEach(btn => {
        btn.onclick = () => showSection(btn.dataset.settingsSection);
    });
    document.getElementById('closeSettingsBtn').onclick = closeSettings;

    // Capture phase, so these run before the reader's own shortcuts (Space,
    // arrows, Escape) and can keep them from acting behind the open view.
    window.addEventListener('keydown', (e) => {
        if ((e.metaKey || e.ctrlKey) && e.key === ',') {
            e.preventDefault();
            e.stopImmediatePropagation();
            isSettingsOpen() ? closeSettings() : openSettings();
        } else if (isSettingsOpen() && e.key === 'Escape') {
            e.preventDefault();
            e.stopImmediatePropagation();
            closeSettings();
        }
    }, true);

    window.openSettings = openSettings;
}
