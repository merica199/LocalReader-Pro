from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from urllib.parse import urlsplit
import time
import json
import psutil

# Import Refactored Modules
from .config import (
    base_dir,
    userdata_dir,
    content_dir,
    settings_file,
    library_file,
)
from .utils import safe_save_json, safe_init_json
import app.state as state_module
from .routers import settings, library, tts, system, export, timer
from .utils import safe_init_json


# --- Lifespan Manager ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    start_time = time.time()

    # 1. Check directories
    if not base_dir.exists():
        print(f"[CRITICAL] Base dir missing: {base_dir}")

    # 2. Init JSON files
    safe_init_json(
        settings_file,
        {
            "pronunciationRules": [],
            "ignoreList": [],
            "voice_id": "af_bella",
            "speed": 1.0,
            "engine_mode": "gpu",
            "ui_language": "en",
        },
    )
    safe_init_json(library_file, [])

    # 3. Detect FFMPEG once at startup. ffmpeg_status defaults to
    # is_installed=False and used to be flipped only by the installer, so an
    # already-present ffmpeg (bundled in bin/ or system-managed) was reported
    # missing and the UI kept offering a download it did not need.
    try:
        from .logic.dependency_manager import (
            FFMPEGInstaller,
            configure_pydub,
            get_ffmpeg_path,
        )

        if FFMPEGInstaller().check_installed():
            configure_pydub()
            state_module.ffmpeg_status["is_installed"] = True
            state_module.ffmpeg_status["message"] = "Ready"
            print(f"[OK] FFMPEG found: {get_ffmpeg_path()}")
        else:
            print("[INFO] FFMPEG not found; MP3 export unavailable until installed.")
    except Exception as e:
        print(f"[WARNING] FFMPEG detection failed: {e}")

    # 4. Clean temp content
    try:
        if content_dir.exists():
            for f in content_dir.glob("temp_*"):
                try:
                    f.unlink()
                except:
                    pass
    except Exception as e:
        print(f"[STARTUP] Cleanup warning: {e}")

    # 5. Load model (Auto-load on startup)
    try:
        from .routers.system import load_engine_logic

        print("[STARTUP] Checking for existing models to auto-load...")
        load_engine_logic()
    except Exception as e:
        print(f"[STARTUP] Auto-load failed (non-critical): {e}")

    print(f"[STARTUP] Server ready in {time.time() - start_time:.2f}s")

    yield

    # Shutdown logic
    state_module.sleep_timer.stop_timer()
    print("[SHUTDOWN] Cleanup complete.")


# --- App Definition ---
app = FastAPI(lifespan=lifespan)

# --- Middleware ---
# No CORS middleware. The window loads the UI from this same server, so every
# request the app makes is same-origin and none of them needs CORS. It used to
# allow every origin, every method, with credentials: an answer that told any
# browser any website could call this server and read the replies, which is
# enough to list the library, delete documents and change settings.

# Names this server may be reached by. It listens on 127.0.0.1 only.
LOCAL_HOSTS = {"127.0.0.1", "localhost"}


def _hostname(netloc: str) -> str:
    try:
        return urlsplit("//" + netloc).hostname or ""
    except ValueError:
        return ""


@app.middleware("http")
async def only_this_app(request: Request, call_next):
    """
    Refuse requests that a web page from another site sends through a browser.

    Listening on 127.0.0.1 keeps other machines out, not other websites: a page
    open in any browser on this Mac runs on this Mac and can send requests to
    127.0.0.1:8000. Without CORS such a page cannot read the replies, but
    browsers still deliver "simple" requests (a form post, a no-cors fetch)
    without asking the server first, and some routes here act on a bare POST.
    So the request itself is checked:

    - Host must name this machine. A site that points its own domain at
      127.0.0.1 (DNS rebinding) looks same-origin to the browser, but its
      requests still carry that domain in Host.
    - Origin, when the browser sends one, must be this server.
    - Sec-Fetch-Site, sent by current browsers, must not say another site.

    Requests carrying none of these (curl, scripts) did not come from a web
    page, and pass.
    """
    host = request.headers.get("host", "")
    if _hostname(host) not in LOCAL_HOSTS:
        return JSONResponse({"detail": "Unknown host"}, status_code=403)
    origin = request.headers.get("origin")
    if origin is not None and origin != f"http://{host}":
        return JSONResponse({"detail": "Requests from other sites are refused"}, status_code=403)
    if request.headers.get("sec-fetch-site") in ("cross-site", "same-site"):
        return JSONResponse({"detail": "Requests from other sites are refused"}, status_code=403)
    return await call_next(request)


@app.middleware("http")
async def no_store_ui_assets(request, call_next):
    """
    Stop the embedded webview from serving stale UI code.

    StaticFiles sends only ETag and Last-Modified. With no Cache-Control, a
    webview is free to apply heuristic freshness and reuse a cached copy without
    revalidating, so an edited .js file can keep running the previous version
    across full application restarts -- the cache lives in the persistent
    storage_path, not in the process. Everything here is served from localhost,
    so there is nothing to gain by caching it.
    """
    response = await call_next(request)
    path = request.url.path
    if path == "/" or path.startswith(("/js", "/css", "/locales", "/assets")):
        response.headers["Cache-Control"] = "no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
    return response

# --- Routers ---
app.include_router(settings.router)
app.include_router(library.router)
app.include_router(tts.router)
app.include_router(system.router)
app.include_router(export.router)
app.include_router(timer.router)

# --- Static Files ---
# Mount static assets
ui_dir = base_dir / "ui"
if ui_dir.exists():
    app.mount("/css", StaticFiles(directory=ui_dir / "css"), name="css")
    app.mount("/js", StaticFiles(directory=ui_dir / "js"), name="js")
    if (ui_dir / "assets").exists():
        app.mount("/assets", StaticFiles(directory=ui_dir / "assets"), name="assets")
    app.mount("/locales", StaticFiles(directory=base_dir / "locales"), name="locales")
    app.mount("/", StaticFiles(directory=ui_dir, html=True), name="ui")
else:
    print(f"[WARNING] UI directory not found: {ui_dir}")


# --- Legacy/Root Endpoints ---
@app.get("/health")
async def health_check():
    process = psutil.Process()
    return {"status": "ok", "memory_mb": process.memory_info().rss / 1024 / 1024}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
