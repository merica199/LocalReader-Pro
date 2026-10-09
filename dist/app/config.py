from pathlib import Path
import os
import sys


# CRITICAL: Path Anchoring Functions
def get_app_anchored_path(relative_path: str) -> Path:
    """
    Returns a guaranteed absolute path relative to THIS script file.
    Immune to where the user launched the terminal from.
    """
    # Get the app root (parent of app/ directory)
    # This file is inside dist/app/config.py, so parent is dist/app/, parent.parent is dist/
    script_dir = Path(__file__).parent.absolute()
    app_root = script_dir.parent

    # Join and resolve to absolute path
    return (app_root / relative_path).absolute()


# Base directories
base_dir = Path(__file__).parent.absolute()
userdata_dir = get_app_anchored_path("userdata")
content_dir = userdata_dir / "content"
cache_db_path = userdata_dir / "audio_cache.db"
# One rendered sample per voice, generated on first request. Regenerable, so it
# is safe to delete; kept out of audio_cache.db because that cache evicts by
# size and previews should survive a heavy reading session.
preview_cache_dir = userdata_dir / "voice_previews"
# One file per sentence of a sleep recording, so a long render can resume. Kept
# apart from audio_cache.db: that cache holds 200 MB and is cleared whenever the
# voice changes, either of which would throw away an unfinished render.
sleep_cache_dir = userdata_dir / "sleep_cache"
# The voice track and other files of the sleep recording being rendered, and
# the latest preview. Emptied at the start of each render.
sleep_work_dir = userdata_dir / "sleep_work"
# Background sounds added for sleep recordings (rain, waves...).
sleep_sounds_dir = userdata_dir / "sleep_sounds"
# The sleep-recording options last used, so they survive a restart.
sleep_settings_file = userdata_dir / "sleep_settings.json"

# File paths
settings_file = userdata_dir / "settings.json"
library_file = userdata_dir / "library.json"

# Settings
MAX_CACHE_SIZE_MB = 200

# Ensure directories exist
try:
    userdata_dir.mkdir(exist_ok=True)
    content_dir.mkdir(exist_ok=True)
    preview_cache_dir.mkdir(exist_ok=True)
except Exception as e:
    print(f"[CRITICAL] Failed to create storage dirs: {e}")
